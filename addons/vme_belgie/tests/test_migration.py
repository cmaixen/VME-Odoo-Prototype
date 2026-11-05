import csv
import io
import zipfile
from datetime import date
from pathlib import Path

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path

from ..models.vme_migration import parse_amount, parse_date

EXAMPLES = Path(file_path("vme_belgie/demo_data/migratie"))


@tagged("post_install", "-at_install")
class TestMigration(TransactionCase):

    def _migration(self, folder, replace=None, skip=()):
        """Migration with the files of an example folder; replace={file: text} overrides one."""
        replace = replace or {}
        attachments = []
        for path in sorted((EXAMPLES / folder).rglob("*")):
            if path.is_dir() or path.name in skip:
                continue
            raw = replace[path.name].encode() if path.name in replace else path.read_bytes()
            attachments.append({"name": path.name, "raw": raw})
        return self.env["vme.migration"].create({
            "attachment_ids": [(0, 0, vals) for vals in attachments],
        })

    def _texts(self, migration, level):
        messages, _plan, _ok = migration._check()
        return [text for lvl, _source, _line, text in messages if lvl == level]

    def _counts(self):
        return {
            model: self.env[model].sudo().with_context(active_test=False).search_count([])
            for model in ("vme.association", "res.company", "res.partner", "res.partner.bank",
                          "vme.lot", "vme.key", "account.move", "ir.attachment")
        }

    # --- Parsing ---

    def test_parse_dates_and_amounts(self):
        self.assertEqual(parse_date("01/01/2027"), date(2027, 1, 1))
        self.assertEqual(parse_date("2027-01-01"), date(2027, 1, 1))
        self.assertIsNone(parse_date(""))
        with self.assertRaises(ValueError):
            parse_date("31/02/2027")
        self.assertEqual(parse_amount("8.432,15"), 8432.15)
        self.assertEqual(parse_amount("8,432.15"), 8432.15)
        self.assertEqual(parse_amount("-150,00"), -150.0)
        self.assertEqual(parse_amount("1234.5"), 1234.5)
        self.assertEqual(parse_amount(" € 12 "), 12.0)
        self.assertEqual(parse_amount(7), 7.0)
        self.assertEqual(parse_amount(""), 0.0)

    def test_comma_separated_csv(self):
        lots = "kavel,type,verdieping\nA1,appartement,Gelijkvloers\n"
        migration = self._migration("residentie-esdoorn")
        rows = migration._read_csv(lots.encode("cp1252"))
        self.assertEqual(rows[1], ["A1", "appartement", "Gelijkvloers"])

    # --- Dry run ---

    def test_dry_run_reports_errors_and_writes_nothing(self):
        migration = self._migration("residentie-esdoorn-met-fouten")
        before = self._counts()
        migration.action_dry_run()
        after = self._counts()
        # Only the report on the migration itself; no VME, partner, bank account or entry.
        self.assertEqual(before, after)
        self.assertEqual(migration.state, "checked")
        errors = self._texts(migration, "error")
        self.assertTrue(any("Liftsleutel" in e and "990" in e for e in errors), errors)
        self.assertTrue(any("A12" in e for e in errors), errors)
        self.assertTrue(any("banksaldo" in e and "iban_reservekapitaal" in e for e in errors), errors)
        # The bank balance still counts, so the opening balance itself is in balance.
        self.assertFalse(any("evenwicht" in e for e in errors), errors)
        # Lift key, unknown lot, and both bank rows (each on its own line of openingsbalans.csv).
        self.assertEqual(migration.error_count, 4, errors)
        warnings = self._texts(migration, "warning")
        self.assertTrue(any("Erfgenaam Esdoorn heeft geen kavel" in w for w in warnings), warnings)
        self.assertTrue(any("A8 heeft geen eigenaar" in w for w in warnings), warnings)
        self.assertTrue(any("Glazenwasser" in w and "btw" in w for w in warnings), warnings)
        self.assertTrue(any("reservekapitaal" in w for w in warnings), warnings)
        self.assertIn("Liftsleutel", migration.report_html)
        self.assertEqual(migration.name, "Overstap Residentie Esdoorn")
        self.assertNotIn("Klaar om te importeren", migration.report_html)

    def test_dry_run_of_corrected_files_has_only_warnings(self):
        migration = self._migration("residentie-esdoorn")
        migration.action_dry_run()
        self.assertEqual(migration.error_count, 0, self._texts(migration, "error"))
        self.assertEqual(migration.transition_date, date(2027, 1, 1))
        self.assertEqual(migration.name, "Overstap Residentie Esdoorn")
        self.assertIn("Klaar om te importeren", migration.report_html)
        self.assertIn("Openingsboeking op 01/01/2027", migration.report_html)
        self.assertIn("Erfgenaam Esdoorn", migration.report_html)

    def test_import_refuses_with_errors(self):
        migration = self._migration("residentie-esdoorn-met-fouten")
        before = self._counts()
        migration.action_import()
        self.assertEqual(migration.state, "checked")
        self.assertFalse(migration.association_id)
        self.assertEqual(before["vme.association"], self._counts()["vme.association"])

    def test_missing_file_and_column(self):
        migration = self._migration("residentie-esdoorn", skip={"openingsbalans.csv"},
                                    replace={"kavels.csv": "nummer;type\nA1;appartement\n"})
        errors = self._texts(migration, "error")
        self.assertTrue(any("openingsbalans.csv ontbreekt" in e for e in errors), errors)
        self.assertTrue(any("Kolom(men) ontbreken: kavel" in e for e in errors), errors)

    def test_unbalanced_opening_balance(self):
        text = (EXAMPLES / "residentie-esdoorn" / "openingsbalans.csv").read_text()
        text = text.replace("fonds_werkkapitaal;;7.180,90", "fonds_werkkapitaal;;7.100,90")
        errors = self._texts(self._migration("residentie-esdoorn", replace={"openingsbalans.csv": text}), "error")
        self.assertTrue(any("niet in evenwicht" in e and "80.00" in e for e in errors), errors)

    def test_opening_balance_unknown_codes(self):
        text = "soort;code;bedrag\neigenaar;E99;10\nleverancier;L99;10\nonbekend;;5\nrekening;400000;5\n"
        errors = self._texts(self._migration("residentie-esdoorn", replace={"openingsbalans.csv": text}), "error")
        self.assertTrue(any("E99" in e for e in errors), errors)
        self.assertTrue(any("L99" in e for e in errors), errors)
        self.assertTrue(any("Onbekende soort onbekend" in e for e in errors), errors)
        self.assertTrue(any("400000" in e for e in errors), errors)

    def test_overlapping_ownerships_and_existing_vme(self):
        text = (EXAMPLES / "residentie-esdoorn" / "eigendommen.csv").read_text()
        text = text.replace("A4;E10;01/07/2025;", "A4;E10;01/06/2025;")
        self.env["vme.association"].create({"name": "Residentie Esdoorn"})
        errors = self._texts(self._migration("residentie-esdoorn", replace={"eigendommen.csv": text}), "error")
        self.assertTrue(any("A4 heeft al een eigenaar" in e for e in errors), errors)
        self.assertTrue(any("bestaat al een VME" in e for e in errors), errors)

    def test_invalid_numbers(self):
        vme = (EXAMPLES / "residentie-esdoorn" / "vme.csv").read_text()
        vme = vme.replace("0000.001.285", "0000.001.286").replace("BE18 9990 0000 9265", "BE18 9990 0000 9266")
        suppliers = (EXAMPLES / "residentie-esdoorn" / "leveranciers.csv").read_text()
        suppliers = suppliers.replace("BE0000001384", "BE0000001385")
        errors = self._texts(self._migration(
            "residentie-esdoorn", replace={"vme.csv": vme, "leveranciers.csv": suppliers}), "error")
        self.assertTrue(any("KBO" in e for e in errors), errors)
        self.assertTrue(any("Ongeldige IBAN" in e for e in errors), errors)
        self.assertTrue(any("btw-nummer" in e for e in errors), errors)

    # --- Import ---

    def test_import_creates_vme_and_opening_balance(self):
        energy = self.env["res.partner"].create({"name": "Energieleverancier Voorbeeld NV", "vat": "BE0000000394"})
        migration = self._migration("residentie-esdoorn")
        migration.action_dry_run()
        migration.action_import()
        self.assertEqual(migration.state, "done")
        self.assertIn("Geïmporteerd:", migration.report_html)
        vme = migration.association_id
        self.assertEqual(vme.name, "Residentie Esdoorn")
        self.assertEqual(vme.company_id.chart_template, "be_comp")
        self.assertEqual(len(vme.lot_ids), 10)
        self.assertEqual(vme.working_capital_bank_id.sanitized_acc_number, "BE29999000009164")
        self.assertEqual(vme.reserve_capital_bank_id.sanitized_acc_number, "BE18999000009265")

        lot_a4 = vme.lot_ids.filtered(lambda lot: lot.name == "A4")
        self.assertEqual(lot_a4._get_owner_on(date(2025, 6, 30)).name, "Vorige eigenaar Esdoorn A4")
        self.assertEqual(lot_a4._get_owner_on(date(2027, 1, 1)).name, "Eigenaar Esdoorn A4")
        self.assertEqual(lot_a4._get_owner_on(date(2027, 1, 1)).ref, "E10")
        keys = {key.name: key for key in vme.key_ids}
        self.assertTrue(keys["Algemene sleutel"].is_balanced)
        self.assertEqual(keys["Liftsleutel"].key_type, "elevator")
        self.assertEqual(len(keys["Liftsleutel"].line_ids), 8)

        # The existing supplier is reused, the others are new; all get a distribution rule.
        rules = vme.distribution_rule_ids
        self.assertEqual(len(rules), 3)
        self.assertIn(energy, rules.partner_id)
        self.assertEqual(rules.filtered(lambda r: r.partner_id.vat == "BE0000001384").key_id, keys["Liftsleutel"])

        # Account codes depend on the company in Odoo 19.
        move = migration.opening_move_id.with_company(vme.company_id)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, date(2027, 1, 1))
        self.assertEqual(move.company_id, vme.company_id)
        self.assertAlmostEqual(sum(move.line_ids.mapped("debit")), 33681.05)
        self.assertAlmostEqual(sum(move.line_ids.mapped("credit")), 33681.05)

        def balance(code, partner_ref=None):
            lines = move.line_ids.filtered(lambda l: l.account_id.code == code)
            if partner_ref:
                lines = lines.filtered(lambda l: l.partner_id.ref == partner_ref)
            return round(sum(lines.mapped("balance")), 2)

        journals = vme._ensure_fund_bank_journals()[vme]
        self.assertEqual(balance(journals["working"].default_account_id.code), 8432.15)
        self.assertEqual(balance(journals["reserve"].default_account_id.code), 24600.0)
        self.assertNotEqual(journals["working"].default_account_id, journals["reserve"].default_account_id)
        self.assertEqual(balance("100100"), -7180.90)
        self.assertEqual(balance("100200"), -24600.0)
        self.assertEqual(balance("400000", "E03"), 412.50)
        self.assertEqual(balance("400000", "E07"), -150.0)
        supplier_lines = move.line_ids.filtered(lambda l: l.partner_id == energy)
        self.assertEqual(supplier_lines.account_id.code, "440000")
        self.assertEqual(supplier_lines.balance, -1284.30)
        # Open owner balances can be paid and matched later.
        receivable = move.line_ids.filtered(lambda l: l.partner_id.ref == "E03")
        self.assertEqual(receivable.amount_residual, 412.50)

        archive = self.env["ir.attachment"].search(
            [("res_model", "=", "vme.association"), ("res_id", "=", vme.id)])
        self.assertEqual(sorted(archive.mapped("name")), ["jaarafrekening-2024.pdf", "jaarafrekening-2025.pdf"])

        # Running the same import again is refused.
        with self.assertRaises(UserError):
            migration.action_import()
        again = self._migration("residentie-esdoorn")
        self.assertTrue(any("bestaat al een VME" in e for e in self._texts(again, "error")))

    def test_import_from_zip_and_excel(self):
        import openpyxl  # noqa: PLC0415

        folder = EXAMPLES / "residentie-esdoorn"
        workbook = openpyxl.Workbook()
        workbook.remove(workbook.active)
        for path in sorted(folder.glob("*.csv")):
            sheet = workbook.create_sheet(path.stem)
            for row in csv.reader(io.StringIO(path.read_text()), delimiter=";"):
                sheet.append(row)
        # Excel turns dates and quotas into real dates and numbers.
        sheet = workbook["vme"]
        sheet["H2"] = date(2027, 1, 1)
        for row in workbook["sleutels"].iter_rows(min_row=2):
            row[2].value, row[4].value = float(row[2].value), float(row[4].value)
        excel = io.BytesIO()
        workbook.save(excel)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("export/residentie-esdoorn.xlsx", excel.getvalue())
            for pdf in (folder / "archief").glob("*.pdf"):
                zipped.writestr(f"export/archief/{pdf.name}", pdf.read_bytes())
        migration = self.env["vme.migration"].create({
            "attachment_ids": [(0, 0, {"name": "export.zip", "raw": archive.getvalue()})],
        })
        messages, plan, ok = migration._check()
        self.assertTrue(ok, [m for m in messages if m[0] == "error"])
        self.assertEqual(plan["vme"]["date"], date(2027, 1, 1))
        self.assertEqual(plan["keys"]["Liftsleutel"]["lines"]["A8"], 185.0)
        self.assertEqual(len(plan["archive"]), 2)
        migration.action_import()
        self.assertEqual(migration.association_id.name, "Residentie Esdoorn")
