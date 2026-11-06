import logging
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import format_date, formatLang

from .vme_assembly import URGENT_MARGIN_DAYS
from .vme_budget import RESERVE_MINIMUM_RATE

_logger = logging.getLogger(__name__)

STEP_CODES = [
    ("closing", "Boekjaar afsluiten"),
    ("statement", "Jaarafrekening"),
    ("budget", "Budget en reservefonds"),
    ("planning", "AV plannen"),
    ("agenda", "Agenda: herbenoemingen"),
    ("convocation", "Oproeping AV"),
    ("assembly", "AV houden"),
    ("minutes", "Notulen bezorgen"),
    ("approved_budget", "Goedgekeurd budget verwerken"),
    ("provision", "Provisieoproep"),
]
STATES = [("pending", "Gepland"), ("ready", "Klaargezet"), ("done", "Afgerond"), ("skipped", "Niet van toepassing")]

# Working agreements of the syndic, in days relative to the last day on which the convocation
# can leave (L). They are not legal terms; the pilot syndic can adjust them here.
CLOSING_BEFORE_CONVOCATION = 21
STATEMENT_BEFORE_CONVOCATION = 7
BUDGET_READY_BEFORE_CONVOCATION = 60
BUDGET_BEFORE_CONVOCATION = 7
PLANNING_READY_BEFORE_PERIOD = 120
AGENDA_READY_BEFORE_CONVOCATION = 30
CONVOCATION_READY_BEFORE = 14
APPROVED_BUDGET_AFTER_ASSEMBLY = 30
PROVISION_READY_BEFORE = 14
PROVISION_DUE_DAYS = 30
# LEGAL-CHECK: art. 3.87 §12 BW - the syndic sends the minutes to the co-owners within thirty
# days after the general assembly.
MINUTES_AFTER_ASSEMBLY = 30
# Without an assembly period the closing and the annual statement still need a deadline.
FALLBACK_CLOSING = (3, 31)
FALLBACK_STATEMENT = (4, 30)

# Steps that a human closes by hand (button or ticking off the task). The other steps are done
# when the underlying fact is there: invoices posted, convocation sent, assembly held.
MANUAL_CODES = ("closing", "statement", "agenda", "minutes", "approved_budget")
# Steps that wait for the assembly: never late while the assembly has not been held.
AFTER_ASSEMBLY_CODES = ("minutes", "approved_budget")

SYNDIC_RENEWAL_ITEM = "Herbenoeming van de syndicus"
AUDITOR_ITEM = "Benoeming van de commissaris van de rekeningen"


class VmeCycleStep(models.Model):
    _name = "vme.cycle.step"
    _description = "Stap in de jaarcyclus"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_deadline, association_id, id"

    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    year = fields.Integer(string="Cyclusjaar", required=True)
    code = fields.Selection(STEP_CODES, string="Soort", required=True)
    sequence = fields.Integer(string="Oproep", default=0, help="Nummer van de provisieoproep, 0 voor andere stappen.")
    sequence_total = fields.Integer(string="Oproepen per jaar")
    name = fields.Char(string="Stap", compute="_compute_name", store=True)
    date_ready = fields.Date(string="Klaarzetten vanaf", required=True)
    date_deadline = fields.Date(string="Uiterlijk", required=True)
    state = fields.Selection(STATES, string="Status", required=True, default="pending", tracking=True)
    is_late = fields.Boolean(string="Te laat", compute="_compute_is_late", search="_search_is_late")
    user_id = fields.Many2one("res.users", string="Verantwoordelijke", domain="[('share', '=', False)]")
    res_model = fields.Char(string="Model van het concept", readonly=True)
    res_id = fields.Many2oneReference(string="Concept", model_field="res_model", readonly=True)
    note = fields.Text(string="Toelichting")
    prepared_date = fields.Date(string="Klaargezet op", readonly=True)
    done_date = fields.Date(string="Afgerond op", readonly=True)

    # The same step exists only once per VME and year.
    _unique_step = models.Constraint(
        "UNIQUE (association_id, year, code, sequence)",
        "Deze stap bestaat al in de jaarcyclus van deze VME.",
    )

    @api.depends("code", "year", "sequence", "sequence_total")
    def _compute_name(self):
        for step in self:
            year = step.year
            step.name = {
                "closing": self.env._("Boekjaar %s afsluiten", year - 1),
                "statement": self.env._("Jaarafrekening %s", year - 1),
                "budget": self.env._("Budget %s en reservefonds", year),
                "planning": self.env._("AV %s plannen", year),
                "agenda": self.env._("Agenda AV %s: herbenoemingen", year),
                "convocation": self.env._("Oproeping AV %s", year),
                "assembly": self.env._("AV %s houden", year),
                "minutes": self.env._("Notulen AV %s bezorgen", year),
                "approved_budget": self.env._("Goedgekeurd budget %s verwerken", year),
                "provision": self.env._("Provisieoproep %(number)s/%(total)s %(year)s",
                                        number=step.sequence, total=step.sequence_total, year=year),
            }.get(step.code, "")

    def _today(self):
        # Tests and the demo can pin "today" via the context, like the assembly planner.
        return self.env.context.get("vme_today") or fields.Date.context_today(self)

    @api.depends("state", "date_deadline")
    @api.depends_context("vme_today")
    def _compute_is_late(self):
        today = self._today()
        for step in self:
            step.is_late = step._is_late(today)

    def _is_late(self, today):
        self.ensure_one()
        if self.state in ("done", "skipped") or not self.date_deadline or self.date_deadline >= today:
            return False
        if self.code in AFTER_ASSEMBLY_CODES and self._get_assembly().state != "held":
            return False
        return True

    def _search_is_late(self, operator, value):
        if operator not in ("in", "not in"):
            return NotImplemented
        today = self._today()
        late = self.sudo().search([("state", "in", ("pending", "ready")), ("date_deadline", "<", today)]).filtered(
            lambda s: s._is_late(today))
        # Searching for "late is False" or "late is True" both arrive as ("in", [bool]).
        wanted = True in value
        return [("id", "in" if wanted == (operator == "in") else "not in", late.ids)]

    # Links

    def _get_assembly(self):
        self.ensure_one()
        return self.env["vme.assembly"].sudo().search([
            ("association_id", "=", self.association_id.id), ("year", "=", self.year),
            ("assembly_type", "=", "ordinary"), ("state", "!=", "cancelled")], limit=1)

    def _get_budget(self):
        self.ensure_one()
        return self.env["vme.budget"].sudo().search([
            ("association_id", "=", self.association_id.id), ("year", "=", self.year)], limit=1)

    def _get_provision_call(self):
        self.ensure_one()
        return self.env["vme.provision.call"].sudo().search([
            ("association_id", "=", self.association_id.id), ("budget_id.year", "=", self.year),
            ("number", "=", self.sequence)], limit=1)

    # Done

    def _check_done(self):
        """Close the open steps whose underlying fact is there."""
        today = self._today()
        for step in self.filtered(lambda s: s.state in ("pending", "ready")):
            if step._is_fact_done():
                step._mark_done(today)

    def _is_fact_done(self):
        self.ensure_one()
        vme = self.association_id.sudo()
        if self.code == "closing":
            return vme._cycle_fiscal_year_closed(self.year - 1)
        if self.code == "provision":
            invoices = self._get_provision_call().invoice_ids.filtered(lambda m: m.state != "cancel")
            return bool(invoices) and all(m.state == "posted" for m in invoices)
        if self.code == "budget":
            budget = self._get_budget()
            return bool(budget) and not budget.reserve_warning
        assembly = self._get_assembly()
        if not assembly:
            return False
        if self.code in ("statement", "agenda"):
            # The convocations carry the agenda and the annual statement of last year.
            return bool(assembly.convocation_ids) or assembly.state == "held"
        if self.code == "planning":
            return assembly.state in ("confirmed", "held")
        if self.code == "convocation":
            return bool(assembly.convocation_sent_date) or assembly.state == "held"
        if self.code == "assembly":
            return assembly.state == "held"
        return False

    def _mark_done(self, today=None):
        today = today or self._today()
        self.write({"state": "done", "done_date": today})
        # Tick off the open tasks of these steps; done steps keep no reminders.
        self.with_context(vme_cycle_closing=True).activity_ids.action_feedback(
            feedback=self.env._("Stap afgerond."))

    # Preparing

    def _prepare(self, today=None):
        """Put the step ready as a draft or a task for its responsible. Never posts or sends anything."""
        today = today or self._today()
        for step in self.filtered(lambda s: s.state == "pending"):
            try:
                with self.env.cr.savepoint():
                    summary, note = getattr(step, f"_prepare_{step.code}")(today)
            except (UserError, ValidationError) as error:
                message = error.args[0] if error.args else str(error)
                summary, note = self.env._("Los eerst op: %s", step.name), message
                _logger.info("Jaarcyclus %s, %s: %s", step.association_id.name, step.name, message)
            step.write({"state": "ready", "prepared_date": today, "note": note or False})
            if summary:
                step.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=max(step.date_deadline, today),
                    summary=summary,
                    note=note or "",
                    user_id=(step.user_id or step.association_id._cycle_default_user()).id,
                )
            step._check_done()

    def _link(self, record):
        self.write({"res_model": record._name, "res_id": record.id})

    def _prepare_closing(self, today):
        return (self.env._("Boekjaar %(year)s van %(vme)s afsluiten", year=self.year - 1, vme=self.association_id.name),
                self.env._("Sluit het boekjaar %s af vóór de jaarafrekening gemaakt wordt.", self.year - 1))

    def _prepare_statement(self, today):
        return (self.env._("Jaarafrekening %(year)s van %(vme)s nakijken", year=self.year - 1, vme=self.association_id.name),
                self.env._("Kijk de jaarafrekening per eigenaar na (VME > Jaarafrekening). Ze gaat mee met de oproeping."))

    def _prepare_budget(self, today):
        vme = self.association_id.sudo()
        budget = self._get_budget()
        # LEGAL-CHECK: art. 3.86 §3 BW - yearly reserve contribution of at least 5% of the ordinary
        # common charges of the previous year, unless the general assembly decides otherwise with 4/5.
        if budget:
            self._link(budget)
            minimum = budget.reserve_minimum
            note = budget.reserve_warning or self.env._(
                "Het budget %(year)s bestaat; de bijdrage aan het reservekapitaal haalt het minimum van %(minimum)s.",
                year=self.year, minimum=formatLang(self.env, minimum, currency_obj=budget.currency_id))
        else:
            charges = self.env["vme.budget"].new({"association_id": vme.id, "year": self.year})._get_previous_year_charges()
            note = self.env._(
                "Maak het budget %(year)s op voor de AV. Minimum bijdrage reservekapitaal: %(minimum)s "
                "(5%% van de gewone lasten van %(prev)s).",
                year=self.year, prev=self.year - 1,
                minimum=formatLang(self.env, charges * RESERVE_MINIMUM_RATE, currency_obj=vme.company_id.currency_id))
        return self.env._("Budget %(year)s van %(vme)s voorbereiden", year=self.year, vme=vme.name), note

    def _prepare_planning(self, today):
        vme = self.association_id.sudo()
        Assembly = self.env["vme.assembly"].sudo()
        Assembly._create_missing_assemblies(self.year, vme)
        assembly = self._get_assembly()
        self._link(assembly)
        if assembly.state == "draft":
            # The planner only proposes; the syndic confirms the meeting.
            assembly._propose_schedule(today)
        if assembly.state == "proposed":
            return (self.env._("Voorstel voor de AV %(year)s van %(vme)s bevestigen", year=self.year, vme=vme.name),
                    self.env._("De AV-planner stelt %(slot)s voor. Bevestig of kies een ander blok.",
                               slot=assembly.slot_id.display_name))
        if assembly.state == "draft":
            return (self.env._("AV %(year)s van %(vme)s met de hand plannen", year=self.year, vme=vme.name),
                    self.env._("Geen vrij blok in de periode van %(start)s tot %(end)s. Voeg een blok toe of plan met de hand.",
                               start=format_date(self.env, assembly.period_start), end=format_date(self.env, assembly.period_end)))
        return False, False

    def _prepare_agenda(self, today):
        vme = self.association_id.sudo()
        assembly = self._get_assembly()
        if not assembly:
            raise UserError(self.env._("Er is nog geen AV %s: plan ze eerst.", self.year))
        self._link(assembly)
        added = assembly._cycle_add_renewal_items()
        note = self.env._("Toegevoegd aan de agenda: %s.", ", ".join(added)) if added else self.env._(
            "De agenda bevat de benoemingen al.")
        return (self.env._("Agenda van de AV %(year)s van %(vme)s nakijken", year=self.year, vme=vme.name), note)

    def _prepare_convocation(self, today):
        vme = self.association_id.sudo()
        assembly = self._get_assembly()
        if not assembly or assembly.state != "confirmed":
            raise UserError(self.env._("Bevestig eerst de AV %s: de oproeping vermeldt datum, uur en plaats.", self.year))
        self._link(assembly)
        if not assembly.convocation_ids:
            # Draft convocations with their PDF; the employee checks and sends them.
            assembly.action_create_convocations()
        return (self.env._("Oproepingen AV %(year)s van %(vme)s nakijken en versturen", year=self.year, vme=vme.name),
                self.env._("%(count)s conceptoproepingen staan klaar. Verstuur ze uiterlijk op %(deadline)s.",
                           count=len(assembly.convocation_ids), deadline=format_date(self.env, self.date_deadline)))

    def _prepare_assembly(self, today):
        assembly = self._get_assembly()
        if assembly:
            self._link(assembly)
        return False, False  # a milestone: nothing to prepare

    def _prepare_minutes(self, today):
        assembly = self._get_assembly()
        if assembly:
            self._link(assembly)
        return (self.env._("Notulen AV %(year)s van %(vme)s bezorgen", year=self.year, vme=self.association_id.name),
                self.env._("Bezorg de notulen aan de eigenaars uiterlijk op %s.", format_date(self.env, self.date_deadline)))

    def _prepare_approved_budget(self, today):
        budget = self._get_budget()
        if budget:
            self._link(budget)
        return (self.env._("Goedgekeurd budget %(year)s van %(vme)s verwerken", year=self.year, vme=self.association_id.name),
                self.env._("Pas het budget aan de beslissing van de AV aan; de volgende provisieoproepen volgen het budget."))

    def _prepare_provision(self, today):
        vme = self.association_id.sudo()
        call = self._get_provision_call()
        if not call:
            budget = self._get_budget()
            if not budget:
                raise UserError(self.env._("Er is geen budget %s: maak het eerst, dan kan de oproep klaargezet worden.", self.year))
            invoice_date = self.date_deadline
            wizard = self.env["vme.provision.call.wizard"].sudo().create({
                "association_ids": [Command.set(vme.ids)],
                "year": self.year,
                "number": self.sequence,
                "invoice_date": invoice_date,
                "date_due": invoice_date + timedelta(days=PROVISION_DUE_DAYS),
                "post_invoices": False,  # drafts only: a human posts them
            })
            call = wizard._create_call(vme, budget).vme_provision_call_id
        self._link(call)
        return (self.env._("Provisieoproep %(number)s/%(total)s %(year)s van %(vme)s nakijken en boeken",
                           number=self.sequence, total=self.sequence_total, year=self.year, vme=vme.name),
                self.env._("%(count)s conceptfacturen staan klaar. Kijk ze na en boek ze; daarna kunnen ze verstuurd worden.",
                           count=len(call.invoice_ids)))

    # Actions

    def action_prepare_now(self):
        self._prepare()

    def action_mark_done(self):
        self._mark_done()

    def action_skip(self):
        self.write({"state": "skipped"})
        self.with_context(vme_cycle_closing=True).activity_ids.action_feedback(
            feedback=self.env._("Niet van toepassing."))

    def action_reopen(self):
        self.write({"state": "pending", "done_date": False, "prepared_date": False})

    def action_open_record(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    @api.model
    def _cron_run_cycle(self):
        self.env["vme.association"].search([("cycle_start_date", "!=", False)])._cycle_sync()


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    cycle_start_date = fields.Date(
        string="Jaarcyclus vanaf",
        help="Vanaf deze datum zet Odoo de stappen van het jaar klaar. Stappen met een termijn ervoor "
             "worden niet aangemaakt. Leeg: geen jaarcyclus.",
    )
    cycle_user_id = fields.Many2one(
        "res.users", string="Verantwoordelijke jaarcyclus", domain="[('share', '=', False)]",
        help="Krijgt de taken van de jaarcyclus. Leeg: de dossierbeheerder van de VME.",
    )
    cycle_step_ids = fields.One2many("vme.cycle.step", "association_id", string="Jaarcyclus")
    cycle_current_step = fields.Char(string="Volgende stap", compute="_compute_cycle_status")
    cycle_late_count = fields.Integer(string="Stappen te laat", compute="_compute_cycle_status")

    @api.depends("cycle_step_ids.state", "cycle_step_ids.date_deadline", "cycle_step_ids.date_ready")
    @api.depends_context("vme_today")
    def _compute_cycle_status(self):
        today = self.env["vme.cycle.step"]._today()
        for vme in self:
            steps = vme.sudo().cycle_step_ids.filtered(lambda s: s.state in ("pending", "ready"))
            late = steps.filtered(lambda s: s._is_late(today))
            vme.cycle_late_count = len(late)
            vme.cycle_current_step = vme._cycle_step_label(steps, late, today) if steps else False

    def _cycle_step_label(self, steps, late, today):
        if late:
            step = late.sorted("date_deadline")[0]
            return self.env._("Te laat: %(step)s (uiterlijk %(date)s)",
                              step=step.name, date=format_date(self.env, step.date_deadline))
        ready = steps.filtered(lambda s: s.state == "ready")
        if ready:
            step = ready.sorted("date_deadline")[0]
            return self.env._("Klaargezet: %(step)s (uiterlijk %(date)s)",
                              step=step.name, date=format_date(self.env, step.date_deadline))
        step = steps.sorted(lambda s: (s.date_ready, s.date_deadline))[0]
        return self.env._("Vanaf %(date)s: %(step)s", step=step.name, date=format_date(self.env, step.date_ready))

    def _get_building_card_data(self, today=None):
        data = super()._get_building_card_data(today=today)
        if not self.cycle_start_date:
            data["cycle_steps"] = None  # no cycle: the building card hides the block
            return data
        data["cycle_steps"] = self.sudo().cycle_step_ids.filtered(
            lambda s: s.state in ("pending", "ready")).sorted("date_deadline")[:8]
        return data

    def _cycle_default_user(self):
        self.ensure_one()
        return self.cycle_user_id or self._vme_task_user()

    # Hooks for other steps

    def _cycle_fiscal_year_closed(self, year):
        """True when the fiscal year is closed. Standard Odoo: the lock date of the VME's company.

        The closing of the fiscal year (built in its own step) can override this hook.
        """
        self.ensure_one()
        lock_date = self.sudo().company_id.fiscalyear_lock_date
        return bool(lock_date and lock_date >= date(year, 12, 31))

    def _cycle_syndic_renewal_due(self, year):
        """True when the mandate of the syndic ends before the ordinary assembly of the next year.

        Without a mandate of the syndic in this module, never. The fee and mandate of the syndic
        (built in its own step) overrides this hook.
        """
        self.ensure_one()
        return False

    # Calendar

    def _cycle_plan(self, year):
        """The fixed steps of the given year with their dates: a list of value dicts."""
        self.ensure_one()
        vme = self.sudo()
        plan = []

        def add(code, ready, deadline, **extra):
            plan.append({"code": code, "sequence": 0, "date_ready": min(ready, deadline),
                         "date_deadline": deadline, **extra})

        start, end = vme._get_assembly_period(year)
        if start:
            assembly = self.env["vme.assembly"].sudo().search([
                ("association_id", "=", vme.id), ("year", "=", year), ("assembly_type", "=", "ordinary"),
                ("state", "!=", "cancelled")], limit=1)
            # LEGAL-CHECK: art. 3.87 §3 BW - convocation at least fifteen days before the meeting.
            if assembly.date:
                last_convocation, held = assembly.convocation_deadline, assembly.date
            else:
                last_convocation, held = end - timedelta(days=vme.convocation_days), end
            jan_first = date(year, 1, 1)
            add("closing", jan_first, last_convocation - timedelta(days=CLOSING_BEFORE_CONVOCATION))
            add("statement", jan_first, last_convocation - timedelta(days=STATEMENT_BEFORE_CONVOCATION))
            add("budget", last_convocation - timedelta(days=BUDGET_READY_BEFORE_CONVOCATION),
                last_convocation - timedelta(days=BUDGET_BEFORE_CONVOCATION))
            add("planning", start - timedelta(days=PLANNING_READY_BEFORE_PERIOD),
                last_convocation - timedelta(days=URGENT_MARGIN_DAYS))
            add("agenda", last_convocation - timedelta(days=AGENDA_READY_BEFORE_CONVOCATION), last_convocation)
            add("convocation", last_convocation - timedelta(days=CONVOCATION_READY_BEFORE), last_convocation)
            # LEGAL-CHECK: art. 3.87 §2 BW - the ordinary assembly is held within its fifteen-day period.
            add("assembly", start, held)
            add("minutes", held, held + timedelta(days=MINUTES_AFTER_ASSEMBLY))
            add("approved_budget", held, held + timedelta(days=APPROVED_BUDGET_AFTER_ASSEMBLY))
        else:
            add("closing", date(year, 1, 1), date(year, *FALLBACK_CLOSING))
            add("statement", date(year, 1, 1), date(year, *FALLBACK_STATEMENT))

        budget = vme.budget_ids.filtered(lambda b: b.year == year)[:1]
        calls = int(budget.calls_per_year) if budget else 4
        months = 12 // calls
        for number in range(1, calls + 1):
            first_day = date(year, 1 + (number - 1) * months, 1)
            add("provision", first_day - timedelta(days=PROVISION_READY_BEFORE), first_day,
                sequence=number, sequence_total=calls)
        return plan

    def _cycle_ensure_steps(self, year):
        """Create the missing steps of the year and move the dates of the open ones."""
        Step = self.env["vme.cycle.step"].sudo()
        for vme in self.sudo():
            existing = {(s.code, s.sequence): s for s in Step.search(
                [("association_id", "=", vme.id), ("year", "=", year)])}
            plan = [v for v in vme._cycle_plan(year) if v["date_deadline"] >= vme.cycle_start_date]
            planned_keys = {(v["code"], v["sequence"]) for v in plan}
            to_create = []
            for values in plan:
                step = existing.get((values["code"], values["sequence"]))
                if not step:
                    to_create.append({"association_id": vme.id, "year": year, **values})
                elif step.state in ("pending", "ready"):
                    changes = {k: v for k, v in values.items() if k not in ("code", "sequence") and step[k] != v}
                    if changes:
                        step.write(changes)
            Step.create(to_create)
            # Fewer provision calls after a budget change: drop the calls that no longer exist.
            Step.browse([s.id for key, s in existing.items()
                         if key not in planned_keys and s.code == "provision" and s.state == "pending"]).unlink()

    def _cycle_sync(self, today=None):
        """Daily run: build the calendar of this and next year, close what is done, prepare what is due."""
        today = today or self.env["vme.cycle.step"]._today()
        Step = self.env["vme.cycle.step"].sudo().with_context(vme_today=today)
        for vme in self.sudo().with_context(vme_today=today).filtered("cycle_start_date"):
            for year in (today.year, today.year + 1):
                vme._cycle_ensure_steps(year)
            steps = Step.search([("association_id", "=", vme.id), ("state", "in", ("pending", "ready"))])
            steps._check_done()
            due = steps.filtered(lambda s: s.state == "pending" and s.date_ready <= today)
            for step in due.sorted(lambda s: (s.date_ready, s.id)):
                step._prepare(today)
            # A prepared step can complete an earlier one (the convocations carry the agenda).
            steps._check_done()

    def action_cycle_sync(self):
        self._cycle_sync()

    def action_open_cycle(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_cycle_step_action")
        action["domain"] = [("association_id", "in", self.ids)]
        action["context"] = {"search_default_open": 1}
        return action


class VmeAssembly(models.Model):
    _inherit = "vme.assembly"

    def _cycle_add_renewal_items(self):
        """Add the (re)appointments of the auditor and, when due, the syndic to the agenda. Returns the titles added."""
        self.ensure_one()
        wanted = []
        # LEGAL-CHECK: art. 3.91 BW - every year the general assembly appoints an auditor.
        if not self.item_ids.filtered(lambda i: "commissaris" in (i.name or "").lower() and "benoem" in i.name.lower()):
            wanted.append(AUDITOR_ITEM)
        # LEGAL-CHECK: art. 3.89 §1 BW - the syndic is appointed for at most three years, renewable
        # by the general assembly.
        if self.association_id._cycle_syndic_renewal_due(self.year) and not self.item_ids.filtered(
                lambda i: "syndicus" in (i.name or "").lower() and "benoem" in i.name.lower()):
            wanted.append(SYNDIC_RENEWAL_ITEM)
        sequence = max(self.item_ids.mapped("sequence") or [0])
        self.item_ids = [Command.create({"sequence": sequence + index, "name": title, "majority": "absolute"})
                         for index, title in enumerate(wanted, start=1)]
        return wanted


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def _action_done(self, feedback=False, attachment_ids=None):
        # Ticking off the task of a step that a human closes by hand closes the step.
        steps = self.env["vme.cycle.step"]
        if not self.env.context.get("vme_cycle_closing"):
            step_ids = [a.res_id for a in self if a.res_model == "vme.cycle.step"]
            steps = self.env["vme.cycle.step"].sudo().browse(step_ids).exists().filtered(
                lambda s: s.code in MANUAL_CODES and s.state in ("pending", "ready"))
        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        if steps:
            steps.write({"state": "done", "done_date": fields.Date.context_today(self)})
        return result
