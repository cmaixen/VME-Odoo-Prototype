from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from . import rent_rules


class VmeRentIndexation(models.Model):
    _name = "vme.rent.indexation"
    _inherit = ["mail.thread"]
    _description = "Indexering van de huur"
    _order = "anniversary_date desc, id desc"
    _rec_name = "display_name"

    contract_id = fields.Many2one("vme.rent.contract", string="Huurcontract", required=True, ondelete="cascade",
                                  index=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True)
    currency_id = fields.Many2one(related="contract_id.currency_id")
    landlord_id = fields.Many2one(related="contract_id.landlord_id", store=True, string="Verhuurder")
    tenant_id = fields.Many2one(related="contract_id.tenant_id", string="Huurder")
    state = fields.Selection([("draft", "Concept"), ("confirmed", "Bevestigd"), ("cancelled", "Geannuleerd")],
                             string="Status", default="draft", required=True, tracking=True)
    anniversary_date = fields.Date(string="Verjaardag", required=True)
    request_date = fields.Date(string="Datum van de brief", required=True, default=fields.Date.context_today,
                               help="De indexering geldt hoogstens drie maanden vóór deze datum.")
    effective_date = fields.Date(string="Nieuwe huur vanaf")

    region = fields.Selection(rent_rules.REGIONS, string="Gewest")
    epc_label = fields.Selection(rent_rules.EPC_LABELS, string="EPC-label")
    base_rent = fields.Monetary(string="Basishuur")
    previous_rent = fields.Monetary(string="Huidige huur")
    start_index_month = fields.Date(string="Maand aanvangsindex")
    start_index = fields.Float(string="Aanvangsindex", digits=(16, 2))
    new_index_month = fields.Date(string="Maand nieuw indexcijfer")
    new_index = fields.Float(string="Nieuw indexcijfer", digits=(16, 2))
    theoretical_rent = fields.Monetary(string="Volledig geïndexeerde huur")
    freeze_anniversary = fields.Date(string="Verjaardag tijdens de indexstop")
    freeze_rate = fields.Float(string="Toegelaten deel tijdens de indexstop", digits=(5, 2))
    correction_factor = fields.Float(string="Correctiefactor", digits=(16, 6))
    new_rent = fields.Monetary(string="Nieuwe huur")
    increase = fields.Monetary(string="Verschil", compute="_compute_increase")

    @api.depends("new_rent", "previous_rent")
    def _compute_increase(self):
        for indexation in self:
            indexation.increase = indexation.new_rent - indexation.previous_rent

    @api.depends("contract_id.name", "anniversary_date")
    def _compute_display_name(self):
        for indexation in self:
            indexation.display_name = self.env._(
                "Indexering %(year)s - %(contract)s",
                year=indexation.anniversary_date and indexation.anniversary_date.year or "",
                contract=indexation.contract_id.name or "")

    @api.model
    def _prepare_amounts(self, contract, anniversary_date, request_date):
        Index = self.env["vme.rent.index"]
        try:
            values = rent_rules.compute_indexation(
                contract.region, contract.rent, contract.date_signed, contract.date_start, anniversary_date,
                contract.epc_label, Index._lookup, request_date=request_date)
        except rent_rules.IndexMissing as missing:
            raise Index._missing_error(missing.month) from None
        currency = contract.currency_id
        return {
            "region": contract.region,
            "epc_label": contract.epc_label,
            "base_rent": contract.rent,
            "previous_rent": contract._get_rent_on(anniversary_date - relativedelta(days=1)),
            "start_index_month": values["start_index_month"],
            "start_index": values["start_index"],
            "new_index_month": values["new_index_month"],
            "new_index": values["new_index"],
            "theoretical_rent": currency.round(values["theoretical_rent"]),
            "freeze_anniversary": values["freeze_anniversary"],
            "freeze_rate": values["freeze_rate"],
            "correction_factor": values["correction_factor"],
            "new_rent": currency.round(values["new_rent"]),
            "effective_date": values["effective_date"],
        }

    def action_recompute(self):
        for indexation in self:
            if indexation.state != "draft":
                raise UserError(self.env._("Alleen een concept kan herberekend worden."))
            indexation.write(self._prepare_amounts(
                indexation.contract_id, indexation.anniversary_date, indexation.request_date))

    def action_confirm(self):
        for indexation in self:
            if indexation.state != "draft":
                continue
            indexation.state = "confirmed"
            # Draft rent invoices from the new rent on still carry the old rent: make them again.
            contract = indexation.contract_id
            drafts = contract.sudo().invoice_ids.filtered(
                lambda m: m.state == "draft" and m.rent_period
                and m.rent_period >= indexation.effective_date.replace(day=1))
            periods = drafts.mapped("rent_period")
            drafts.unlink()
            for period in periods:
                contract._create_rent_invoices(period)
            indexation.contract_id.message_post(body=self.env._(
                "Huur geïndexeerd tot %(rent)s per maand vanaf %(date)s.",
                rent=indexation.currency_id.format(indexation.new_rent),
                date=format_date(self.env, indexation.effective_date)))

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_print_letter(self):
        return self.env.ref("vme_rentmeester.action_report_indexation_letter").report_action(self)

    def _get_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Indexering"),
            "res_model": "vme.rent.indexation",
            "res_id": self.id,
            "view_mode": "form",
        }
