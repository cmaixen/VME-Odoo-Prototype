"""Digital and hybrid general assembly (step 24).

Owners take part online through the portal, vote electronically per agenda item, vote in writing
before the meeting where allowed, and sign the minutes electronically. Nothing here counts votes:
an online vote is an ordinary vme.assembly.vote with a source and a time, and the rules of step 11
(_count_votes, _get_outcome, quorum, proxy limits) stay the only place where votes are counted.

Portal users have no access rights on these models. The portal controller works as sudo, but only
through the methods below, which always take the logged-in partner and check what it may do.
"""
import hashlib
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError

# LEGAL-CHECK: art. 3.87 §1 BW - co-owners may take part in the general assembly at a distance
# (electronically) when the convocation provides for it; they count as present for quorum and votes.
MEETING_MODES = [
    ("in_person", "In de zaal"),
    ("hybrid", "Hybride (zaal en online)"),
    ("online", "Volledig online"),
]
ATTENDANCE_MODES = [("room", "In de zaal"), ("online", "Online"), ("written", "Schriftelijk vooraf")]
VOTE_SOURCES = [("room", "In de zaal"), ("online", "Online"), ("written", "Schriftelijk vooraf")]
VOTE_VALUES = ("for", "against", "abstain")


def sha256_hex(data):
    return hashlib.sha256(data or b"").hexdigest()


def attachment_sha256(attachment):
    """SHA-256 of the stored file. Read without bin_size: the web client sets it, and then a binary
    field returns its size as text instead of the content."""
    return sha256_hex(attachment.sudo().with_context(bin_size=False).raw) if attachment else False


class VmeAssembly(models.Model):
    _inherit = "vme.assembly"

    meeting_mode = fields.Selection(MEETING_MODES, string="Vorm", required=True, default="in_person", tracking=True)
    video_url = fields.Char(string="Videolink", help="Link naar de videovergadering (bv. Jitsi of Teams). "
                                                     "Eigenaars zien hem pas na hun aanmelding in het portaal.")
    online_token = fields.Char(string="Code online deelname", readonly=True, copy=False)
    online_url = fields.Char(string="Link online deelname", compute="_compute_online_url")
    online_open = fields.Boolean(string="Online onthaal open", readonly=True, copy=False, tracking=True)
    online_attendee_count = fields.Integer(string="Online aanwezig", compute="_compute_online_attendee_count")
    minutes_attachment_id = fields.Many2one("ir.attachment", string="Notulen ter ondertekening", readonly=True, copy=False)
    minutes_sha256 = fields.Char(string="SHA-256 van de notulen", compute="_compute_minutes_sha256")
    signature_ids = fields.One2many("vme.assembly.signature", "assembly_id", string="Handtekeningen")
    signature_state = fields.Selection(
        [("none", "Niet gevraagd"), ("pending", "Te ondertekenen"), ("signed", "Ondertekend"),
         ("invalid", "Ongeldig: PDF gewijzigd")],
        string="Ondertekening", compute="_compute_signature_state",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("meeting_mode", "in_person") != "in_person" and not vals.get("online_token"):
                vals["online_token"] = secrets.token_urlsafe(16)
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if vals.get("meeting_mode") in ("hybrid", "online"):
            for assembly in self.filtered(lambda a: not a.online_token):
                assembly.online_token = secrets.token_urlsafe(16)
        return result

    @api.depends("online_token", "meeting_mode")
    def _compute_online_url(self):
        base_url = self.get_base_url()
        for assembly in self:
            assembly.online_url = (
                f"{base_url}/av/{assembly.online_token}"
                if assembly.online_token and assembly.meeting_mode != "in_person" else False
            )

    @api.depends("attendee_ids.attendance_mode", "attendee_ids.attendance")
    def _compute_online_attendee_count(self):
        for assembly in self:
            assembly.online_attendee_count = len(assembly.attendee_ids.filtered(
                lambda a: a.attendance == "present" and a.attendance_mode == "online"))

    @api.depends("minutes_attachment_id", "minutes_attachment_id.raw")
    def _compute_minutes_sha256(self):
        # Always computed from the stored file itself, never remembered: a changed PDF has another hash.
        for assembly in self:
            assembly.minutes_sha256 = attachment_sha256(assembly.minutes_attachment_id)

    @api.depends("signature_ids.state", "signature_ids.document_sha256", "minutes_sha256")
    def _compute_signature_state(self):
        for assembly in self:
            current = assembly.signature_ids.filtered(lambda s: s.document_sha256 == assembly.minutes_sha256)
            if not assembly.signature_ids:
                assembly.signature_state = "none"
            elif assembly.signature_ids.filtered(lambda s: s.state == "signed") - current:
                assembly.signature_state = "invalid"
            elif current and all(s.state == "signed" for s in current):
                assembly.signature_state = "signed"
            else:
                assembly.signature_state = "pending"

    # Online meeting

    def _check_online(self):
        for assembly in self:
            if assembly.meeting_mode == "in_person":
                raise UserError(self.env._("%s is een vergadering in de zaal: zet de vorm op hybride of online.",
                                           assembly.name))
            if assembly.state != "confirmed":
                raise UserError(self.env._("Alleen een bevestigde AV kan online plaatsvinden."))

    def action_open_online(self):
        """Open the online reception: owners can now sign in through the portal."""
        self._check_online()
        for assembly in self:
            if not assembly.attendee_ids:
                assembly.action_create_attendance_list()
        self.online_open = True

    def action_close_online(self):
        self.online_open = False

    def action_mark_held(self):
        for assembly in self:
            open_items = assembly.item_ids.filtered(lambda i: i.voting_state == "open")
            if open_items:
                raise UserError(self.env._(
                    "Sluit eerst de stemming over: %s", ", ".join(open_items.mapped("name"))))
        self.filtered("online_open").online_open = False
        return super().action_mark_held()

    def _portal_attendee(self, partner):
        """The line of the owner on the attendance list, or an empty recordset."""
        self.ensure_one()
        return self.attendee_ids.filtered(lambda a: a.partner_id == partner._vme_owner())

    def _portal_voting_rights(self, partner):
        """Attendees for whom this partner may vote: itself when present, plus the owners it represents."""
        self.ensure_one()
        owner = partner._vme_owner()
        own = self.attendee_ids.filtered(lambda a: a.partner_id == owner and a.attendance == "present")
        # LEGAL-CHECK: art. 3.87 §7 BW - the proxy holder votes for the co-owners who gave a proxy.
        proxies = self.attendee_ids.filtered(lambda a: a.attendance == "represented" and a.proxy_holder_id == owner)
        return own | proxies

    def _portal_check_in(self, partner, ip_address):
        """Online sign-in of an owner: present, online, with time and IP."""
        self.ensure_one()
        attendee = self._portal_attendee(partner)
        if not attendee:
            raise UserError(self.env._("U staat niet op de aanwezigheidslijst van deze vergadering."))
        if not self.online_open:
            raise UserError(self.env._("Het online onthaal is nog niet open. De syndicus opent het bij de start."))
        if attendee.attendance == "represented":
            raise UserError(self.env._(
                "U hebt een volmacht gegeven aan %s. Neem contact op met de syndicus als u toch zelf wilt deelnemen.",
                attendee.proxy_holder_id.name))
        if attendee.attendance == "present" and attendee.attendance_mode == "online":
            return attendee
        attendee.write({
            "attendance": "present",
            "attendance_mode": "online",
            "checked_in_at": fields.Datetime.now(),
            "check_in_ip": ip_address,
        })
        return attendee

    # Minutes and signatures

    def action_prepare_signing(self):
        """Freeze the minutes as a PDF with its SHA-256 and ask chair, secretary and owners present to sign.

        Nothing is sent: the signers find the minutes in the portal. Preparing again after a change
        makes a new PDF; earlier signatures then no longer match and show as invalid.
        """
        for assembly in self:
            if assembly.state != "held":
                raise UserError(self.env._("De notulen worden ondertekend na de vergadering: zet de AV eerst op Gehouden."))
            if not assembly.chair_id or not assembly.secretary_id:
                raise UserError(self.env._("Vul eerst de voorzitter en de secretaris in."))
            content, _ext = self.env["ir.actions.report"]._render_qweb_pdf(
                "vme_belgie.action_report_assembly_minutes", assembly.ids)
            attachment = self.env["ir.attachment"].create({
                "name": f"Notulen {assembly.name}.pdf",
                "raw": content,
                "res_model": assembly._name,
                "res_id": assembly.id,
                "mimetype": "application/pdf",
            })
            assembly.minutes_attachment_id = attachment
            digest = assembly.minutes_sha256
            # Requests for an older version that nobody signed have no value for the audit trail.
            assembly.signature_ids.filtered(lambda s: s.state == "pending" and s.document_sha256 != digest).unlink()
            # LEGAL-CHECK: art. 3.87 §10 BW - the minutes are signed at the end of the meeting by the
            # chair, the secretary and the co-owners still present (in the room or online). Owners who
            # only voted in writing beforehand were not at the meeting.
            signers = [(assembly.chair_id, "chair"), (assembly.secretary_id, "secretary")]
            signers += [(a.partner_id, "owner") for a in assembly.attendee_ids
                        if a.attendance == "present" and a.attendance_mode != "written"]
            seen = set(assembly.signature_ids.filtered(lambda s: s.document_sha256 == digest).partner_id)
            vals = []
            for partner, role in signers:
                if partner in seen:
                    continue
                seen.add(partner)
                vals.append({"assembly_id": assembly.id, "partner_id": partner.id, "role": role,
                             "document_sha256": digest})
            self.env["vme.assembly.signature"].create(vals)

    def action_open_minutes_pdf(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "target": "new",
                "url": f"/web/content/{self.minutes_attachment_id.id}?download=true"}

    def _portal_signature(self, partner):
        """The open signature request of this partner for the current PDF."""
        self.ensure_one()
        return self.signature_ids.filtered(
            lambda s: s.partner_id == partner._vme_owner() and s.document_sha256 == self.minutes_sha256)[:1]


class VmeAssemblyItem(models.Model):
    _inherit = "vme.assembly.item"

    voting_state = fields.Selection(
        [("not_open", "Niet geopend"), ("open", "Stemming open"), ("closed", "Gesloten")],
        string="Elektronische stemming", required=True, default="not_open", copy=False, tracking=True,
    )
    voting_opened_at = fields.Datetime(string="Stemming geopend op", readonly=True, copy=False)
    voting_closed_at = fields.Datetime(string="Stemming gesloten op", readonly=True, copy=False)
    # LEGAL-CHECK: art. 3.87 §1 BW - written voting before the meeting, only where the law and the
    # rules of co-ownership allow it. Check per decision; the default is no.
    allow_advance_vote = fields.Boolean(
        string="Schriftelijk vooraf", help="Eigenaars mogen vóór de vergadering in het portaal stemmen over dit punt.")
    online_vote_count = fields.Integer(string="Online stemmen", compute="_compute_online_vote_count")

    @api.depends("vote_ids.source")
    def _compute_online_vote_count(self):
        for item in self:
            item.online_vote_count = len(item.vote_ids.filtered(lambda v: v.source in ("online", "written")))

    def action_open_voting(self):
        for item in self:
            item.assembly_id._check_online()
            if item.majority == "none":
                raise UserError(self.env._("Over %s wordt niet gestemd.", item.name))
            if item.voting_state != "not_open":
                raise UserError(self.env._("De stemming over %s is al geopend.", item.name))
            if not item.assembly_id.attendee_ids:
                raise UserError(self.env._("Maak eerst de aanwezigheidslijst."))
        self.write({"voting_state": "open", "voting_opened_at": fields.Datetime.now()})

    def action_close_voting(self):
        """Close the vote: from now on nobody votes on this item, online or in writing."""
        for item in self:
            if item.voting_state != "open":
                raise UserError(self.env._("De stemming over %s is niet open.", item.name))
        self.write({"voting_state": "closed", "voting_closed_at": fields.Datetime.now()})

    def _portal_vote_rights(self, partner):
        """(attendees the partner may vote for now, source) for this item; ([], False) if no vote is possible."""
        self.ensure_one()
        assembly = self.assembly_id
        Attendee = self.env["vme.assembly.attendee"]
        if self.majority == "none" or assembly.state != "confirmed":
            return Attendee, False
        if self.voting_state == "open":
            return assembly._portal_voting_rights(partner), "online"
        if self.voting_state == "not_open" and self.allow_advance_vote and not assembly.online_open:
            # Before the meeting: the owner itself (absent or already voting in writing) and its proxies.
            owner = partner._vme_owner()
            own = assembly.attendee_ids.filtered(
                lambda a: a.partner_id == owner and (a.attendance == "absent" or a.attendance_mode == "written"))
            proxies = assembly.attendee_ids.filtered(
                lambda a: a.attendance == "represented" and a.proxy_holder_id == owner)
            return own | proxies, "written"
        return Attendee, False

    def _portal_cast_votes(self, partner, choices, ip_address):
        """Record the votes of a partner: {attendee: "for"/"against"/"abstain"}. A vote is final."""
        self.ensure_one()
        rights, source = self._portal_vote_rights(partner)
        if not source:
            raise UserError(self.env._("Er kan nu niet gestemd worden over %s.", self.name))
        if not choices:
            raise UserError(self.env._("Kies voor, tegen of onthouding."))
        Vote = self.env["vme.assembly.vote"]
        already = self.vote_ids.attendee_id
        for attendee, vote in choices.items():
            if attendee not in rights:
                raise UserError(self.env._("U kunt niet stemmen voor %s.", attendee.partner_id.name))
            if vote not in VOTE_VALUES:
                raise UserError(self.env._("Ongeldige stem."))
            # LEGAL-CHECK: art. 3.87 §6-7 BW - one vote per co-owner, cast by the owner or by its proxy holder.
            if attendee in already:
                raise UserError(self.env._("Er is al gestemd voor %s over dit punt.", attendee.partner_id.name))
        now = fields.Datetime.now()
        if source == "written":
            # LEGAL-CHECK: art. 3.87 §1 BW - a co-owner who votes in writing beforehand counts as present.
            absent = self.env["vme.assembly.attendee"].concat(*choices).filtered(lambda a: a.attendance == "absent")
            absent.write({"attendance": "present", "attendance_mode": "written",
                          "checked_in_at": now, "check_in_ip": ip_address})
        return Vote.create([{
            "item_id": self.id,
            "attendee_id": attendee.id,
            "vote": vote,
            "source": source,
            "cast_at": now,
            "voter_partner_id": partner._vme_owner().id,
            "ip_address": ip_address,
        } for attendee, vote in choices.items()])


class VmeAssemblyAttendee(models.Model):
    _inherit = "vme.assembly.attendee"

    attendance_mode = fields.Selection(ATTENDANCE_MODES, string="Hoe")
    checked_in_at = fields.Datetime(string="Aangemeld op", readonly=True)
    check_in_ip = fields.Char(string="IP-adres aanmelding", readonly=True)
    votes_remotely = fields.Boolean(
        string="Stemt zelf online", compute="_compute_votes_remotely",
        help="Online of schriftelijk aanwezig, of vertegenwoordigd door iemand die online deelneemt: "
             "stemmen komen dan uit het portaal, niet uit de zaal.")

    @api.depends("attendance", "attendance_mode", "proxy_holder_id", "assembly_id.attendee_ids.attendance_mode")
    def _compute_votes_remotely(self):
        for attendee in self:
            if attendee.attendance == "represented":
                holder = attendee.assembly_id.attendee_ids.filtered(lambda a: a.partner_id == attendee.proxy_holder_id)
                attendee.votes_remotely = holder.attendance_mode in ("online", "written")
            else:
                attendee.votes_remotely = attendee.attendance == "present" and attendee.attendance_mode in ("online", "written")


class VmeAssemblyVote(models.Model):
    _inherit = "vme.assembly.vote"

    source = fields.Selection(VOTE_SOURCES, string="Hoe", required=True, default="room")
    cast_at = fields.Datetime(string="Tijdstip", readonly=True)
    voter_partner_id = fields.Many2one("res.partner", string="Gestemd door", readonly=True,
                                       help="De eigenaar zelf of zijn volmachthouder.")
    ip_address = fields.Char(string="IP-adres", readonly=True)

    # The audit trail: a vote from the portal is final and can no longer be changed or removed.
    LOCKED_SOURCES = ("online", "written")

    def write(self, vals):
        if self.filtered(lambda v: v.source in self.LOCKED_SOURCES):
            raise UserError(self.env._("Een online of schriftelijke stem kan niet meer gewijzigd worden."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda v: v.source in self.LOCKED_SOURCES):
            raise UserError(self.env._("Een online of schriftelijke stem kan niet verwijderd worden."))
        return super().unlink()


class VmeAssemblySignature(models.Model):
    _name = "vme.assembly.signature"
    _description = "Elektronische handtekening van de notulen"
    _order = "assembly_id, id"

    assembly_id = fields.Many2one("vme.assembly", string="AV", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one("res.partner", string="Ondertekenaar", required=True)
    role = fields.Selection([("chair", "Voorzitter"), ("secretary", "Secretaris"), ("owner", "Aanwezige eigenaar")],
                            string="Rol", required=True)
    document_sha256 = fields.Char(string="SHA-256 van de PDF", required=True, readonly=True,
                                  help="Hash van de notulen zoals ze ter ondertekening zijn klaargezet en ondertekend.")
    state = fields.Selection([("pending", "Te ondertekenen"), ("signed", "Ondertekend")],
                             string="Status", required=True, default="pending", readonly=True)
    signed_at = fields.Datetime(string="Ondertekend op", readonly=True)
    signed_name = fields.Char(string="Getypte naam", readonly=True)
    ip_address = fields.Char(string="IP-adres", readonly=True)
    user_agent = fields.Char(string="Browser", readonly=True)
    is_valid = fields.Boolean(string="Geldig", compute="_compute_is_valid",
                              help="Ondertekend, en de PDF is sindsdien niet gewijzigd.")

    @api.depends("state", "document_sha256", "assembly_id.minutes_sha256")
    def _compute_is_valid(self):
        for signature in self:
            signature.is_valid = signature.state == "signed" and signature.document_sha256 == signature.assembly_id.minutes_sha256

    def write(self, vals):
        if self.filtered(lambda s: s.state == "signed"):
            raise UserError(self.env._("Een handtekening kan na het ondertekenen niet meer gewijzigd worden."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda s: s.state == "signed"):
            raise UserError(self.env._("Een handtekening hoort bij het auditspoor en kan niet verwijderd worden."))
        return super().unlink()

    def _portal_sign(self, partner, signed_name, ip_address, user_agent):
        """Sign the minutes: who, when, IP and the hash of the PDF that was really shown."""
        self.ensure_one()
        if self.partner_id != partner._vme_owner():
            raise UserError(self.env._("Deze handtekening is niet voor u."))
        if self.state != "pending":
            raise UserError(self.env._("U hebt deze notulen al ondertekend."))
        # The hash is recomputed from the stored PDF now: if it changed since it was prepared, nobody signs it.
        current = attachment_sha256(self.assembly_id.minutes_attachment_id)
        if current != self.document_sha256:
            raise UserError(self.env._("De notulen zijn gewijzigd sinds ze ter ondertekening klaargezet werden."))
        if not (signed_name or "").strip():
            raise UserError(self.env._("Typ uw naam om te ondertekenen."))
        self.write({
            "state": "signed",
            "signed_at": fields.Datetime.now(),
            "signed_name": signed_name.strip(),
            "ip_address": ip_address,
            "user_agent": (user_agent or "")[:250],
        })


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _vme_portal_assembly(self, assembly_id):
        """A confirmed or held assembly of a VME in which this partner is an owner on the attendance
        list (or a current owner, before the list exists). Empty recordset otherwise."""
        self.ensure_one()
        assembly = self.env["vme.assembly"].sudo().browse(assembly_id).exists()
        if not assembly or assembly.state not in ("confirmed", "held"):
            return self.env["vme.assembly"]
        if assembly._portal_attendee(self):
            return assembly
        today = fields.Date.context_today(self)
        current = self._vme_portal_ownerships().filtered(
            lambda o: o.association_id == assembly.association_id and (not o.date_end or o.date_end >= today))
        return assembly if current and not assembly.attendee_ids else self.env["vme.assembly"]

    def _vme_portal_assemblies_to_sign(self, association):
        """Held assemblies of this VME where this partner still has to sign the current minutes."""
        self.ensure_one()
        signatures = self.env["vme.assembly.signature"].sudo().search([
            ("partner_id", "=", self._vme_owner().id), ("state", "=", "pending"),
            ("assembly_id.association_id", "=", association.id)])
        return signatures.filtered(lambda s: s.document_sha256 == s.assembly_id.minutes_sha256).assembly_id
