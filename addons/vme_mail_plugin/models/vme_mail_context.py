"""What the Outlook add-in shows next to a mail: who sent it, which VME and lot, what is open, and the
AI proposal for it. Everything runs as the logged-in user, under the company and auditor rules."""
import base64
import email
import email.policy
import email.utils
import re
from pathlib import Path

from lxml import html as lxml_html
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_normalize
from odoo.tools.misc import file_path

from odoo.addons.vme_belgie.models.vme_access import check_not_auditor
from odoo.addons.vme_belgie.models.vme_damage import CLOSED_STATES as CLAIM_CLOSED_STATES
from odoo.addons.vme_belgie.models.vme_request import CLOSED_STATES as REQUEST_CLOSED_STATES
from odoo.addons.vme_belgie.models.vme_work_item import AI_SUMMARY_PREFIX

# Records a mail can be filed on (an internal note, see _vme_mail_log).
LOG_MODELS = ("vme.association", "vme.request", "vme.damage.claim")
# Text the AI assistant (ai/assistant.py) puts in front of the reply in its note on a request.
REQUEST_REPLY_PREFIX = "Voorgesteld antwoord van de AI-assistent"
# Labels in the activity note of ai/assistant.py (activity_note), mapped to the key in the proposal.
NOTE_LABELS = {"Kavel": "lot", "Onderwerp": "topic", "Dringendheid": "urgency", "Zekerheid koppeling": "confidence"}
# Fictitious demo mails, copies of ai/inbox/ (the Odoo container only mounts addons/).
DEMO_INBOX = "vme_mail_plugin/demo_data/inbox"
# Header names of a .txt demo mail (same as ai/mails.py).
TXT_HEADERS = {"van": "from", "from": "from", "onderwerp": "subject", "subject": "subject",
               "datum": "date", "date": "date", "message-id": "message_id"}


def mail_reference(message_id):
    """The key ai/assistant.py stores for a mail: the Message-ID without <>."""
    return (message_id or "").strip().strip("<>")


class VmeMailContext(models.AbstractModel):
    _name = "vme.mail.context"
    _description = "Mail in Outlook gekoppeld aan VME en kavel"

    # Context of one mail

    @api.model
    def _vme_mail_context(self, email_from, name="", subject="", message_id="", association_id=False, lot_id=False):
        """Everything the task pane shows for a mail.

        Without ``association_id`` the sender is looked up as owner or tenant on today's date in every
        VME the user can see. With it (the staff member picked a VME or lot after a search), that VME
        and lot are the only match.
        """
        if association_id:
            vme = self.env["vme.association"].browse(association_id).exists()
            lot = self.env["vme.lot"].browse(lot_id).exists() if lot_id else self.env["vme.lot"]
            matches = [self._vme_mail_manual_match(vme, lot)] if vme else []
        else:
            matches = self._vme_mail_matches(email_from)
        return {
            "sender": {"email": email_normalize(email_from or "") or email_from or "", "name": name or ""},
            "matches": matches,
            "proposal": self._vme_mail_proposal(message_id),
            "request_types": [{"code": t.code, "name": t.name}
                              for t in self.env["vme.request.type"].search([])],
            "can_write": not self.env.user.has_group("vme_belgie.group_vme_auditor"),
        }

    @api.model
    def _vme_mail_matches(self, email_from):
        """One match per VME and role in which this address is an owner or tenant today.

        Generalises vme.request._identify_in over all VMEs the user can see; an owner of several
        lots in one VME is one match with several lots.
        """
        normalized = email_normalize(email_from or "")
        if not normalized:
            return []
        today = fields.Date.context_today(self)
        # The addresses are compared as superuser: an auditor may not read tenants, but the sender's own
        # address is in the mail. Which lots and VMEs come back still follows the user's record rules.
        partners = self.env["res.partner"].sudo().with_context(active_test=False).search(
            [("email_normalized", "=", normalized)])
        if not partners:
            return []
        lots = self.env["vme.ownership"].search([("partner_id", "in", partners.ids)]).lot_id
        lots |= self.env["vme.lot.contact"].search([("partner_id", "in", partners.ids), ("role", "=", "tenant")]).lot_id
        found = {}
        for lot in lots.sorted(lambda l: (l.association_id.name, l.sequence, l.name)):
            owner = lot.sudo()._get_owner_on(today)
            people = [("owner", owner)] if owner.email_normalized == normalized else []
            people += [("tenant", tenant) for tenant in lot.sudo()._get_tenants_on(today)
                       if tenant.email_normalized == normalized]
            for role, partner in people:
                key = (lot.association_id, role, partner.sudo(False))
                found[key] = found.get(key, self.env["vme.lot"]) | lot
        return [self._vme_mail_match(vme, match_lots, role, partner)
                for (vme, role, partner), match_lots in found.items()]

    @api.model
    def _vme_mail_manual_match(self, vme, lot):
        """A VME or lot the staff member chose for an unknown sender; the owner is today's owner."""
        owner = lot._get_owner_on(fields.Date.context_today(self)) if lot else self.env["res.partner"]
        return self._vme_mail_match(vme, lot, "manual", owner)

    @api.model
    def _vme_mail_match(self, vme, lots, role, partner):
        return {
            "vme": {"id": vme.id, "name": vme.name, "url": self._vme_mail_url(vme)},
            "lots": [{"id": lot.id, "name": lot.name, "url": self._vme_mail_url(lot)} for lot in lots],
            "role": role,
            "partner": self._vme_mail_partner(partner),
            "open_items": self._vme_mail_open_items(vme, lots, partner),
        }

    @api.model
    def _vme_mail_partner(self, partner):
        """Name and link of the owner or tenant, if the user may read the contact (an auditor not a tenant)."""
        if not partner:
            return False
        if not partner.has_access("read"):
            return {"id": partner.id, "name": "", "email": "", "url": False}
        return {"id": partner.id, "name": partner.name, "email": partner.email or "", "url": self._vme_mail_url(partner)}

    @api.model
    def _vme_mail_open_items(self, vme, lots, partner):
        """Overdue provisions, open requests and damage claims of this partner and these lots in this VME."""
        arrears = self.env["vme.arrears"]
        requests = self.env["vme.request"]
        if partner:
            arrears = arrears.search([("association_id", "=", vme.id), ("partner_id", "=", partner.id)])
        # Requests of this person, or about these lots (made from a mail of an address we did not know).
        who = ([("requester_id", "=", partner.id)] if partner else []) + ([("lot_id", "in", lots.ids)] if lots else [])
        if who:
            requests = requests.search([("association_id", "=", vme.id), ("state", "not in", REQUEST_CLOSED_STATES)]
                                       + (["|"] if len(who) == 2 else []) + who)
        claim_domain = [("association_id", "=", vme.id), ("state", "not in", CLAIM_CLOSED_STATES)]
        if lots and partner:
            claim_domain += ["|", ("lot_ids", "in", lots.ids), ("reporter_id", "=", partner.id)]
        elif lots:
            claim_domain += [("lot_ids", "in", lots.ids)]
        elif partner:
            claim_domain += [("reporter_id", "=", partner.id)]
        claims = self.env["vme.damage.claim"].search(claim_domain) if (lots or partner) else self.env["vme.damage.claim"]
        fund_labels = dict(arrears._fields["fund"]._description_selection(self.env))
        request_states = dict(requests._fields["state"]._description_selection(self.env))
        claim_states = dict(claims._fields["state"]._description_selection(self.env))
        return {
            "arrears": [{
                "name": line.move_name, "reference": line.payment_reference or "",
                "fund": fund_labels.get(line.fund, ""), "date_due": fields.Date.to_string(line.date_maturity),
                "days_overdue": line.days_overdue, "amount": line.amount_residual,
                "amount_text": self._vme_mail_amount(line.amount_residual, line.currency_id),
            } for line in arrears],
            "arrears_total": self._vme_mail_amount(sum(arrears.mapped("amount_residual")), vme.company_id.currency_id),
            "requests": [{"id": r.id, "name": r.display_name, "state": request_states.get(r.state, r.state),
                          "url": self._vme_mail_url(r)} for r in requests],
            "claims": [{"id": c.id, "name": c.name, "state": claim_states.get(c.state, c.state),
                        "url": self._vme_mail_url(c)} for c in claims],
        }

    # The AI proposal made earlier by ai/assistant.py

    @api.model
    def _vme_mail_proposal(self, message_id):
        """The AI proposal for this mail: a request made from it, or an "AI-voorstel" activity on the VME."""
        reference = mail_reference(message_id)
        if not reference:
            return False
        request = self.env["vme.request"].search([("source_reference", "=", reference)], limit=1)
        from_request = request and self._vme_mail_proposal_from_request(request)
        if from_request and from_request["reply_html"]:
            return from_request
        # A request made later from the pane carries no AI reply: the activity then still has it.
        activity = self.env["mail.activity"].search([
            ("res_model", "=", "vme.association"), ("summary", "=like", AI_SUMMARY_PREFIX + "%"),
            ("note", "ilike", reference)], limit=1)
        if activity:
            return self._vme_mail_proposal_from_activity(activity)
        return from_request or False

    @api.model
    def _vme_mail_proposal_from_request(self, request):
        note = request.message_ids.filtered(
            lambda m: REQUEST_REPLY_PREFIX in (m.body or "")).sorted("id")[:1]
        reply_html = ""
        if note:
            # The note is a bold title paragraph followed by the reply.
            tree = lxml_html.fragment_fromstring(str(note.body), create_parent="div")
            paragraphs = tree.findall("p")
            reply_html = "".join(lxml_html.tostring(p, encoding="unicode") for p in paragraphs[1:])
        return {
            "source": "request",
            "vme": {"id": request.association_id.id, "name": request.association_id.name},
            "lot": request.lot_id.name or "",
            "lot_id": request.lot_id.id,
            "topic": request.request_type_id.name,
            "confidence": "",
            "reason": "",
            "reply_subject": self.env._("Re: %s", request.title) if request.title else "",
            "reply_html": reply_html,
            "record": {"name": request.display_name, "url": self._vme_mail_url(request)},
        }

    @api.model
    def _vme_mail_proposal_from_activity(self, activity):
        vme = self.env["vme.association"].browse(activity.res_id)
        tree = lxml_html.fragment_fromstring(str(activity.note or ""), create_parent="div")
        values = {}
        for item in tree.iter("li"):
            label = item.findtext("b") or ""
            key = NOTE_LABELS.get(label.rstrip(":").strip())
            if key:
                values[key] = item.text_content().split(":", 1)[-1].strip()
        confidence, _sep, reason = values.get("confidence", "").partition("—")
        reply_subject, reply_html = "", ""
        for heading in tree.iter("h4"):
            title = heading.text_content()
            if title.startswith("Conceptantwoord:"):
                reply_subject = title.split(":", 1)[1].strip()
                quote = heading.getnext()
                if quote is not None and quote.tag == "blockquote":
                    reply_html = "".join(lxml_html.tostring(child, encoding="unicode") for child in quote)
                break
        lot = self.env["vme.lot"].search(
            [("association_id", "=", vme.id), ("name", "=", values.get("lot", ""))], limit=1) if values.get("lot") else None
        return {
            "source": "activity",
            "vme": {"id": vme.id, "name": vme.name},
            "lot": values.get("lot", ""),
            "lot_id": lot.id if lot else False,
            "topic": values.get("topic", ""),
            "urgency": values.get("urgency", ""),
            "confidence": confidence.strip(),
            "reason": reason.strip(),
            "reply_subject": reply_subject,
            "reply_html": reply_html,
            "record": {"name": activity.summary, "url": self._vme_mail_url(vme)},
        }

    # Unknown sender: search a VME or lot

    @api.model
    def _vme_mail_search(self, term, limit=20):
        term = (term or "").strip()
        if len(term) < 2:
            return []
        results = []
        for vme in self.env["vme.association"].search([("name", "ilike", term)], limit=limit):
            results.append({"association_id": vme.id, "lot_id": False, "name": vme.name})
        lots = self.env["vme.lot"].search(
            ["|", ("name", "ilike", term), ("association_id.name", "ilike", term)], limit=limit)
        # "Linde A4": the VME name and the lot name in one search term.
        words = term.split()
        if not lots and len(words) > 1:
            lots = self.env["vme.lot"].search([("association_id.name", "ilike", " ".join(words[:-1])),
                                               ("name", "=ilike", words[-1])], limit=limit)
        for lot in lots:
            owner = lot.current_owner_id
            results.append({"association_id": lot.association_id.id, "lot_id": lot.id,
                            "name": f"{lot.display_name}" + (f" ({owner.name})" if owner else "")})
        return results[:limit]

    # Actions from the task pane; nothing is sent

    @api.model
    def _vme_mail_log(self, model, res_id, subject, email_from, name, body, mail_date="", attachments=None):
        """File the mail on the VME, request or damage claim as an internal note: followers get no mail.

        ``attachments`` is a list of {"name", "datas" (base64), "mimetype"}.
        """
        check_not_auditor(self.env)
        if model not in LOG_MODELS:
            raise UserError(self.env._("Een mail kan alleen bij een VME, aanvraag of schadedossier bewaard worden."))
        record = self.env[model].browse(res_id).exists()
        if not record:
            raise UserError(self.env._("Dit dossier bestaat niet meer."))
        record.check_access("write")
        sender = f"{name} <{email_from}>" if name else email_from
        message = record.message_post(
            body=Markup("<p><b>%s</b></p><p>%s</p><p>%s</p>") % (
                self.env._("Mail bewaard vanuit Outlook"),
                Markup("<br/>").join([self.env._("Van: %s", sender), self.env._("Onderwerp: %s", subject)]
                                     + ([self.env._("Datum: %s", mail_date)] if mail_date else [])),
                Markup("<br/>").join((body or "").splitlines())),
            attachments=[(att["name"], base64.b64decode(att["datas"])) for att in attachments or []],
            message_type="comment", subtype_xmlid="mail.mt_note",
        )
        return {"message_id": message.id, "url": self._vme_mail_url(record)}

    @api.model
    def _vme_mail_request(self, association_id, request_type, email_from, name="", lot_id=False, subject="",
                          body="", message_id="", attachments=None):
        """Create a request from the mail; its procedure prepares drafts and to-dos, nothing is sent."""
        check_not_auditor(self.env)
        Request = self.env["vme.request"]
        Request.check_access("create")
        request_id = Request.create_from_intake(
            association_id, request_type, email_from, name=name, lot_id=lot_id, subject=subject, body=body,
            channel="mail", reference=mail_reference(message_id), attachments=attachments)
        request = Request.browse(request_id)
        return {"id": request.id, "name": request.display_name, "url": self._vme_mail_url(request)}

    # Helpers

    @api.model
    def _vme_mail_url(self, record):
        """Backend URL of a record on this instance, opened in the browser from the task pane."""
        return f"{self._vme_mail_base_url()}/odoo/{record._name}/{record.id}"

    @api.model
    def _vme_mail_base_url(self):
        """Address of this Odoo for Outlook: the HTTPS address if one is set, else web.base.url."""
        params = self.env["ir.config_parameter"].sudo()
        return (params.get_param("vme_mail_plugin.base_url") or params.get_param("web.base.url") or "").rstrip("/")

    @api.model
    def _vme_mail_amount(self, amount, currency):
        return f"{currency.symbol or ''} {amount:,.2f}".replace(",", " ").replace(".", ",").strip()

    # Demo: the fictitious mails of ai/inbox/ for the browser preview

    @api.model
    def _vme_mail_demo_inbox(self):
        """The demo mails as the task pane reads them from Outlook."""
        folder = Path(file_path(DEMO_INBOX))
        return [self._vme_mail_read_demo(path) for path in sorted(folder.iterdir())
                if path.suffix.lower() in (".eml", ".txt")]

    @api.model
    def _vme_mail_read_demo(self, path):
        if path.suffix.lower() == ".eml":
            message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
            headers = {key: str(message.get(header, "")) for key, header in
                       (("from", "From"), ("subject", "Subject"), ("date", "Date"), ("message_id", "Message-ID"))}
            part = message.get_body(preferencelist=("plain",))
            body = part.get_content() if part else ""
            attachments = [{"name": att.get_filename() or "bijlage", "mimetype": att.get_content_type(),
                            "datas": base64.b64encode(att.get_content()).decode()}
                           for att in message.iter_attachments()]
        else:
            lines = path.read_text(encoding="utf-8").splitlines()
            headers, index = {}, 0
            for index, line in enumerate(lines):
                key, sep, value = line.partition(":")
                if not line.strip() or not sep or key.strip().lower() not in TXT_HEADERS:
                    break
                headers[TXT_HEADERS[key.strip().lower()]] = value.strip()
            body, attachments = "\n".join(lines[index:]), []
        sender_name, sender_email = email.utils.parseaddr(headers.get("from", ""))
        return {
            "file": path.name,
            "from": {"emailAddress": sender_email.lower(), "displayName": sender_name},
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "internetMessageId": headers.get("message_id", "").strip(),
            "body": re.sub(r"\n{3,}", "\n\n", body.strip()),
            "attachments": attachments,
        }
