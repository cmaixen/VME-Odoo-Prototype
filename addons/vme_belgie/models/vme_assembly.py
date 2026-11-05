import calendar
from datetime import date, datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date

# Blocks are entered in Belgian local time; Odoo stores datetimes in UTC.
LOCAL_TZ = pytz.timezone("Europe/Brussels")

# LEGAL-CHECK: art. 3.87 §2 BW - the ordinary general assembly takes place every year
# within the period of fifteen days fixed in the rules of co-ownership.
ASSEMBLY_PERIOD_DAYS = 15

# LEGAL-CHECK: art. 3.87 §3 BW - the convocation is sent at least fifteen days before the
# meeting, unless the rules of co-ownership set another term.
DEFAULT_CONVOCATION_DAYS = 15

# Warn this many days before the last day on which a convocation can still leave on time.
URGENT_MARGIN_DAYS = 30

MONTHS = [(str(m), name) for m, name in enumerate(
    ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
     "september", "oktober", "november", "december"], start=1)]


def local_to_utc(day, hour):
    """Naive UTC datetime for a local date and a float hour (19.5 = 19:30)."""
    local = datetime.combine(day, time()) + timedelta(hours=hour)
    return LOCAL_TZ.localize(local).astimezone(pytz.utc).replace(tzinfo=None)


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    # LEGAL-CHECK: art. 3.87 §2 BW - fifteen-day period from the rules of co-ownership.
    assembly_period_month = fields.Selection(MONTHS, string="AV-periode: maand")
    assembly_period_day = fields.Integer(string="AV-periode: vanaf dag", default=1)
    assembly_period_display = fields.Char(string="Periode gewone AV", compute="_compute_assembly_period_display")
    # LEGAL-CHECK: art. 3.87 §3 BW - at least 15 days unless the rules of co-ownership say otherwise.
    convocation_days = fields.Integer(
        string="Oproepingstermijn (dagen)", default=DEFAULT_CONVOCATION_DAYS,
        help="Aantal dagen tussen het versturen van de oproeping en de AV. Wettelijk minstens 15, "
             "tenzij het reglement van mede-eigendom anders bepaalt.",
    )
    assembly_ids = fields.One2many("vme.assembly", "association_id", string="Algemene vergaderingen")

    @api.depends("assembly_period_month", "assembly_period_day")
    def _compute_assembly_period_display(self):
        for vme in self:
            start, end = vme._get_assembly_period(2025)  # any non-leap year
            vme.assembly_period_display = (
                self.env._("%(start)s tot %(end)s", start=format_date(self.env, start, date_format="d MMMM"),
                           end=format_date(self.env, end, date_format="d MMMM"))
                if start else False
            )

    @api.constrains("assembly_period_month", "assembly_period_day", "convocation_days")
    def _check_assembly_period(self):
        for vme in self:
            if vme.assembly_period_month:
                # Checked against a non-leap year, so 29 February is refused.
                last_day = calendar.monthrange(2025, int(vme.assembly_period_month))[1]
                if not 1 <= vme.assembly_period_day <= last_day:
                    raise ValidationError(self.env._(
                        "De AV-periode moet beginnen op een dag tussen 1 en %s.", last_day))
            if vme.convocation_days < 1:
                raise ValidationError(self.env._("De oproepingstermijn moet minstens één dag zijn."))

    def _get_assembly_period(self, year):
        """(first day, last day) of the fifteen-day assembly period in the given year."""
        self.ensure_one()
        if not self.assembly_period_month or not self.assembly_period_day:
            return False, False
        start = date(year, int(self.assembly_period_month), self.assembly_period_day)
        return start, start + timedelta(days=ASSEMBLY_PERIOD_DAYS - 1)

    def action_open_assemblies(self):
        return self._action_open_related("vme.assembly", self.env._("Algemene vergaderingen"))


class ResUsers(models.Model):
    _inherit = "res.users"

    vme_max_assemblies_per_evening = fields.Integer(
        string="Max. AV's per avond", default=2,
        help="Hoeveel algemene vergaderingen deze medewerker op één avond mag leiden.",
    )


class VmeAssemblyRoom(models.Model):
    _name = "vme.assembly.room"
    _description = "Vergaderzaal"
    _order = "name"

    name = fields.Char(string="Zaal", required=True)
    address = fields.Char(string="Adres")
    capacity = fields.Integer(string="Aantal plaatsen")
    active = fields.Boolean(default=True)


class VmeAssemblySlot(models.Model):
    _name = "vme.assembly.slot"
    _description = "Blok voor algemene vergaderingen"
    _order = "date, time_start, id"

    date = fields.Date(string="Datum", required=True)
    time_start = fields.Float(string="Beginuur", required=True, default=19.0)
    assembly_duration = fields.Float(string="Duur per AV (uren)", required=True, default=2.0)
    location_type = fields.Selection(
        [("room", "Zaal"), ("online", "Online")], string="Waar", required=True, default="room"
    )
    room_id = fields.Many2one("vme.assembly.room", string="Zaal", ondelete="restrict")
    user_id = fields.Many2one(
        "res.users", string="Medewerker", required=True, default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )
    max_assemblies = fields.Integer(
        string="Max. AV's in dit blok", required=True, default=1,
        help="AV's in hetzelfde blok volgen elkaar op, elk met de duur per AV.",
    )
    datetime_start = fields.Datetime(string="Begin", compute="_compute_datetimes", store=True)
    datetime_end = fields.Datetime(string="Einde", compute="_compute_datetimes", store=True)
    assembly_ids = fields.One2many("vme.assembly", "slot_id", string="Algemene vergaderingen")
    assembly_count = fields.Integer(string="Gepland", compute="_compute_assembly_count")
    free_count = fields.Integer(string="Vrij", compute="_compute_assembly_count")
    note = fields.Char(string="Opmerking")

    _positive_capacity = models.Constraint(
        "CHECK (max_assemblies > 0 AND assembly_duration > 0)",
        "Een blok heeft minstens plaats voor één AV en een duur per AV.",
    )

    @api.depends("date", "time_start", "assembly_duration", "max_assemblies")
    def _compute_datetimes(self):
        for slot in self:
            if not slot.date:
                slot.datetime_start = slot.datetime_end = False
                continue
            slot.datetime_start = local_to_utc(slot.date, slot.time_start)
            slot.datetime_end = local_to_utc(slot.date, slot.time_start + slot.assembly_duration * slot.max_assemblies)

    @api.depends("assembly_ids.state", "max_assemblies")
    def _compute_assembly_count(self):
        for slot in self:
            slot.assembly_count = len(slot._active_assemblies())
            slot.free_count = slot.max_assemblies - slot.assembly_count

    @api.depends("date", "time_start", "location_type", "room_id", "user_id")
    def _compute_display_name(self):
        for slot in self:
            if not slot.date:
                slot.display_name = False
                continue
            hours, minutes = divmod(round(slot.time_start * 60), 60)
            where = slot.room_id.name if slot.location_type == "room" else self.env._("online")
            slot.display_name = f"{format_date(self.env, slot.date, date_format='EEE d MMM yyyy')} " \
                                f"{hours:02d}:{minutes:02d} - {where} ({slot.user_id.name})"

    def _active_assemblies(self):
        self.ensure_one()
        return self.assembly_ids.filtered(lambda a: a.state in ("proposed", "confirmed", "held"))

    @api.onchange("location_type")
    def _onchange_location_type(self):
        if self.location_type == "online":
            self.room_id = False

    @api.constrains("location_type", "room_id")
    def _check_room(self):
        for slot in self:
            if slot.location_type == "room" and not slot.room_id:
                raise ValidationError(self.env._("Kies een zaal of zet het blok op online."))

    @api.constrains("date", "time_start", "assembly_duration", "max_assemblies", "location_type", "room_id", "user_id")
    def _check_double_booking(self):
        """A room and an employee can only be in one block at a time."""
        for slot in self:
            overlapping = self.search([
                ("id", "!=", slot.id),
                ("datetime_start", "<", slot.datetime_end),
                ("datetime_end", ">", slot.datetime_start),
            ])
            if slot.location_type == "room" and overlapping.filtered(lambda o: o.room_id == slot.room_id):
                raise ValidationError(self.env._(
                    "Zaal %(room)s is op %(date)s al geboekt in een ander blok.",
                    room=slot.room_id.name, date=format_date(self.env, slot.date)))
            if overlapping.filtered(lambda o: o.user_id == slot.user_id):
                raise ValidationError(self.env._(
                    "%(user)s heeft op %(date)s al een ander blok op hetzelfde uur.",
                    user=slot.user_id.name, date=format_date(self.env, slot.date)))

    def write(self, vals):
        result = super().write(vals)
        if {"date", "time_start", "assembly_duration", "location_type", "room_id", "user_id"} & vals.keys():
            self.assembly_ids._check_slot_capacity()
            self.assembly_ids.filtered(lambda a: a.state == "confirmed")._sync_calendar_event()
        return result

    @api.constrains("max_assemblies")
    def _check_max_assemblies(self):
        self.assembly_ids._check_slot_capacity()


class VmeAssembly(models.Model):
    _name = "vme.assembly"
    _description = "Algemene vergadering"
    _inherit = ["mail.thread"]
    _order = "period_end, association_id"

    name = fields.Char(string="Naam", compute="_compute_name", store=True)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    year = fields.Integer(string="Jaar", required=True, default=lambda self: fields.Date.today().year + 1)
    period_start = fields.Date(string="Periode van", compute="_compute_period", store=True, readonly=False)
    period_end = fields.Date(string="Periode tot", compute="_compute_period", store=True, readonly=False)
    state = fields.Selection(
        [("draft", "Te plannen"), ("proposed", "Voorgesteld"), ("confirmed", "Bevestigd"),
         ("held", "Gehouden"), ("cancelled", "Geannuleerd")],
        string="Status", required=True, default="draft", tracking=True,
    )
    slot_id = fields.Many2one(
        "vme.assembly.slot", string="Blok", ondelete="restrict", tracking=True, index=True
    )
    slot_user_id = fields.Many2one(related="slot_id.user_id", string="Medewerker")
    location = fields.Char(string="Locatie", compute="_compute_location")
    datetime_start = fields.Datetime(string="Begin", compute="_compute_schedule", store=True)
    datetime_end = fields.Datetime(string="Einde", compute="_compute_schedule", store=True)
    date = fields.Date(string="Datum AV", compute="_compute_schedule", store=True)
    # LEGAL-CHECK: art. 3.87 §3 BW - convocation at least 15 days before the meeting.
    convocation_days = fields.Integer(related="association_id.convocation_days")
    convocation_deadline = fields.Date(
        string="Oproeping uiterlijk", compute="_compute_convocation_deadline", store=True,
        help="Laatste dag om de oproeping te versturen: datum van de AV min de oproepingstermijn.",
    )
    convocation_sent_date = fields.Date(string="Oproeping verstuurd op", tracking=True)
    warning = fields.Char(string="Waarschuwing", compute="_compute_warning")
    warning_level = fields.Selection(
        [("ok", "In orde"), ("warning", "Opletten"), ("danger", "Te laat")],
        string="Signaal", compute="_compute_warning", search="_search_warning_level",
    )
    calendar_event_id = fields.Many2one("calendar.event", string="Afspraak", readonly=True, copy=False)

    _unique_year_per_association = models.Constraint(
        "UNIQUE (association_id, year)",
        "Er bestaat al een gewone AV voor deze VME en dit jaar.",
    )

    @api.depends("association_id.name", "year")
    def _compute_name(self):
        for assembly in self:
            assembly.name = self.env._("Gewone AV %(year)s %(vme)s", year=assembly.year,
                                       vme=assembly.association_id.name or "")

    @api.depends("association_id.assembly_period_month", "association_id.assembly_period_day", "year")
    def _compute_period(self):
        for assembly in self:
            if assembly.association_id and assembly.year:
                assembly.period_start, assembly.period_end = assembly.association_id._get_assembly_period(assembly.year)
            else:
                assembly.period_start = assembly.period_end = False

    @api.depends("slot_id.datetime_start", "slot_id.assembly_duration", "slot_id.assembly_ids", "slot_id.date")
    def _compute_schedule(self):
        for assembly in self:
            slot = assembly.slot_id
            if not slot or not slot.datetime_start:
                assembly.datetime_start = assembly.datetime_end = assembly.date = False
                continue
            # Meetings in one block follow each other in the order they were planned.
            position = slot.assembly_ids.sorted("id").ids.index(assembly.id) if assembly.id in slot.assembly_ids.ids else 0
            assembly.datetime_start = slot.datetime_start + timedelta(hours=slot.assembly_duration * position)
            assembly.datetime_end = assembly.datetime_start + timedelta(hours=slot.assembly_duration)
            assembly.date = slot.date

    @api.depends("slot_id.room_id", "slot_id.location_type")
    def _compute_location(self):
        for assembly in self:
            slot = assembly.slot_id
            assembly.location = slot and (slot.room_id.name if slot.location_type == "room" else self.env._("Online"))

    @api.depends("date", "association_id.convocation_days")
    def _compute_convocation_deadline(self):
        for assembly in self:
            assembly.convocation_deadline = (
                assembly.date - timedelta(days=assembly.convocation_days) if assembly.date else False
            )

    @api.depends("state", "date", "period_start", "period_end", "convocation_deadline", "convocation_sent_date")
    @api.depends_context("vme_today")
    def _compute_warning(self):
        today = self._today()
        for assembly in self:
            assembly.warning, assembly.warning_level = assembly._get_warning(today)

    def _search_warning_level(self, operator, value):
        if operator not in ("in", "not in"):
            return NotImplemented
        open_assemblies = self.search([("state", "not in", ("held", "cancelled"))])
        matching = open_assemblies.filtered(lambda a: a.warning_level in value)
        return [("id", operator, matching.ids)]

    def _today(self):
        # Tests and the planner can pin "today" via the context.
        return self.env.context.get("vme_today") or fields.Date.context_today(self)

    def _get_warning(self, today):
        """(message, level) for the planning dashboard; (False, "ok") when all is well."""
        self.ensure_one()
        if self.state in ("held", "cancelled"):
            return False, "ok"
        if not self.period_start:
            return self.env._("De VME heeft geen AV-periode."), "warning"
        if not self.date:
            # Latest day on which the convocation can still leave for a meeting inside the period.
            last_convocation = self.period_end - timedelta(days=self.convocation_days)
            if today > last_convocation:
                return self.env._(
                    "Niet meer haalbaar: de oproeping had uiterlijk op %s moeten vertrekken om binnen de periode te vergaderen.",
                    format_date(self.env, last_convocation)), "danger"
            if today > last_convocation - timedelta(days=URGENT_MARGIN_DAYS):
                return self.env._(
                    "Dringend plannen: de oproeping moet uiterlijk op %s vertrekken.",
                    format_date(self.env, last_convocation)), "warning"
            return False, "ok"
        if self.convocation_sent_date and self.convocation_sent_date > self.convocation_deadline:
            return self.env._(
                "De oproeping vertrok te laat (%(sent)s, uiterlijk %(deadline)s).",
                sent=format_date(self.env, self.convocation_sent_date),
                deadline=format_date(self.env, self.convocation_deadline)), "danger"
        if not self.convocation_sent_date and today > self.convocation_deadline:
            return self.env._(
                "De oproeping zou te laat vertrekken: uiterlijk %s.",
                format_date(self.env, self.convocation_deadline)), "danger"
        if not self.period_start <= self.date <= self.period_end:
            return self.env._(
                "De AV valt buiten de periode van %(start)s tot %(end)s.",
                start=format_date(self.env, self.period_start), end=format_date(self.env, self.period_end)), "warning"
        return False, "ok"

    @api.constrains("slot_id", "state")
    def _check_slot_capacity(self):
        """No more meetings in a block than it holds, and no more per employee per evening."""
        for slot in self.slot_id:
            if len(slot._active_assemblies()) > slot.max_assemblies:
                raise ValidationError(self.env._(
                    "Het blok %(slot)s is vol (maximaal %(max)s AV's).", slot=slot.display_name, max=slot.max_assemblies))
            user = slot.user_id
            evening = self.search([
                ("slot_id.user_id", "=", user.id), ("slot_id.date", "=", slot.date),
                ("state", "in", ("proposed", "confirmed", "held")),
            ])
            if len(evening) > user.vme_max_assemblies_per_evening:
                raise ValidationError(self.env._(
                    "%(user)s mag maximaal %(max)s AV's per avond leiden (%(date)s).",
                    user=user.name, max=user.vme_max_assemblies_per_evening, date=format_date(self.env, slot.date)))

    def write(self, vals):
        if "slot_id" in vals and "state" not in vals:
            # Choosing a block by hand is an adjustment by the syndic: it counts as a proposal
            # until confirmed. Removing the block sends the meeting back to "to plan".
            if vals["slot_id"]:
                super(VmeAssembly, self.filtered(lambda a: a.state == "draft")).write({"state": "proposed"})
            else:
                super(VmeAssembly, self.filtered(lambda a: a.state in ("proposed", "confirmed"))).write({"state": "draft"})
                self.calendar_event_id.unlink()
        result = super().write(vals)
        if "slot_id" in vals:
            self.filtered(lambda a: a.state == "confirmed")._sync_calendar_event()
        return result

    # Actions

    def action_confirm(self):
        for assembly in self:
            if not assembly.slot_id:
                raise UserError(self.env._("Kies eerst een blok voor %s.", assembly.name))
        self.write({"state": "confirmed"})
        self._sync_calendar_event()

    def action_reset(self):
        self.calendar_event_id.unlink()
        self.write({"state": "draft", "slot_id": False})

    def action_mark_held(self):
        self.write({"state": "held"})

    def action_cancel(self):
        self.calendar_event_id.unlink()
        self.write({"state": "cancelled", "slot_id": False})

    def action_mark_convocation_sent(self):
        self.write({"convocation_sent_date": fields.Date.context_today(self)})

    def _sync_calendar_event(self):
        """Create or move the calendar meeting of each confirmed assembly."""
        model = self.env["ir.model"]._get_id(self._name)
        Event = self.env["calendar.event"].with_context(no_mail_to_attendees=True, dont_notify=True)
        for assembly in self:
            if not assembly.slot_id:
                assembly.calendar_event_id.unlink()
                continue
            slot = assembly.slot_id
            vals = {
                "name": assembly.name,
                "start": assembly.datetime_start,
                "stop": assembly.datetime_end,
                "user_id": slot.user_id.id,
                "partner_ids": [fields.Command.set(slot.user_id.partner_id.ids)],
                "location": slot.room_id.address and f"{slot.room_id.name}, {slot.room_id.address}" or assembly.location,
                "description": self.env._("Gewone algemene vergadering van %s.", assembly.association_id.name),
                "res_model_id": model,
                "res_id": assembly.id,
            }
            if assembly.calendar_event_id:
                assembly.calendar_event_id.with_context(no_mail_to_attendees=True, dont_notify=True).write(vals)
            else:
                assembly.calendar_event_id = Event.create(vals)

    def action_open_calendar_event(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "calendar.event",
            "res_id": self.calendar_event_id.id,
            "view_mode": "form",
        }

    # Planner

    @api.model
    def _create_missing_assemblies(self, year, associations=None):
        """One ordinary assembly per VME with an assembly period, if it does not exist yet."""
        associations = (associations or self.env["vme.association"].search([])).filtered("assembly_period_month")
        existing = self.search([("year", "=", year), ("association_id", "in", associations.ids)]).association_id
        return self.create([{"association_id": vme.id, "year": year} for vme in associations - existing])

    def _propose_schedule(self, today=None):
        """Put every assembly in self that is still to plan into a free block inside its period.

        Blocks are filled in date order; each block takes, among the assemblies it can host,
        the one whose period ends first. For assigning meetings to dates within their own
        interval, this earliest-deadline rule plans as many meetings as possible.
        Returns the assemblies that could not be planned.
        """
        today = today or self._today()
        todo = self.filtered(lambda a: a.state == "draft" and a.period_start)
        if not todo:
            return todo
        # A block is only usable if the convocation can still leave on time.
        slots = self.env["vme.assembly.slot"].search([
            ("date", ">=", min(todo.mapped("period_start"))),
            ("date", "<=", max(todo.mapped("period_end"))),
        ])
        planned_per_evening = {}  # (user, date) -> number of meetings
        for assembly in self.search([("slot_id", "in", slots.ids), ("state", "in", ("proposed", "confirmed", "held"))]):
            key = (assembly.slot_id.user_id, assembly.slot_id.date)
            planned_per_evening[key] = planned_per_evening.get(key, 0) + 1

        unplanned = todo
        for slot in slots:
            free = slot.max_assemblies - len(slot._active_assemblies())
            key = (slot.user_id, slot.date)
            while free > 0 and planned_per_evening.get(key, 0) < slot.user_id.vme_max_assemblies_per_evening:
                candidates = unplanned.filtered(
                    lambda a: a.period_start <= slot.date <= a.period_end
                    and slot.date - timedelta(days=a.convocation_days) >= today
                )
                if not candidates:
                    break
                chosen = candidates.sorted(lambda a: (a.period_end, a.association_id.name))[0]
                chosen.write({"slot_id": slot.id, "state": "proposed"})
                unplanned -= chosen
                free -= 1
                planned_per_evening[key] = planned_per_evening.get(key, 0) + 1
        for assembly in unplanned:
            assembly.message_post(body=self.env._(
                "Geen vrij blok gevonden tussen %(start)s en %(end)s. Voeg een blok toe of plan de AV met de hand.",
                start=format_date(self.env, assembly.period_start), end=format_date(self.env, assembly.period_end)))
        return unplanned
