from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import format_date

from .cron_tools import run_per_record

INSTALLATION_TYPES = [
    ("elevator", "Lift"),
    ("fire_extinguishers", "Brandblussers en haspels"),
    ("electrical", "Elektrische installatie gemene delen"),
    ("heating_boiler", "CV-ketel"),
    ("smoke_vents", "Rookluiken en RWA"),
    ("other", "Andere"),
]

# Default inspection interval in months per installation type; editable per installation.
DEFAULT_INTERVAL_MONTHS = {
    # LEGAL-CHECK: KB 9 maart 2003 betreffende de beveiliging van liften - preventive
    # inspection by an accredited inspection body (EDTC).
    "elevator": 6,
    # LEGAL-CHECK: NBN S21-050 - yearly maintenance check of portable fire extinguishers and hoses.
    "fire_extinguishers": 12,
    # LEGAL-CHECK: AREI (Algemeen Reglement op de Elektrische Installaties) - periodic
    # inspection of the common parts of residential buildings.
    "electrical": 60,
    # LEGAL-CHECK: Vlaamse regelgeving verwarmingsaudit/onderhoud - gas boilers; differs per
    # region and fuel (fuel oil is yearly).
    "heating_boiler": 24,
    # LEGAL-CHECK: no general legal interval found; manufacturer and fire department advice.
    "smoke_vents": 12,
    "other": 12,
}

# LEGAL-CHECK: KB 9 maart 2003 - risk analysis of an elevator at least every 15 years.
ELEVATOR_RISK_ANALYSIS_YEARS = 15

DUE_STATES = [
    ("overdue", "Vervallen"),
    ("due_30", "Binnen 30 dagen"),
    ("due_60", "Binnen 60 dagen"),
    ("due_90", "Binnen 90 dagen"),
    ("ok", "In orde"),
    ("unknown", "Geen keuring gekend"),
]

INSPECTION_KINDS = [
    ("inspection", "Preventieve inspectie / periodieke keuring"),
    ("retest", "Herkeuring"),
    ("risk_analysis", "Risicoanalyse"),
    ("maintenance", "Onderhoudsbezoek"),
]
# Inspection kinds that count as the periodic inspection of an installation.
PERIODIC_KINDS = ("inspection", "retest")

# Days before the due date at which the responsible user gets a task.
ACTIVITY_LEAD_DAYS = 60


def _due_state(due_date, today):
    if not due_date:
        return "unknown"
    days = (due_date - today).days
    if days < 0:
        return "overdue"
    for limit, state in ((30, "due_30"), (60, "due_60"), (90, "due_90")):
        if days <= limit:
            return state
    return "ok"


class VmeInstallation(models.Model):
    _name = "vme.installation"
    _description = "Installatie met keuringsplicht"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "next_inspection_date, association_id, name"

    name = fields.Char(string="Naam", required=True, tracking=True)
    active = fields.Boolean(string="Actief", default=True)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    installation_type = fields.Selection(INSTALLATION_TYPES, string="Soort", required=True, tracking=True)
    location = fields.Char(string="Plaats", help="Bijvoorbeeld: blok A, trappenhal, kelder.")
    responsible_user_id = fields.Many2one(
        "res.users", string="Verantwoordelijke", default=lambda self: self.env.user, tracking=True
    )

    maintenance_partner_id = fields.Many2one("res.partner", string="Onderhoudsfirma", tracking=True)
    # The maintenance contract itself (reference, end, notice) is a vme.contract, see vme_contract.py.
    inspection_partner_id = fields.Many2one(
        "res.partner", string="Keuringsorganisme", tracking=True,
        help="Bij een lift: de erkende dienst voor technische controle (EDTC).",
    )
    inspection_interval_months = fields.Integer(
        string="Keuringsfrequentie (maanden)",
        compute="_compute_inspection_interval_months", store=True, readonly=False,
    )

    inspection_ids = fields.One2many("vme.inspection", "installation_id", string="Keuringsverslagen")
    remark_ids = fields.One2many("vme.inspection.remark", "installation_id", string="Opmerkingen")
    open_remark_count = fields.Integer(string="Open opmerkingen", compute="_compute_remark_counts")
    overdue_remark_count = fields.Integer(string="Opmerkingen over termijn", compute="_compute_remark_counts")

    last_inspection_date = fields.Date(
        string="Laatste keuring", compute="_compute_inspection_dates", store=True
    )
    next_inspection_date = fields.Date(
        string="Volgende keuring", compute="_compute_inspection_dates", store=True, tracking=True
    )
    due_state = fields.Selection(DUE_STATES, string="Status keuring", compute="_compute_due_state")

    # Elevators
    last_risk_analysis_date = fields.Date(
        string="Laatste risicoanalyse", compute="_compute_inspection_dates", store=True
    )
    next_risk_analysis_date = fields.Date(
        string="Volgende risicoanalyse", compute="_compute_inspection_dates", store=True
    )
    risk_analysis_due_state = fields.Selection(
        DUE_STATES, string="Status risicoanalyse", compute="_compute_due_state"
    )
    retest_required = fields.Boolean(
        string="Herkeuring nodig", compute="_compute_retest_required", store=True, tracking=True
    )

    # Due dates for which a task was already created, so the cron never makes it twice.
    activity_inspection_due_date = fields.Date(copy=False)
    activity_risk_analysis_due_date = fields.Date(copy=False)

    @api.depends("installation_type")
    def _compute_inspection_interval_months(self):
        for installation in self:
            if not installation.inspection_interval_months:
                installation.inspection_interval_months = DEFAULT_INTERVAL_MONTHS.get(
                    installation.installation_type, 12
                )

    @api.depends("inspection_ids.date", "inspection_ids.kind", "inspection_interval_months", "installation_type")
    def _compute_inspection_dates(self):
        for installation in self:
            periodic = installation.inspection_ids.filtered(lambda i: i.kind in PERIODIC_KINDS and i.date)
            last = max(periodic.mapped("date"), default=False)
            installation.last_inspection_date = last
            installation.next_inspection_date = (
                last + relativedelta(months=installation.inspection_interval_months)
                if last and installation.inspection_interval_months else False
            )
            if installation.installation_type == "elevator":
                risk = installation.inspection_ids.filtered(lambda i: i.kind == "risk_analysis" and i.date)
                last_risk = max(risk.mapped("date"), default=False)
                installation.last_risk_analysis_date = last_risk
                installation.next_risk_analysis_date = (
                    last_risk + relativedelta(years=ELEVATOR_RISK_ANALYSIS_YEARS) if last_risk else False
                )
            else:
                installation.last_risk_analysis_date = False
                installation.next_risk_analysis_date = False

    @api.depends("inspection_ids.date", "inspection_ids.kind", "inspection_ids.result")
    def _compute_retest_required(self):
        # The latest periodic report decides: "niet conform" needs a retest, a compliant
        # inspection or retest afterwards clears it.
        for installation in self:
            periodic = installation.inspection_ids.filtered(lambda i: i.kind in PERIODIC_KINDS and i.date)
            latest = periodic.sorted(lambda i: (i.date, i.id))[-1:]
            installation.retest_required = latest.result == "non_compliant"

    @api.depends("next_inspection_date", "next_risk_analysis_date")
    def _compute_due_state(self):
        today = fields.Date.context_today(self)
        for installation in self:
            installation.due_state = _due_state(installation.next_inspection_date, today)
            installation.risk_analysis_due_state = (
                _due_state(installation.next_risk_analysis_date, today)
                if installation.installation_type == "elevator" else False
            )

    @api.depends("remark_ids.state", "remark_ids.deadline")
    def _compute_remark_counts(self):
        for installation in self:
            open_remarks = installation.remark_ids.filtered("is_open")
            installation.open_remark_count = len(open_remarks)
            installation.overdue_remark_count = len(open_remarks.filtered("is_overdue"))

    @api.model
    def _cron_schedule_inspection_activities(self):
        """Create one task per due date for inspections and risk analyses due within 60 days."""
        limit = fields.Date.context_today(self) + relativedelta(days=ACTIVITY_LEAD_DAYS)
        todo = self.env.ref("mail.mail_activity_data_todo")
        # Only what still needs a task, so a cron that ran out of time continues with the rest (K-D18).
        due = self.search(["|", ("next_inspection_date", "<=", limit), ("next_risk_analysis_date", "<=", limit)]).filtered(
            lambda i: i._inspection_task_due(limit) or i._risk_analysis_task_due(limit))
        run_per_record(due, lambda installation: installation._schedule_due_activities(limit, todo))

    def _inspection_task_due(self, limit):
        return self.next_inspection_date and self.next_inspection_date <= limit \
            and self.activity_inspection_due_date != self.next_inspection_date

    def _risk_analysis_task_due(self, limit):
        return self.next_risk_analysis_date and self.next_risk_analysis_date <= limit \
            and self.activity_risk_analysis_due_date != self.next_risk_analysis_date

    def _schedule_due_activities(self, limit, todo):
        """The inspection and risk analysis tasks this installation still needs; one record of the daily cron."""
        self.ensure_one()
        installation = self
        if installation._inspection_task_due(limit):
            installation.activity_schedule(
                activity_type_id=todo.id,
                date_deadline=installation.next_inspection_date,
                summary=self.env._("Keuring plannen: %s", installation.name),
                note=self.env._(
                    "De keuring van %(installation)s (%(vme)s) vervalt op %(date)s.",
                    installation=installation.name, vme=installation.association_id.name,
                    date=format_date(self.env, installation.next_inspection_date),
                ),
                user_id=(installation.responsible_user_id or installation.association_id._vme_task_user()).id,
            )
            installation.activity_inspection_due_date = installation.next_inspection_date
        if installation._risk_analysis_task_due(limit):
            installation.activity_schedule(
                activity_type_id=todo.id,
                date_deadline=installation.next_risk_analysis_date,
                summary=self.env._("Risicoanalyse lift laten uitvoeren: %s", installation.name),
                user_id=(installation.responsible_user_id or installation.association_id._vme_task_user()).id,
            )
            installation.activity_risk_analysis_due_date = installation.next_risk_analysis_date

    def _close_done_inspection_activity(self):
        """Mark the "Keuring plannen" task done once a new inspection moved the due date past it."""
        todo = self.env.ref("mail.mail_activity_data_todo")
        for installation in self.filtered("activity_inspection_due_date"):
            due = installation.activity_inspection_due_date
            if installation.next_inspection_date and installation.next_inspection_date <= due:
                continue
            installation.activity_ids.filtered(
                lambda a: a.activity_type_id == todo and a.date_deadline == due
            ).action_feedback(feedback=self.env._(
                "Keuring geregistreerd; volgende keuring: %s.",
                format_date(self.env, installation.next_inspection_date)))
            installation.activity_inspection_due_date = False

    def _register_inspection_from_bill(self, move):
        """Record an inspection for a posted bill of this installation's inspection body (once per bill)."""
        self.ensure_one()
        if self.env["vme.inspection"].search_count([("move_id", "=", move.id)]):
            return self.env["vme.inspection"]
        inspection = self.env["vme.inspection"].create({
            "installation_id": self.id,
            "date": move.invoice_date,
            "partner_id": move.partner_id.id,
            "kind": "inspection",
            "result": "compliant",
            "move_id": move.id,
        })
        message = self.env._(
            "Keuring van %(installation)s geregistreerd op %(date)s via factuur %(move)s; "
            "volgende keuring: %(next)s. Vul het verslag en eventuele opmerkingen aan.",
            installation=self.name, date=format_date(self.env, move.invoice_date), move=move.name,
            next=format_date(self.env, self.next_inspection_date),
        )
        self.message_post(body=message)
        move.message_post(body=message)
        return inspection


class VmeInspection(models.Model):
    _name = "vme.inspection"
    _description = "Keuringsverslag"
    _order = "date desc, id desc"

    installation_id = fields.Many2one(
        "vme.installation", string="Installatie", required=True, ondelete="cascade", index=True
    )
    association_id = fields.Many2one(related="installation_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="installation_id.company_id", store=True)
    date = fields.Date(string="Datum", required=True, default=fields.Date.context_today)
    partner_id = fields.Many2one("res.partner", string="Keuringsorganisme of firma")
    kind = fields.Selection(INSPECTION_KINDS, string="Soort", required=True, default="inspection")
    result = fields.Selection(
        [("compliant", "Conform"), ("remarks", "Conform met opmerkingen"), ("non_compliant", "Niet conform / stilstand")],
        string="Resultaat", required=True, default="compliant",
    )
    report = fields.Binary(string="Verslag (PDF)", attachment=True)
    report_filename = fields.Char(string="Bestandsnaam verslag")
    remark_ids = fields.One2many("vme.inspection.remark", "inspection_id", string="Opmerkingen")
    move_id = fields.Many2one("account.move", string="Factuur", ondelete="set null", index=True)
    note = fields.Text(string="Notitie")

    _unique_move = models.Constraint(
        "UNIQUE (move_id)", "Deze factuur is al aan een keuringsverslag gekoppeld."
    )

    @api.model_create_multi
    def create(self, vals_list):
        inspections = super().create(vals_list)
        inspections.installation_id._close_done_inspection_activity()
        return inspections

    @api.depends("installation_id.name", "kind", "date")
    def _compute_display_name(self):
        kinds = dict(INSPECTION_KINDS)
        for inspection in self:
            inspection.display_name = f"{inspection.installation_id.name} - {kinds.get(inspection.kind, '')} " \
                                      f"{format_date(self.env, inspection.date) if inspection.date else ''}"


class VmeInspectionRemark(models.Model):
    _name = "vme.inspection.remark"
    _description = "Opmerking uit een keuringsverslag"
    _inherit = ["mail.thread"]
    _order = "deadline, id"

    inspection_id = fields.Many2one(
        "vme.inspection", string="Keuringsverslag", required=True, ondelete="cascade", index=True
    )
    installation_id = fields.Many2one(related="inspection_id.installation_id", store=True, string="Installatie")
    association_id = fields.Many2one(related="inspection_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="inspection_id.company_id", store=True)
    name = fields.Char(string="Opmerking", required=True)
    severity = fields.Selection(
        [("minor", "Licht"), ("major", "Ernstig"), ("blocking", "Stilstand")],
        string="Ernst", required=True, default="minor",
    )
    deadline = fields.Date(string="Termijn")
    responsible = fields.Selection(
        [("maintenance", "Onderhoudsfirma"), ("syndic", "Syndicus"), ("other", "Andere")],
        string="Verantwoordelijke", required=True, default="maintenance",
    )
    state = fields.Selection(
        [("open", "Open"), ("planned", "Gepland"), ("resolved", "Opgelost"), ("retested", "Herkeurd")],
        string="Status", required=True, default="open", tracking=True,
    )
    resolved_date = fields.Date(string="Opgelost op")
    is_open = fields.Boolean(string="Open", compute="_compute_is_open", store=True)
    is_overdue = fields.Boolean(string="Over termijn", compute="_compute_is_overdue", search="_search_is_overdue")

    @api.depends("state")
    def _compute_is_open(self):
        for remark in self:
            remark.is_open = remark.state in ("open", "planned")

    @api.depends("deadline", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for remark in self:
            remark.is_overdue = remark.is_open and bool(remark.deadline) and remark.deadline < today

    def _search_is_overdue(self, operator, value):
        domain = [("is_open", "=", True), ("deadline", "<", fields.Date.context_today(self))]
        # Odoo 19 passes "in"/"not in" with a list of values (e.g. [False]), not a single boolean.
        if operator in ("in", "not in"):
            positive = (True in value) == (operator == "in")
        else:
            positive = bool(value) == (operator == "=")
        return domain if positive else ["!", "&", *domain]

    def write(self, vals):
        if vals.get("state") in ("resolved", "retested") and "resolved_date" not in vals:
            vals["resolved_date"] = fields.Date.context_today(self)
        return super().write(vals)
