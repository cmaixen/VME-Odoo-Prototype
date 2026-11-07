"""Fictitious 281.50 payments of 2026: an external auditor, a consultancy firm and an expert without full data.

Runs at the end of the demo history; every number is fictitious (company numbers 0000..., national
register number 00.00.00-...).
"""
from datetime import date

from odoo import api, models
from odoo.fields import Command

# VME: (partner values, invoice date, payment date, description, amount); no VAT on these bills.
BELCOTAX_DEMO = {
    "Hof ter Beuken": ({
        "name": "Commissaris Voorbeeld Beuken", "street": "Controlelaan 12", "zip": "2000", "city": "Voorbeeldstad",
        "vme_belcotax_category": "fees", "vme_belcotax_profession": "Accountant",
        "vme_national_number": "00.00.00-002.95",
    }, date(2026, 3, 20), date(2026, 4, 10), "Nazicht van de rekeningen 2025 door de commissaris", 650.0),
    "Residentie Linde": ({
        "name": "Advies Voorbeeld BV", "is_company": True, "vat": "BE0000000889", "street": "Raadgeverstraat 4",
        "zip": "9000", "city": "Voorbeeldgem", "email": "facturen@advies.example.com",
        "vme_belcotax_category": "fees", "vme_belcotax_profession": "Ingenieur-adviseur",
    }, date(2026, 5, 12), date(2026, 6, 1), "Technisch advies gevelrenovatie", 1800.0),
    # Kaaihuis: the expert has no address and no national register number yet, to show the warnings.
    "Kaaihuis": ({
        "name": "Expert Voorbeeld Kaaihuis", "vme_belcotax_category": "fees",
    }, date(2026, 6, 15), date(2026, 7, 1), "Expertise vochtprobleem kelder", 420.0),
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_belcotax(self):
        Partner = self.env["res.partner"]
        be = self.env.ref("base.be")
        for vme in self.search([("name", "in", list(BELCOTAX_DEMO))]):
            values, invoice_date, payment_date, description, amount = BELCOTAX_DEMO[vme.name]
            company = vme.company_id
            # The auditor of Hof ter Beuken comes from the council demo data.
            partner = Partner.search([("name", "=", values["name"])], limit=1)
            partner = partner or Partner.create({"name": values["name"]})
            partner.write({**values, "country_id": be.id, "vme_belcotax_liable": True})
            key = vme.key_ids.filtered(lambda k: k.key_type == "general")[:1]
            account = self.env["account.account"].with_company(company).search(
                [("company_ids", "in", company.id), ("code", "=", "613290")], limit=1)
            bill = self.env["account.move"].with_company(company).create({
                "move_type": "in_invoice", "partner_id": partner.id, "invoice_date": invoice_date,
                "ref": f"FICHE-{invoice_date:%Y%m%d}",
                "invoice_line_ids": [Command.create({
                    "name": description, "quantity": 1, "price_unit": amount, "account_id": account.id,
                    "vme_key_id": key.id, "tax_ids": [Command.clear()],
                })],
            })
            bill.action_post()
            journal = vme._ensure_fund_bank_journals()[vme]["working"]
            self.env["account.payment.register"].with_company(company).with_context(
                active_model="account.move", active_ids=bill.ids,
            ).create({"journal_id": journal.id, "payment_date": payment_date}).action_create_payments()
            self.env["vme.belcotax.statement"].create({"association_id": vme.id, "year": 2026})
