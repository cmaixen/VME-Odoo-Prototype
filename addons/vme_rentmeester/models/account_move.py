from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    rent_contract_id = fields.Many2one("vme.rent.contract", string="Huurcontract", index=True, copy=False,
                                       readonly=True)
    rent_period = fields.Date(string="Huurmaand", copy=False, readonly=True)
    rent_landlord_id = fields.Many2one(related="rent_contract_id.landlord_id", store=True, string="Verhuurder")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    rent_line_type = fields.Selection(
        [("rent", "Huur"), ("charges", "Lasten"), ("settlement", "Afrekening lasten")],
        string="Soort huurlijn", copy=False,
    )
