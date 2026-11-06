import json
from pathlib import Path

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path

EXAMPLES = Path(file_path("vme_belgie/demo_data/migratie"))
DOCS = EXAMPLES / "residentie-wilg-documenten"
# What ai/overname.py --mock reads from the demo documents (kept up to date by the tests in ai/tests).
READINGS = json.loads((DOCS / "voorstel-mock.json").read_text(encoding="utf-8"))
MINUTES = ("notulen-av-2025.pdf", "notulen-av-2026.pdf")


@tagged("post_install", "-at_install")
class TestMigrationAi(TransactionCase):

    def _migration(self, deed="basisakte.pdf", replace=None):
        """A takeover of Residentie Wilg: the owner list as CSV, the deed and the minutes as documents."""
        replace = replace or {}
        files = [{"name": path.name, "raw": replace.pop(path.name, None) or path.read_bytes()}
                 for path in sorted((EXAMPLES / "residentie-wilg").iterdir())]
        files += [{"name": name, "raw": text.encode()} for name, text in replace.items()]
        documents = [{"name": name, "raw": (DOCS / name).read_bytes()} for name in (deed, *MINUTES)]
        return self.env["vme.migration"].create({
            "attachment_ids": [(0, 0, vals) for vals in files],
            "document_ids": [(0, 0, vals) for vals in documents],
        })

    def _read(self, migration):
        """What the script does: hand the readings of each document to Odoo."""
        readings = [{"attachment_id": doc.id, "file": doc.name, **READINGS[doc.name]} for doc in migration.document_ids]
        return migration.vme_ai_apply_takeover(readings, "mock")

    def _texts(self, migration, level):
        messages, _plan, _ok = migration._check()
        return [text for lvl, _source, _line, text in messages if lvl == level]

    def _counts(self):
        return {
            model: self.env[model].sudo().with_context(active_test=False).search_count([])
            for model in ("vme.association", "res.partner", "vme.lot", "vme.key", "vme.works", "vme.mandate",
                          "mail.activity", "account.move")
        }

    def _line(self, migration, **values):
        return migration.proposal_ids.filtered(lambda line: all(line[f] == v for f, v in values.items()))

    # --- Reading ---

    def test_documents_wait_for_a_reading(self):
        migration = self._migration()
        self.assertEqual(migration.ai_state, "to_read")
        self.assertTrue(any("nog niet gelezen" in e for e in self._texts(migration, "error")))

    def test_reading_makes_a_proposal_and_nothing_else(self):
        migration = self._migration()
        before = self._counts()
        summary = self._read(migration)
        self.assertEqual(before, self._counts())
        self.assertEqual(migration.ai_state, "read")
        self.assertEqual(migration.ai_model, "mock")
        lines = migration.proposal_ids
        # 6 VME data (the KBO number in both minutes), 14 lots, 14 + 8 + 4 + 4 shares from the deed, 4 from the minutes, 2 works, 2 procedures, 3 mandates.
        self.assertEqual(summary, {"lines": 61, "uncertain": 0, "documents": ["basisakte.pdf", *MINUTES]})
        self.assertEqual(len(lines), 61)
        self.assertEqual(set(lines.mapped("state")), {"proposed"})
        self.assertEqual(lines.mapped("sequence"), list(range(1, 62)))
        self.assertEqual(len(migration.proposal_share_ids), 34)
        self.assertEqual(len(migration.proposal_works_ids), 2)
        a1 = self._line(migration, kind="share", key_name="Algemene delen", lot_name="A1")
        self.assertEqual((a1.value, a1.key_total, a1.page, a1.source_name), ("95", "1000", 2, "basisakte.pdf"))
        self.assertIn("95/1000", a1.fragment)
        self.assertEqual(a1.action_open_source()["url"], f"/web/content/{a1.attachment_id.id}#page=2")
        roof = self._line(migration, kind="works", description="Renovatie dak trap B")
        self.assertEqual((roof.amount, roof.financing, str(roof.date)), ("48500.00", "reserve", "2025-04-10"))
        self.assertEqual(migration.proposal_pending_count, 61)
        self.assertIn("61 regels", migration.message_ids[0].body)

    def test_unchecked_lines_block_the_import(self):
        migration = self._migration()
        self._read(migration)
        migration.action_dry_run()
        self.assertTrue(any("61 regels uit het voorstel zijn nog niet nagekeken" in e
                            for e in self._texts(migration, "error")))
        migration.action_import()
        self.assertFalse(migration.association_id)

    def test_a_new_reading_replaces_the_proposal_of_the_ai(self):
        migration = self._migration()
        self._read(migration)
        manual = self.env["vme.migration.proposal"].create({
            "migration_id": migration.id, "kind": "vme", "vme_field": "kbo", "value": "0000.001.483"})
        self.assertEqual((manual.state, manual.origin), ("accepted", "manual"))
        self._read(migration)
        self.assertEqual(len(migration.proposal_ids), 62)
        self.assertIn(manual, migration.proposal_ids)
        # New documents ask for a new reading.
        migration.document_ids = [(0, 0, {"name": "extra.pdf", "raw": b"%PDF-1.4"})]
        self.assertEqual(migration.ai_state, "to_read")

    # --- The scan: unsure shares ---

    def test_unsure_shares_are_marked_and_checked_by_the_sum(self):
        migration = self._migration(deed="basisakte-scan.pdf")
        self.assertEqual(self._read(migration)["uncertain"], 2)
        a2 = self._line(migration, kind="share", key_name="Algemene delen", lot_name="A2")
        b3 = self._line(migration, kind="share", key_name="Algemene delen", lot_name="B3")
        self.assertTrue(a2.uncertain and b3.uncertain)
        self.assertFalse(a2.value)
        self.assertIn("Onleesbaar", a2.note)
        self.assertEqual(b3.value, "105")

        # "Accept the certain lines" leaves the two unsure shares to be checked one by one.
        migration.action_accept_certain()
        self.assertEqual(migration.proposal_pending_count, 2)
        self.assertEqual((a2.state, b3.state), ("proposed", "proposed"))

        # Accepted as read: the share of A2 is missing and B3 gets a warning.
        (a2 | b3).action_accept()
        errors, warnings = self._texts(migration, "error"), self._texts(migration, "warning")
        self.assertTrue(any("quotiteit" in e for e in errors), errors)
        self.assertTrue(any("Onzeker gelezen" in w and "B3" in w for w in warnings), warnings)

        # The staff member reads the deed and fills in 110: the sum is right again.
        a2.value = "110"
        self.assertTrue(a2.edited)
        self.assertFalse(a2.uncertain)
        errors = self._texts(migration, "error")
        self.assertFalse(errors, errors)

    def test_a_wrong_correction_is_caught_by_the_sum(self):
        migration = self._migration(deed="basisakte-scan.pdf")
        self._read(migration)
        migration.proposal_ids.action_accept()
        self._line(migration, kind="share", key_name="Algemene delen", lot_name="A2").value = "100"
        self.assertTrue(any("Algemene delen" in e and "990" in e for e in self._texts(migration, "error")))

    # --- Import ---

    def test_import_of_the_accepted_proposal(self):
        migration = self._migration()
        self._read(migration)
        migration.action_accept_certain()
        self.assertEqual(migration.proposal_pending_count, 0)
        migration.action_dry_run()
        self.assertEqual(migration.error_count, 0, migration.report_html)
        self.assertIn("2 werken uit de notulen", migration.report_html)
        migration.action_import()

        vme = migration.association_id
        self.assertEqual(vme.name, "Residentie Wilg")
        self.assertEqual(vme.kbo_number, "0000.001.483")  # from the minutes
        self.assertEqual((vme.street, vme.zip, vme.city), ("Wilgenlaan 21", "3000", "Voorbeeldstad"))  # from the deed
        self.assertEqual(vme.working_capital_bank_id.acc_number.replace(" ", ""), "BE82999000009568")  # from vme.csv
        self.assertEqual(len(vme.lot_ids), 14)
        keys = self.env["vme.key"].search([("association_id", "=", vme.id)])
        self.assertEqual({k.name: (k.key_type, k.total_shares) for k in keys}, {
            "Algemene delen": ("general", 1000), "Lift": ("elevator", 1000), "Trap A": ("other", 450),
            "Trap B": ("other", 430), "Garagepoort": ("other", 4)})
        lift = keys.filtered(lambda k: k.name == "Lift")
        self.assertNotIn("G1", lift.line_ids.lot_id.mapped("name"))

        works = self.env["vme.works"].search([("association_id", "=", vme.id)])
        self.assertEqual({w.name: (w.budget, w.financing, w.key_id.name, w.state) for w in works}, {
            "Renovatie dak trap B": (48500.0, "reserve", "Algemene delen", "draft"),
            "Vervanging garagepoort": (6200.0, "working", "Garagepoort", "draft")})
        mandates = self.env["vme.mandate"].search([("association_id", "=", vme.id)])
        self.assertEqual({m.partner_id.name: (m.role, str(m.date_start)) for m in mandates}, {
            "Eigenaar Wilg A3": ("chair", "2026-04-16"), "Eigenaar Wilg B2": ("member", "2026-04-16"),
            "Eigenaar Wilg B4": ("auditor", "2026-04-16")})
        self.assertEqual(mandates.filtered(lambda m: m.role == "chair").partner_id.ref, "W03")  # the owner, not a copy
        activities = vme.activity_ids.filtered(lambda a: a.summary.startswith("Lopende procedure"))
        self.assertEqual(sorted(activities.mapped("summary")), [
            "Lopende procedure: Bouwbedrijf Voorbeeld NV", "Lopende procedure: de eigenaar van kavel G3"])
        self.assertIn("Bouwbedrijf Voorbeeld NV", vme.legal_proceedings)  # for the notary at a sale
        archived = self.env["ir.attachment"].search([("res_model", "=", "vme.association"), ("res_id", "=", vme.id)])
        self.assertTrue({"basisakte.pdf", *MINUTES} <= set(archived.mapped("name")))
        with self.assertRaises(UserError):
            migration.proposal_ids[0].action_reject()

    def test_rejected_lines_are_left_out(self):
        migration = self._migration()
        self._read(migration)
        migration.action_accept_certain()
        self._line(migration, kind="works", description="Renovatie dak trap B").action_reject()
        self._line(migration, kind="mandate", person="Eigenaar Wilg B4").action_reject()
        _messages, plan, ok = migration._check()
        self.assertTrue(ok)
        self.assertEqual([w["name"] for w in plan["works"]], ["Vervanging garagepoort"])
        self.assertEqual(len(plan["mandates"]), 2)

    # --- Checks on what the minutes say ---

    def test_deviating_key_without_four_fifths(self):
        migration = self._migration()
        self._read(migration)
        migration.action_accept_certain()
        self.assertFalse(any("4/5" in w for w in self._texts(migration, "warning")))
        for line in migration.proposal_share_ids.filtered(lambda l: l.key_name == "Garagepoort"):
            line.majority = "2/3 van de stemmen"
        self.assertTrue(any("Garagepoort" in w and "4/5" in w for w in self._texts(migration, "warning")))

    def test_council_member_must_be_an_owner(self):
        migration = self._migration()
        self._read(migration)
        migration.action_accept_certain()
        self._line(migration, kind="mandate", person="Eigenaar Wilg B2").person = "Buurman Zonder Kavel"
        self.assertTrue(any("Buurman Zonder Kavel" in e and "raad" in e for e in self._texts(migration, "error")))
        # An auditor needs not be an owner: a new contact is made.
        self._line(migration, kind="mandate", person="Buurman Zonder Kavel").role = "auditor"
        self._line(migration, kind="mandate", person="Eigenaar Wilg B4").action_reject()
        self.assertFalse(self._texts(migration, "error"))
        self.assertTrue(any("nieuw contact" in i for i in self._texts(migration, "info")))

    def test_works_need_a_known_key_and_an_amount(self):
        migration = self._migration()
        self._read(migration)
        migration.action_accept_certain()
        roof = self._line(migration, kind="works", description="Renovatie dak trap B")
        roof.write({"key_name": "Dak", "amount": "0"})
        errors = self._texts(migration, "error")
        self.assertTrue(any("Sleutel Dak bestaat niet" in e for e in errors), errors)
        self.assertTrue(any("groter zijn dan 0" in e for e in errors), errors)

    # --- Together with exported files ---

    def test_deed_replaces_exported_lots_and_shares_with_a_warning_per_difference(self):
        lots = "kavel;type;verdieping\n" + "".join(
            f"{lot};{'berging' if lot == 'A1' else 'appartement'};\n" for lot in ("A1", "A2", "A3", "A9"))
        shares = "sleutel;soort;totaal;kavel;quotiteit\nAlgemene delen;algemeen;1000;A1;96\nAlgemene delen;algemeen;1000;A2;110\n"
        migration = self._migration(replace={"kavels.csv": lots, "sleutels.csv": shares})
        self._read(migration)
        migration.action_accept_certain()
        warnings, infos = self._texts(migration, "warning"), self._texts(migration, "info")
        self.assertTrue(any("A1: type berging in kavels.csv, appartement in het voorstel" in w for w in warnings), warnings)
        self.assertTrue(any("A9 staat in kavels.csv maar niet in het voorstel" in w for w in warnings), warnings)
        self.assertTrue(any("Algemene delen / A1: quotiteit 96 in sleutels.csv, 95 in het voorstel" in w
                            for w in warnings), warnings)
        self.assertTrue(any("kavels komt uit het voorstel" in i for i in infos), infos)
        self.assertFalse(self._texts(migration, "error"))

    def test_vme_data_of_the_documents_win_over_vme_csv(self):
        csv = "naam;kbo;iban_werkkapitaal;iban_reservekapitaal;overstapdatum\n" \
              "Residentie Wilg;0000.001.582;BE82 9990 0000 9568;BE71 9990 0000 9669;01/01/2027\n"
        migration = self._migration(replace={"vme.csv": csv})
        self._read(migration)
        migration.action_accept_certain()
        _messages, plan, _ok = migration._check()
        self.assertEqual(plan["vme"]["kbo"], "0000.001.483")
        self.assertTrue(any("KBO-nummer" in w and "0000.001.582" in w for w in self._texts(migration, "warning")))
