from datetime import date

from odoo import api, fields, models, tools
from odoo.tools import format_date

from .account_chart_template import VME_FUND_ACCOUNTS

DEFAULT_ARREARS_THRESHOLD = 1000.0
# Due states of installations and contracts shown on the building card.
INSPECTION_CARD_STATES = ("overdue", "due_30", "due_60", "due_90")
SIGNALS = [
    ("reserve", "Reservefonds onder 5%"),
    ("arrears", "Achterstallen boven de drempel"),
    ("assembly", "AV buiten de periode"),
    ("inspection", "Vervallen keuring"),
]


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    arrears_signal_threshold = fields.Monetary(
        string="Signaal achterstallen vanaf", default=DEFAULT_ARREARS_THRESHOLD,
        help="De portefeuille toont een signaal als de achterstallen van alle eigenaars samen hoger zijn.",
    )
    working_capital_balance = fields.Monetary(string="Stand werkkapitaal", compute="_compute_portfolio")
    reserve_capital_balance = fields.Monetary(string="Stand reservekapitaal", compute="_compute_portfolio")
    arrears_amount = fields.Monetary(string="Achterstallen", compute="_compute_portfolio")
    budget_to_date_amount = fields.Monetary(string="Budget tot vandaag", compute="_compute_portfolio")
    actual_to_date_amount = fields.Monetary(string="Kosten tot vandaag", compute="_compute_portfolio")
    budget_usage = fields.Float(
        string="Budget verbruikt", compute="_compute_portfolio",
        help="Kosten tot vandaag gedeeld door het budget tot vandaag.",
    )
    signal_reserve = fields.Boolean(string="Reservefonds onder 5%", compute="_compute_portfolio",
                                    search="_search_signal_reserve")
    signal_arrears = fields.Boolean(string="Achterstallen boven de drempel", compute="_compute_portfolio",
                                    search="_search_signal_arrears")
    signal_assembly = fields.Boolean(string="AV buiten de periode", compute="_compute_portfolio",
                                     search="_search_signal_assembly")
    signal_inspection = fields.Boolean(string="Vervallen keuring", compute="_compute_portfolio",
                                       search="_search_signal_inspection")
    signal_count = fields.Integer(string="Aantal signalen", compute="_compute_portfolio", search="_search_signal_count")
    signal_summary = fields.Char(string="Signalen", compute="_compute_portfolio")
    building_card_html = fields.Html(string="Gebouwkaart", compute="_compute_building_card_html", sanitize=False)

    def _card_today(self):
        # Tests can pin "today" via the context, like the assembly planner.
        return self.env.context.get("vme_today") or fields.Date.context_today(self)

    # Capitals

    def _fund_accounts(self):
        self.ensure_one()
        company = self.sudo().company_id
        Account = self.env["account.account"].sudo().with_company(company)
        return {
            fund: Account.search([("company_ids", "in", company.id), ("code", "=", code)], limit=1)
            for fund, (code, _name) in VME_FUND_ACCOUNTS.items()
        }

    def _get_capital_history(self, date_to=None):
        """Working and reserve capital per year, from the first year with bookings up to date_to.

        Reserve capital: provisions called (credit on 100200) minus what was used for works (debit).
        Working capital: provisions called (credit on 100100) minus the costs of the vendor bills
        that are not paid from the reserve capital, VAT included. Bank shows what is on each fund's
        bank account.
        """
        self.ensure_one()
        vme = self.sudo()
        currency = vme.company_id.currency_id
        date_to = date_to or self._card_today()
        accounts = vme._fund_accounts()
        MoveLine = self.env["account.move.line"].sudo()
        movements = {"working": {}, "reserve": {}}
        for fund, account in accounts.items():
            if not account:
                continue
            for line in MoveLine.search([
                ("account_id", "=", account.id), ("company_id", "=", vme.company_id.id),
                ("parent_state", "=", "posted"), ("date", "<=", date_to),
            ]):
                year_moves = movements[fund].setdefault(line.date.year, {"in": 0.0, "out": 0.0})
                year_moves["in"] += line.credit
                year_moves["out"] += line.debit
        for line in MoveLine.search([
            ("company_id", "=", vme.company_id.id),
            ("move_id.move_type", "in", ("in_invoice", "in_refund")),
            ("parent_state", "=", "posted"), ("display_type", "=", "product"),
            ("move_id.invoice_date", "<=", date_to), ("move_id.vme_reserve_move_id", "=", False),
        ]):
            sign = -1 if line.move_id.move_type == "in_refund" else 1
            year_moves = movements["working"].setdefault(line.move_id.invoice_date.year, {"in": 0.0, "out": 0.0})
            year_moves["out"] += sign * line.price_total

        all_years = set(movements["working"]) | set(movements["reserve"])
        years = list(range(min(all_years), date_to.year + 1)) if all_years else [date_to.year]
        history, balance = [], {"working": 0.0, "reserve": 0.0}
        for year in years:
            entry = {"year": year}
            for fund in ("working", "reserve"):
                moves = movements[fund].get(year, {"in": 0.0, "out": 0.0})
                opening = balance[fund]
                balance[fund] = currency.round(opening + moves["in"] - moves["out"])
                entry[fund] = {
                    "opening": currency.round(opening),
                    "in": currency.round(moves["in"]),
                    "out": currency.round(moves["out"]),
                    "closing": balance[fund],
                }
            history.append(entry)

        bank = {}
        for fund, bank_account in (("working", vme.working_capital_bank_id), ("reserve", vme.reserve_capital_bank_id)):
            journal = self.env["account.journal"].sudo().search([
                ("company_id", "=", vme.company_id.id), ("type", "=", "bank"),
                ("bank_account_id", "=", bank_account.id)], limit=1) if bank_account else False
            if not journal:
                bank[fund] = False
                continue
            # On the bank: the bank statements, plus registered payments that no statement matched yet.
            booked = sum(MoveLine.search([
                ("journal_id", "=", journal.id), ("account_id", "=", journal.default_account_id.id),
                ("parent_state", "=", "posted"), ("date", "<=", date_to)]).mapped("balance"))
            pending = sum(self.env["account.payment"].sudo().search([
                ("journal_id", "=", journal.id), ("state", "in", ("in_process", "paid")),
                ("is_matched", "=", False), ("date", "<=", date_to)]).mapped("amount_company_currency_signed"))
            bank[fund] = currency.round(booked + pending)
        return {
            "years": history,
            "working": balance["working"],
            "reserve": balance["reserve"],
            "bank": bank,
            "currency": currency,
        }

    def action_open_capital_history(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_capital_movement_action")
        action["domain"] = [("association_id", "=", self.id)]
        action["display_name"] = self.env._("Verloop kapitalen %s", self.name)
        return action

    # Signals

    def _get_signals(self, today=None):
        """Signals of the portfolio for this VME: a list of {code, label, message}."""
        self.ensure_one()
        vme = self.sudo()
        today = today or self._card_today()
        currency = vme.company_id.currency_id
        labels = dict(SIGNALS)
        signals = []

        # LEGAL-CHECK: art. 3.86 §3 BW - yearly reserve contribution of at least 5% of the ordinary
        # common charges of the previous year, unless the general assembly decided otherwise with 4/5.
        budget = vme.budget_ids.filtered(lambda b: b.year == today.year)[:1]
        if budget.reserve_warning:
            signals.append({"code": "reserve", "message": budget.reserve_warning})

        arrears = vme._get_arrears_total()
        if currency.compare_amounts(arrears, vme.arrears_signal_threshold) > 0:
            signals.append({"code": "arrears", "message": self.env._(
                "Achterstallen van %(amount)s, boven de drempel van %(threshold)s.",
                amount=tools.formatLang(self.env, arrears, currency_obj=currency),
                threshold=tools.formatLang(self.env, vme.arrears_signal_threshold, currency_obj=currency))})

        message = vme._get_assembly_signal(today)
        if message:
            signals.append({"code": "assembly", "message": message})

        # The inspection intervals themselves carry their LEGAL-CHECK in vme_installation.py.
        overdue = vme.installation_ids.filtered(
            lambda i: i.due_state == "overdue" or i.risk_analysis_due_state == "overdue")
        if overdue:
            signals.append({"code": "inspection", "message": self.env._(
                "Vervallen keuring of risicoanalyse: %s.", ", ".join(overdue.mapped("name")))})

        for signal in signals:
            signal["label"] = labels[signal["code"]]
        return signals

    def _get_arrears_total(self):
        self.ensure_one()
        arrears = self.env["vme.arrears"].sudo().search([("association_id", "=", self.id)])
        return self.company_id.currency_id.round(sum(arrears.mapped("amount_residual")))

    def _get_assembly_signal(self, today):
        """Message when the ordinary assembly of this year is or was not held in its period."""
        self.ensure_one()
        # LEGAL-CHECK: art. 3.87 §2 BW - the ordinary general assembly is held every year within
        # the fifteen-day period fixed in the rules of co-ownership.
        start, end = self._get_assembly_period(today.year)
        if not start:
            return False
        assemblies = self.env["vme.assembly"].sudo().search([
            ("association_id", "=", self.id), ("year", "=", today.year), ("state", "!=", "cancelled")])
        outside = assemblies.filtered(
            lambda a: a.date and not (a.period_start <= a.date <= a.period_end) and (a.state == "held" or a.date >= today))
        if outside:
            return self.env._(
                "De gewone AV van %(date)s valt buiten de periode van %(start)s tot %(end)s.",
                date=format_date(self.env, outside[0].date),
                start=format_date(self.env, start), end=format_date(self.env, end))
        held = assemblies.filtered(lambda a: a.state == "held" and a.date and start <= a.date <= end)
        if end < today and not held:
            return self.env._(
                "Geen gewone AV gehouden in de periode van %(start)s tot %(end)s.",
                start=format_date(self.env, start), end=format_date(self.env, end))
        return False

    @api.depends_context("vme_today")
    def _compute_portfolio(self):
        today = self._card_today()
        for vme in self:
            if not vme.id or not vme.company_id:
                vme.update({
                    "working_capital_balance": 0.0, "reserve_capital_balance": 0.0, "arrears_amount": 0.0,
                    "budget_to_date_amount": 0.0, "actual_to_date_amount": 0.0, "budget_usage": 0.0,
                    "signal_count": 0, "signal_summary": False, **{f"signal_{code}": False for code, _ in SIGNALS},
                })
                continue
            vme_sudo = vme.sudo()
            capital = vme_sudo._get_capital_history(today)
            tracking = vme_sudo._get_budget_tracking(today.year, today)
            signals = vme_sudo._get_signals(today)
            codes = {signal["code"] for signal in signals}
            vme.update({
                "working_capital_balance": capital["working"],
                "reserve_capital_balance": capital["reserve"],
                "arrears_amount": vme_sudo._get_arrears_total(),
                "budget_to_date_amount": tracking["total"]["budget_to_date"],
                "actual_to_date_amount": tracking["total"]["actual"],
                "budget_usage": tracking["total"]["usage"],
                "signal_count": len(signals),
                "signal_summary": ", ".join(signal["label"] for signal in signals) or False,
                **{f"signal_{code}": code in codes for code, _ in SIGNALS},
            })

    def _search_signal(self, code, operator, value):
        """Search on a signal; computed fresh, since the signals depend on many other models."""
        if operator not in ("=", "!=", "in", "not in"):
            return NotImplemented
        wanted = set(value) if operator in ("in", "not in") else {value}
        today = self._card_today()
        matching = self.search([]).filtered(
            lambda vme: any(signal["code"] == code for signal in vme._get_signals(today)) in wanted)
        return [("id", "not in" if operator in ("!=", "not in") else "in", matching.ids)]

    def _search_signal_reserve(self, operator, value):
        return self._search_signal("reserve", operator, value)

    def _search_signal_arrears(self, operator, value):
        return self._search_signal("arrears", operator, value)

    def _search_signal_assembly(self, operator, value):
        return self._search_signal("assembly", operator, value)

    def _search_signal_inspection(self, operator, value):
        return self._search_signal("inspection", operator, value)

    def _search_signal_count(self, operator, value):
        compare = {
            ">": lambda n: n > value, ">=": lambda n: n >= value, "=": lambda n: n == value,
            "!=": lambda n: n != value, "<": lambda n: n < value, "<=": lambda n: n <= value,
        }.get(operator)
        if not compare:
            return NotImplemented
        today = self._card_today()
        return [("id", "in", self.search([]).filtered(lambda vme: compare(len(vme._get_signals(today)))).ids)]

    # Building card

    def _get_building_card_data(self, today=None):
        """Everything the building card shows, read as sudo for the company of this VME."""
        self.ensure_one()
        vme = self.sudo().with_company(self.sudo().company_id)
        today = today or self._card_today()
        currency = vme.company_id.currency_id
        lots = vme.lot_ids
        lot_types = dict(self.env["vme.lot"]._fields["lot_type"]._description_selection(self.env))
        lot_summary = [
            (lot_types.get(lot_type, lot_type), len(lots.filtered(lambda l, t=lot_type: l.lot_type == t)))
            for lot_type in dict.fromkeys(lots.mapped("lot_type"))
        ]
        next_assembly = self.env["vme.assembly"].sudo().search([
            ("association_id", "=", vme.id), ("state", "not in", ("held", "cancelled"))], order="year, id", limit=1)
        council = vme.mandate_ids.filtered(lambda m: m.is_current).sorted(lambda m: (m.role != "chair", m.role))

        arrears_lines = self.env["vme.arrears"].sudo().search([("association_id", "=", vme.id)])
        arrears_by_partner = {}
        for line in arrears_lines:
            entry = arrears_by_partner.setdefault(line.partner_id, {"partner": line.partner_id, "amount": 0.0, "days": 0})
            entry["amount"] += line.amount_residual
            entry["days"] = max(entry["days"], line.days_overdue)
        aging_labels = dict(self.env["vme.arrears"]._fields["aging"]._description_selection(self.env))
        arrears_by_aging = [
            (label, currency.round(sum(arrears_lines.filtered(lambda l, b=bucket: l.aging == b).mapped("amount_residual"))))
            for bucket, label in aging_labels.items()
        ]

        works = self.env["vme.works"].sudo().search([
            ("association_id", "=", vme.id), ("state", "not in", ("closed", "cancelled"))])
        damage = self.env["vme.damage.claim"].sudo().search([
            ("association_id", "=", vme.id), ("state", "not in", ("paid", "refused", "cancelled"))])
        sales = self.env["vme.sale.file"].sudo().search([
            ("association_id", "=", vme.id), ("state", "not in", ("done", "cancelled"))])
        collections = self.env["vme.collection"].sudo().search([
            ("association_id", "=", vme.id), ("state", "in", ("open", "forwarded"))])

        installations = vme.installation_ids.filtered(
            lambda i: i.due_state in INSPECTION_CARD_STATES or i.risk_analysis_due_state in INSPECTION_CARD_STATES
            or i.overdue_remark_count
        ).sorted(lambda i: min(d for d in (i.next_inspection_date, i.next_risk_analysis_date, date.max) if d))
        contracts = self.env["vme.contract"].sudo().search([
            ("association_id", "=", vme.id), ("state", "=", "running"), ("notice_deadline", "!=", False)],
            order="notice_deadline")

        bills_to_pay = self.env["account.move"].sudo().search([
            ("company_id", "=", vme.company_id.id), ("move_type", "=", "in_invoice"), ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")), ("amount_residual", ">", 0)],
            order="invoice_date_due, id")

        return {
            "vme": vme,
            "today": today,
            "currency": currency,
            "signals": vme._get_signals(today),
            "lot_summary": lot_summary,
            "owner_count": vme.owner_count,
            "next_assembly": next_assembly,
            "council": council,
            "capital": vme._get_capital_history(today),
            "budget": vme._get_budget_tracking(today.year, today),
            "arrears_total": currency.round(sum(arrears_lines.mapped("amount_residual"))),
            "arrears_by_aging": arrears_by_aging,
            "arrears_partners": sorted(arrears_by_partner.values(), key=lambda e: -e["amount"]),
            "works": works,
            "damage": damage,
            "sales": sales,
            "collections": collections,
            "installations": installations,
            "contracts": contracts,
            "requests": vme._get_open_requests(),
            "bills_to_pay": bills_to_pay,
            "payment_batches": vme._get_open_payment_batches(),
            # Approval of vendor bills before payment (step 20), when installed.
            "has_approval": "vme_approval_state" in self.env["account.move"]._fields,
            "selection_label": self._selection_label,
        }

    def _get_open_requests(self):
        """Open requests of residents (step 19), or None when that module part is not installed."""
        self.ensure_one()
        if "vme.request" not in self.env:
            return None
        Request = self.env["vme.request"].sudo()
        domain = [("association_id", "=", self.id)]
        if "state" in Request._fields:
            domain.append(("state", "not in", ("done", "closed", "cancelled", "refused")))
        return Request.search(domain, limit=20)

    def _get_open_payment_batches(self):
        """Payment batches not yet confirmed by the bank (step 20), or None without that step."""
        self.ensure_one()
        if "vme.payment.batch" not in self.env:
            return None
        Batch = self.env["vme.payment.batch"].sudo()
        domain = [("company_id", "=", self.company_id.id)] if "company_id" in Batch._fields else []
        if "state" in Batch._fields:
            domain.append(("state", "in", ("draft", "generated", "sent")))
        return Batch.search(domain, limit=20)

    @api.model
    def _selection_label(self, record, field_name):
        field = record._fields[field_name]
        return dict(field._description_selection(self.env)).get(record[field_name], "")

    @api.depends_context("vme_today")
    def _compute_building_card_html(self):
        QWeb = self.env["ir.qweb"]
        for vme in self:
            if not vme.id or not vme.company_id:
                vme.building_card_html = False
                continue
            vme.building_card_html = QWeb._render("vme_belgie.building_card_content", vme._get_building_card_data())

    def _get_portal_finances(self, today=None):
        """Simple version of the building card for owners in the portal: capitals and budget per key."""
        self.ensure_one()
        today = today or self._card_today()
        capital = self._get_capital_history(today)
        budget = self._get_budget_tracking(today.year, today)
        return {
            "currency": capital["currency"],
            "working": capital["working"],
            "reserve": capital["reserve"],
            "budget": budget,
        }

    def action_open_building_card(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Gebouwkaart"),
            "res_model": "vme.association",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("vme_belgie.vme_association_view_form_card").id, "form")],
            "target": "current",
        }


class VmeCapitalMovement(models.Model):
    """Movements of working and reserve capital, for a cumulated line graph. Read-only SQL view."""

    _name = "vme.capital.movement"
    _description = "Verloop werk- en reservekapitaal"
    _auto = False
    _order = "date, id"

    association_id = fields.Many2one("vme.association", string="VME", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    date = fields.Date(string="Datum", readonly=True)
    fund = fields.Selection([("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")], string="Fonds", readonly=True)
    kind = fields.Selection([("in", "Opgevraagd"), ("out", "Gebruikt")], string="Soort", readonly=True)
    move_id = fields.Many2one("account.move", string="Boeking", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner", readonly=True)
    amount = fields.Monetary(string="Bedrag", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Keep in line with vme.association._get_capital_history(). Account codes are stored per
        # company (code_store); every VME company is a root company.
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT aml.id * 10 + 1 AS id, vme.id AS association_id, aml.company_id, aml.company_currency_id AS currency_id,
                   aml.date, CASE account.code_store->>(aml.company_id::text) WHEN %s THEN 'working' ELSE 'reserve' END AS fund,
                   CASE WHEN aml.balance < 0 THEN 'in' ELSE 'out' END AS kind,
                   aml.move_id, aml.partner_id, -aml.balance AS amount
              FROM account_move_line aml
              JOIN account_account account ON account.id = aml.account_id
              JOIN vme_association vme ON vme.company_id = aml.company_id
             WHERE aml.parent_state = 'posted' AND account.code_store->>(aml.company_id::text) IN %s
            UNION ALL
            SELECT aml.id * 10 + 2, vme.id, move.company_id, aml.company_currency_id, move.invoice_date, 'working', 'out',
                   move.id, move.partner_id,
                   CASE WHEN move.move_type = 'in_refund' THEN 1 ELSE -1 END * aml.price_total
              FROM account_move_line aml
              JOIN account_move move ON move.id = aml.move_id
              JOIN vme_association vme ON vme.company_id = move.company_id
             WHERE move.move_type IN ('in_invoice', 'in_refund') AND move.state = 'posted'
               AND move.invoice_date IS NOT NULL AND move.vme_reserve_move_id IS NULL
               AND aml.display_type = 'product'
        """, (VME_FUND_ACCOUNTS["working"][0], tuple(code for code, _name in VME_FUND_ACCOUNTS.values())))
