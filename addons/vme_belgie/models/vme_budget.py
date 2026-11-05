from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, formatLang

# LEGAL-CHECK: art. 3.86 §3 BW - yearly reserve fund contribution of at least 5% of the
# ordinary common charges of the previous year, unless the general assembly decides
# otherwise with a 4/5 majority.
RESERVE_MINIMUM_RATE = 0.05


class VmeBudget(models.Model):
    _name = "vme.budget"
    _description = "Jaarbudget VME"
    _order = "association_id, year desc"

    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    year = fields.Integer(string="Jaar", required=True, default=lambda self: fields.Date.today().year + 1)
    working_capital_budget = fields.Monetary(string="Jaarbudget werkkapitaal", required=True)
    reserve_capital_contribution = fields.Monetary(string="Jaarbijdrage reservekapitaal", required=True)
    calls_per_year = fields.Selection(
        [("1", "1 keer per jaar"), ("2", "Halfjaarlijks"), ("4", "Per kwartaal"), ("12", "Maandelijks")],
        string="Oproepen per jaar",
        required=True,
        default="4",
    )
    reserve_exception_by_general_assembly = fields.Boolean(
        string="AV besliste met 4/5 anders",
        help="De algemene vergadering besliste met een 4/5-meerderheid om minder dan 5% op te bouwen.",
    )
    previous_year_charges = fields.Monetary(
        string="Gewone lasten vorig jaar", compute="_compute_reserve_check"
    )
    previous_year_charges_estimated = fields.Boolean(compute="_compute_reserve_check")
    reserve_minimum = fields.Monetary(string="Minimum reservebijdrage (5%)", compute="_compute_reserve_check")
    reserve_warning = fields.Char(compute="_compute_reserve_check")
    provision_call_ids = fields.One2many("vme.provision.call", "budget_id", string="Provisieoproepen")

    _unique_year_per_association = models.Constraint(
        "UNIQUE (association_id, year)",
        "Er bestaat al een budget voor deze VME en dit jaar.",
    )

    @api.depends("association_id", "year", "working_capital_budget", "reserve_capital_contribution",
                 "reserve_exception_by_general_assembly")
    def _compute_reserve_check(self):
        for budget in self:
            charges = budget._get_previous_year_charges()
            budget.previous_year_charges_estimated = not charges
            budget.previous_year_charges = charges or budget.working_capital_budget
            budget.reserve_minimum = budget.previous_year_charges * RESERVE_MINIMUM_RATE
            below = float_compare(
                budget.reserve_capital_contribution, budget.reserve_minimum,
                precision_rounding=budget.currency_id.rounding or 0.01,
            ) < 0
            if below and not budget.reserve_exception_by_general_assembly:
                basis = (self.env._("geschat op het werkkapitaalbudget") if budget.previous_year_charges_estimated
                         else self.env._("op basis van de geboekte lasten van %s", budget.year - 1))
                budget.reserve_warning = self.env._(
                    "De bijdrage aan het reservekapitaal (%(contribution)s) is lager dan 5%% van de gewone "
                    "lasten van vorig jaar (%(minimum)s, %(basis)s). Dat mag alleen als de AV met 4/5 anders besliste.",
                    contribution=formatLang(self.env, budget.reserve_capital_contribution, currency_obj=budget.currency_id),
                    minimum=formatLang(self.env, budget.reserve_minimum, currency_obj=budget.currency_id),
                    basis=basis,
                )
            else:
                budget.reserve_warning = False

    def _get_previous_year_charges(self):
        """Posted vendor bills (incl. VAT, which is a cost for a VME) of the previous year."""
        self.ensure_one()
        if not self.company_id or not self.year:
            return 0.0
        bills = self.env["account.move"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", f"{self.year - 1}-01-01"),
            ("invoice_date", "<=", f"{self.year - 1}-12-31"),
        ])
        return -sum(bills.mapped("amount_total_signed"))

    @api.depends("association_id.name", "year")
    def _compute_display_name(self):
        for budget in self:
            budget.display_name = f"{budget.association_id.name} {budget.year}"

    @api.constrains("working_capital_budget", "reserve_capital_contribution")
    def _check_amounts(self):
        for budget in self:
            if budget.working_capital_budget < 0 or budget.reserve_capital_contribution < 0:
                raise ValidationError(self.env._("Budgetbedragen kunnen niet negatief zijn."))
