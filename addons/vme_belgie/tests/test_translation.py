from datetime import date

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTranslation(TransactionCase):
    """Documents for an owner are in the owner's language (see docs/dev/vertaling.md)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for lang in ("nl_BE", "fr_BE"):
            cls.env["res.lang"]._activate_lang(lang)
        cls.env["ir.module.module"].search([("name", "=", "vme_belgie")])._update_translations(["fr_BE"])
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
