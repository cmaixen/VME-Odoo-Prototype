from odoo import fields, models

RENT_ACCOUNT_CODE = "489100"


class ResCompany(models.Model):
    _inherit = "res.company"

    is_rent_management = fields.Boolean(
        string="Rentmeesterkantoor",
        help="De huurcontracten, huurfacturen en afrekeningen aan huurders komen in deze company.",
    )

    def _rent_account(self):
        """Account for rent and charges collected on behalf of landlords (created when missing)."""
        self.ensure_one()
        Account = self.env["account.account"].sudo().with_company(self)
        account = Account.search([("company_ids", "in", self.id), ("code", "=", RENT_ACCOUNT_CODE)], limit=1)
        if not account:
            # The rent is the landlord's money: the office owes it to the landlord, it is not its own revenue.
            account = Account.create({
                "code": RENT_ACCOUNT_CODE,
                "name": self.env._("Huur en lasten voor rekening van verhuurders"),
                "account_type": "liability_current",
                "company_ids": [self.id],
            })
        return account
