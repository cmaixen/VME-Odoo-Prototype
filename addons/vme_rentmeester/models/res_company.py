from odoo import api, fields, models
from odoo.exceptions import ValidationError

RENT_ACCOUNT_CODE = "489100"
FEE_ACCOUNT_CODE = "700100"
FEE_TAX_XMLID = "attn_VAT-OUT-21-S"


class ResCompany(models.Model):
    _inherit = "res.company"

    is_rent_management = fields.Boolean(
        string="Rentmeesterkantoor",
        help="De huurcontracten, huurfacturen en afrekeningen aan huurders komen in deze company.",
    )
    # LEGAL-CHECK: KB 29 juni 2018 (Code van plichtenleer van de vastgoedmakelaars), nakijken welk artikel -
    # gelden van derden staan op een aparte derdenrekening (rubriekrekening), niet op de eigen rekening van het kantoor.
    rent_bank_id = fields.Many2one(
        "res.partner.bank", string="Derdenrekening",
        domain="[('partner_id', '=', partner_id)]",
        help="De rekening van het kantoor waarop de huurders betalen en waarvan het saldo naar de verhuurders gaat.")

    @api.constrains("rent_bank_id")
    def _check_rent_bank(self):
        # Bank accounts have no company of their own: the third-party account must be one of the office itself.
        for company in self.filtered("rent_bank_id"):
            if company.rent_bank_id.partner_id.commercial_partner_id != company.partner_id.commercial_partner_id:
                raise ValidationError(self.env._("Kies als derdenrekening een rekening van %s zelf.", company.name))

    def _rent_account(self):
        """Account for rent and charges collected on behalf of landlords (created when missing)."""
        self.ensure_one()
        # The rent is the landlord's money: the office owes it to the landlord, it is not its own revenue.
        return self._rent_get_account(RENT_ACCOUNT_CODE, self.env._("Huur en lasten voor rekening van verhuurders"),
                                      "liability_current")

    def _rent_fee_account(self):
        """Revenue account of the rental agent's fee (created when missing)."""
        self.ensure_one()
        return self._rent_get_account(FEE_ACCOUNT_CODE, self.env._("Erelonen rentmeester"), "income")

    def _rent_get_account(self, code, name, account_type):
        Account = self.env["account.account"].sudo().with_company(self)
        account = Account.search([("company_ids", "in", self.id), ("code", "=", code)], limit=1)
        return account or Account.create({
            "code": code, "name": name, "account_type": account_type, "company_ids": [self.id],
        })

    def _rent_fee_tax(self):
        """VAT 21% on services, from the Belgian chart of accounts of the office."""
        if not self:
            return self.env["account.tax"]
        self.ensure_one()
        tax = self.env["account.chart.template"].with_company(self).ref(FEE_TAX_XMLID, raise_if_not_found=False)
        return tax or self.env["account.tax"].sudo().search([
            ("company_id", "=", self.id), ("type_tax_use", "=", "sale"), ("amount", "=", 21.0),
            ("amount_type", "=", "percent")], limit=1)
