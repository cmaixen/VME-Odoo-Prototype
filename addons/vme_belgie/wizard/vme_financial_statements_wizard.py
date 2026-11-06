from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date


class VmeFinancialStatementsWizard(models.TransientModel):
    _name = "vme.financial.statements.wizard"
    _description = "Balans en resultatenrekening"

    association_id = fields.Many2one("vme.association", string="VME", required=True)
    year = fields.Integer(string="Boekjaar", required=True, default=lambda self: fields.Date.today().year)
    preview_html = fields.Html(string="Voorbeeld", compute="_compute_preview_html", sanitize=False)

    def _get_statements(self):
        self.ensure_one()
        vme = self.association_id._origin or self.association_id
        return vme._get_financial_statements(self.year)

    def _render_values(self, statements):
        return {"statements": statements, "format_date": lambda value: format_date(self.env, value)}

    @api.depends("association_id", "year")
    def _compute_preview_html(self):
        QWeb = self.env["ir.qweb"]
        for wizard in self:
            if not wizard.association_id or not wizard.year:
                wizard.preview_html = False
                continue
            values = wizard._render_values([wizard._get_statements()])
            wizard.preview_html = QWeb._render("vme_belgie.financial_statements_body", values)

    def action_print(self):
        self.ensure_one()
        if not self._get_statements()["has_bookings"]:
            raise UserError(self.env._("Geen boekingen voor %(vme)s tot eind %(year)s.",
                                       vme=self.association_id.name, year=self.year))
        return self.env.ref("vme_belgie.action_report_financial_statements").report_action(self)
