from odoo import fields, models


class VmeRentSettlementWizard(models.TransientModel):
    _name = "vme.rent.settlement.wizard"
    _description = "Afrekening lasten huurder maken"

    contract_id = fields.Many2one("vme.rent.contract", string="Huurcontract", required=True)
    year = fields.Integer(string="Jaar", required=True, default=lambda self: fields.Date.context_today(self).year)

    def action_create(self):
        self.ensure_one()
        Settlement = self.env["vme.rent.settlement"]
        settlement = Settlement.search([("contract_id", "=", self.contract_id.id), ("year", "=", self.year)])
        if settlement:
            settlement.filtered(lambda s: s.state == "draft").action_recompute()
        else:
            settlement = Settlement.create({"contract_id": self.contract_id.id, "year": self.year})
        return {
            "type": "ir.actions.act_window",
            "name": settlement.display_name,
            "res_model": "vme.rent.settlement",
            "res_id": settlement.id,
            "view_mode": "form",
        }
