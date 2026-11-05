from odoo import api, fields, models

FUNDS = [("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")]


class VmeProvisionCall(models.Model):
    _name = "vme.provision.call"
    _description = "Provisieoproep"
    _order = "date desc, association_id"

    budget_id = fields.Many2one("vme.budget", string="Budget", required=True, ondelete="restrict", index=True)
    association_id = fields.Many2one(related="budget_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="budget_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    number = fields.Integer(string="Oproep", required=True)
    date = fields.Date(string="Factuurdatum", required=True)
    date_due = fields.Date(string="Vervaldatum", required=True)
    invoice_ids = fields.One2many("account.move", "vme_provision_call_id", string="Facturen")
    amount_working = fields.Monetary(string="Werkkapitaal", compute="_compute_amounts", store=True)
    amount_reserve = fields.Monetary(string="Reservekapitaal", compute="_compute_amounts", store=True)
    # compute_sudo: the overview spans all VMEs, whatever companies the user has selected.
    invoice_count = fields.Integer(string="Aantal facturen", compute="_compute_payment_status", compute_sudo=True)
    paid_count = fields.Integer(string="Betaald", compute="_compute_payment_status", compute_sudo=True)
    open_count = fields.Integer(string="Open", compute="_compute_payment_status", compute_sudo=True)

    _unique_number_per_budget = models.Constraint(
        "UNIQUE (budget_id, number)",
        "Deze provisieoproep bestaat al voor dit budget.",
    )

    @api.depends("invoice_ids.amount_total", "invoice_ids.vme_fund")
    def _compute_amounts(self):
        for call in self:
            call.amount_working = sum(call.invoice_ids.filtered(lambda m: m.vme_fund == "working").mapped("amount_total"))
            call.amount_reserve = sum(call.invoice_ids.filtered(lambda m: m.vme_fund == "reserve").mapped("amount_total"))

    @api.depends("invoice_ids.payment_state", "invoice_ids.state")
    def _compute_payment_status(self):
        for call in self:
            invoices = call.invoice_ids.filtered(lambda m: m.state != "cancel")
            call.invoice_count = len(invoices)
            call.paid_count = len(invoices.filtered(lambda m: m.payment_state in ("paid", "in_payment")))
            call.open_count = call.invoice_count - call.paid_count

    @api.depends("association_id.name", "number", "budget_id.year", "budget_id.calls_per_year")
    def _compute_display_name(self):
        for call in self:
            call.display_name = self.env._(
                "%(vme)s oproep %(number)s/%(total)s %(year)s",
                vme=call.association_id.name, number=call.number,
                total=call.budget_id.calls_per_year, year=call.budget_id.year,
            )

    def action_open_invoices(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("account.action_move_out_invoice_type")
        action["domain"] = [("vme_provision_call_id", "in", self.ids)]
        action["context"] = {"default_move_type": "out_invoice"}
        return action
