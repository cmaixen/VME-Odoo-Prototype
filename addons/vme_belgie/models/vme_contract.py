from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from .cron_tools import run_per_record

CONTRACT_TYPES = [
    ("maintenance", "Onderhoud"),
    ("cleaning", "Schoonmaak"),
    ("insurance", "Verzekering"),
    ("energy", "Energie"),
    ("elevator", "Lift"),
    ("staff", "Conciërge en personeel"),
    ("other", "Andere"),
]

# Default notice period in months per contract type; editable per contract.
DEFAULT_NOTICE_MONTHS = {
    "maintenance": 3,
    "cleaning": 3,
    # LEGAL-CHECK: art. 85 Wet van 4 april 2014 betreffende de verzekeringen - an insurance
    # contract runs for at most one year, is renewed tacitly and can be cancelled at least
    # three months before its due date.
    "insurance": 3,
    # LEGAL-CHECK: art. 18 §2/3 Elektriciteitswet 29 april 1999 - households and small
    # businesses can cancel an energy contract at any time with one month notice (also in the
    # regional energy decrees); whether that applies to a VME is to be confirmed.
    "energy": 1,
    "elevator": 6,
    # LEGAL-CHECK: art. 37/2 Arbeidsovereenkomstenwet 3 juli 1978 - the notice period of an
    # employment contract depends on seniority and is not computed here; the default is for
    # the contract with the social secretariat.
    "staff": 3,
    "other": 3,
}

# LEGAL-CHECK: art. 3.89 §5 BW - the syndic evaluates the contracts for regular supplies of
# goods and services every year and submits that evaluation to the general assembly
# (numbering of the point to be confirmed).
EVALUATION_INTERVAL_MONTHS = 12

# Days before the notice deadline and the evaluation date at which the responsible user gets a task.
NOTICE_LEAD_DAYS = 60
EVALUATION_LEAD_DAYS = 30

NOTICE_STATES = [
    ("passed", "Opzegtermijn verstreken"),
    ("due_30", "Binnen 30 dagen"),
    ("due_60", "Binnen 60 dagen"),
    ("due_90", "Binnen 90 dagen"),
    ("ok", "Ruim op tijd"),
    ("none", "Geen opzegtermijn"),
]


def add_months_to_period_end(period_end, months):
    """Last day of a period of `months` that starts the day after period_end.

    Counting from the next day keeps month-end periods at the month end: a period up to
    28 February 2027 renewed for a year ends on 29 February 2028.
    """
    return period_end + timedelta(days=1) + relativedelta(months=months) - timedelta(days=1)


def notice_deadline(period_end, notice_months):
    """Last day on which notice can reach the supplier for a period ending on period_end.

    The notice period counts back from the day the next period would start: three months
    before a period ending on 31 March is 31 December, before 28 February it is 30 November.
    """
    if not period_end or not notice_months:
        return False
    return add_months_to_period_end(period_end, -notice_months)


def notice_state(deadline, today):
    if not deadline:
        return "none"
    days = (deadline - today).days
    if days < 0:
        return "passed"
    for limit, state in ((30, "due_30"), (60, "due_60"), (90, "due_90")):
        if days <= limit:
            return state
    return "ok"


class VmeContract(models.Model):
    _name = "vme.contract"
    _description = "Contract van een VME"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "association_id, notice_deadline, name"

    name = fields.Char(string="Omschrijving", required=True, tracking=True)
    reference = fields.Char(string="Contractnummer of polis", tracking=True)
    active = fields.Boolean(string="Actief", default=True)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    contract_type = fields.Selection(CONTRACT_TYPES, string="Soort", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Leverancier", required=True, index=True, tracking=True,
        help="Bij een conciërge: het sociaal secretariaat dat de loonkosten factureert.",
    )
    installation_id = fields.Many2one(
        "vme.installation", string="Installatie", index=True,
        domain="[('association_id', '=', association_id)]",
        help="Optioneel: de installatie waarvoor dit een onderhoudscontract is.",
    )
    responsible_user_id = fields.Many2one(
        "res.users", string="Verantwoordelijke", default=lambda self: self.env.user, tracking=True
    )
    state = fields.Selection(
        [("running", "Lopend"), ("notice_given", "Opgezegd"), ("ended", "Beëindigd")],
        string="Status", required=True, default="running", tracking=True,
    )

    date_start = fields.Date(string="Begindatum")
    date_end = fields.Date(
        string="Einde huidige periode", tracking=True,
        help="Leeg voor een contract van onbepaalde duur zonder vaste vervaldag.",
    )
    auto_renew = fields.Boolean(string="Stilzwijgende verlenging", default=True, tracking=True)
    renewal_months = fields.Integer(string="Verlenging met (maanden)", default=12, aggregator=False)
    notice_period_months = fields.Integer(
        string="Opzegtermijn (maanden)",
        compute="_compute_notice_period_months", store=True, readonly=False, aggregator=False,
    )
    notice_deadline = fields.Date(
        string="Opzeggen uiterlijk op", compute="_compute_notice_deadline", store=True,
        help="De laatste dag waarop de opzeg bij de leverancier moet zijn om het contract op het "
             "einde van de huidige periode te laten stoppen.",
    )
    notice_state = fields.Selection(NOTICE_STATES, string="Status opzegtermijn", compute="_compute_notice_state")
    notice_given_date = fields.Date(string="Opgezegd op", copy=False, tracking=True)

    annual_amount = fields.Monetary(string="Geraamde jaarkost", currency_field="currency_id")
    billed_this_year = fields.Monetary(
        string="Gefactureerd dit jaar", currency_field="currency_id", compute="_compute_billed_this_year",
        help="Geboekte facturen van deze leverancier in deze VME sinds 1 januari.",
    )
    distribution_rule_id = fields.Many2one(
        "vme.distribution.rule", string="Verdeelregel", compute="_compute_distribution_rule_id",
        help="De verdeelregel van deze leverancier: zijn facturen worden met die sleutel verdeeld.",
    )
    distribution_key_id = fields.Many2one(
        "vme.key", string="Verdeelsleutel", compute="_compute_distribution_rule_id")
    distribution_account_id = fields.Many2one(
        "account.account", string="Kostenrekening", compute="_compute_distribution_rule_id")

    evaluation_ids = fields.One2many("vme.contract.evaluation", "contract_id", string="Evaluaties")
    last_evaluation_date = fields.Date(
        string="Laatste evaluatie", compute="_compute_evaluation_dates", store=True
    )
    next_evaluation_date = fields.Date(
        string="Volgende evaluatie", compute="_compute_evaluation_dates", store=True
    )
    note = fields.Html(string="Notities")

    # Dates for which a task was already created, so the cron never makes it twice.
    activity_notice_deadline = fields.Date(copy=False)
    activity_evaluation_date = fields.Date(copy=False)

    @api.depends("contract_type")
    def _compute_notice_period_months(self):
        for contract in self:
            if not contract.notice_period_months:
                contract.notice_period_months = DEFAULT_NOTICE_MONTHS.get(contract.contract_type, 3)

    @api.depends("date_end", "notice_period_months")
    def _compute_notice_deadline(self):
        for contract in self:
            contract.notice_deadline = notice_deadline(contract.date_end, contract.notice_period_months)

    @api.depends("notice_deadline", "state")
    def _compute_notice_state(self):
        today = fields.Date.context_today(self)
        for contract in self:
            contract.notice_state = (
                notice_state(contract.notice_deadline, today) if contract.state == "running" else "none"
            )

    @api.depends("evaluation_ids.date", "date_start")
    def _compute_evaluation_dates(self):
        for contract in self:
            last = max(contract.evaluation_ids.filtered("date").mapped("date"), default=False)
            contract.last_evaluation_date = last
            base = last or contract.date_start
            contract.next_evaluation_date = base + relativedelta(months=EVALUATION_INTERVAL_MONTHS) if base else False

    @api.depends("company_id", "partner_id")
    def _compute_distribution_rule_id(self):
        Rule = self.env["vme.distribution.rule"]
        for contract in self:
            rule = Rule._find_rule(contract.company_id, contract.partner_id)
            contract.distribution_rule_id = rule
            contract.distribution_key_id = rule.key_id
            contract.distribution_account_id = rule.account_id

    def _bills_domain(self, date_from=None):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("commercial_partner_id", "=", self.partner_id.commercial_partner_id.id),
        ]
        if date_from:
            domain += [("state", "=", "posted"), ("invoice_date", ">=", date_from)]
        return domain

    @api.depends("company_id", "partner_id")
    def _compute_billed_this_year(self):
        year_start = date(fields.Date.context_today(self).year, 1, 1)
        for contract in self:
            if not contract.partner_id or not contract.company_id:
                contract.billed_this_year = 0
                continue
            # The bills live in the company of the VME, which is often not the active company.
            bills = self.env["account.move"].sudo().search(contract._bills_domain(year_start))
            contract.billed_this_year = sum(
                bill.amount_total if bill.move_type == "in_invoice" else -bill.amount_total for bill in bills
            )

    def action_open_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Facturen van %s", self.partner_id.name),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": self._bills_domain(),
            "context": {"default_move_type": "in_invoice", "default_partner_id": self.partner_id.id,
                        "allowed_company_ids": self.company_id.ids},
        }

    def action_give_notice(self):
        """Record that the syndic sent the notice; nothing is sent from here."""
        today = fields.Date.context_today(self)
        for contract in self:
            if contract.state != "running":
                raise UserError(self.env._("Alleen een lopend contract kan opgezegd worden."))
            contract.write({"state": "notice_given", "notice_given_date": today})
            if contract.notice_deadline and today > contract.notice_deadline:
                body = self.env._(
                    "Opzeg geregistreerd op %(today)s, na de opzegtermijn (%(deadline)s). Vraag de leverancier "
                    "te bevestigen of het contract op %(end)s eindigt of nog een periode doorloopt.",
                    today=format_date(self.env, today), deadline=format_date(self.env, contract.notice_deadline),
                    end=format_date(self.env, contract.date_end),
                )
            else:
                body = self.env._(
                    "Opzeg geregistreerd op %(today)s; het contract eindigt op %(end)s.",
                    today=format_date(self.env, today),
                    end=format_date(self.env, contract.date_end) if contract.date_end else self.env._("de afgesproken datum"),
                )
            contract.message_post(body=body)
            contract._notice_activities().action_feedback(feedback=self.env._("Opzeg geregistreerd."))

    def _notice_activities(self):
        """Open tasks the cron made for the notice deadline of this contract."""
        self.ensure_one()
        todo = self.env.ref("mail.mail_activity_data_todo")
        return self.activity_ids.filtered(
            lambda a: a.activity_type_id == todo and a.date_deadline == self.activity_notice_deadline
            and a.summary and a.summary.startswith(self.env._("Opzeggen of verlengen"))
        )

    def action_end(self):
        self.write({"state": "ended"})

    def action_reopen(self):
        self.write({"state": "running", "notice_given_date": False})

    @api.model
    def _cron_schedule_contract_activities(self):
        """Renew or end contracts whose period is over, then create one task per notice deadline
        (60 days ahead) and per yearly evaluation (30 days ahead)."""
        today = fields.Date.context_today(self)
        self._roll_over_expired_contracts(today)
        todo = self.env.ref("mail.mail_activity_data_todo")

        notice_limit = today + relativedelta(days=NOTICE_LEAD_DAYS)
        evaluation_limit = today + relativedelta(days=EVALUATION_LEAD_DAYS)
        # Only what still needs a task, so a cron that ran out of time continues with the rest (K-D18).
        to_notice = self.search([
            ("state", "=", "running"), ("notice_deadline", ">=", today), ("notice_deadline", "<=", notice_limit),
        ]).filtered(lambda c: c.activity_notice_deadline != c.notice_deadline)
        to_evaluate = self.search([("state", "=", "running"), ("next_evaluation_date", "<=", evaluation_limit)]).filtered(
            lambda c: c.activity_evaluation_date != c.next_evaluation_date)
        run_per_record(to_notice | to_evaluate, lambda contract: contract._schedule_due_activities(today, todo))

    def _schedule_due_activities(self, today, todo):
        """The notice and evaluation tasks this contract still needs; one record of the daily cron."""
        self.ensure_one()
        contract = self
        if contract.activity_notice_deadline != contract.notice_deadline and contract.notice_deadline \
                and today <= contract.notice_deadline <= today + relativedelta(days=NOTICE_LEAD_DAYS):
            next_end = add_months_to_period_end(contract.date_end, contract.renewal_months) \
                if contract.auto_renew and contract.renewal_months else False
            contract.activity_schedule(
                activity_type_id=todo.id,
                date_deadline=contract.notice_deadline,
                summary=self.env._("Opzeggen of verlengen: %s", contract.name),
                note=self.env._(
                    "Wil %(vme)s het contract %(contract)s met %(partner)s niet voortzetten, dan moet de opzeg "
                    "uiterlijk op %(deadline)s bij de leverancier zijn (opzegtermijn %(months)s maanden). %(after)s",
                    vme=contract.association_id.name, contract=contract.name, partner=contract.partner_id.name,
                    deadline=format_date(self.env, contract.notice_deadline), months=contract.notice_period_months,
                    after=self.env._("Anders loopt het door tot %s.", format_date(self.env, next_end)) if next_end
                    else self.env._("Anders eindigt het op %s.", format_date(self.env, contract.date_end)),
                ),
                user_id=(contract.responsible_user_id or contract.association_id._vme_task_user()).id,
            )
            contract.activity_notice_deadline = contract.notice_deadline
        if contract.activity_evaluation_date != contract.next_evaluation_date and contract.next_evaluation_date \
                and contract.next_evaluation_date <= today + relativedelta(days=EVALUATION_LEAD_DAYS):
            contract.activity_schedule(
                activity_type_id=todo.id,
                date_deadline=max(contract.next_evaluation_date, today),
                summary=self.env._("Jaarlijkse evaluatie: %s", contract.name),
                note=self.env._(
                    "Evalueer het contract %(contract)s (%(vme)s) en leg de evaluatie voor op de volgende "
                    "algemene vergadering.", contract=contract.name, vme=contract.association_id.name,
                ),
                user_id=(contract.responsible_user_id or contract.association_id._vme_task_user()).id,
            )
            contract.activity_evaluation_date = contract.next_evaluation_date

    def _roll_over_expired_contracts(self, today):
        for contract in self.search([("state", "in", ("running", "notice_given")), ("date_end", "<", today)]):
            if contract.state == "running" and contract.auto_renew and contract.renewal_months > 0:
                new_end = contract.date_end
                while new_end < today:
                    new_end = add_months_to_period_end(new_end, contract.renewal_months)
                contract.message_post(body=self.env._(
                    "Stilzwijgend verlengd tot %(end)s; opzeggen kan nu tot %(deadline)s.",
                    end=format_date(self.env, new_end),
                    deadline=format_date(self.env, notice_deadline(new_end, contract.notice_period_months)),
                ))
                contract.date_end = new_end
            else:
                contract.state = "ended"
                contract.message_post(body=self.env._(
                    "Beëindigd op %s.", format_date(self.env, contract.date_end)))


class VmeContractEvaluation(models.Model):
    _name = "vme.contract.evaluation"
    _description = "Jaarlijkse evaluatie van een contract"
    _order = "date desc, id desc"

    contract_id = fields.Many2one("vme.contract", string="Contract", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="contract_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="contract_id.company_id", store=True)
    date = fields.Date(string="Datum", required=True, default=fields.Date.context_today)
    user_id = fields.Many2one("res.users", string="Door", default=lambda self: self.env.user)
    rating = fields.Selection(
        [("good", "Goed"), ("sufficient", "Voldoende"), ("insufficient", "Onvoldoende")],
        string="Beoordeling", required=True, default="good",
    )
    outcome = fields.Selection(
        [("continue", "Verderzetten"), ("renegotiate", "Heronderhandelen"),
         ("tender", "Nieuwe offertes vragen"), ("terminate", "Opzeggen")],
        string="Voorstel", required=True, default="continue",
    )
    assembly_id = fields.Many2one(
        "vme.assembly", string="Voorgelegd op AV", domain="[('association_id', '=', association_id)]"
    )
    note = fields.Text(string="Toelichting")


class VmeDistributionRule(models.Model):
    _inherit = "vme.distribution.rule"

    @api.depends("partner_id.name", "key_id.name")
    def _compute_display_name(self):
        # Shown on a contract: "supplier - key" says what the rule does.
        for rule in self:
            rule.display_name = f"{rule.partner_id.name} - {rule.key_id.name}" if rule.partner_id else False


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    contract_ids = fields.One2many("vme.contract", "association_id", string="Contracten")


class VmeInstallation(models.Model):
    _inherit = "vme.installation"

    contract_ids = fields.One2many("vme.contract", "installation_id", string="Contracten")
    maintenance_contract_id = fields.Many2one(
        "vme.contract", string="Onderhoudscontract", compute="_compute_maintenance_contract_id",
    )
    maintenance_contract_end = fields.Date(
        string="Einde onderhoudscontract", compute="_compute_maintenance_contract_id")

    @api.depends("contract_ids.state", "contract_ids.date_end")
    def _compute_maintenance_contract_id(self):
        for installation in self:
            running = installation.contract_ids.filtered(lambda c: c.state != "ended")
            contract = running.sorted(lambda c: c.date_end or date.max)[:1]
            installation.maintenance_contract_id = contract
            installation.maintenance_contract_end = contract.date_end
