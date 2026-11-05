from odoo import fields, models


class VmeCostAllocation(models.Model):
    _name = "vme.cost.allocation"
    _description = "Kostenverdeling per eigenaar"
    _order = "move_id, lot_id, date_from"

    move_id = fields.Many2one("account.move", string="Factuur", required=True, ondelete="cascade", index=True)
    move_line_id = fields.Many2one(
        "account.move.line", string="Factuurlijn", required=True, ondelete="cascade", index=True
    )
    association_id = fields.Many2one("vme.association", string="VME", required=True, index=True)
    company_id = fields.Many2one(related="move_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    invoice_date = fields.Date(related="move_id.invoice_date", string="Factuurdatum", store=True)
    supplier_id = fields.Many2one(related="move_id.partner_id", string="Leverancier", store=True)
    description = fields.Char(related="move_line_id.name", string="Omschrijving")
    key_id = fields.Many2one("vme.key", string="Sleutel", required=True)
    lot_id = fields.Many2one("vme.lot", string="Kavel", required=True)
    partner_id = fields.Many2one("res.partner", string="Eigenaar", required=True, index=True)
    # Summing shares or days over several lots means nothing, so no group totals.
    shares = fields.Float(string="Quotiteit", digits=(16, 2), aggregator=None)
    date_from = fields.Date(string="Van", required=True)
    date_to = fields.Date(string="Tot", required=True)
    days = fields.Integer(string="Dagen", aggregator=None)
    amount = fields.Monetary(string="Bedrag", required=True)
    # Only for keys "op verbruik": amount = fixed part (shares) + variable part (consumption).
    fixed_amount = fields.Monetary(string="Vast deel")
    variable_amount = fields.Monetary(string="Variabel deel")
    consumption = fields.Float(string="Verbruik", digits=(16, 3), aggregator=None)
