"""Works decided by the general assembly: quotes, award, execution, delivery and their bills."""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import clean_context, float_compare, format_amount, format_date

from .account_chart_template import VME_FUND_ACCOUNTS
from .allocation_tools import largest_remainder

# LEGAL-CHECK: art. 3.88 §1, 1°, c) BW - the assembly fixes, with an absolute majority, the
# amount of contracts and works above which competition is compulsory. The law sets no number
# of quotes; art. 3.89 §5, 15° BW asks the syndic for "several" quotes on the basis of
# specifications. Three is the usual practice and the default here, editable per VME.
DEFAULT_MIN_QUOTES = 3
DEFAULT_QUOTE_THRESHOLD = 5000

# LEGAL-CHECK: art. 1792 en 2270 oud BW - ten-year liability of contractor and architect for
# serious defects, counted from the acceptance of the works (here the provisional delivery).
LIABILITY_YEARS = 10
# Usual contractual period between provisional and final delivery; not a legal rule.
FINAL_DELIVERY_MONTHS = 12

WORKS_STATES = [
    ("draft", "Voorbereiding"),
    ("quotes", "Offertes"),
    ("awarded", "Gegund"),
    ("in_progress", "In uitvoering"),
    ("delivered", "Voorlopig opgeleverd"),
    ("closed", "Definitief opgeleverd"),
    ("cancelled", "Geannuleerd"),
]
# States in which bills of the contractor are linked to the works automatically.
BILLABLE_STATES = ("awarded", "in_progress", "delivered")


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    works_quote_threshold = fields.Monetary(
        string="Offertes verplicht vanaf", currency_field="currency_id", default=DEFAULT_QUOTE_THRESHOLD,
        help="Bedrag dat de AV vastlegde: voor werken vanaf dit bedrag moet de syndicus meerdere offertes vragen.",
    )
    works_min_quotes = fields.Integer(
        string="Minimum aantal offertes", default=DEFAULT_MIN_QUOTES,
        help="Aantal offertes dat nodig is om werken boven de drempel te gunnen.",
    )
    works_ids = fields.One2many("vme.works", "association_id", string="Werkdossiers")
    currency_id = fields.Many2one(related="company_id.currency_id")

    def _check_company_selected(self):
        """Bills live in the company of the VME: it must be selected at the top right in Odoo."""
        self.ensure_one()
        if self.company_id not in self.env.companies:
            raise UserError(self.env._(
                "Kies rechtsboven in Odoo ook de VME %s: de facturen staan in haar boekhouding.", self.name))

    def _get_fund_balance(self, fund, on_date=None):
        """Balance of the working or reserve capital account in the books of this VME, read as sudo."""
        self.ensure_one()
        company = self.sudo().company_id
        account = self.env["account.account"].sudo().with_company(company).search([
            ("company_ids", "in", company.id), ("code", "=", VME_FUND_ACCOUNTS[fund][0])], limit=1)
        if not account:
            return 0.0
        domain = [("account_id", "=", account.id), ("company_id", "=", company.id), ("parent_state", "=", "posted")]
        if on_date:
            domain.append(("date", "<=", on_date))
        [(balance,)] = self.env["account.move.line"].sudo()._read_group(domain, aggregates=["balance:sum"])
        return company.currency_id.round(-(balance or 0.0))


class VmeAssemblyItem(models.Model):
    _inherit = "vme.assembly.item"

    works_ids = fields.One2many("vme.works", "decision_id", string="Werkdossiers")

    def action_create_works(self):
        self.ensure_one()
        if self.works_ids:
            return self.works_ids[:1]._get_form_action()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Werkdossier"),
            "res_model": "vme.works",
            "view_mode": "form",
            "context": {"default_association_id": self.association_id.id, "default_decision_id": self.id},
        }


class VmeWorks(models.Model):
    _name = "vme.works"
    _description = "Werkdossier"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "state_sequence, planned_start, id desc"

    name = fields.Char(string="Werken", required=True, tracking=True)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    user_id = fields.Many2one(
        "res.users", string="Verantwoordelijke", default=lambda self: self.env.user, domain="[('share', '=', False)]")
    description = fields.Html(string="Beschrijving")
    state = fields.Selection(WORKS_STATES, string="Status", required=True, default="draft", tracking=True)
    state_sequence = fields.Integer(compute="_compute_state_sequence", store=True)

    # Decision and financing
    decision_id = fields.Many2one(
        "vme.assembly.item", string="Beslissing AV", tracking=True,
        domain="[('association_id', '=', association_id), ('outcome', '=', 'adopted')]",
        help="De beslissing van de algemene vergadering die de werken goedkeurt.",
    )
    decision_number = fields.Char(related="decision_id.decision_number", string="Nr. beslissing")
    decision_date = fields.Date(related="decision_id.assembly_date", string="Datum AV")
    budget = fields.Monetary(
        string="Budget", compute="_compute_from_decision", store=True, readonly=False, tracking=True,
        help="Overgenomen uit de geraamde kostprijs van de beslissing.",
    )
    key_id = fields.Many2one(
        "vme.key", string="Verdeelsleutel", compute="_compute_from_decision", store=True, readonly=False,
        domain="[('association_id', '=', association_id)]",
        help="Sleutel om de facturen van de werken te verdelen. Overgenomen uit de beslissing, anders de algemene sleutel.",
    )
    financing = fields.Selection(
        [("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")], string="Financiering",
        required=True, default="reserve", tracking=True,
        help="Reservekapitaal: de facturen worden uit het reservekapitaal betaald en niet afgerekend in het werkkapitaal.",
    )
    reserve_balance = fields.Monetary(string="Stand reservekapitaal", compute="_compute_reserve")
    reserve_committed = fields.Monetary(
        string="Al vastgelegd", compute="_compute_reserve",
        help="Nog niet gefactureerd deel van andere gegunde werken uit het reservekapitaal.")
    reserve_available = fields.Monetary(string="Beschikbaar reservekapitaal", compute="_compute_reserve")
    reserve_shortfall = fields.Monetary(string="Tekort reservekapitaal", compute="_compute_reserve")

    # Quotes and award
    quote_ids = fields.One2many("vme.works.quote", "works_id", string="Offertes")
    quote_count = fields.Integer(string="Aantal offertes", compute="_compute_quotes")
    min_quotes = fields.Integer(string="Nodige offertes", compute="_compute_quotes")
    quotes_missing = fields.Integer(string="Ontbrekende offertes", compute="_compute_quotes")
    quote_deadline = fields.Date(string="Offertes binnen tegen")
    awarded_quote_id = fields.Many2one("vme.works.quote", string="Gegunde offerte", readonly=True, copy=False)
    contractor_id = fields.Many2one(
        related="awarded_quote_id.partner_id", string="Aannemer", store=True)
    contract_amount = fields.Monetary(related="awarded_quote_id.amount", string="Opdrachtbedrag", store=True)
    award_date = fields.Date(string="Gegund op", readonly=True, copy=False)

    # Execution and delivery
    planned_start = fields.Date(string="Geplande start", tracking=True)
    planned_end = fields.Date(string="Gepland einde", tracking=True)
    date_start = fields.Date(string="Werkelijke start", copy=False, tracking=True)
    progress = fields.Integer(string="Voortgang (%)", tracking=True)
    provisional_delivery_date = fields.Date(string="Voorlopige oplevering", copy=False, tracking=True)
    final_delivery_date = fields.Date(string="Definitieve oplevering", copy=False, tracking=True)
    liability_end_date = fields.Date(
        string="Einde tienjarige aansprakelijkheid", compute="_compute_liability_end", store=True)
    delivery_remarks = fields.Text(string="Opmerkingen bij de oplevering")

    # Bills
    bill_ids = fields.One2many(
        "account.move", "vme_works_id", string="Facturen", domain=[("move_type", "in", ("in_invoice", "in_refund"))])
    bill_count = fields.Integer(compute="_compute_invoiced")
    invoiced_amount = fields.Monetary(string="Gefactureerd", compute="_compute_invoiced")
    remaining_amount = fields.Monetary(string="Nog te factureren", compute="_compute_invoiced")

    @api.depends("state")
    def _compute_state_sequence(self):
        order = [code for code, _label in WORKS_STATES]
        for works in self:
            works.state_sequence = order.index(works.state)

    @api.depends("decision_id")
    def _compute_from_decision(self):
        for works in self:
            decision = works.decision_id
            if decision.works_amount and not works.budget:
                works.budget = decision.works_amount
            if not works.key_id:
                works.key_id = decision.works_key_id or works.association_id.key_ids.filtered(
                    lambda k: k.key_type == "general")[:1]

    @api.depends("quote_ids.amount", "budget", "association_id.works_quote_threshold", "association_id.works_min_quotes")
    def _compute_quotes(self):
        for works in self:
            works.quote_count = len(works.quote_ids)
            works.min_quotes = works._required_quotes()
            works.quotes_missing = max(works.min_quotes - works.quote_count, 0)

    def _required_quotes(self, amount=None):
        """Number of quotes needed for works of this amount (default: budget)."""
        self.ensure_one()
        vme = self.association_id
        amount = self.budget if amount is None else amount
        # LEGAL-CHECK: art. 3.88 §1, 1°, c) BW - competition above the amount fixed by the assembly.
        if vme.works_quote_threshold and float_compare(amount, vme.works_quote_threshold, 2) >= 0:
            return max(vme.works_min_quotes, 1)
        return 1

    @api.depends("financing", "budget", "contract_amount", "association_id", "bill_ids.state")
    def _compute_reserve(self):
        # Balance and committed works once per VME, not once per row of the list.
        balances, running = {}, {}
        for works in self:
            if not works.association_id or works.financing != "reserve":
                works.reserve_balance = works.reserve_committed = works.reserve_available = works.reserve_shortfall = 0.0
                continue
            vme = works.association_id
            if vme not in balances:
                balances[vme] = vme._get_fund_balance("reserve")
                running[vme] = self.search([
                    ("association_id", "=", vme.id), ("financing", "=", "reserve"), ("state", "in", BILLABLE_STATES)])
            balance = balances[vme]
            others = running[vme].filtered(lambda other, w=works: other.id != w._origin.id)
            committed = sum(max(other.contract_amount - other.invoiced_amount, 0.0) for other in others)
            needed = max((works.contract_amount or works.budget) - works.invoiced_amount, 0.0)
            works.reserve_balance = balance
            works.reserve_committed = works.currency_id.round(committed)
            works.reserve_available = works.currency_id.round(balance - committed)
            works.reserve_shortfall = works.currency_id.round(max(needed - (balance - committed), 0.0))

    @api.depends("provisional_delivery_date")
    def _compute_liability_end(self):
        for works in self:
            works.liability_end_date = works.provisional_delivery_date and \
                works.provisional_delivery_date + relativedelta(years=LIABILITY_YEARS)

    @api.depends("bill_ids.state", "bill_ids.amount_total_signed", "contract_amount")
    def _compute_invoiced(self):
        for works in self:
            posted = works.bill_ids.filtered(lambda m: m.state == "posted")
            works.bill_count = len(works.bill_ids)
            works.invoiced_amount = works.currency_id.round(-sum(posted.mapped("amount_total_signed")))
            works.remaining_amount = max(works.contract_amount - works.invoiced_amount, 0.0)

    @api.constrains("decision_id", "association_id")
    def _check_decision(self):
        for works in self.filtered("decision_id"):
            if works.decision_id.association_id != works.association_id:
                raise ValidationError(self.env._("De beslissing hoort bij een andere VME."))
            if works.decision_id.outcome != "adopted":
                raise ValidationError(self.env._("Een werkdossier hangt aan een aangenomen beslissing van de AV."))

    def _get_form_action(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "vme.works", "res_id": self.id, "view_mode": "form"}

    def _task(self, summary, deadline, note=None):
        self.ensure_one()
        self.activity_schedule(
            "mail.mail_activity_data_todo", date_deadline=deadline or fields.Date.context_today(self),
            summary=summary, note=note, user_id=(self.user_id or self.env.user).id)

    def _done_tasks(self, feedback):
        self.activity_ids.action_feedback(feedback=feedback)

    def _check_state(self, *allowed):
        for works in self:
            if works.state not in allowed:
                raise UserError(self.env._(
                    "%(works)s staat op \"%(state)s\"; deze stap kan niet.",
                    works=works.name, state=dict(WORKS_STATES)[works.state]))

    # Steps

    def action_request_quotes(self):
        """Start asking quotes; the request letters themselves are made and sent by a person."""
        self._check_state("draft")
        for works in self:
            if not works.budget:
                raise UserError(self.env._("Vul het budget van de werken in."))
            works.state = "quotes"
            works._task(
                self.env._("Offertes opvragen voor %s", works.name), works.quote_deadline,
                self.env._("Vraag minstens %s offerte(s) op basis van hetzelfde lastenboek.", works.min_quotes))
        return True

    def _award(self, quote):
        """Award the works to the contractor of the quote."""
        self.ensure_one()
        self._check_state("quotes")
        if quote.works_id != self:
            raise UserError(self.env._("Deze offerte hoort bij een ander werkdossier."))
        required = self._required_quotes(max(self.budget, quote.amount))
        if len(self.quote_ids) < required:
            raise UserError(self.env._(
                "Voor werken van dit bedrag zijn minstens %(required)s offertes nodig (drempel van de AV: "
                "%(threshold)s). Er zijn er %(count)s.",
                required=required, count=len(self.quote_ids),
                threshold=self.association_id.works_quote_threshold))
        today = fields.Date.context_today(self)
        quote.state = "awarded"
        (self.quote_ids - quote).state = "rejected"
        self.write({"awarded_quote_id": quote.id, "award_date": today, "state": "awarded"})
        self._done_tasks(self.env._("Gegund aan %s.", quote.partner_id.name))
        self._task(
            self.env._("Opdrachtbevestiging opmaken voor %s", quote.partner_id.name), today,
            self.env._("Maak de opdrachtbevestiging en de weigeringen voor de andere aannemers op en verstuur ze zelf."))
        if self.planned_start:
            self._task(self.env._("Start van de werken opvolgen"), self.planned_start)
        message = self.env._("Gegund aan %(contractor)s voor %(amount)s.", contractor=quote.partner_id.name,
                             amount=format_amount(self.env, quote.amount, self.currency_id))
        if self.reserve_shortfall:
            message += " " + self.env._(
                "Opgelet: het reservekapitaal volstaat niet, er ontbreekt %s. Vraag een bijzondere bijdrage "
                "op of laat de AV de financiering aanpassen.",
                format_amount(self.env, self.reserve_shortfall, self.currency_id))
        self.message_post(body=message)
        return True

    def action_start(self):
        self._check_state("awarded")
        for works in self:
            works.write({"state": "in_progress", "date_start": works.date_start or fields.Date.context_today(self)})
            works.activity_ids.filtered(lambda a: a.summary == self.env._("Start van de werken opvolgen")).action_feedback(
                feedback=self.env._("Werken gestart."))
        return True

    def action_deliver(self):
        """Provisional delivery: the works are executed and leave the information for the notary."""
        self._check_state("in_progress")
        today = fields.Date.context_today(self)
        for works in self:
            delivery = works.provisional_delivery_date or today
            works.write({"state": "delivered", "provisional_delivery_date": delivery, "progress": 100})
            if works.decision_id:
                works.decision_id.works_done = True
            works._task(self.env._("Definitieve oplevering van %s", works.name),
                        delivery + relativedelta(months=FINAL_DELIVERY_MONTHS),
                        self.env._("Kijk na of de opmerkingen van de voorlopige oplevering opgelost zijn."))
            works.message_post(body=self.env._(
                "Voorlopig opgeleverd op %(date)s. De tienjarige aansprakelijkheid loopt tot %(end)s.",
                date=format_date(self.env, delivery), end=format_date(self.env, works.liability_end_date)))
        return True

    def action_close(self):
        self._check_state("delivered")
        for works in self:
            works.write({"state": "closed",
                         "final_delivery_date": works.final_delivery_date or fields.Date.context_today(self)})
            works._done_tasks(self.env._("Definitief opgeleverd."))
        return True

    def action_cancel(self):
        self._check_state("draft", "quotes", "awarded")
        if self.bill_ids.filtered(lambda m: m.state == "posted"):
            raise UserError(self.env._("Er zijn al geboekte facturen voor deze werken."))
        self._done_tasks(self.env._("Werken geannuleerd."))
        self.state = "cancelled"
        return True

    def action_reset_draft(self):
        self._check_state("cancelled")
        self.write({"state": "draft", "awarded_quote_id": False, "award_date": False})
        self.quote_ids.state = "received"
        return True

    def action_open_bills(self):
        self.ensure_one()
        self.association_id._check_company_selected()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Facturen %s", self.name),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(self.env.ref("account.view_in_invoice_bill_tree").id, "list"), (False, "form")],
            "domain": [("vme_works_id", "=", self.id)],
            "context": {"default_move_type": "in_invoice", "default_vme_works_id": self.id,
                        "default_partner_id": self.contractor_id.id,
                        "default_company_id": self.company_id.id},
        }

    def action_open_allocations(self):
        self.ensure_one()
        return self.bill_ids.filtered(lambda m: m.state == "posted").action_vme_open_allocations()


class VmeWorksQuote(models.Model):
    _name = "vme.works.quote"
    _description = "Offerte voor werken"
    _order = "works_id, amount, id"

    works_id = fields.Many2one("vme.works", string="Werkdossier", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="works_id.company_id", store=True)
    currency_id = fields.Many2one(related="works_id.currency_id")
    partner_id = fields.Many2one("res.partner", string="Aannemer", required=True)
    date = fields.Date(string="Datum offerte", default=fields.Date.context_today)
    reference = fields.Char(string="Referentie")
    amount = fields.Monetary(
        string="Bedrag incl. btw", required=True,
        help="Totaal met btw: de meeste VME's zijn niet btw-plichtig, dus de btw is een kost.")
    validity_date = fields.Date(string="Geldig tot")
    duration_weeks = fields.Integer(string="Duur (weken)")
    notes = fields.Text(string="Opmerkingen")
    attachment_ids = fields.Many2many("ir.attachment", string="Offerte (PDF)")
    state = fields.Selection(
        [("received", "Ontvangen"), ("awarded", "Gegund"), ("rejected", "Niet gekozen")],
        string="Status", required=True, default="received")
    budget_difference = fields.Monetary(
        string="Verschil met budget", compute="_compute_comparison",
        help="Positief: duurder dan het budget van de AV.")
    is_cheapest = fields.Boolean(string="Laagste prijs", compute="_compute_comparison")

    @api.depends("amount", "works_id.budget", "works_id.quote_ids.amount")
    def _compute_comparison(self):
        for quote in self:
            quote.budget_difference = quote.amount - quote.works_id.budget
            amounts = quote.works_id.quote_ids.mapped("amount")
            quote.is_cheapest = bool(amounts) and float_compare(quote.amount, min(amounts), 2) == 0

    def action_award(self):
        self.ensure_one()
        return self.works_id._award(self)


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_works_id = fields.Many2one(
        "vme.works", string="Werkdossier", compute="_compute_vme_works_id", store=True, readonly=False,
        index=True, copy=False, domain="[('company_id', '=', company_id), ('state', 'in', %s)]" % (BILLABLE_STATES,),
        help="Werken waarvoor deze factuur is. Wordt voorgesteld als de leverancier de aannemer is van gegunde werken.",
    )
    vme_works_financing = fields.Selection(related="vme_works_id.financing", string="Financiering werken")
    vme_reserve_move_id = fields.Many2one(
        "account.move", string="Aanwending reservekapitaal", readonly=True, copy=False,
        help="Boeking die deze factuur ten laste van het reservekapitaal brengt.")

    @api.depends("partner_id", "company_id", "move_type")
    def _compute_vme_works_id(self):
        for move in self:
            if move.vme_works_id or move.state != "draft" or move.move_type not in ("in_invoice", "in_refund") \
                    or not move.partner_id:
                continue
            works = self.env["vme.works"].sudo().search([
                ("company_id", "=", move.company_id.id), ("state", "in", BILLABLE_STATES),
                ("contractor_id", "=", move.partner_id.commercial_partner_id.id)])
            if len(works) == 1:
                move.vme_works_id = works.id

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered(lambda m: m.vme_works_id.financing == "reserve" and m.move_type in ("in_invoice", "in_refund")
                        and not m.vme_reserve_move_id)._vme_book_reserve_use()
        return posted

    def _vme_book_reserve_use(self):
        """Bring works bills to the charge of the reserve capital: debit the reserve, credit the costs.

        The costs of the bill stay distributed per owner (to show each share in the works), but
        the annual statement leaves them out of the working capital balance.
        """
        # LEGAL-CHECK: art. 3.86 §3 BW en KB 12 juli 2012 (minimum chart of accounts) - the reserve
        # capital pays for works; align the accounts and the treatment of non-deductible VAT.
        for move in self:
            company = move.company_id
            reserve_account = self.env["account.account"].with_company(company).search([
                ("company_ids", "in", company.id), ("code", "=", VME_FUND_ACCOUNTS["reserve"][0])], limit=1)
            journal = self.env["account.journal"].search(
                [("company_id", "=", company.id), ("type", "=", "general")], limit=1)
            if not reserve_account or not journal:
                raise UserError(self.env._("%s heeft geen rekening reservekapitaal of geen diverse dagboek.", company.name))
            lines = move._vme_distributable_lines()
            # amount_total_signed is negative for a bill and positive for a credit note.
            amount = -move.amount_total_signed
            parts = largest_remainder(amount, [abs(line.price_total) or 1.0 for line in lines], 2)
            by_account = {}
            for line, part in zip(lines, parts):
                by_account[line.account_id] = by_account.get(line.account_id, 0.0) + part
            label = self.env._("Aanwending reservekapitaal: %(bill)s (%(works)s)", bill=move.name, works=move.vme_works_id.name)

            def line_vals(account, balance):
                return fields.Command.create({
                    "account_id": account.id, "name": label,
                    "debit": balance if balance > 0 else 0.0, "credit": -balance if balance < 0 else 0.0})

            # Without the defaults of the bill form (default_vme_works_id, default_move_type, ...).
            entry = self.env["account.move"].with_context(clean_context(self.env.context)).with_company(company).create({
                "move_type": "entry",
                "journal_id": journal.id,
                "date": move.date,
                "ref": label,
                "line_ids": [line_vals(reserve_account, amount)]
                            + [line_vals(account, -part) for account, part in by_account.items()],
            })
            entry.action_post()
            move.vme_reserve_move_id = entry
            move.message_post(body=self.env._("Ten laste van het reservekapitaal geboekt (%s).", entry.name))

    def button_draft(self):
        reserve_moves = self.vme_reserve_move_id.filtered(lambda m: m.state == "posted")
        result = super().button_draft()
        if reserve_moves:
            reserve_moves._reverse_moves(
                [{"ref": self.env._("Terugdraaien %s", m.ref), "date": m.date} for m in reserve_moves], cancel=True)
            self.vme_reserve_move_id = False
        return result


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.depends("move_id.vme_works_id")
    def _compute_vme_key_id(self):
        # Lines of a works bill take the key of the works, unless a key was chosen by hand.
        works_lines = self.filtered(lambda line: line.move_id.vme_works_id.key_id and line.display_type == "product"
                                    and line.move_id.move_type in ("in_invoice", "in_refund"))
        for line in works_lines:
            if not line.vme_key_id or line.vme_key_id == line._vme_rule().key_id:
                line.vme_key_id = line.move_id.vme_works_id.key_id
        super(AccountMoveLine, self - works_lines)._compute_vme_key_id()
