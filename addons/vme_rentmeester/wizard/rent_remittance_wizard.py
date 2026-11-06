from dateutil.relativedelta import relativedelta

from odoo import fields, models


class VmeRentRemittanceWizard(models.TransientModel):
    _name = "vme.rent.remittance.wizard"
    _description = "Doorstortingen maken"

    month = fields.Date(
        string="Maand", required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1))
    company_id = fields.Many2one(
        "res.company", string="Rentmeesterkantoor", required=True, domain=[("is_rent_management", "=", True)],
        default=lambda self: self.env["vme.rent.contract"]._default_company())
    landlord_ids = fields.Many2many("res.partner", string="Verhuurders", help="Leeg laten voor alle verhuurders.")

    def action_create(self):
        self.ensure_one()
        remittances = self.env["vme.rent.remittance"]._create_for_month(
            self.month, self.company_id, self.landlord_ids or None)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Doorstortingen"),
            "res_model": "vme.rent.remittance",
            "view_mode": "list,form",
            "domain": [("id", "in", remittances.ids)],
        }
