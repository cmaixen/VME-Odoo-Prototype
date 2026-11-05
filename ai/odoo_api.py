"""Small client for the Odoo JSON-RPC API, plus the reads and writes the assistant needs."""
import base64
import itertools
import json
import urllib.request
from datetime import date


class OdooError(Exception):
    pass


class OdooClient:
    """Logs in once and calls model methods through /jsonrpc (execute_kw)."""

    def __init__(self, url, db, login, password, timeout=30):
        self.url = url.rstrip("/") + "/jsonrpc"
        self.db = db
        self.password = password
        self.timeout = timeout
        self._ids = itertools.count(1)
        self.uid = self._call("common", "login", db, login, password)
        if not self.uid:
            raise OdooError(f"Aanmelden bij Odoo mislukt voor gebruiker {login!r} op database {db!r}.")

    def _call(self, service, method, *args):
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
            "id": next(self._ids),
        }
        request = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read())
        if result.get("error"):
            error = result["error"]
            message = error.get("data", {}).get("message") or error.get("message")
            raise OdooError(message)
        return result["result"]

    def execute(self, model, method, *args, **kwargs):
        return self._call("object", "execute_kw", self.db, self.uid, self.password, model, method, list(args), kwargs)


class VmeDirectory:
    """VME's, lots and owners as one snapshot, read once per run.

    Works across all companies the user may see: each VME is its own company, and the
    assistant must be able to place a mail on any of them.
    """

    def __init__(self, odoo):
        self.odoo = odoo
        user = odoo.execute("res.users", "read", [odoo.uid], fields=["company_ids"])[0]
        self.context = {"allowed_company_ids": user["company_ids"]}

    def _search_read(self, model, domain, fields):
        return self.odoo.execute(model, "search_read", domain, fields=fields, context=self.context)

    def load(self, today=None):
        """Return a list of VME's, each with its lots, their current owner and tenants."""
        today = (today or date.today()).isoformat()
        associations = self._search_read("vme.association", [], ["name", "street", "zip", "city"])
        lots = self._search_read("vme.lot", [], ["name", "association_id", "lot_type", "floor", "current_owner_id"])
        tenancies = self._search_read(
            "vme.lot.contact",
            [("role", "=", "tenant"), ("date_start", "<=", today), "|", ("date_end", "=", False), ("date_end", ">=", today)],
            ["lot_id", "partner_id"],
        )
        partner_ids = sorted(
            {lot["current_owner_id"][0] for lot in lots if lot["current_owner_id"]}
            | {tenancy["partner_id"][0] for tenancy in tenancies}
        )
        partners = {
            partner["id"]: partner
            for partner in self._search_read("res.partner", [("id", "in", partner_ids)], ["name", "email"])
        }
        tenants_by_lot = {}
        for tenancy in tenancies:
            tenant = partners.get(tenancy["partner_id"][0])
            if tenant:
                tenants_by_lot.setdefault(tenancy["lot_id"][0], []).append(
                    {"id": tenant["id"], "name": tenant["name"], "email": tenant["email"] or ""})

        vmes = {
            vme["id"]: {
                "id": vme["id"],
                "name": vme["name"],
                "address": " ".join(part for part in (vme["street"], vme["zip"], vme["city"]) if part),
                "lots": [],
            }
            for vme in associations
        }
        for lot in lots:
            vme = vmes.get(lot["association_id"] and lot["association_id"][0])
            if not vme:
                continue
            owner = partners.get(lot["current_owner_id"] and lot["current_owner_id"][0])
            vme["lots"].append({
                "id": lot["id"],
                "name": lot["name"],
                "type": lot["lot_type"],
                "floor": lot["floor"] or "",
                "owner": {"id": owner["id"], "name": owner["name"], "email": owner["email"] or ""} if owner else None,
                "tenants": tenants_by_lot.get(lot["id"], []),
            })
        return list(vmes.values())

    def find_activity(self, reference):
        """Id of an activity already made for this mail, or None."""
        ids = self.odoo.execute(
            "mail.activity", "search",
            [("res_model", "=", "vme.association"), ("note", "ilike", reference)],
            limit=1, context=self.context,
        )
        return ids[0] if ids else None

    def create_activity(self, association_id, summary, note_html, deadline: date, user_id=None):
        """Schedule a to-do on the VME. Nothing is sent: a staff member reviews it."""
        self.odoo.execute(
            "vme.association", "activity_schedule", [association_id],
            act_type_xmlid="mail.mail_activity_data_todo",
            date_deadline=deadline.isoformat(),
            summary=summary,
            note=note_html,
            user_id=user_id or self.odoo.uid,
            context=self.context,
        )
        return self.find_activity_by_summary(association_id, summary)

    def find_activity_by_summary(self, association_id, summary):
        ids = self.odoo.execute(
            "mail.activity", "search",
            [("res_model", "=", "vme.association"), ("res_id", "=", association_id), ("summary", "=", summary)],
            order="id desc", limit=1, context=self.context,
        )
        return ids[0] if ids else None

    def create_damage_claim(self, association_id, subject, body, reference, lot_id=None, owner_id=None,
                            mail_date=None):
        """Draft damage claim on the VME (step 14); one per mail. Nothing is declared or sent."""
        return self.odoo.execute(
            "vme.damage.claim", "create_from_mail", association_id, subject, body,
            reference=reference, lot_id=lot_id, owner_id=owner_id,
            mail_date=mail_date.isoformat() if mail_date else None, context=self.context,
        )

    def find_request(self, reference):
        """Id of a request already made from this mail, or None."""
        ids = self.odoo.execute(
            "vme.request", "search", [("source_reference", "=", reference)], limit=1, context=self.context,
        )
        return ids[0] if ids else None

    def create_request(self, association_id, request_type, mail, lot_id=None, summary="", proposed_reply=""):
        """Create a request with its fixed procedure in Odoo; Odoo recognises the requester by e-mail.

        Nothing is sent: Odoo prepares the proof request or the order as drafts on the request.
        """
        return self.odoo.execute(
            "vme.request", "create_from_intake",
            association_id=association_id,
            request_type=request_type,
            email=mail.sender_email,
            name=mail.sender_name,
            lot_id=lot_id or False,
            subject=mail.subject,
            body=mail.body,
            channel="mail",
            reference=mail.reference,
            summary=summary,
            proposed_reply=proposed_reply,
            attachments=[
                {"name": name, "datas": base64.b64encode(content).decode(), "mimetype": mimetype}
                for name, content, mimetype in mail.attachments
            ],
            context=self.context,
        )
