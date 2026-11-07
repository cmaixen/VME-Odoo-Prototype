"""Damage claims: report, lots involved, insurance policy, declaration, expertise, repair and payment."""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date, html2plaintext

from .vme_installation import DUE_STATES, _due_state

# LEGAL-CHECK: art. 74 §1 wet 4 april 2014 betreffende de verzekeringen - the insured reports a
# claim as soon as reasonably possible, and in any case within the term set in the policy.
# Eight days is a common term in building insurance policies; editable per policy.
DEFAULT_DECLARATION_DAYS = 8
# LEGAL-CHECK: art. 88 §1 wet 4 april 2014 betreffende de verzekeringen - a claim against the
# insurer lapses three years after the event that gives rise to it.
PRESCRIPTION_YEARS = 3
# Days after the declaration to check whether the insurer appointed an expert; not a legal rule.
EXPERT_FOLLOW_UP_DAYS = 14
# Days before the declaration deadline at which a claim turns orange.
WARNING_DAYS = 3
# LEGAL-CHECK: art. 85 wet 4 april 2014 betreffende de verzekeringen - a policy of at most one
# year renews tacitly unless a party gives notice at least three months before the due date.
NOTICE_MONTHS = 3
# Days before the due date of a policy at which the responsible user gets a task: in time to
# check the policy before the notice deadline.
RENEWAL_LEAD_DAYS = 120

DAMAGE_TYPES = [
    ("water", "Waterschade"),
    ("fire", "Brand"),
    ("storm", "Storm en hagel"),
    ("glass", "Glasbreuk"),
    ("burglary", "Inbraak en vandalisme"),
    ("liability", "Burgerlijke aansprakelijkheid"),
    ("other", "Andere"),
]

CLAIM_STATES = [
    ("reported", "Gemeld"),
    ("declared", "Aangegeven"),
    ("expertise", "Expertise"),
    ("repair", "Herstelling"),
    ("paid", "Uitbetaald"),
    ("refused", "Geweigerd"),
    ("cancelled", "Geannuleerd"),
]
CLOSED_STATES = ("paid", "refused", "cancelled")


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    insurance_policy_ids = fields.One2many("vme.insurance.policy", "association_id", string="Verzekeringspolissen")
    damage_claim_ids = fields.One2many("vme.damage.claim", "association_id", string="Schadedossiers")


class VmeInsurancePolicy(models.Model):
    _name = "vme.insurance.policy"
    _description = "Verzekeringspolis"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "association_id, policy_type, id"

    name = fields.Char(string="Polis", required=True)
    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    active = fields.Boolean(default=True)
    policy_type = fields.Selection(
        [("building", "Brandverzekering gebouw"), ("liability", "Burgerlijke aansprakelijkheid"),
         ("legal", "Rechtsbijstand"), ("other", "Andere")],
        string="Soort", required=True, default="building")
    insurer_id = fields.Many2one("res.partner", string="Verzekeraar", required=True)
    broker_id = fields.Many2one("res.partner", string="Makelaar")
    policy_number = fields.Char(string="Polisnummer", required=True)
    date_start = fields.Date(string="Begin lopende periode")
    date_end = fields.Date(
        string="Vervaldag", tracking=True,
        help="Einde van de lopende periode. Zonder opzeg verlengt de polis meestal stilzwijgend met een jaar.")
    tacit_renewal = fields.Boolean(string="Stilzwijgende verlenging", default=True)
    notice_deadline = fields.Date(
        string="Opzeggen uiterlijk", compute="_compute_notice_deadline", store=True,
        help="Laatste dag om de polis op te zeggen tegen de vervaldag.")
    due_state = fields.Selection(DUE_STATES, string="Status vervaldag", compute="_compute_due_state")
    insured_value = fields.Monetary(
        string="Verzekerde waarde", tracking=True, help="Waarde waarvoor het gebouw verzekerd is.")
    valuation_basis = fields.Selection(
        [("new_value", "Nieuwbouwwaarde"), ("expertise", "Expertise"), ("abex", "Geïndexeerd (ABEX)"),
         ("unknown", "Niet gekend")],
        string="Basis verzekerde waarde", default="unknown")
    premium = fields.Monetary(string="Jaarpremie")
    user_id = fields.Many2one(
        "res.users", string="Verantwoordelijke", default=lambda self: self.env.user,
        domain="[('share', '=', False)]")
    # Due date for which a task was already created, so the cron never makes it twice.
    activity_due_date = fields.Date(copy=False)
    deductible = fields.Monetary(string="Vrijstelling", help="Eigen risico per schadegeval.")
    declaration_days = fields.Integer(
        string="Aangifte binnen (dagen)", default=DEFAULT_DECLARATION_DAYS,
        help="Termijn uit de polis om een schade aan te geven bij de verzekeraar.")
    coverage = fields.Text(string="Dekking")
    claim_ids = fields.One2many("vme.damage.claim", "policy_id", string="Schadedossiers")
    claim_count = fields.Integer(string="Aantal schadegevallen", compute="_compute_claim_count")

    @api.depends("name", "policy_number")
    def _compute_display_name(self):
        for policy in self:
            policy.display_name = f"{policy.name} ({policy.policy_number})" if policy.policy_number else policy.name

    @api.depends("date_end")
    def _compute_notice_deadline(self):
        for policy in self:
            policy.notice_deadline = policy.date_end and policy.date_end - relativedelta(months=NOTICE_MONTHS)

    @api.depends("date_end")
    def _compute_due_state(self):
        today = fields.Date.context_today(self)
        for policy in self:
            policy.due_state = _due_state(policy.date_end, today)

    @api.depends("claim_ids")
    def _compute_claim_count(self):
        for policy in self:
            policy.claim_count = len(policy.claim_ids)

    def action_open_claims(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Schadedossiers %s", self.display_name),
            "res_model": "vme.damage.claim",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_association_id": self.association_id.id, "default_policy_id": self.id},
        }

    def action_renewed(self):
        """The staff member checked the renewal: the policy runs one more year. Nothing is sent."""
        for policy in self:
            if not policy.date_end:
                raise UserError(self.env._("Vul eerst de vervaldag van %s in.", policy.display_name))
            old_end = policy.date_end
            policy.write({"date_start": old_end + timedelta(days=1), "date_end": old_end + relativedelta(years=1)})
            policy.activity_ids.filtered(
                lambda a: (a.summary or "").startswith(policy._renewal_task_prefix())
            ).action_feedback(feedback=self.env._("Verlengd tot %s.", format_date(self.env, policy.date_end)))
            policy.message_post(body=self.env._(
                "Polis verlengd: nieuwe vervaldag %s.", format_date(self.env, policy.date_end)))
        return True

    def _renewal_task_prefix(self):
        return self.env._("Verzekering nakijken")

    @api.model
    def _cron_schedule_policy_activities(self):
        """One task per due date for policies due within RENEWAL_LEAD_DAYS days."""
        today = fields.Date.context_today(self)
        limit = today + relativedelta(days=RENEWAL_LEAD_DAYS)
        todo = self.env.ref("mail.mail_activity_data_todo")
        for policy in self.search([("date_end", "!=", False), ("date_end", "<=", limit)]):
            if policy.activity_due_date == policy.date_end:
                continue
            deadline = policy.notice_deadline if policy.notice_deadline >= today else max(policy.date_end, today)
            policy.activity_schedule(
                activity_type_id=todo.id,
                date_deadline=deadline,
                summary=self.env._("%(prefix)s: %(policy)s vervalt op %(date)s",
                                   prefix=policy._renewal_task_prefix(), policy=policy.name,
                                   date=format_date(self.env, policy.date_end)),
                note=self.env._(
                    "Kijk de polis van %(vme)s na: verzekerde waarde, premie en dekking. Verlengen of opzeggen "
                    "(opzeg uiterlijk %(notice)s). Na de verlenging: knop Verlengd.",
                    vme=policy.association_id.name, notice=format_date(self.env, policy.notice_deadline)),
                user_id=(policy.user_id or policy.association_id._vme_task_user()).id,
            )
            policy.activity_due_date = policy.date_end


class VmeDamageClaim(models.Model):
    _name = "vme.damage.claim"
    _description = "Schadedossier"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "report_date desc, id desc"

    name = fields.Char(string="Schadegeval", required=True, tracking=True)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    user_id = fields.Many2one(
        "res.users", string="Verantwoordelijke", default=lambda self: self.env.user, domain="[('share', '=', False)]")
    state = fields.Selection(CLAIM_STATES, string="Status", required=True, default="reported", tracking=True)
    damage_type = fields.Selection(DAMAGE_TYPES, string="Soort schade", required=True, default="water")

    # Report
    event_date = fields.Date(string="Datum schadegeval", default=fields.Date.context_today, tracking=True)
    report_date = fields.Date(string="Gemeld op", required=True, default=fields.Date.context_today)
    reporter_id = fields.Many2one("res.partner", string="Gemeld door")
    source = fields.Selection(
        [("mail", "E-mail"), ("phone", "Telefoon"), ("portal", "Portaal"), ("staff", "Vaststelling syndicus")],
        string="Via", default="phone")
    mail_reference = fields.Char(string="Referentie mail", copy=False, index=True,
                                 help="Message-ID van de mail waaruit de melding komt.")
    description = fields.Text(string="Omschrijving")
    lot_ids = fields.Many2many("vme.lot", string="Betrokken kavels", domain="[('association_id', '=', association_id)]")
    common_parts = fields.Boolean(string="Gemene delen beschadigd")
    cause = fields.Char(string="Vermoedelijke oorzaak")

    # Insurance
    policy_id = fields.Many2one(
        "vme.insurance.policy", string="Polis", compute="_compute_policy_id", store=True, readonly=False,
        domain="[('association_id', '=', association_id)]", tracking=True)
    insurer_id = fields.Many2one(related="policy_id.insurer_id", string="Verzekeraar")
    deductible = fields.Monetary(related="policy_id.deductible", string="Vrijstelling")
    declaration_deadline = fields.Date(string="Aangifte uiterlijk", compute="_compute_deadlines", store=True)
    declaration_date = fields.Date(string="Aangegeven op", copy=False, tracking=True)
    insurer_reference = fields.Char(string="Dossiernummer verzekeraar", copy=False, tracking=True)
    prescription_date = fields.Date(
        string="Verjaring", compute="_compute_deadlines", store=True,
        help="Na deze datum kan de VME de verzekeraar niet meer aanspreken voor dit schadegeval.")
    deadline_state = fields.Selection(
        [("none", "Geen termijn"), ("ok", "Op tijd"), ("warning", "Binnenkort"), ("danger", "Te laat")],
        string="Termijn", compute="_compute_deadline_state")
    deadline_text = fields.Char(string="Signaal termijn", compute="_compute_deadline_state")

    # Expertise and repair
    expert_id = fields.Many2one("res.partner", string="Expert", tracking=True)
    expertise_date = fields.Date(string="Expertise op", tracking=True)
    estimated_amount = fields.Monetary(string="Geraamde schade")
    repair_partner_id = fields.Many2one("res.partner", string="Hersteller", tracking=True)
    repair_date = fields.Date(string="Hersteld op", copy=False)
    bill_ids = fields.One2many(
        "account.move", "vme_damage_claim_id", string="Facturen herstelling",
        domain=[("move_type", "in", ("in_invoice", "in_refund"))])
    repair_cost = fields.Monetary(string="Kosten herstelling", compute="_compute_amounts")

    # Payment
    compensation_amount = fields.Monetary(string="Vergoeding verzekeraar", tracking=True)
    payment_date = fields.Date(string="Uitbetaald op", copy=False, tracking=True)
    net_cost = fields.Monetary(
        string="Ten laste van de VME", compute="_compute_amounts",
        help="Kosten herstelling min de vergoeding van de verzekeraar.")
    refusal_reason = fields.Text(string="Reden weigering")

    @api.depends("association_id")
    def _compute_policy_id(self):
        for claim in self:
            if not claim.policy_id:
                policies = claim.association_id.insurance_policy_ids
                claim.policy_id = policies.filtered(lambda p: p.policy_type == "building")[:1] or policies[:1]

    @api.depends("report_date", "event_date", "policy_id.declaration_days")
    def _compute_deadlines(self):
        for claim in self:
            days = claim.policy_id.declaration_days if claim.policy_id else DEFAULT_DECLARATION_DAYS
            start = claim.event_date or claim.report_date
            claim.declaration_deadline = start and start + timedelta(days=days)
            claim.prescription_date = start and start + relativedelta(years=PRESCRIPTION_YEARS)

    @api.depends("state", "declaration_deadline")
    def _compute_deadline_state(self):
        today = fields.Date.context_today(self)
        for claim in self:
            deadline = claim.declaration_deadline if claim.state == "reported" else False
            claim.deadline_text = False
            if not deadline:
                claim.deadline_state = "none"
            elif deadline < today:
                claim.deadline_state = "danger"
                claim.deadline_text = self.env._(
                    "De termijn om de schade aan te geven bij de verzekeraar is verstreken op %s.",
                    format_date(self.env, deadline))
            elif deadline <= today + timedelta(days=WARNING_DAYS):
                claim.deadline_state = "warning"
                claim.deadline_text = self.env._(
                    "Geef de schade aan bij de verzekeraar uiterlijk op %s.", format_date(self.env, deadline))
            else:
                claim.deadline_state = "ok"

    @api.depends("bill_ids.state", "bill_ids.amount_total_signed", "compensation_amount")
    def _compute_amounts(self):
        for claim in self:
            posted = claim.bill_ids.filtered(lambda m: m.state == "posted")
            claim.repair_cost = claim.currency_id.round(-sum(posted.mapped("amount_total_signed")))
            claim.net_cost = claim.repair_cost - claim.compensation_amount

    @api.constrains("lot_ids", "association_id", "policy_id")
    def _check_vme(self):
        for claim in self:
            if claim.lot_ids.association_id - claim.association_id:
                raise ValidationError(self.env._("Alle betrokken kavels moeten tot de VME van het dossier behoren."))
            if claim.policy_id and claim.policy_id.association_id != claim.association_id:
                raise ValidationError(self.env._("De polis hoort bij een andere VME."))

    @api.model_create_multi
    def create(self, vals_list):
        claims = super().create(vals_list)
        for claim in claims.filtered(lambda c: c.state == "reported"):
            claim._task(
                self.env._("Schade aangeven bij %s", claim.insurer_id.name or self.env._("de verzekeraar")),
                claim.declaration_deadline,
                self.env._("Termijn uit de polis: %s dagen na het schadegeval.",
                           claim.policy_id.declaration_days or DEFAULT_DECLARATION_DAYS))
        return claims

    def _task(self, summary, deadline, note=None):
        self.ensure_one()
        self.activity_schedule(
            "mail.mail_activity_data_todo", date_deadline=deadline or fields.Date.context_today(self),
            summary=summary, note=note, user_id=(self.user_id or self.env.user).id)

    def _done_tasks(self, feedback):
        self.activity_ids.action_feedback(feedback=feedback)

    def _check_state(self, *allowed):
        for claim in self:
            if claim.state not in allowed:
                raise UserError(self.env._(
                    "%(claim)s staat op \"%(state)s\"; deze stap kan niet.",
                    claim=claim.name, state=dict(CLAIM_STATES)[claim.state]))

    # Steps

    def action_declare(self):
        """The staff member declared the claim to the insurer (the declaration itself is sent by a person)."""
        self._check_state("reported")
        today = fields.Date.context_today(self)
        for claim in self:
            if not claim.policy_id:
                raise UserError(self.env._("Kies de verzekeringspolis waaronder de schade valt."))
            declared = claim.declaration_date or today
            claim.write({"state": "declared", "declaration_date": declared})
            claim._done_tasks(self.env._("Aangegeven op %s.", format_date(self.env, declared)))
            claim._task(self.env._("Aanstelling expert opvolgen"), declared + timedelta(days=EXPERT_FOLLOW_UP_DAYS))
            if declared > claim.declaration_deadline:
                claim.message_post(body=self.env._(
                    "Opgelet: aangegeven na de termijn uit de polis (%s). De verzekeraar kan de vergoeding "
                    "verminderen als hij daardoor nadeel lijdt.", format_date(self.env, claim.declaration_deadline)))
        return True

    def action_expertise(self):
        self._check_state("declared")
        for claim in self:
            if not claim.expert_id:
                raise UserError(self.env._("Vul de expert in die de verzekeraar aanstelde."))
            claim.state = "expertise"
            claim._done_tasks(self.env._("Expert %s aangesteld.", claim.expert_id.name))
            claim._task(self.env._("Expertise bijwonen en verslag opvolgen"), claim.expertise_date)
        return True

    def action_repair(self):
        self._check_state("declared", "expertise")
        for claim in self:
            claim.state = "repair"
            claim._done_tasks(self.env._("Herstelling gestart."))
            claim._task(self.env._("Herstelling en factuur opvolgen"),
                        fields.Date.context_today(self) + timedelta(days=EXPERT_FOLLOW_UP_DAYS))
        return True

    def action_paid(self):
        self._check_state("declared", "expertise", "repair")
        for claim in self:
            if not claim.compensation_amount or not claim.payment_date:
                raise UserError(self.env._("Vul het bedrag en de datum van de vergoeding in."))
            claim.state = "paid"
            claim._done_tasks(self.env._("Vergoeding ontvangen."))
        return True

    def action_refuse(self):
        self._check_state("declared", "expertise", "repair")
        for claim in self:
            if not claim.refusal_reason:
                raise UserError(self.env._("Vul de reden in waarom de verzekeraar weigert."))
            claim.state = "refused"
            claim._done_tasks(self.env._("Geweigerd door de verzekeraar."))
        return True

    def action_cancel(self):
        self._check_state("reported", "declared")
        self._done_tasks(self.env._("Schadedossier geannuleerd."))
        self.state = "cancelled"
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
            "domain": [("vme_damage_claim_id", "=", self.id)],
            "context": {"default_move_type": "in_invoice", "default_vme_damage_claim_id": self.id,
                        "default_partner_id": self.repair_partner_id.id,
                        "default_company_id": self.company_id.id},
        }

    # From a mail of an owner (step 7, ai/)

    @api.model
    def create_from_mail(self, association_id, subject, body, reference=None, lot_id=None, owner_id=None,
                         mail_date=None):
        """Draft damage claim from an owner mail; nothing is declared or sent. Returns its id.

        A mail that already has a claim (same Message-ID) returns that claim.
        """
        if reference:
            existing = self.search([("mail_reference", "=", reference)], limit=1)
            if existing:
                return existing.id
        vme = self.env["vme.association"].browse(association_id).exists()
        if not vme:
            raise UserError(self.env._("Onbekende VME."))
        lot = self.env["vme.lot"].browse(lot_id).exists() if lot_id else self.env["vme.lot"]
        report_date = fields.Date.to_date(mail_date) if mail_date else fields.Date.context_today(self)
        claim = self.create({
            "association_id": vme.id,
            "name": subject or self.env._("Schademelding"),
            "lot_ids": [fields.Command.set(lot.filtered(lambda l: l.association_id == vme).ids)],
            "reporter_id": owner_id or False,
            "source": "mail",
            "mail_reference": reference,
            "description": html2plaintext(body) if body and "<" in body else body,
            "event_date": report_date,
            "report_date": report_date,
        })
        claim.message_post(body=self.env._("Aangemaakt uit een mail van een eigenaar. Kijk de gegevens na."))
        return claim.id


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_damage_claim_id = fields.Many2one(
        "vme.damage.claim", string="Schadedossier", index=True, copy=False,
        domain="[('company_id', '=', company_id), ('state', 'not in', %s)]" % (CLOSED_STATES,))
