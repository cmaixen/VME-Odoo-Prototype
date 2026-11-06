"""The general assembly itself: agenda, convocations, attendance, proxies, votes and minutes."""
import base64

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date

# LEGAL-CHECK: art. 3.88 §1-3 BW - required majorities. Abstentions, blank and invalid votes
# do not count as cast votes (art. 3.87 §8 BW). Unanimity is of all co-owners, not only
# those present (art. 3.88 §3 BW).
MAJORITIES = [
    ("none", "Geen stemming"),
    ("absolute", "Volstrekte meerderheid"),
    ("two_thirds", "Twee derde"),
    ("four_fifths", "Vier vijfde"),
    ("unanimous", "Eenparigheid"),
]
# (numerator, denominator, strict): votes for * denominator compared with cast votes * numerator.
MAJORITY_RULES = {
    "absolute": (1, 2, True),  # more than half
    "two_thirds": (2, 3, False),  # at least two thirds
    "four_fifths": (4, 5, False),  # at least four fifths
}

# LEGAL-CHECK: art. 3.87 §7 BW - nobody may hold more than three proxies, unless the votes
# they hold themselves plus those of their proxies do not exceed 10% of all votes.
MAX_PROXIES = 3
PROXY_VOTE_LIMIT = 0.10

# Standard points of an ordinary assembly: (title, majority). "{prev}" is the closed year.
DEFAULT_AGENDA = [
    ("Opening, vaststelling van het quorum en verkiezing van voorzitter en secretaris", "absolute"),
    ("Verslag van de syndicus over het voorbije jaar", "none"),
    ("Goedkeuring van de jaarrekening {prev}", "absolute"),
    ("Kwijting aan de syndicus en aan de commissaris van de rekeningen", "absolute"),
    ("Budget werkkapitaal en bijdrage reservekapitaal {year}", "absolute"),
    ("Benoeming van de commissaris van de rekeningen", "absolute"),
]

SHARE_FACTOR = 100  # shares have two decimals; votes are counted in hundredths to avoid float issues


def _units(shares):
    return round(shares * SHARE_FACTOR)


class VmeAssembly(models.Model):
    _inherit = "vme.assembly"

    item_ids = fields.One2many("vme.assembly.item", "assembly_id", string="Agenda", copy=True)
    attendee_ids = fields.One2many("vme.assembly.attendee", "assembly_id", string="Aanwezigheidslijst")
    convocation_ids = fields.One2many("vme.assembly.convocation", "assembly_id", string="Oproepingen")
    convocation_count = fields.Integer(compute="_compute_convocation_count")
    # LEGAL-CHECK: art. 3.87 §5 BW - without quorum a second assembly may be convened at least
    # fifteen days later; it deliberates whatever the number of members present.
    second_session = fields.Boolean(
        string="Tweede vergadering",
        help="Tweede vergadering na een eerste zonder quorum: er is geen quorumvereiste.",
    )
    owners_total = fields.Integer(string="Eigenaars", compute="_compute_quorum")
    owners_present = fields.Integer(string="Aanwezig of vertegenwoordigd", compute="_compute_quorum")
    shares_total = fields.Float(string="Quotiteiten totaal", compute="_compute_quorum")
    shares_present = fields.Float(string="Quotiteiten aanwezig", compute="_compute_quorum")
    quorum_reached = fields.Boolean(string="Quorum bereikt", compute="_compute_quorum")
    quorum_text = fields.Char(string="Quorum", compute="_compute_quorum")
    chair_id = fields.Many2one("res.partner", string="Voorzitter")
    secretary_id = fields.Many2one("res.partner", string="Secretaris")

    @api.model_create_multi
    def create(self, vals_list):
        assemblies = super().create(vals_list)
        for assembly in assemblies.filtered(lambda a: not a.item_ids):
            # An extraordinary assembly only gets the opening; its own points are added by hand.
            agenda = DEFAULT_AGENDA if assembly.assembly_type == "ordinary" else DEFAULT_AGENDA[:1]
            assembly.item_ids = [fields.Command.create({
                "sequence": index,
                "name": title.format(prev=assembly.year - 1, year=assembly.year),
                "majority": majority,
            }) for index, (title, majority) in enumerate(agenda, start=1)]
        return assemblies

    @api.depends("convocation_ids")
    def _compute_convocation_count(self):
        for assembly in self:
            assembly.convocation_count = len(assembly.convocation_ids)

    @api.depends("attendee_ids.attendance", "attendee_ids.shares", "second_session")
    def _compute_quorum(self):
        for assembly in self:
            attendees = assembly.attendee_ids
            present = attendees.filtered(lambda a: a.attendance in ("present", "represented"))
            assembly.owners_total = len(attendees)
            assembly.owners_present = len(present)
            assembly.shares_total = sum(attendees.mapped("shares"))
            assembly.shares_present = sum(present.mapped("shares"))
            assembly.quorum_reached = assembly._is_quorum_reached(
                len(attendees), len(present), _units(assembly.shares_total), _units(assembly.shares_present))
            assembly.quorum_text = self.env._(
                "%(owners)s van %(total)s eigenaars, %(shares)s van %(all)s quotiteiten",
                owners=len(present), total=len(attendees),
                shares="%g" % assembly.shares_present, all="%g" % assembly.shares_total,
            ) if attendees else False

    def _is_quorum_reached(self, owners_total, owners_present, shares_total, shares_present):
        """Quorum rule; shares in whole units."""
        self.ensure_one()
        if not owners_total:
            return False
        if self.second_session:
            return True
        # LEGAL-CHECK: art. 3.87 §5 BW - more than half of the co-owners holding at least half
        # of the shares, or co-owners holding more than three quarters of the shares.
        majority_of_owners = 2 * owners_present > owners_total and 2 * shares_present >= shares_total
        three_quarters = 4 * shares_present > 3 * shares_total
        return majority_of_owners or three_quarters

    def _get_owner_votes(self):
        """{partner: (lots, shares)} on the date of the assembly, from the general key."""
        self.ensure_one()
        on_date = self.date or self.period_start or fields.Date.context_today(self)
        key = self.association_id.key_ids.filtered(lambda k: k.key_type == "general")[:1]
        if not key:
            raise UserError(self.env._("%s heeft geen algemene verdeelsleutel.", self.association_id.name))
        # LEGAL-CHECK: art. 3.87 §6 BW - each co-owner votes with the shares of his lots in the common parts.
        result = {}
        for line in key.line_ids:
            owner = line.lot_id._get_owner_on(on_date)
            if not owner:
                continue
            lots, shares = result.get(owner, (self.env["vme.lot"], 0.0))
            result[owner] = (lots | line.lot_id, shares + line.shares)
        return result

    # Attendance and votes

    def action_create_attendance_list(self):
        for assembly in self:
            existing = assembly.attendee_ids.partner_id
            self.env["vme.assembly.attendee"].create([{
                "assembly_id": assembly.id,
                "partner_id": owner.id,
                "lot_names": ", ".join(lots.sorted("sequence").mapped("name")),
                "shares": shares,
            } for owner, (lots, shares) in assembly._get_owner_votes().items() if owner not in existing])

    def action_prepare_votes(self):
        """A vote line per present or represented owner on every point that is voted on."""
        for assembly in self:
            if not assembly.attendee_ids:
                raise UserError(self.env._("Maak eerst de aanwezigheidslijst."))
            assembly.item_ids.filtered(lambda i: i.majority != "none")._prepare_votes()

    # Convocations

    def action_create_convocations(self):
        """Draft convocation per owner with its PDF; nothing is sent."""
        self.ensure_one()
        if not self.date:
            raise UserError(self.env._("Plan de AV eerst in een blok: de oproeping vermeldt datum, uur en plaats."))
        if not self.item_ids:
            raise UserError(self.env._("De agenda is leeg."))
        existing = self.convocation_ids.partner_id
        convocations = self.env["vme.assembly.convocation"].create([{
            "assembly_id": self.id,
            "partner_id": owner.id,
            "lot_names": ", ".join(lots.sorted("sequence").mapped("name")),
            "shares": shares,
        } for owner, (lots, shares) in self._get_owner_votes().items() if owner not in existing])
        convocations._generate_documents()
        # LEGAL-CHECK: art. 3.87 §3 BW - convocation at least fifteen days before the meeting.
        late = self._today() > self.convocation_deadline
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Oproepingen klaar als concept"),
                "message": self.env._(
                    "%(count)s oproepingen aangemaakt. Let op: de uiterste datum (%(deadline)s) is voorbij.",
                    count=len(convocations), deadline=format_date(self.env, self.convocation_deadline),
                ) if late else self.env._(
                    "%(count)s oproepingen aangemaakt. Verstuur ze uiterlijk op %(deadline)s.",
                    count=len(convocations), deadline=format_date(self.env, self.convocation_deadline)),
                "type": "warning" if late else "success",
                "sticky": late,
                "next": self.action_open_convocations(),
            },
        }

    def action_open_convocations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Oproepingen"),
            "res_model": "vme.assembly.convocation",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("assembly_id", "=", self.id)],
        }

    # Closing and minutes

    def action_mark_held(self):
        for assembly in self:
            pending = assembly.item_ids.filtered(lambda i: i.outcome == "pending")
            if pending:
                raise UserError(self.env._(
                    "Er is nog niet gestemd over: %s", ", ".join(pending.mapped("name"))))
        result = super().action_mark_held()
        self._register_decisions()
        return result

    def _register_decisions(self):
        """Number the decisions per VME and year, and create a follow-up task per adopted decision."""
        # LEGAL-CHECK: art. 3.93 §4 BW - the syndic keeps a register of the decisions of the general assembly.
        Item = self.env["vme.assembly.item"]
        for assembly in self:
            decided = assembly.item_ids.filtered(lambda i: i.outcome in ("adopted", "rejected") and not i.decision_number)
            taken = Item.search_count([
                ("association_id", "=", assembly.association_id.id), ("year", "=", assembly.year),
                ("decision_number", "!=", False)])
            for number, item in enumerate(decided.sorted("sequence"), start=taken + 1):
                item.decision_number = f"{assembly.year}/{number:02d}"
            for item in decided.filtered(lambda i: i.outcome == "adopted" and i.follow_up_summary):
                item.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=item.follow_up_deadline or fields.Date.context_today(self),
                    summary=item.follow_up_summary,
                    note=self.env._("Beslissing %(number)s van de AV van %(vme)s.",
                                    number=item.decision_number, vme=assembly.association_id.name),
                    user_id=(item.follow_up_user_id or assembly.slot_user_id or self.env.user).id,
                )

    def action_print_minutes(self):
        # LEGAL-CHECK: art. 3.87 §10 BW - the syndic writes the minutes, signed at the end of the
        # meeting by the chair, the secretary and the co-owners still present.
        return self.env.ref("vme_belgie.action_report_assembly_minutes").report_action(self)


class VmeAssemblyItem(models.Model):
    _name = "vme.assembly.item"
    _description = "Agendapunt algemene vergadering"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "assembly_id, sequence, id"

    assembly_id = fields.Many2one("vme.assembly", string="AV", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="assembly_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="assembly_id.company_id", store=True)
    year = fields.Integer(related="assembly_id.year", store=True)
    assembly_date = fields.Date(related="assembly_id.date", string="Datum AV")
    sequence = fields.Integer(string="Nr.", default=10)
    name = fields.Char(string="Agendapunt", required=True)
    description = fields.Text(string="Toelichting")
    majority = fields.Selection(MAJORITIES, string="Vereiste meerderheid", required=True, default="absolute")
    vote_ids = fields.One2many("vme.assembly.vote", "item_id", string="Stemmen")
    votes_for = fields.Float(string="Voor", compute="_compute_outcome", store=True)
    votes_against = fields.Float(string="Tegen", compute="_compute_outcome", store=True)
    votes_abstain = fields.Float(string="Onthouding", compute="_compute_outcome", store=True)
    outcome = fields.Selection(
        [("info", "Geen stemming"), ("pending", "Nog te stemmen"), ("adopted", "Aangenomen"),
         ("rejected", "Verworpen"), ("no_quorum", "Geen quorum")],
        string="Uitslag", compute="_compute_outcome", store=True,
    )
    decision = fields.Text(string="Beslissing")
    decision_number = fields.Char(string="Nr. beslissing", readonly=True, copy=False)
    follow_up_summary = fields.Char(string="Opvolgtaak", help="bv. Offertes vragen voor de dakwerken")
    follow_up_user_id = fields.Many2one("res.users", string="Opvolging door", domain="[('share', '=', False)]")
    follow_up_deadline = fields.Date(string="Opvolgen tegen")

    @api.depends("majority", "vote_ids.vote", "vote_ids.attendee_id.attendance", "vote_ids.attendee_id.shares",
                 "assembly_id.attendee_ids.attendance", "assembly_id.attendee_ids.shares", "assembly_id.second_session")
    def _compute_outcome(self):
        for item in self:
            counted = item._count_votes()
            item.votes_for = counted["for"] / SHARE_FACTOR
            item.votes_against = counted["against"] / SHARE_FACTOR
            item.votes_abstain = counted["abstain"] / SHARE_FACTOR
            item.outcome = item._get_outcome(counted)

    def _count_votes(self):
        """Votes per answer in hundredths of a share, for present or represented owners only."""
        self.ensure_one()
        attendees = self.assembly_id.attendee_ids.filtered(lambda a: a.attendance in ("present", "represented"))
        present_units = sum(_units(a.shares) for a in attendees)
        counted = {"for": 0, "against": 0, "abstain": 0}
        for vote in self.vote_ids.filtered(lambda v: v.attendee_id in attendees):
            units = _units(vote.attendee_id.shares)
            # LEGAL-CHECK: art. 3.87 §6 BW - nobody votes with more votes than all other
            # present or represented co-owners together.
            units = min(units, present_units - units)
            counted[vote.vote] += units
        return counted

    def _get_outcome(self, counted):
        self.ensure_one()
        if self.majority == "none":
            return "info"
        if not self.vote_ids:
            return "pending"
        assembly = self.assembly_id
        if not assembly.quorum_reached:
            return "no_quorum"
        votes_for, cast = counted["for"], counted["for"] + counted["against"]
        if self.majority == "unanimous":
            # LEGAL-CHECK: art. 3.88 §3 BW - unanimity of the votes of all co-owners.
            all_units = sum(_units(a.shares) for a in assembly.attendee_ids)
            return "adopted" if votes_for == all_units else "rejected"
        numerator, denominator, strict = MAJORITY_RULES[self.majority]
        if not cast:
            return "rejected"
        adopted = (votes_for * denominator > cast * numerator) if strict else (votes_for * denominator >= cast * numerator)
        return "adopted" if adopted else "rejected"

    def _prepare_votes(self):
        """A vote line in the room for every present or represented owner who does not vote through the portal."""
        Vote = self.env["vme.assembly.vote"]
        for item in self:
            attendees = item.assembly_id.attendee_ids.filtered(
                lambda a: a.attendance in ("present", "represented") and not a.votes_remotely)
            missing = attendees - item.vote_ids.attendee_id
            Vote.create([{"item_id": item.id, "attendee_id": a.id} for a in missing])

    def action_all_for(self):
        self._prepare_votes()
        self.vote_ids.filtered(lambda v: v.source == "room").vote = "for"

    def action_open_votes(self):
        self.ensure_one()
        self._prepare_votes()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "vme.assembly.item",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("vme_belgie.vme_assembly_item_view_form").id, "form")],
            "target": "new",
        }

    @api.depends("sequence", "name")
    def _compute_display_name(self):
        for item in self:
            item.display_name = f"{item.sequence}. {item.name}"


class VmeAssemblyAttendee(models.Model):
    _name = "vme.assembly.attendee"
    _description = "Aanwezigheid op een algemene vergadering"
    _order = "assembly_id, id"

    assembly_id = fields.Many2one("vme.assembly", string="AV", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one("res.partner", string="Eigenaar", required=True)
    lot_names = fields.Char(string="Kavels")
    shares = fields.Float(string="Quotiteiten", digits=(16, 2))
    attendance = fields.Selection(
        [("absent", "Afwezig"), ("present", "Aanwezig"), ("represented", "Volmacht")],
        string="Aanwezigheid", required=True, default="absent",
    )
    proxy_holder_id = fields.Many2one("res.partner", string="Volmachthouder")

    _unique_owner = models.Constraint(
        "UNIQUE (assembly_id, partner_id)", "Elke eigenaar staat maar één keer op de aanwezigheidslijst.")

    @api.constrains("attendance", "proxy_holder_id")
    def _check_proxy(self):
        for attendee in self:
            if attendee.attendance == "represented" and not attendee.proxy_holder_id:
                raise ValidationError(self.env._("Vul de volmachthouder in voor %s.", attendee.partner_id.name))
            if attendee.proxy_holder_id == attendee.partner_id:
                raise ValidationError(self.env._("Een eigenaar kan geen volmacht aan zichzelf geven."))
        for assembly in self.assembly_id:
            assembly.attendee_ids._check_proxy_limits()

    def _check_proxy_limits(self):
        """Proxies per holder within the legal limit (self: all attendees of one assembly)."""
        if not self:
            return
        total_units = sum(_units(a.shares) for a in self)
        represented = self.filtered(lambda a: a.attendance == "represented")
        for holder in represented.proxy_holder_id:
            proxies = represented.filtered(lambda a: a.proxy_holder_id == holder)
            if len(proxies) <= MAX_PROXIES:
                continue
            own = self.filtered(lambda a: a.partner_id == holder and a.attendance == "present")
            held_units = sum(_units(a.shares) for a in proxies | own)
            # LEGAL-CHECK: art. 3.87 §7 BW - more than three proxies only up to 10% of all votes.
            if held_units > PROXY_VOTE_LIMIT * total_units:
                raise ValidationError(self.env._(
                    "%(holder)s heeft %(count)s volmachten met samen %(share).1f%% van de stemmen. Meer dan %(max)s "
                    "volmachten mag alleen als dat (met de eigen stemmen) niet meer is dan 10%% van alle stemmen.",
                    holder=holder.name, count=len(proxies), share=100 * held_units / total_units, max=MAX_PROXIES))


class VmeAssemblyVote(models.Model):
    _name = "vme.assembly.vote"
    _description = "Stem op een agendapunt"
    _order = "item_id, attendee_id"

    item_id = fields.Many2one("vme.assembly.item", string="Agendapunt", required=True, ondelete="cascade", index=True)
    attendee_id = fields.Many2one("vme.assembly.attendee", string="Aanwezige", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="attendee_id.partner_id")
    lot_names = fields.Char(related="attendee_id.lot_names")
    shares = fields.Float(related="attendee_id.shares")
    attendance = fields.Selection(related="attendee_id.attendance")
    vote = fields.Selection(
        [("for", "Voor"), ("against", "Tegen"), ("abstain", "Onthouding")],
        string="Stem", required=True, default="for",
    )

    _unique_vote = models.Constraint("UNIQUE (item_id, attendee_id)", "Eén stem per eigenaar en agendapunt.")


class VmeAssemblyConvocation(models.Model):
    _name = "vme.assembly.convocation"
    _description = "Oproeping tot de algemene vergadering"
    _inherit = ["mail.thread"]
    _order = "assembly_id, id"

    assembly_id = fields.Many2one("vme.assembly", string="AV", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="assembly_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="assembly_id.company_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Eigenaar", required=True)
    email = fields.Char(related="partner_id.email")
    lot_names = fields.Char(string="Kavels")
    shares = fields.Float(string="Quotiteiten", digits=(16, 2))
    state = fields.Selection([("draft", "Concept"), ("sent", "Verstuurd")], string="Status",
                             default="draft", required=True, tracking=True)
    sent_date = fields.Date(string="Verstuurd op", readonly=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Bijlagen")

    _unique_owner = models.Constraint(
        "UNIQUE (assembly_id, partner_id)", "Er bestaat al een oproeping voor deze eigenaar.")

    @api.depends("partner_id.name", "assembly_id.name")
    def _compute_display_name(self):
        for convocation in self:
            convocation.display_name = self.env._(
                "Oproeping %(owner)s", owner=convocation.partner_id.name or "")

    def _generate_documents(self):
        """Convocation with agenda and proxy form, plus the owner's annual statement of last year."""
        Report = self.env["ir.actions.report"]
        for convocation in self:
            assembly = convocation.assembly_id
            content, _ext = Report._render_qweb_pdf("vme_belgie.action_report_assembly_convocation", convocation.ids)
            attachments = self.env["ir.attachment"].create({
                "name": f"Oproeping AV {assembly.year} {assembly.association_id.name} - {convocation.partner_id.name}.pdf",
                "datas": base64.b64encode(content),
                "res_model": convocation._name,
                "res_id": convocation.id,
                "mimetype": "application/pdf",
            })
            statement = self.env["vme.annual.statement.wizard"].create({
                "association_id": assembly.association_id.id,
                "year": assembly.year - 1,
                "partner_ids": [fields.Command.set(convocation.partner_id.ids)],
            })
            if assembly.assembly_type == "ordinary" and statement._get_statement()["statements"]:
                content, _ext = Report._render_qweb_pdf("vme_belgie.action_report_annual_statement", statement.ids)
                attachments |= self.env["ir.attachment"].create({
                    "name": f"Jaarafrekening {assembly.year - 1} - {convocation.partner_id.name}.pdf",
                    "datas": base64.b64encode(content),
                    "res_model": convocation._name,
                    "res_id": convocation.id,
                    "mimetype": "application/pdf",
                })
            convocation.attachment_ids = [fields.Command.set(attachments.ids)]

    def action_open_composer(self):
        """Open the mail composer with the documents; the employee checks and sends it."""
        self.ensure_one()
        assembly = self.assembly_id
        if assembly.assembly_type == "ordinary":
            body = self.env._(
                "<p>Beste %(owner)s,</p><p>Als eigenaar van %(lots)s nodigen wij u uit op de gewone algemene "
                "vergadering van %(vme)s op %(date)s in %(place)s. In bijlage vindt u de oproeping met de agenda, "
                "een volmachtformulier en uw jaarafrekening.</p>",
                owner=self.partner_id.name, lots=self.lot_names, vme=assembly.association_id.name,
                date=format_date(self.env, assembly.date), place=assembly.location,
            )
        else:
            body = self.env._(
                "<p>Beste %(owner)s,</p><p>Als eigenaar van %(lots)s nodigen wij u uit op een buitengewone algemene "
                "vergadering van %(vme)s op %(date)s in %(place)s. In bijlage vindt u de oproeping met de agenda "
                "en een volmachtformulier.</p>",
                owner=self.partner_id.name, lots=self.lot_names, vme=assembly.association_id.name,
                date=format_date(self.env, assembly.date), place=assembly.location,
            )
        if assembly.online_url:
            # LEGAL-CHECK: art. 3.87 §1 BW - the convocation states how to take part at a distance.
            body += self.env._(
                "<p>U kunt ook online deelnemen en stemmen. Gebruik op de avond van de vergadering deze link en "
                "meld u aan in het eigenaarsportaal: <a href=\"%(url)s\">%(url)s</a>.</p>", url=assembly.online_url)
        if assembly.item_ids.filtered("allow_advance_vote"):
            body += self.env._(
                "<p>Over sommige punten kunt u vooraf schriftelijk stemmen in het portaal, tot de vergadering begint.</p>")
        body += self.env._("<p>Met vriendelijke groeten,<br/>De syndicus</p>")
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": self._name,
                "default_res_ids": self.ids,
                "default_composition_mode": "comment",
                "default_subject": self.env._("Oproeping %s", assembly.name),
                "default_body": body,
                "default_partner_ids": self.partner_id.ids,
                "default_attachment_ids": self.attachment_ids.ids,
                "mark_convocation_as_sent": True,
            },
        }

    def message_post(self, **kwargs):
        # Only the composer opened from "Versturen" marks a convocation as sent.
        if self.env.context.get("mark_convocation_as_sent"):
            self.filtered(lambda c: c.state == "draft").action_mark_sent()
        return super().message_post(**kwargs)

    def action_mark_sent(self):
        today = fields.Date.context_today(self)
        self.write({"state": "sent", "sent_date": today})
        for assembly in self.assembly_id.filtered(lambda a: not a.convocation_sent_date):
            assembly.convocation_sent_date = today

    def action_print(self):
        return self.env.ref("vme_belgie.action_report_assembly_convocation").report_action(self)
