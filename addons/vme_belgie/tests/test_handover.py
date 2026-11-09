import base64
import csv
import io
import zipfile
from datetime import date
from pathlib import Path

from markupsafe import Markup

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path

from ..models.vme_migration import TABLES

ESDOORN = Path(file_path("vme_belgie/demo_data/migratie/residentie-esdoorn"))
HANDOVER_DATE = date(2027, 3, 31)


@tagged("post_install", "-at_install")
class TestHandover(TransactionCase):
    """Handover package of Residentie Esdoorn, imported from the example files and with a quarter of activity."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls._import([(path.relative_to(ESDOORN).as_posix(), path.read_bytes())
                               for path in sorted(ESDOORN.rglob("*")) if path.is_file()])
        company = cls.vme.company_id
        keys = {key.name: key for key in cls.vme.key_ids}
        partners = {rule.partner_id.name: rule.partner_id for rule in cls.vme.distribution_rule_ids}
        cls.window_cleaner = partners["Glazenwasser Voorbeeld"]
        cls.lift_company = partners["Liftdienst Esdoorn Voorbeeld BV"]
        owner_a1 = cls.vme.lot_ids.filtered(lambda lot: lot.name == "A1")._get_owner_on(HANDOVER_DATE)

        # A cost and a debt to the window cleaner after the transition: a P&L account in the opening balance.
        Account = cls.env["account.account"].with_company(company)
        cls.expense = Account.search([("company_ids", "in", company.id), ("account_type", "=", "expense"),
                                      ("code", "=like", "61%")], order="code", limit=1)
        journal = cls.env["account.journal"].with_company(company).search(
            [("company_id", "=", company.id), ("type", "=", "general")], limit=1)
        cls.env["account.move"].with_company(company).create({
            "move_type": "entry", "journal_id": journal.id, "date": date(2027, 2, 15), "ref": "Glazen februari",
            "line_ids": [
                Command.create({"name": "Ramen", "account_id": cls.expense.id, "debit": 300.0}),
                Command.create({"name": "Ramen", "credit": 300.0, "partner_id": cls.window_cleaner.id,
                                "account_id": cls.window_cleaner.with_company(company).property_account_payable_id.id}),
            ],
        }).action_post()

        cls.works = cls.env["vme.works"].create({
            "association_id": cls.vme.id, "name": "Vernieuwing liftcabine", "budget": 15000.0,
            "financing": "reserve", "key_id": keys["Liftsleutel"].id,
        })
        cls.insurer = cls.env["res.partner"].create({"name": "Verzekeraar Esdoorn Voorbeeld", "is_company": True})
        policy = cls.env["vme.insurance.policy"].create({
            "association_id": cls.vme.id, "name": "Brandverzekering gebouw", "insurer_id": cls.insurer.id,
            "policy_number": "POL-ESD-1",
        })
        cls.claim = cls.env["vme.damage.claim"].create({
            "association_id": cls.vme.id, "name": "Waterschade kelder", "policy_id": policy.id,
            "event_date": date(2027, 2, 1), "report_date": date(2027, 2, 2),
        })
        cls.contract = cls.env["vme.contract"].create({
            "association_id": cls.vme.id, "name": "Onderhoud lift", "contract_type": "maintenance",
            "partner_id": cls.lift_company.id, "reference": "LIFT-2027",
        })
        cls.env["vme.mandate"].create({
            "association_id": cls.vme.id, "role": "chair", "partner_id": owner_a1.id, "date_start": date(2027, 1, 15),
        })
        cls.vme.legal_proceedings = Markup("<ul><li>Geschil met de aannemer over vochtschade in de kelder</li></ul>")
        cls.env["vme.document"].create({
            "association_id": cls.vme.id, "folder_id": cls.env.ref("vme_belgie.folder_deed").id,
            "name": "Basisakte", "filename": "basisakte.pdf", "date": date(2010, 3, 1),
            "datas": base64.b64encode(b"%PDF-1.4 basisakte Esdoorn"),
        })

    @classmethod
    def _import(cls, files):
        migration = cls.env["vme.migration"].create({
            "attachment_ids": [Command.create({"name": name, "raw": raw}) for name, raw in files],
        })
        migration.action_dry_run()
        errors = [text for level, _source, _line, text in migration._check()[0] if level == "error"]
        assert not errors, errors
        migration.action_import()
        return migration.association_id

    def _wizard(self, vme=None, **vals):
        return self.env["vme.handover.wizard"].create({
            "association_id": (vme or self.vme).id, "handover_date": HANDOVER_DATE, **vals})

    @staticmethod
    def _tables(raw):
        """{table: [row dict]} of the CSV files in a package."""
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return {
                table: list(csv.DictReader(io.StringIO(archive.read(f"{table}.csv").decode("utf-8-sig")), delimiter=";"))
                for table in TABLES
            }

    # --- The package ---

    def test_package_contents(self):
        mails = self.env["mail.mail"].search_count([])
        wizard = self._wizard(recipient_id=self.env["res.partner"].create({"name": "Syndicus Nieuw Voorbeeld"}).id)
        self.assertEqual(wizard.deadline, date(2027, 4, 30))
        self.assertEqual(wizard.statement_year, 2027)
        self.assertIn("lopende werken", wizard.summary_html)
        action = wizard.action_build_package()

        attachment = self.env["ir.attachment"].browse(int(action["url"].split("/")[3].split("?")[0]))
        self.assertEqual(action["target"], "self")
        self.assertEqual((attachment.res_model, attachment.res_id), ("vme.association", self.vme.id))
        self.assertEqual(attachment.name, "Overdracht Residentie Esdoorn 2027-03-31.zip")
        with zipfile.ZipFile(io.BytesIO(attachment.raw)) as archive:
            names = set(archive.namelist())
            form = archive.read("rapporten/Overdrachtsdocument.pdf").decode()
        self.assertTrue({f"{table}.csv" for table in TABLES} <= names)
        self.assertTrue({
            "rapporten/Balans en resultatenrekening 2027.pdf", "rapporten/Openstaande saldi eigenaars.pdf",
            "rapporten/Reservekapitaal.pdf", "archief/Basisakte en reglement van mede-eigendom/basisakte.pdf",
            "archief/Bijlagen VME/jaarafrekening-2024.pdf",
        } <= names, names)
        # In tests Odoo renders reports as HTML: the handover form lists what is handed over.
        for text in ("Syndicus Nieuw Voorbeeld", "BE29 9990 0000 9164", "Vernieuwing liftcabine", "Waterschade kelder",
                     "Geschil met de aannemer", "Onderhoud lift", "POL-ESD-1", "Eigenaar Esdoorn A1", "openingsbalans.csv"):
            self.assertIn(text, form)

        # Kept on the VME as an internal note; nothing goes out.
        message = self.vme.message_ids[:1]
        self.assertEqual(message.attachment_ids, attachment)
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_note"))
        self.assertEqual(self.env["mail.mail"].search_count([]), mails)

    def test_documents_also_when_read_with_bin_size(self):
        # As the web client does after the button: binary fields would give their size instead of the file.
        documents = self._wizard().with_context(bin_size=True)._handover_data()["documents"]
        self.assertIn(("archief/Basisakte en reglement van mede-eigendom/basisakte.pdf", b"%PDF-1.4 basisakte Esdoorn"),
                      documents)

    def test_opening_balance_on_the_handover_date(self):
        tables = self._tables(self._wizard()._build_package()[0])
        rows = {(row["soort"], row["code"]): row["bedrag"] for row in tables["openingsbalans"]}
        self.assertEqual(rows[("bank_werkkapitaal", "")], "8432,15")
        self.assertEqual(rows[("bank_reservekapitaal", "")], "24600,00")
        self.assertEqual(rows[("fonds_reservekapitaal", "")], "24600,00")
        self.assertEqual(rows[("eigenaar", "E07")], "-150,00")
        # The heir without a lot comes along as an owner, with the balance.
        self.assertEqual(rows[("eigenaar", "E09")], "236,40")
        supplier = {row["naam"]: row["code"] for row in tables["leveranciers"]}["Glazenwasser Voorbeeld"]
        self.assertEqual(rows[("leverancier", supplier)], "300,00")
        self.assertEqual(rows[("rekening", self.expense.with_company(self.vme.company_id).code)], "300,00")
        self.assertEqual(tables["werken"], [{"omschrijving": "Vernieuwing liftcabine", "bedrag": "15000,00",
                                             "financiering": "reservekapitaal", "sleutel": "Liftsleutel", "datum_av": ""}])
        self.assertEqual(tables["mandaten"][0]["naam"], "Eigenaar Esdoorn A1")
        reserve = self._wizard()._reserve_data()
        self.assertEqual((reserve["balance"], reserve["committed"], reserve["available"]), (24600.0, 15000.0, 9600.0))
        self.assertEqual([row["amount"] for row in reserve["movements"]], [24600.0])
        arrears = {row["code"]: row["balance"] for row in self._wizard()._arrears_data()["owners"]}
        self.assertEqual(arrears, {"E03": 412.5, "E07": -150.0, "E09": 236.4})
        # Before the transition there is nothing to take over.
        early = self._tables(self._wizard(handover_date=date(2026, 12, 31))._build_package()[0])
        self.assertEqual(early["openingsbalans"], [])

    def test_roundtrip_export_import(self):
        """The package reads back in with our own import, and the new VME exports to the same files."""
        raw, name = self._wizard()._build_package()
        exported = self._tables(raw)

        # The old VME stays in this database: free up its name, KBO number and bank accounts.
        self.vme.write({"name": "Residentie Esdoorn (vorige syndicus)", "kbo_number": "0123.456.749"})
        self.vme.working_capital_bank_id.acc_number = "BE68 5390 0754 7034"
        self.vme.reserve_capital_bank_id.acc_number = "BE71 0961 2345 6769"

        migration = self.env["vme.migration"].create({"attachment_ids": [Command.create({"name": name, "raw": raw})]})
        migration.action_dry_run()
        self.assertEqual(migration.error_count, 0, migration.report_html)
        migration.action_import()
        self.assertEqual(migration.state, "done")
        new = migration.association_id
        self.assertEqual(new.name, "Residentie Esdoorn")
        self.assertEqual(new.working_capital_bank_id.sanitized_acc_number, "BE29999000009164")
        self.assertEqual(migration.opening_move_id.date, HANDOVER_DATE)

        again = self._tables(self._wizard(new)._build_package()[0])
        for table in TABLES:
            if table != "vme":
                self.assertEqual(again[table], exported[table], table)
        self.assertEqual(again["vme"][0]["overstapdatum"], "31/03/2027")

        # The books of the new VME: same balance per account as the old one on the handover date.
        def balances(vme):
            company = vme.company_id
            groups = self.env["account.move.line"]._read_group(
                [("company_id", "=", company.id), ("parent_state", "=", "posted"), ("date", "<=", HANDOVER_DATE)],
                ["account_id"], ["balance:sum"])
            return {account.with_company(company).code: round(balance, 2) for account, balance in groups if round(balance, 2)}
        self.assertEqual(balances(new), balances(self.vme))
        self.assertEqual(self.env["vme.works"].search([("association_id", "=", new.id)]).budget, 15000.0)
        self.assertIn("Geschil met de aannemer", new.legal_proceedings)

    def test_balance_without_kind_goes_to_suspense(self):
        company = self.vme.company_id
        Account = self.env["account.account"].with_company(company)
        vat = Account.search([("company_ids", "in", company.id), ("code", "=like", "451%")], limit=1)
        journal = self.env["account.journal"].with_company(company).search(
            [("company_id", "=", company.id), ("type", "=", "general")], limit=1)
        self.env["account.move"].with_company(company).create({
            "move_type": "entry", "journal_id": journal.id, "date": date(2027, 3, 1),
            "line_ids": [Command.create({"name": "Btw", "account_id": self.expense.id, "debit": 42.0}),
                         Command.create({"name": "Btw", "account_id": vat.id, "credit": 42.0})],
        }).action_post()
        data = self._wizard()._handover_data()
        rows = [row for row in data["tables"]["openingsbalans"] if row["code"] == "499000"]
        self.assertEqual(len(rows), 1, data["tables"]["openingsbalans"])
        self.assertEqual(rows[0]["bedrag"], "-42,00")
        self.assertIn(vat.with_company(company).code, rows[0]["omschrijving"])
        self.assertTrue(any("wachtrekening" in warning for warning in data["warnings"]))

    def test_staff_without_accounting_rights(self):
        """C-D1: a VME staff member without accounting rights builds the package for the VMEs of his companies."""
        main = self.env.ref("base.main_company")
        staff = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Overdracht", "login": "medewerker.overdracht@example.com",
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            "company_id": main.id, "company_ids": [Command.set((main | self.vme.company_id).ids)],
        })
        self.assertFalse(staff.has_group("account.group_account_invoice"))
        wizard = self.env["vme.handover.wizard"].with_user(staff).with_company(main).create({
            "association_id": self.vme.id, "handover_date": date(2027, 3, 31)})
        self.assertIn("lopende werken", wizard.summary_html)
        action = wizard.action_build_package()
        attachment = self.env["ir.attachment"].browse(int(action["url"].split("/")[3].split("?")[0]))
        tables = self._tables(attachment.raw)
        self.assertTrue(tables["openingsbalans"])
        self.assertTrue(tables["eigenaars"])
        # Not for a VME outside his companies.
        stranger = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Ander Kantoor", "login": "medewerker.ander@example.com",
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            "company_id": main.id, "company_ids": [Command.set(main.ids)],
        })
        with self.assertRaises(AccessError):
            self._wizard().with_user(stranger)._build_package()

    def test_auditor_cannot_build_a_package(self):
        auditor = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Commissaris Esdoorn", "login": "commissaris.esdoorn@example.com",
            "group_ids": [Command.set([self.env.ref("vme_belgie.group_vme_auditor").id])],
            "company_id": self.vme.company_id.id, "company_ids": [Command.set(self.vme.company_id.ids)],
        })
        with self.assertRaises(AccessError):
            self._wizard().with_user(auditor)._build_package()
