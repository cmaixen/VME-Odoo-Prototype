from odoo import fields, models


class VmeRentInvoiceWizard(models.TransientModel):
    _name = "vme.rent.invoice.wizard"
    _description = "Huurfacturen maken"

    month = fields.Date(string="Maand", required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    contract_ids = fields.Many2many("vme.rent.contract", string="Contracten",
                                    help="Leeg laten voor alle lopende contracten.")
    post = fields.Boolean(string="Meteen boeken", help="Anders blijven de facturen concepten. Er wordt niets verstuurd.")

    def action_create(self):
        self.ensure_one()
        contracts = self.contract_ids or self.env["vme.rent.contract"].search([("state", "in", ("active", "notice"))])
        moves = contracts._create_rent_invoices(self.month, post=self.post)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Huurfacturen"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(self.env.ref("vme_rentmeester.rent_invoice_view_list").id, "list"), (False, "form")],
            "domain": [("id", "in", moves.ids)],
            "context": {"allowed_company_ids": (moves.company_id | self.env.company).ids},
        }
