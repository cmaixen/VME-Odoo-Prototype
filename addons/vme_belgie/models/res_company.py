from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Without a document layout, the first PDF of a company opens Odoo's layout wizard instead of the PDF:
    # every VME is a company, so that wizard would pop up in the middle of the work (and of a demo).

    @api.model_create_multi
    def create(self, vals_list):
        layout = self.env.ref("web.external_layout_standard", raise_if_not_found=False)
        for vals in vals_list:
            if layout and not vals.get("external_report_layout_id"):
                vals["external_report_layout_id"] = layout.id
        return super().create(vals_list)

    @api.model
    def _ensure_report_layout(self):
        layout = self.env.ref("web.external_layout_standard", raise_if_not_found=False)
        if layout:
            self.sudo().search([("external_report_layout_id", "=", False)]).external_report_layout_id = layout
