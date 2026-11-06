"""Collection of overdue provisions and settlements: arrears overview, dossiers, reminders and costs."""
import base64
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import format_date

from .vme_provision_call import FUNDS
from .vme_access import check_not_auditor

AGING_BUCKETS = [
    ("0_30", "1-30 dagen"),
    ("31_60", "31-60 dagen"),
    ("61_90", "61-90 dagen"),
    ("90_plus", "Meer dan 90 dagen"),
]
LEVELS = [("1", "Vriendelijke herinnering"), ("2", "Aanmaning"), ("3", "Ingebrekestelling")]
LEVEL_TEMPLATES = {
    "1": "vme_belgie.mail_template_collection_reminder",
    "2": "vme_belgie.mail_template_collection_demand",
    "3": "vme_belgie.mail_template_collection_notice",
}
# Belgian PCMN: interest on receivables and other operating income.
INTEREST_ACCOUNT_CODE = "751000"
PENALTY_ACCOUNT_CODE = "743000"
# LEGAL-CHECK: wet 5 mei 1865 betreffende de lening tegen interest - the legal interest rate in civil
# matters is published every year in the Belgisch Staatsblad; update the parameter each January.
DEFAULT_LEGAL_INTEREST_RATE = 4.5


def aging_bucket(days):
    """Aging bucket of an amount that is `days` days overdue (days >= 1)."""
    if days <= 30:
        return "0_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "90_plus"


def legal_max_penalty(balance):
    """Highest lump-sum damages a consumer may be charged on an unpaid balance."""
    # LEGAL-CHECK: art. XIX.4 §2 WER (wet 4 mei 2023) - scale for consumer debts:
    # up to 150 euro: 20 euro; 150.01 to 500: 30 euro + 10% above 150; above 500: 65 euro + 5% above 500,
    # with a maximum of 2000 euro.
    if balance <= 0:
        return 0.0
    if balance <= 150:
        return 20.0
    if balance <= 500:
        return 30.0 + 0.10 * (balance - 150)
    return min(65.0 + 0.05 * (balance - 500), 2000.0)


def composer_action(record, subject, body, partners, attachment, context):
    """Mail composer for one record with a PDF attachment; the employee checks and sends the mail."""
    return {
        "type": "ir.actions.act_window",
        "res_model": "mail.compose.message",
        "view_mode": "form",
        "views": [(False, "form")],
        "target": "new",
        "context": {
            "default_model": record._name,
            "default_res_ids": record.ids,
            "default_composition_mode": "comment",
            "default_subject": subject,
            "default_body": body,
            "default_partner_ids": partners.ids,
            "default_attachment_ids": attachment.ids,
            **context,
        },
    }


def move_description(move):
    """Readable description of an open invoice: fund and provision call, or the costs of a dossier."""
    if move.vme_collection_id:
        return move.env._("Interest en schadevergoeding")
    if move.vme_provision_call_id:
        call = move.vme_provision_call_id
        return move.env._(
            "%(fund)s oproep %(number)s/%(total)s %(year)s", fund=dict(FUNDS).get(move.vme_fund, ""),
            number=call.number, total=call.budget_id.calls_per_year, year=call.budget_id.year)
    return move.ref or move.name


def render_attachment(record, report_ref, name):
    """Render one PDF on demand (about two seconds each) and attach it to the record."""
    content, _ext = record.env["ir.actions.report"]._render_qweb_pdf(report_ref, record.ids)
    return record.env["ir.attachment"].create({
        "name": name, "datas": base64.b64encode(content), "mimetype": "application/pdf",
        "res_model": record._name, "res_id": record.id,
    })


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    # Collection rules from the reglement van mede-eigendom, per VME.
    collection_first_reminder_days = fields.Integer(
        string="Eerste herinnering na (dagen)", default=0,
        help="Aantal dagen na de vervaldag waarna een vriendelijke herinnering voorgesteld wordt.")
    # LEGAL-CHECK: art. XIX.2 §1 WER - costs only after a free first reminder and a term of at least
    # 14 calendar days; we use the same term between every level.
    collection_interval_days = fields.Integer(
        string="Termijn tussen twee niveaus (dagen)", default=14,
        help="Termijn na een herinnering voor het volgende niveau voorgesteld wordt of kosten aangerekend worden.")
    collection_interest_rate = fields.Float(
        string="Nalatigheidsinterest (% per jaar)", default=8.0, digits=(5, 2),
        help="Volgens het reglement van mede-eigendom.")
    collection_penalty_percent = fields.Float(
        string="Forfaitaire schadevergoeding (% van het saldo)", default=10.0, digits=(5, 2))
    collection_penalty_min = fields.Float(string="Minimale schadevergoeding (EUR)", default=50.0, digits=(16, 2))
    collection_consumer_rules = fields.Boolean(
        string="Eigenaars als consument behandelen", default=True,
        help="Past de grenzen voor consumentenschulden toe (Boek XIX Wetboek van economisch recht): eerste "
             "herinnering kosteloos, kosten pas na 14 dagen, interest en schadevergoeding begrensd.")
    collection_effective_rate = fields.Float(
        string="Toegepaste interestvoet (%)", compute="_compute_collection_effective_rate", digits=(5, 2))
    collection_count = fields.Integer(string="Invorderingen", compute="_compute_collection_count")

    _check_collection_settings = models.Constraint(
        "CHECK (collection_interest_rate >= 0 AND collection_penalty_percent >= 0 AND collection_penalty_min >= 0 "
        "AND collection_interval_days >= 0 AND collection_first_reminder_days >= 0)",
        "De instellingen voor de invordering mogen niet negatief zijn.",
    )

    @api.depends("collection_interest_rate", "collection_consumer_rules")
    def _compute_collection_effective_rate(self):
        legal = self._get_legal_interest_rate()
        for vme in self:
            rate = vme.collection_interest_rate
            if vme.collection_consumer_rules:
                # LEGAL-CHECK: art. XIX.4 §1 WER - at most the legal interest rate plus 8 percentage points.
                rate = min(rate, legal + 8.0)
            vme.collection_effective_rate = rate

    def _compute_collection_count(self):
        counts = dict(self.env["vme.collection"]._read_group(
            [("association_id", "in", self.ids), ("state", "!=", "closed")], ["association_id"], ["__count"]))
        for vme in self:
            vme.collection_count = counts.get(vme, 0)

    @api.model
    def _get_legal_interest_rate(self):
        value = self.env["ir.config_parameter"].sudo().get_param("vme_belgie.legal_interest_rate")
        try:
            return float(value) if value else DEFAULT_LEGAL_INTEREST_RATE
        except ValueError:
            return DEFAULT_LEGAL_INTEREST_RATE

    def action_open_collections(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_collection_action")
        action["domain"] = [("association_id", "in", self.ids)]
        return action


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_collection_id = fields.Many2one(
        "vme.collection", string="Invorderingsdossier", index=True, ondelete="restrict", copy=False,
        help="Nalatigheidsinterest en schadevergoeding aangerekend in dit dossier.")


class VmeArrears(models.Model):
    """Overdue open receivables of all VMEs, one line per invoice (SQL view)."""
    _name = "vme.arrears"
    _description = "Achterstal"
    _auto = False
    _order = "date_maturity, id"

    association_id = fields.Many2one("vme.association", string="VME", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Eigenaar", readonly=True)
    collection_id = fields.Many2one("vme.collection", string="Dossier", readonly=True)
    # Names instead of a link to the invoice: it lives in the VME's company, which the user may not have selected.
    move_name = fields.Char(string="Factuur", readonly=True)
    payment_reference = fields.Char(string="Gestructureerde mededeling", readonly=True)
    fund = fields.Selection([("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")], string="Fonds", readonly=True)
    is_cost = fields.Boolean(string="Interest of schadevergoeding", readonly=True)
    date_maturity = fields.Date(string="Vervaldag", readonly=True)
    days_overdue = fields.Integer(string="Dagen te laat", readonly=True, aggregator="max")
    aging = fields.Selection(AGING_BUCKETS, string="Ouderdom", readonly=True)
    amount_residual = fields.Monetary(string="Openstaand", readonly=True)

    @property
    def _table_query(self):
        # Keep the buckets in line with aging_bucket().
        return """
            SELECT aml.id,
                   vme.id AS association_id,
                   aml.company_id,
                   aml.company_currency_id AS currency_id,
                   aml.partner_id,
                   col.id AS collection_id,
                   move.name AS move_name,
                   move.payment_reference,
                   move.vme_fund AS fund,
                   move.vme_collection_id IS NOT NULL AS is_cost,
                   aml.date_maturity,
                   CURRENT_DATE - aml.date_maturity AS days_overdue,
                   CASE WHEN CURRENT_DATE - aml.date_maturity <= 30 THEN '0_30'
                        WHEN CURRENT_DATE - aml.date_maturity <= 60 THEN '31_60'
                        WHEN CURRENT_DATE - aml.date_maturity <= 90 THEN '61_90'
                        ELSE '90_plus' END AS aging,
                   aml.amount_residual
              FROM account_move_line aml
              JOIN account_account account ON account.id = aml.account_id
              JOIN account_move move ON move.id = aml.move_id
              JOIN vme_association vme ON vme.company_id = aml.company_id
         LEFT JOIN vme_collection col ON col.association_id = vme.id AND col.partner_id = aml.partner_id
                                     AND col.state != 'closed'
             WHERE account.account_type = 'asset_receivable'
               AND aml.parent_state = 'posted'
               AND NOT aml.reconciled
               AND aml.amount_residual > 0
               AND aml.date_maturity < CURRENT_DATE
        """

    def action_refresh_collections(self):
        check_not_auditor(self.env)
        return self.env["vme.collection"].action_refresh()


class VmeCollection(models.Model):
    _name = "vme.collection"
    _description = "Invorderingsdossier"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "state, association_id, partner_id"

    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one("res.partner", string="Eigenaar", required=True, index=True)
    email = fields.Char(related="partner_id.email")
    lot_names = fields.Char(string="Kavels", compute="_compute_lot_names")
    state = fields.Selection(
        [("open", "Lopend"), ("forwarded", "Doorgestuurd"), ("closed", "Afgesloten")],
        string="Status", default="open", required=True, tracking=True)
    reminder_ids = fields.One2many("vme.collection.reminder", "collection_id", string="Herinneringen")
    level = fields.Selection(
        [("0", "Nog geen")] + LEVELS, string="Niveau", compute="_compute_level", store=True,
        help="Hoogste niveau dat al verstuurd is.")
    last_reminder_date = fields.Date(string="Laatste herinnering", compute="_compute_level", store=True)
    arrears_ids = fields.One2many("vme.arrears", "collection_id", string="Achterstallen")
    cost_move_ids = fields.One2many("account.move", "vme_collection_id", string="Aangerekende kosten")
    # A summary instead of the invoices themselves: they live in the VME's company.
    cost_summary = fields.Html(string="Kostenfacturen", compute="_compute_cost_summary", compute_sudo=True, sanitize=False)
    interest_until = fields.Date(string="Interest aangerekend tot", readonly=True)
    penalty_date = fields.Date(string="Schadevergoeding aangerekend op", readonly=True)
    forward_partner_id = fields.Many2one("res.partner", string="Advocaat of deurwaarder", tracking=True)
    forward_date = fields.Date(string="Doorgestuurd op", readonly=True)
    note = fields.Text(string="Notities")

    # Live figures on the date of today (or the context key vme_today, for tests).
    amount_due = fields.Monetary(string="Achterstallig", compute="_compute_status", compute_sudo=True)
    oldest_due_date = fields.Date(string="Oudste vervaldag", compute="_compute_status", compute_sudo=True)
    days_overdue = fields.Integer(string="Dagen te laat", compute="_compute_status", compute_sudo=True)
    aging = fields.Selection(AGING_BUCKETS, string="Ouderdom", compute="_compute_status", compute_sudo=True)
    next_level = fields.Selection(LEVELS, string="Voorgesteld niveau", compute="_compute_status", compute_sudo=True)
    next_step = fields.Char(string="Volgende stap", compute="_compute_status", compute_sudo=True)
    interest_preview = fields.Monetary(string="Interest nu", compute="_compute_costs_preview", compute_sudo=True)
    penalty_preview = fields.Monetary(string="Schadevergoeding nu", compute="_compute_costs_preview", compute_sudo=True)
    costs_blocked_reason = fields.Char(compute="_compute_costs_preview", compute_sudo=True)

    _unique_open_dossier = models.UniqueIndex(
        "(association_id, partner_id) WHERE state != 'closed'",
        "Deze eigenaar heeft al een lopend invorderingsdossier in deze VME.",
    )

    @api.depends("partner_id.name", "association_id.name")
    def _compute_display_name(self):
        for collection in self:
            collection.display_name = self.env._(
                "%(owner)s - %(vme)s", owner=collection.partner_id.name or "", vme=collection.association_id.name or "")

    @api.depends("reminder_ids.state", "reminder_ids.level", "reminder_ids.sent_date")
    def _compute_level(self):
        for collection in self:
            sent = collection.reminder_ids.filtered(lambda r: r.state == "sent")
            collection.level = max(sent.mapped("level"), default="0")
            collection.last_reminder_date = max(sent.mapped("sent_date"), default=False)

    def _compute_lot_names(self):
        for collection in self:
            ownerships = self.env["vme.ownership"].sudo().search([
                ("partner_id", "=", collection.partner_id.id),
                ("lot_id.association_id", "=", collection.association_id.id),
            ])
            collection.lot_names = ", ".join(sorted(set(ownerships.lot_id.mapped("name"))))

    @api.model
    def _get_today(self):
        return self.env.context.get("vme_today") or fields.Date.context_today(self)

    def _open_lines(self, today=None, overdue_only=True):
        """Open receivable lines of the owner in this VME; overdue only, plus costs of this dossier."""
        self.ensure_one()
        today = today or self._get_today()
        lines = self.env["account.move.line"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("account_id.account_type", "=", "asset_receivable"),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("amount_residual", ">", 0),
        ], order="date_maturity, id")
        if overdue_only:
            # Charged costs are due at once, so they appear on the next reminder of the same day.
            lines = lines.filtered(lambda l: l.date_maturity < today or l.move_id.vme_collection_id == self)
        return lines

    @api.depends_context("vme_today")
    def _compute_status(self):
        today = self._get_today()
        for collection in self:
            lines = collection._open_lines(today) if collection.company_id else self.env["account.move.line"]
            overdue = lines.filtered(lambda l: l.date_maturity < today)
            collection.amount_due = collection.currency_id.round(sum(lines.mapped("amount_residual")))
            collection.oldest_due_date = min(overdue.mapped("date_maturity"), default=False)
            collection.days_overdue = (today - collection.oldest_due_date).days if collection.oldest_due_date else 0
            collection.aging = aging_bucket(collection.days_overdue) if collection.days_overdue else False
            collection.next_level = collection._get_next_level(today, overdue)
            collection.next_step = collection._get_next_step(today, overdue)

    def _get_next_level(self, today, overdue):
        """Next reminder level to propose, or False: levels go up one by one, with a term in between."""
        self.ensure_one()
        vme = self.association_id
        if self.state != "open" or not overdue:
            return False
        if self.reminder_ids.filtered(lambda r: r.state == "draft"):
            return False
        oldest = min(overdue.mapped("date_maturity"))
        if self.level == "0":
            return "1" if (today - oldest).days >= max(vme.collection_first_reminder_days, 1) else False
        if self.level == "3":
            return False
        if (today - self.last_reminder_date).days < vme.collection_interval_days:
            return False
        return str(int(self.level) + 1)

    def _get_next_step(self, today, overdue):
        self.ensure_one()
        if self.state == "closed":
            return self.env._("Afgesloten")
        if self.state == "forwarded":
            return self.env._("Bij %s", self.forward_partner_id.name or self.env._("advocaat of deurwaarder"))
        if not overdue:
            return self.env._("Niets achterstallig")
        if self.reminder_ids.filtered(lambda r: r.state == "draft"):
            return self.env._("Concept nakijken en versturen")
        if self.next_level:
            return self.env._("%s voorstellen", dict(LEVELS)[self.next_level])
        if self.level == "3":
            if (today - self.last_reminder_date).days >= self.association_id.collection_interval_days:
                return self.env._("Doorsturen naar advocaat of deurwaarder")
        return self.env._("Termijn loopt")

    def _compute_cost_summary(self):
        for collection in self:
            moves = collection.cost_move_ids.filtered(lambda m: m.state == "posted")
            rows = [Markup("<tr><td>%s</td><td>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td></tr>") % (
                move.name, format_date(self.env, move.invoice_date),
                tools.format_amount(self.env, move.amount_total, move.currency_id),
                tools.format_amount(self.env, move.amount_residual, move.currency_id),
            ) for move in moves.sorted("invoice_date")]
            collection.cost_summary = Markup(
                "<table class='table table-sm'><thead><tr><th>%s</th><th>%s</th><th class='text-end'>%s</th>"
                "<th class='text-end'>%s</th></tr></thead><tbody>%s</tbody></table>") % (
                self.env._("Factuur"), self.env._("Datum"), self.env._("Bedrag"), self.env._("Nog open"),
                Markup("").join(rows)) if rows else False

    # Interest and lump-sum damages

    @api.depends_context("vme_today")
    def _compute_costs_preview(self):
        today = self._get_today()
        for collection in self:
            if not collection.company_id:
                collection.interest_preview = collection.penalty_preview = 0.0
                collection.costs_blocked_reason = False
                continue
            costs = collection._compute_costs(today)
            collection.interest_preview = sum(item["amount"] for item in costs["interest"])
            collection.penalty_preview = costs["penalty"]
            collection.costs_blocked_reason = costs["blocked"]

    def _costs_start_date(self):
        """First day costs may run, or False when no costs may be charged yet."""
        self.ensure_one()
        vme = self.association_id
        if not vme.collection_consumer_rules:
            return None
        # LEGAL-CHECK: art. XIX.2 §1 WER - the first reminder is free; interest and damages only run
        # from the end of a term of at least 14 days after it was sent. Check whether interest may
        # run from the due date instead when the reglement van mede-eigendom says so.
        first = self.reminder_ids.filtered(lambda r: r.state == "sent" and r.level == "1").sorted("sent_date")[:1]
        if not first:
            return False
        return first.sent_date + timedelta(days=vme.collection_interval_days)

    def _compute_costs(self, today):
        """Interest per open invoice and the lump-sum damages that can be charged on `today`.

        Interest: open amount x rate x days / 365, from the due date (or the end of the consumer term,
        or the date up to which interest was already charged) until today. Damages: once per dossier,
        a percentage of the open principal with a minimum, capped by the consumer scale.
        Costs already charged in a dossier never bear interest themselves.
        """
        self.ensure_one()
        vme = self.association_id
        currency = self.currency_id
        result = {"interest": [], "penalty": 0.0, "blocked": False}
        lines = self._open_lines(today).filtered(lambda l: not l.move_id.vme_collection_id and l.date_maturity < today)
        if not lines:
            return result
        start_min = self._costs_start_date()
        if start_min is False:
            result["blocked"] = self.env._("Eerst een kosteloze vriendelijke herinnering versturen.")
            return result
        if start_min and start_min > today:
            result["blocked"] = self.env._("Kosten kunnen pas vanaf %s.", format_date(self.env, start_min))
            return result
        rate = vme.collection_effective_rate
        for line in lines:
            start = max(d for d in (line.date_maturity, start_min, self.interest_until) if d)
            days = (today - start).days
            if days <= 0 or not rate:
                continue
            # LEGAL-CHECK: reglement van mede-eigendom (art. 3.85 BW) - simple interest per year of 365 days.
            amount = currency.round(line.amount_residual * rate / 100 * days / 365)
            if amount:
                result["interest"].append({
                    "line": line, "days": days, "start": start, "rate": rate, "amount": amount,
                })
        if not self.penalty_date:
            principal = sum(lines.mapped("amount_residual"))
            penalty = max(principal * vme.collection_penalty_percent / 100, vme.collection_penalty_min)
            if vme.collection_consumer_rules:
                penalty = min(penalty, legal_max_penalty(principal))
            result["penalty"] = currency.round(penalty)
        return result

    def action_charge_costs(self):
        check_not_auditor(self.env)
        self._charge_costs()

    def _charge_costs(self):
        """Book interest and damages on the owner as an invoice in the VME's company; returns the invoices."""
        today = self._get_today()
        invoices = self.env["account.move"].sudo()
        for collection in self:
            costs = collection._compute_costs(today)
            if costs["blocked"]:
                raise UserError(costs["blocked"])
            if not costs["interest"] and not costs["penalty"]:
                raise UserError(self.env._("Er zijn geen kosten om aan te rekenen voor %s.", collection.display_name))
            invoice = collection._create_cost_invoice(costs, today)
            invoices |= invoice
            vals = {"interest_until": today}
            if costs["penalty"]:
                vals["penalty_date"] = today
            collection.write(vals)
            collection.reminder_ids.filtered(lambda r: r.state == "draft")._update_content()
            collection.message_post(body=self.env._(
                "Kosten aangerekend: interest %(interest)s, schadevergoeding %(penalty)s (%(invoice)s).",
                interest=tools.format_amount(self.env, sum(i["amount"] for i in costs["interest"]), collection.currency_id),
                penalty=tools.format_amount(self.env, costs["penalty"], collection.currency_id),
                invoice=invoice.name,
            ))
        return invoices

    def _create_cost_invoice(self, costs, today):
        self.ensure_one()
        company = self.company_id
        Account = self.env["account.account"].sudo().with_company(company)
        accounts = {
            code: Account.search([("company_ids", "in", company.id), ("code", "=", code)], limit=1)
            for code in (INTEREST_ACCOUNT_CODE, PENALTY_ACCOUNT_CODE)
        }
        journal = self.env["account.journal"].sudo().search([("company_id", "=", company.id), ("type", "=", "sale")], limit=1)
        if not journal or not all(accounts.values()):
            raise UserError(self.env._("Het rekeningstelsel van %s is niet volledig.", self.association_id.name))
        lines = [Command.create({
            "name": self.env._(
                "Nalatigheidsinterest %(rate)s%% per jaar op %(invoice)s, %(days)s dagen vanaf %(start)s",
                rate=f"{item['rate']:g}", invoice=item["line"].move_id.name, days=item["days"],
                start=format_date(self.env, item["start"]),
            ),
            "quantity": 1,
            "price_unit": item["amount"],
            "account_id": accounts[INTEREST_ACCOUNT_CODE].id,
            "tax_ids": [Command.clear()],
        }) for item in costs["interest"]]
        if costs["penalty"]:
            lines.append(Command.create({
                "name": self.env._("Forfaitaire schadevergoeding volgens het reglement van mede-eigendom"),
                "quantity": 1,
                "price_unit": costs["penalty"],
                "account_id": accounts[PENALTY_ACCOUNT_CODE].id,
                "tax_ids": [Command.clear()],
            }))
        invoice = self.env["account.move"].sudo().with_company(company).create({
            "move_type": "out_invoice",
            "journal_id": journal.id,
            "partner_id": self.partner_id.id,
            "invoice_date": today,
            "invoice_date_due": today,
            # Costs are income of the working capital, paid to its bank account.
            "vme_fund": "working",
            "vme_collection_id": self.id,
            "invoice_line_ids": lines,
        })
        invoice.action_post()
        return invoice

    # Dossiers and reminder proposals

    @api.model
    def _refresh(self, today=None):
        """Open a dossier per owner with arrears, close paid ones and propose the next reminders.

        Never sends anything: reminders are created as drafts.
        """
        today = today or self._get_today()
        vmes = self.env["vme.association"].sudo().search([("company_id", "!=", False)])
        by_company = {vme.company_id.id: vme for vme in vmes}
        groups = self.env["account.move.line"].sudo()._read_group([
            ("company_id", "in", list(by_company)),
            ("account_id.account_type", "=", "asset_receivable"),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("amount_residual", ">", 0),
            ("date_maturity", "<", today),
            ("partner_id", "!=", False),
        ], ["company_id", "partner_id"])
        Collection = self.sudo()
        existing = {(c.association_id.id, c.partner_id.id): c for c in Collection.search([("state", "!=", "closed")])}
        new = Collection
        for company, partner in groups:
            vme = by_company[company.id]
            if (vme.id, partner.id) not in existing:
                new |= Collection.create({"association_id": vme.id, "partner_id": partner.id})
        collections = Collection.search([("state", "!=", "closed")])
        paid = collections.filtered(lambda c: not c._open_lines(today, overdue_only=False))
        for collection in paid:
            collection.reminder_ids.filtered(lambda r: r.state == "draft").write({"state": "cancel"})
            collection.state = "closed"
            collection.message_post(body=self.env._("Alles betaald: dossier afgesloten."))
        reminders = self.env["vme.collection.reminder"]
        for collection in (collections - paid).filtered(lambda c: c.state == "open").with_context(vme_today=today):
            if collection.next_level:
                reminders |= collection._create_reminder(collection.next_level, today)
        return new, paid, reminders

    def _create_reminder(self, level, today):
        self.ensure_one()
        sent = self.reminder_ids.filtered(lambda r: r.state == "sent")
        reminder = self.env["vme.collection.reminder"].sudo().create({
            "collection_id": self.id,
            "level": level,
            "date": today,
            "first_reminder_date": max(sent.filtered(lambda r: r.level == "1").mapped("sent_date"), default=False),
            "second_reminder_date": max(sent.filtered(lambda r: r.level == "2").mapped("sent_date"), default=False),
        })
        reminder._update_content()
        return reminder

    @api.model
    def action_refresh(self):
        check_not_auditor(self.env)
        new, paid, reminders = self._refresh()
        message = self.env._(
            "%(new)s nieuwe dossiers, %(paid)s afgesloten, %(drafts)s herinneringen klaar om na te kijken.",
            new=len(new), paid=len(paid), drafts=len(reminders),
        )
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_collection_reminder_action")
        action["views"] = [(False, "list"), (False, "form")]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Invordering bijgewerkt"),
                "message": message,
                "type": "success",
                "next": action,
            },
        }

    @api.model
    def _cron_refresh(self):
        self._refresh()

    def action_propose_reminder(self):
        check_not_auditor(self.env)
        self.ensure_one()
        today = self._get_today()
        if not self.next_level:
            raise UserError(self.env._("Er is nu geen nieuw niveau voor te stellen: %s.", self.next_step))
        reminder = self._create_reminder(self.next_level, today)
        return reminder._get_form_action()

    def action_open_reminders(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_collection_reminder_action")
        action["domain"] = [("collection_id", "in", self.ids)]
        action["context"] = {}
        return action

    def action_reopen(self):
        self.write({"state": "open"})

    def action_close(self):
        self.reminder_ids.filtered(lambda r: r.state == "draft").write({"state": "cancel"})
        self.write({"state": "closed"})

    # Forwarding to a lawyer or bailiff

    def _get_overview_data(self):
        """Data for the PDF overview, read as sudo: the invoices live in the VME's company."""
        self.ensure_one()
        today = self._get_today()
        lines = self._open_lines(today, overdue_only=False)
        return {
            "today": today,
            "lines": [{
                "name": line.move_id.name,
                "description": move_description(line.move_id),
                "invoice_date": line.move_id.invoice_date,
                "date_maturity": line.date_maturity,
                "days": max((today - line.date_maturity).days, 0),
                "reference": line.move_id.payment_reference,
                "amount": line.amount_residual,
            } for line in lines],
            "total": sum(lines.mapped("amount_residual")),
            "costs": [{
                "name": move.name, "date": move.invoice_date, "amount": move.amount_total,
                "residual": move.amount_residual,
            } for move in self.sudo().cost_move_ids.filtered(lambda m: m.state == "posted")],
        }

    def action_forward(self):
        """Open the mail composer to the lawyer or bailiff with the PDF overview; nothing is sent by itself."""
        check_not_auditor(self.env)
        self.ensure_one()
        if not self.forward_partner_id:
            raise UserError(self.env._("Kies eerst de advocaat of deurwaarder."))
        if "3" not in self.reminder_ids.filtered(lambda r: r.state == "sent").mapped("level"):
            raise UserError(self.env._("Verstuur eerst een ingebrekestelling voor u het dossier doorstuurt."))
        attachment = render_attachment(
            self, "vme_belgie.action_report_collection_overview",
            self.env._("Invorderingsdossier %s.pdf", self.display_name))
        body = self.env._(
            "<p>Geachte,</p><p>Namens de VME %(vme)s vragen wij u de invordering over te nemen van de achterstallen "
            "van %(owner)s (kavels %(lots)s). Het openstaande saldo bedraagt %(amount)s. In bijlage vindt u het "
            "overzicht met de facturen, de herinneringen en de aangerekende kosten.</p>"
            "<p>Met vriendelijke groeten,<br/>De syndicus</p>",
            vme=self.association_id.name, owner=self.partner_id.name, lots=self.lot_names or "-",
            amount=tools.format_amount(self.env, self.amount_due, self.currency_id),
        )
        return composer_action(
            self, subject=self.env._("Invordering %s", self.display_name), body=body,
            partners=self.forward_partner_id, attachment=attachment,
            context={"mark_collection_as_forwarded": True},
        )

    def message_post(self, **kwargs):
        # Only the composer opened from "Doorsturen" marks a dossier as forwarded.
        if self.env.context.get("mark_collection_as_forwarded"):
            self.filtered(lambda c: c.state == "open").write({
                "state": "forwarded", "forward_date": fields.Date.context_today(self)})
        return super().message_post(**kwargs)

    def action_print_overview(self):
        return self.env.ref("vme_belgie.action_report_collection_overview").report_action(self)


class VmeCollectionReminder(models.Model):
    _name = "vme.collection.reminder"
    _description = "Herinnering voor achterstallen"
    _inherit = ["mail.thread"]
    _order = "date desc, level, id"

    collection_id = fields.Many2one("vme.collection", string="Dossier", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="collection_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="collection_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one(related="collection_id.partner_id", store=True, string="Eigenaar")
    email = fields.Char(related="partner_id.email")
    level = fields.Selection(LEVELS, string="Niveau", required=True)
    state = fields.Selection(
        [("draft", "Concept"), ("sent", "Verstuurd"), ("cancel", "Geannuleerd")],
        string="Status", default="draft", required=True, tracking=True)
    date = fields.Date(string="Opgemaakt op", required=True, default=fields.Date.context_today)
    sent_date = fields.Date(string="Verstuurd op", readonly=True)
    first_reminder_date = fields.Date(string="Herinnering van")
    second_reminder_date = fields.Date(string="Aanmaning van")
    line_ids = fields.One2many("vme.collection.reminder.line", "reminder_id", string="Openstaande bedragen")
    amount_due = fields.Monetary(string="Openstaand saldo", readonly=True)
    interest_rate = fields.Float(string="Interestvoet", digits=(5, 2), readonly=True)
    subject = fields.Char(string="Onderwerp")
    body_html = fields.Html(string="Tekst", sanitize_style=True)

    @api.depends("level", "partner_id.name")
    def _compute_display_name(self):
        levels = dict(LEVELS)
        for reminder in self:
            reminder.display_name = self.env._(
                "%(level)s %(owner)s", level=levels.get(reminder.level, ""), owner=reminder.partner_id.name or "")

    def _update_content(self):
        """Snapshot the open amounts and render the Dutch template of the level (fast, no PDF)."""
        for reminder in self:
            collection = reminder.collection_id
            lines = collection._open_lines(reminder.date)
            reminder.write({
                "line_ids": [Command.clear()] + [Command.create({
                    "move_name": line.move_id.name,
                    "description": move_description(line.move_id),
                    "fund": line.move_id.vme_fund,
                    "date_maturity": line.date_maturity,
                    "payment_reference": line.move_id.payment_reference,
                    "bank_account": line.move_id.partner_bank_id.acc_number,
                    "amount": line.amount_residual,
                }) for line in lines],
                "amount_due": reminder.currency_id.round(sum(lines.mapped("amount_residual"))),
                "interest_rate": collection.association_id.collection_effective_rate,
            })
            template = self.env.ref(LEVEL_TEMPLATES[reminder.level]).sudo()
            reminder.write({
                "subject": template._render_field("subject", reminder.ids)[reminder.id],
                "body_html": template._render_field("body_html", reminder.ids)[reminder.id],
            })

    def action_update(self):
        check_not_auditor(self.env)
        if self.filtered(lambda r: r.state != "draft"):
            raise UserError(self.env._("Alleen concepten kunnen bijgewerkt worden."))
        self._update_content()

    def action_open_composer(self):
        """Render the letter now and open the mail composer; the employee checks and sends it."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(self.env._("Deze herinnering is al verstuurd of geannuleerd."))
        if not self.email:
            raise UserError(self.env._("%s heeft geen e-mailadres: druk de brief af en verstuur ze per post.",
                                       self.partner_id.name))
        attachment = render_attachment(self, "vme_belgie.action_report_collection_reminder", f"{self.subject}.pdf")
        return composer_action(
            self, subject=self.subject, body=self.body_html, partners=self.partner_id, attachment=attachment,
            context={"mark_reminder_as_sent": True},
        )

    def message_post(self, **kwargs):
        # Only the composer opened from "Versturen" marks a reminder as sent.
        if self.env.context.get("mark_reminder_as_sent"):
            self.filtered(lambda r: r.state == "draft").action_mark_sent()
        return super().message_post(**kwargs)

    def action_mark_sent(self):
        drafts = self.filtered(lambda r: r.state == "draft")
        if drafts != self:
            raise UserError(self.env._("Alleen concepten kunnen als verstuurd gemarkeerd worden."))
        today = self.env["vme.collection"]._get_today()
        self.write({"state": "sent", "sent_date": today})
        for reminder in self:
            reminder.collection_id.message_post(body=self.env._(
                "%(level)s verstuurd (openstaand %(amount)s).", level=dict(LEVELS)[reminder.level],
                amount=tools.format_amount(self.env, reminder.amount_due, reminder.currency_id)))

    def action_cancel(self):
        self.filtered(lambda r: r.state == "draft").write({"state": "cancel"})

    def action_print(self):
        return self.env.ref("vme_belgie.action_report_collection_reminder").report_action(self)

    def _get_form_action(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    @api.constrains("level", "collection_id")
    def _check_one_draft(self):
        for reminder in self:
            drafts = reminder.collection_id.reminder_ids.filtered(lambda r: r.state == "draft")
            if len(drafts) > 1:
                raise ValidationError(self.env._("Er is al een concept voor %s.", reminder.collection_id.display_name))


class VmeCollectionReminderLine(models.Model):
    _name = "vme.collection.reminder.line"
    _description = "Openstaand bedrag op een herinnering"
    _order = "date_maturity, id"

    reminder_id = fields.Many2one("vme.collection.reminder", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="reminder_id.currency_id")
    move_name = fields.Char(string="Factuur")
    description = fields.Char(string="Omschrijving")
    fund = fields.Selection([("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")], string="Fonds")
    date_maturity = fields.Date(string="Vervaldag")
    payment_reference = fields.Char(string="Gestructureerde mededeling")
    bank_account = fields.Char(string="Rekening")
    amount = fields.Monetary(string="Openstaand")
