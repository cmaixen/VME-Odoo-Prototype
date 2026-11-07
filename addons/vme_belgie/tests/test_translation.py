from datetime import date

import polib

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_path

# Modules with a French translation; each has i18n/<module>.pot and i18n/fr.po.
TRANSLATED_MODULES = ("vme_belgie", "vme_rentmeester", "vme_website")


@tagged("post_install", "-at_install")
class TestTranslation(TransactionCase):
    """Documents for an owner are in the owner's language (see docs/dev/vertaling.md)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for lang in ("nl_BE", "fr_BE"):
            cls.env["res.lang"]._activate_lang(lang)
        cls.env["ir.module.module"].search([("name", "in", ["base", "account", "l10n_be", "vme_belgie"])]) \
            ._update_translations(["fr_BE"])
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Vertaling"})
        cls.env.cr.precommit.run()  # load the chart of accounts and the fund accounts
        Bank = cls.env["res.partner.bank"]
        banks = Bank.create([{"acc_number": n, "partner_id": cls.vme.partner_id.id}
                             for n in ("BE68 5390 0754 7034", "BE71 0961 2345 6769")])
        cls.vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        banks.with_user(cls.env.ref("base.user_admin")).allow_out_payment = True
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": n, "lot_type": "apartment"} for n in ("A1", "A2")])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 500}) for lot in cls.lots],
        })
        cls.owner_nl, cls.owner_fr = cls.env["res.partner"].create([
            {"name": "Eigenaar V1", "lang": "nl_BE"}, {"name": "Eigenaar V2", "lang": "fr_BE"}])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(cls.lots, (cls.owner_nl, cls.owner_fr))])
        cls.env["vme.budget"].create({
            "association_id": cls.vme.id, "year": 2026,
            "working_capital_budget": 4000, "reserve_capital_contribution": 400, "calls_per_year": "4",
        })

    def test_provision_line_in_the_owners_language(self):
        wizard = self.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set(self.vme.ids)], "year": 2026, "number": 1,
            "invoice_date": date(2026, 1, 15), "date_due": date(2026, 1, 31), "post_invoices": False,
        })
        calls = self.env["vme.provision.call"].search(wizard.action_create_calls()["domain"])
        working = calls.invoice_ids.filtered(lambda m: m.vme_fund == "working")
        line = {m.partner_id: m.invoice_line_ids.name for m in working}
        self.assertEqual(line[self.owner_nl], "Werkkapitaal oproep 1/4 2026 - kavel A1 (500/1000)")
        self.assertEqual(line[self.owner_fr], "Fonds de roulement appel 1/4 2026 - lot A2 (500/1000)")

    def test_letter_in_the_recipients_language(self):
        Log = self.env["vme.communication.log"]
        logs = Log.create([{"association_id": self.vme.id, "partner_id": owner.id, "channel": "registered",
                            "lot_names": lot.name, "subject": "Test"}
                           for owner, lot in zip((self.owner_nl, self.owner_fr), self.lots)])
        html = {}
        for log in logs:
            content, _ = self.env["ir.actions.report"]._render_qweb_html(
                "vme_belgie.action_report_communication_letter", log.ids)
            html[log.partner_id] = content.decode()
        self.assertIn("AANGETEKEND", html[self.owner_nl])
        self.assertIn("Kavels:", html[self.owner_nl])
        self.assertIn("RECOMMANDÉ", html[self.owner_fr])
        self.assertNotIn("Kavels:", html[self.owner_fr])

    def _set_vme_lang(self, lang):
        self.vme.partner_id.lang = lang
        self.vme.company_id.partner_id.lang = lang

    def test_po_files_are_complete(self):
        """Every term of the .pot is translated in fr.po, without fuzzy entries (docs/dev/vertaling.md)."""
        for module in TRANSLATED_MODULES:
            pot = polib.pofile(file_path(f"{module}/i18n/{module}.pot"))
            po = polib.pofile(file_path(f"{module}/i18n/fr.po"))
            translated = {(e.msgctxt, e.msgid) for e in po if e.msgstr and "fuzzy" not in e.flags}
            missing = [e.msgid for e in pot if e.msgid and (e.msgctxt, e.msgid) not in translated]
            self.assertFalse(missing, f"{module}: {len(missing)} termen zonder Franse vertaling, bv. {missing[:5]}")

    def test_financial_statements_in_the_vmes_language(self):
        wizard = self.env["vme.financial.statements.wizard"].create({"association_id": self.vme.id, "year": 2026})
        report = "vme_belgie.action_report_financial_statements"
        html_nl = self.env["ir.actions.report"]._render_qweb_html(report, wizard.ids)[0].decode()
        self.assertIn("Balans op", html_nl)
        self.assertIn("Kredietinstelling: werkkapitaal", html_nl)
        self._set_vme_lang("fr_BE")
        html = self.env["ir.actions.report"]._render_qweb_html(report, wizard.ids)[0].decode()
        for dutch in ("Balans op", "Kredietinstelling", "Over te dragen middelen", "Activa", "Opbrengsten"):
            self.assertNotIn(dutch, html)
        self.assertIn("Bilan au", html)
        self.assertIn("31/12/2026", html)
        self.assertIn("Reporté de 2025", html)
        # The fund accounts of a new VME have their name in every installed language.
        working = self.env["account.account"].with_company(self.vme.company_id).search([
            ("company_ids", "in", self.vme.company_id.id), ("code", "=", "100100")])
        self.assertEqual(working.with_context(lang="fr_BE").name, "Fonds de roulement")
        self.assertEqual(working.with_context(lang="nl_BE").name, "Werkkapitaal")

    def _syndic_office(self):
        office = self.env["res.company"].create({
            "name": "Syndic Traduction SRL", "is_syndic_office": True, "country_id": self.env.ref("base.be").id,
            "currency_id": self.env.ref("base.EUR").id, "street": "Rue du Bureau 1", "zip": "1000",
            "city": "Bruxelles", "company_registry": "0000.000.592",
        })
        self.env["vme.association"]._load_vme_chart(office.id)
        self.env.user.company_ids |= office
        return office

    def test_syndic_posting_in_the_vmes_language(self):
        office = self._syndic_office()
        self._set_vme_lang("fr_BE")
        mandate = self.env["vme.syndic.mandate"].create({
            "association_id": self.vme.id, "partner_id": office.partner_id.id, "date_start": date(2026, 10, 20)})
        html = self.env["ir.actions.report"]._render_qweb_html(
            "vme_belgie.action_report_syndic_posting", mandate.ids)[0].decode()
        self.assertIn("Syndic Traduction SRL", html)
        self.assertIn("20/10/2026", html)
        for dutch in ("Aanstelling van de syndicus", "Burgerlijk Wetboek", "eigenaarsportaal"):
            self.assertNotIn(dutch, html)
        self.assertIn("Code civil", html)
        mandate.action_make_posting()
        self.assertNotIn("Aanplakking", mandate.posting_document_id.name)

    def test_fee_invoice_in_the_vmes_language(self):
        office = self._syndic_office()
        agreement = self.env["vme.management.agreement"].create({
            "association_id": self.vme.id, "syndic_company_id": office.id, "date_start": date(2026, 1, 1),
            "fee_basis": "lot", "fee_amount": 10.0, "billing_period": "quarter", "indexation": "none",
        })
        self._set_vme_lang("fr_BE")
        mail = self.env["vme.registered.mail"].create({
            "association_id": self.vme.id, "partner_id": self.owner_nl.id, "subject": "Brief",
            "date": date(2026, 8, 3)})
        mail.action_deposit()
        agreement.service_line_ids.date = date(2026, 8, 3)  # deposited today; move it into the quarter
        invoice = agreement._create_fee_invoice(date(2026, 7, 1), date(2026, 9, 30))
        fixed = invoice.invoice_line_ids.filtered(lambda l: not l.vme_service_line_id)
        service = invoice.invoice_line_ids - fixed
        self.assertNotIn("ereloon", fixed.name.lower())
        self.assertIn("(2 lots × 3 ", fixed.name)
        self.assertIn("juillet 2026", fixed.name)
        self.assertNotIn("Aangetekende zending", service.name)
        self.assertIn("recommandé", service.name.lower())
