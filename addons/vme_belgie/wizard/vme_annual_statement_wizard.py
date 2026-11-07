from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import formatLang


class VmeAnnualStatementWizard(models.TransientModel):
    _name = "vme.annual.statement.wizard"
    _description = "Jaarafrekening"

    association_id = fields.Many2one("vme.association", string="VME", required=True)
    year = fields.Integer(string="Jaar", required=True, default=lambda self: fields.Date.today().year)
    partner_ids = fields.Many2many(
        "res.partner", string="Eigenaars",
        help="Leeg laten voor alle eigenaars met kosten of provisies in dit jaar.",
    )
    preview_html = fields.Html(string="Voorbeeld", compute="_compute_preview_html", sanitize=False)

    def _get_statement(self):
        self.ensure_one()
        vme = self.association_id._origin or self.association_id
        # The statement is read as sudo: first make sure the user may read this VME at all.
        vme.check_access("read")
        return vme._get_annual_statement(self.year, self.partner_ids._origin or None)

    @api.depends("association_id", "year", "partner_ids")
    def _compute_preview_html(self):
        for wizard in self:
            if not wizard.association_id or not wizard.year:
                wizard.preview_html = False
                continue
            data = wizard._get_statement()
            currency = data["currency"]

            def money(amount, currency=currency):
                return formatLang(self.env, amount, currency_obj=currency)

            rows = Markup("").join(
                Markup("<tr><td>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td>"
                       "<td class='text-end'>%s</td><td class='text-end fw-bold %s'>%s</td></tr>") % (
                    st["partner"].name, money(st["cost_total"]), money(st["working"]["paid"]),
                    money(st["working"]["open"]) if st["working"]["open"] else "",
                    "text-danger" if st["balance"] > 0 else "text-success", money(st["balance"]),
                )
                for st in data["statements"]
            )
            header = Markup("<tr><th>%s</th><th class='text-end'>%s</th><th class='text-end'>%s</th>"
                            "<th class='text-end'>%s</th><th class='text-end'>%s</th></tr>") % (
                self.env._("Eigenaar"), self.env._("Aandeel kosten"), self.env._("Betaalde provisies"),
                self.env._("Nog open"), self.env._("Saldo"))
            if data["is_complete"]:
                check = Markup("<div class='alert alert-success'>%s</div>") % self.env._(
                    "Controle: de som van alle aandelen (%(allocated)s) is gelijk aan de geboekte kosten van %(year)s.",
                    allocated=money(data["allocated_total"]), year=wizard.year)
            else:
                check = Markup("<div class='alert alert-warning'>%s</div>") % self.env._(
                    "Controle: geboekte kosten %(bills)s, verdeeld %(allocated)s. Niet verdeeld: %(moves)s",
                    bills=money(data["bills_total"]), allocated=money(data["allocated_total"]),
                    moves=", ".join(data["undistributed_bills"].mapped("display_name")) or "-")
            legend = Markup("<p class='text-muted small'>%s</p>") % self.env._(
                "Saldo in het rood: de eigenaar betaalt bij. In het groen (min): in het voordeel van de eigenaar.")
            wizard.preview_html = check + Markup("<table class='table table-sm'>%s%s</table>") % (header, rows) + legend

    def action_print(self):
        self.ensure_one()
        if not self._get_statement()["statements"]:
            raise UserError(self.env._("Geen kosten of provisies voor %(vme)s in %(year)s.",
                                       vme=self.association_id.name, year=self.year))
        return self.env.ref("vme_belgie.action_report_annual_statement").report_action(self)
