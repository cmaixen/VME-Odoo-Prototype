from datetime import date

from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError

# Costs of a key or account count as over budget when they exceed the budget up to today by
# more than this share: one bill a few days early is no reason for a signal.
BUDGET_TOLERANCE = 0.10


def budget_elapsed_ratio(year, date_to):
    """Share of the budget year that has passed on date_to (both days included), between 0 and 1.

    The budget is spread evenly per day: a yearly budget of 3650 is 10 per day, also in a leap year
    (then 3650 / 366 per day).
    """
    start, end = date(year, 1, 1), date(year, 12, 31)
    if date_to < start:
        return 0.0
    if date_to >= end:
        return 1.0
    return ((date_to - start).days + 1) / ((end - start).days + 1)


class VmeBudget(models.Model):
    _inherit = "vme.budget"

    line_ids = fields.One2many("vme.budget.line", "budget_id", string="Budget per rekening en sleutel", copy=True)
    lines_total = fields.Monetary(string="Ingedeeld", compute="_compute_lines_total")
    unassigned_amount = fields.Monetary(
        string="Niet ingedeeld", compute="_compute_lines_total",
        help="Deel van het werkkapitaalbudget dat niet aan een rekening is toegewezen.",
    )

    @api.depends("line_ids.amount", "working_capital_budget")
    def _compute_lines_total(self):
        for budget in self:
            budget.lines_total = sum(budget.line_ids.mapped("amount"))
            budget.unassigned_amount = budget.working_capital_budget - budget.lines_total


class VmeBudgetLine(models.Model):
    _name = "vme.budget.line"
    _description = "Budget per rekening en sleutel"
    _order = "budget_id, sequence, id"

    budget_id = fields.Many2one("vme.budget", string="Jaarbudget", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    association_id = fields.Many2one(related="budget_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="budget_id.company_id", store=True)
    currency_id = fields.Many2one(related="budget_id.currency_id")
    year = fields.Integer(related="budget_id.year", store=True, string="Jaar")
    name = fields.Char(string="Omschrijving")
    account_id = fields.Many2one(
        "account.account", string="Rekening", required=True,
        domain="[('company_ids', 'in', company_id), ('account_type', '=like', 'expense%')]",
    )
    key_id = fields.Many2one(
        "vme.key", string="Verdeelsleutel", domain="[('association_id', '=', association_id)]",
        help="Leeg: de kosten op deze rekening, welke sleutel ze ook krijgen.",
    )
    amount = fields.Monetary(string="Budget", required=True)

    @api.constrains("amount")
    def _check_amount(self):
        if any(line.amount < 0 for line in self):
            raise ValidationError(self.env._("Een budgetregel kan niet negatief zijn."))


class VmeBudgetAnalysis(models.Model):
    """Budget against actual costs per VME, year, account and key. Read-only SQL view for pivot and graph.

    Budget rows come from the budget lines (and the unassigned rest of the working capital budget),
    actual rows from the product lines of posted vendor bills, VAT included because it is a cost
    for a VME. Bills paid from the reserve capital are not part of the working capital budget.
    """

    _name = "vme.budget.analysis"
    _description = "Budgetopvolging"
    _auto = False
    _order = "association_id, year desc, account_id, key_id"

    association_id = fields.Many2one("vme.association", string="VME", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    year = fields.Integer(string="Jaar", readonly=True, aggregator=None)
    date = fields.Date(string="Datum", readonly=True)
    kind = fields.Selection(
        [("budget", "Budget"), ("unassigned", "Budget niet ingedeeld"), ("actual", "Werkelijke kost")],
        string="Soort", readonly=True,
    )
    account_id = fields.Many2one("account.account", string="Rekening", readonly=True)
    key_id = fields.Many2one("vme.key", string="Verdeelsleutel", readonly=True)
    move_id = fields.Many2one("account.move", string="Factuur", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Leverancier", readonly=True)
    name = fields.Char(string="Omschrijving", readonly=True)
    budget_amount = fields.Monetary(string="Budget jaar", readonly=True)
    budget_to_date = fields.Monetary(string="Budget tot vandaag", readonly=True)
    actual_amount = fields.Monetary(string="Werkelijk", readonly=True)
    difference = fields.Monetary(
        string="Verschil", readonly=True, help="Budget tot vandaag min werkelijke kosten; negatief is overschreden.",
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Same spreading per day as budget_elapsed_ratio(), with today's date.
        ratio = """LEAST(GREATEST(CURRENT_DATE - make_date(b.year, 1, 1) + 1, 0),
                         make_date(b.year, 12, 31) - make_date(b.year, 1, 1) + 1)::numeric
                   / (make_date(b.year, 12, 31) - make_date(b.year, 1, 1) + 1)"""
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT d.*, d.budget_to_date - d.actual_amount AS difference
              FROM (
                SELECT bl.id * 10 + 1 AS id, b.association_id, b.company_id, c.currency_id, b.year,
                       make_date(b.year, 1, 1) AS date, 'budget' AS kind, bl.account_id, bl.key_id,
                       NULL::integer AS move_id, NULL::integer AS partner_id, bl.name,
                       bl.amount AS budget_amount, ROUND(bl.amount * {ratio}, 2) AS budget_to_date,
                       0::numeric AS actual_amount
                  FROM vme_budget_line bl
                  JOIN vme_budget b ON b.id = bl.budget_id
                  JOIN res_company c ON c.id = b.company_id
                UNION ALL
                SELECT b.id * 10 + 2, b.association_id, b.company_id, c.currency_id, b.year,
                       make_date(b.year, 1, 1), 'unassigned', NULL, NULL, NULL, NULL, 'Niet ingedeeld',
                       rest.amount, ROUND(rest.amount * {ratio}, 2), 0
                  FROM vme_budget b
                  JOIN res_company c ON c.id = b.company_id
                  CROSS JOIN LATERAL (
                      SELECT b.working_capital_budget - COALESCE(SUM(bl.amount), 0) AS amount
                        FROM vme_budget_line bl WHERE bl.budget_id = b.id
                  ) rest
                 WHERE rest.amount != 0
                UNION ALL
                SELECT aml.id * 10 + 3, vme.id, move.company_id, c.currency_id,
                       EXTRACT(YEAR FROM move.invoice_date)::integer, move.invoice_date, 'actual',
                       aml.account_id, aml.vme_key_id, move.id, move.partner_id, aml.name,
                       0, 0, CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END * aml.price_total
                  FROM account_move_line aml
                  JOIN account_move move ON move.id = aml.move_id
                  JOIN vme_association vme ON vme.company_id = move.company_id
                  JOIN res_company c ON c.id = move.company_id
                 WHERE move.move_type IN ('in_invoice', 'in_refund')
                   AND move.state = 'posted'
                   AND move.invoice_date IS NOT NULL
                   AND move.vme_reserve_move_id IS NULL
                   AND aml.display_type = 'product'
              ) AS d
        """)


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    def _get_budget_tracking(self, year=None, date_to=None):
        """Working capital budget against actual costs from 1 January up to date_to (default today).

        Returns the rows per account and key, the same figures per account and per key, and the
        totals. The budget up to date_to is the yearly budget spread evenly per day. Read as sudo,
        like the annual statement: the records live in the company of the VME.
        """
        self.ensure_one()
        # In the company of the VME: account codes are stored per company.
        vme = self.sudo().with_company(self.sudo().company_id)
        currency = vme.company_id.currency_id
        date_to = date_to or fields.Date.context_today(self)
        year = year or date_to.year
        ratio = budget_elapsed_ratio(year, date_to)
        budget = vme.budget_ids.filtered(lambda b: b.year == year)[:1]
        Account, Key = vme.env["account.account"], vme.env["vme.key"]

        rows = {}

        def add(account, key, budget_amount=0.0, actual=0.0):
            row = rows.setdefault((account, key), {"account": account, "key": key, "budget": 0.0, "actual": 0.0})
            row["budget"] += budget_amount
            row["actual"] += actual

        for line in budget.line_ids:
            add(line.account_id, line.key_id, budget_amount=line.amount)
        if budget and not currency.is_zero(budget.unassigned_amount):
            add(Account, Key, budget_amount=budget.unassigned_amount)

        bill_lines = vme.env["account.move.line"].search([
            ("company_id", "=", vme.company_id.id),
            ("move_id.move_type", "in", ("in_invoice", "in_refund")),
            ("parent_state", "=", "posted"),
            ("display_type", "=", "product"),
            ("move_id.invoice_date", ">=", date(year, 1, 1)),
            ("move_id.invoice_date", "<=", min(date_to, date(year, 12, 31))),
            ("move_id.vme_reserve_move_id", "=", False),
        ])
        for line in bill_lines:
            sign = -1 if line.move_id.move_type == "in_refund" else 1
            # A budget line without key covers the costs of its account under any key.
            key = line.vme_key_id
            if (line.account_id, key) not in rows and (line.account_id, Key) in rows:
                key = Key
            add(line.account_id, key, actual=sign * line.price_total)

        def finish(row):
            row["budget"] = currency.round(row["budget"])
            row["actual"] = currency.round(row["actual"])
            row["budget_to_date"] = currency.round(row["budget"] * ratio)
            row["difference"] = currency.round(row["budget_to_date"] - row["actual"])
            row["usage"] = row["actual"] / row["budget_to_date"] if row["budget_to_date"] else 0.0
            if not row["budget"] and row["actual"] > 0:
                row["status"] = "no_budget"
            elif row["actual"] > row["budget_to_date"] * (1 + BUDGET_TOLERANCE) and row["difference"] < 0:
                row["status"] = "over"
            else:
                row["status"] = "ok"
            return row

        def group(field):
            groups = {}
            for row in rows.values():
                target = groups.setdefault(row[field], {field: row[field], "budget": 0.0, "actual": 0.0})
                target["budget"] += row["budget"]
                target["actual"] += row["actual"]
            return [finish(g) for g in groups.values()]

        def sort_key(row):
            account, key = row.get("account"), row.get("key")
            return (not account, account.code or "" if account else "", not key, key.sequence if key else 0,
                    key.name or "" if key else "")

        by_account = sorted(group("account"), key=sort_key)
        by_key = sorted(group("key"), key=sort_key)
        total = finish({
            "budget": sum(r["budget"] for r in rows.values()),
            "actual": sum(r["actual"] for r in rows.values()),
        })
        return {
            "year": year,
            "date_to": date_to,
            "ratio": ratio,
            "budget": budget,
            "currency": currency,
            "rows": sorted((finish(r) for r in rows.values()), key=sort_key),
            "by_account": by_account,
            "by_key": by_key,
            "total": total,
        }

    def action_open_budget_analysis(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_budget_analysis_action")
        action["domain"] = [("association_id", "=", self.id)]
        action["context"] = {"search_default_this_year": 1}
        action["display_name"] = self.env._("Budgetopvolging %s", self.name)
        return action
