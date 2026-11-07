"""Building insurance and mandatory certificates per building: status, tasks and signals.

The certificates are vme.document records with a certificate type (asbestos, PID, EPC); the
electrical inspection of the common parts is the existing vme.installation of type "electrical".
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import format_date

CERTIFICATE_TYPES = [
    ("asbestos", "Asbestattest gemene delen"),
    ("pid", "Postinterventiedossier"),
    ("epc_common", "EPC gemeenschappelijke delen"),
    ("electrical", "Elektrische keuring gemene delen"),
]
# Certificates that are a document; the electrical inspection comes from the installations.
DOCUMENT_CERTIFICATES = ("asbestos", "pid", "epc_common")

# Validity in months after the date of the certificate; 0 means it does not expire.
CERTIFICATE_VALIDITY_MONTHS = {
    # LEGAL-CHECK: Vlaams Materialendecreet en VLAREMA (OVAM) - an asbestos certificate is valid
    # for ten years, shorter when the building changes.
    "asbestos": 120,
    # LEGAL-CHECK: KB 25 januari 2001 tijdelijke of mobiele bouwplaatsen, nu codex welzijn op het
    # werk boek V titel 2 - the post-intervention file has no end date; it is completed after works.
    "pid": 0,
    # LEGAL-CHECK: Vlaams Energiebesluit, EPC gemeenschappelijke delen - valid for ten years.
    "epc_common": 120,
}

# Folder where a new certificate of each type goes (xml ids of data/document_folders.xml).
CERTIFICATE_FOLDERS = {
    "asbestos": "vme_belgie.folder_certificates",
    "pid": "vme_belgie.folder_pid",
    "epc_common": "vme_belgie.folder_certificates",
}

# LEGAL-CHECK: Vlaams Materialendecreet - an asbestos certificate is required for buildings
# built before 2001; for the common parts at every sale of a lot since 1 May 2025 and for every
# co-ownership by 31 December 2026 (date to be confirmed).
ASBESTOS_BUILT_BEFORE = 2001
ASBESTOS_DEADLINE = date(2026, 12, 31)
# LEGAL-CHECK: KB 25 januari 2001 tijdelijke of mobiele bouwplaatsen, art. 34-36 - a
# post-intervention file exists for buildings put up from 1 May 2001 and passes to the buyer.
PID_BUILT_FROM = 2001
# LEGAL-CHECK: Vlaams Energiebesluit - every apartment building in Flanders has an EPC for the
# common parts since 1 January 2022; the minimum number of units is to be confirmed.
EPC_MIN_APARTMENTS = 2

CERTIFICATE_STATES = ("ok", "expiring", "expired", "missing", "unknown")
# Days before the end of validity at which a certificate turns orange and gets a task.
CERTIFICATE_LEAD_DAYS = 90
# Days within which a building policy due date gives a signal on the building card.
INSURANCE_SIGNAL_DAYS = 30

REGIONS = [("flanders", "Vlaanderen"), ("brussels", "Brussel"), ("wallonia", "Wallonië")]


def region_from_zip(zip_code):
    """Region of a Belgian postal code; False when unknown."""
    try:
        number = int((zip_code or "").strip()[:4])
    except ValueError:
        return False
    if 1000 <= number <= 1299:
        return "brussels"
    if 1500 <= number <= 3999 or 8000 <= number <= 9999:
        return "flanders"
    if 1300 <= number <= 1499 or 4000 <= number <= 7999:
        return "wallonia"
    return False


def certificate_applies(certificate_type, region, construction_year, apartment_count):
    """True or False whether a certificate is mandatory for a building, None if the year is missing."""
    if certificate_type == "asbestos":
        if region != "flanders":
            return False
        return None if not construction_year else construction_year < ASBESTOS_BUILT_BEFORE
    if certificate_type == "pid":
        return None if not construction_year else construction_year >= PID_BUILT_FROM
    if certificate_type == "epc_common":
        return region == "flanders" and apartment_count >= EPC_MIN_APARTMENTS
    # The periodic inspection interval of the electrical installation is in vme_installation.py.
    return certificate_type == "electrical"


class VmeDocument(models.Model):
    _inherit = "vme.document"

    certificate_type = fields.Selection(
        CERTIFICATE_TYPES[:3], string="Attest", index=True,
        help="Verplicht attest van het gebouw. Telt mee in de opvolging op de gebouwkaart en bij een verkoop.")
    valid_until = fields.Date(
        string="Geldig tot", compute="_compute_valid_until", store=True, readonly=False, precompute=True,
        help="Leeg: geen einddatum.")

    @api.depends("certificate_type", "date")
    def _compute_valid_until(self):
        for document in self:
            months = CERTIFICATE_VALIDITY_MONTHS.get(document.certificate_type, 0)
            document.valid_until = document.date + relativedelta(months=months) if months and document.date else False

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        documents.filtered("certificate_type")._close_certificate_tasks()
        return documents

    def write(self, vals):
        result = super().write(vals)
        if "certificate_type" in vals or "valid_until" in vals:
            self.filtered("certificate_type")._close_certificate_tasks()
        return result

    def _close_certificate_tasks(self):
        """A new certificate closes the open task of that certificate on the VME."""
        today = fields.Date.context_today(self)
        for document in self:
            if document.valid_until and document.valid_until <= today + relativedelta(days=CERTIFICATE_LEAD_DAYS):
                continue
            vme = document.association_id
            prefix = vme._certificate_task_prefix(document.certificate_type)
            vme.activity_ids.filtered(lambda a, p=prefix: (a.summary or "").startswith(p)).action_feedback(
                feedback=self.env._("Attest toegevoegd: %s.", document.name))


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    construction_year = fields.Integer(
        string="Bouwjaar", help="Bepaalt welke attesten verplicht zijn (asbestattest, postinterventiedossier).")
    region = fields.Selection(
        REGIONS, string="Gewest", compute="_compute_region", store=True, readonly=False,
        help="Afgeleid uit de postcode. Asbestattest en EPC gemene delen volgen de Vlaamse regels.")
    compliance_html = fields.Html(string="Verzekering en attesten", compute="_compute_compliance_html", sanitize=False)

    @api.depends("zip")
    def _compute_region(self):
        for vme in self:
            vme.region = region_from_zip(vme.zip) or vme.region

    # Certificates

    @api.model
    def _certificate_task_prefix(self, certificate_type):
        # The task summary starts with the label; a new certificate closes the task by that prefix.
        return dict(self._certificate_type_labels())[certificate_type]

    @api.model
    def _certificate_type_labels(self):
        return self.env["vme.document"]._fields["certificate_type"]._description_selection(self.env) + [
            ("electrical", self.env._("Elektrische keuring gemene delen"))]

    def _get_certificate_status(self, today=None, documents=None):
        """Status of the mandatory certificates of this VME: a list of dicts.

        Each dict: type, label, state (one of CERTIFICATE_STATES), document, installation, valid_until,
        message. documents: the certificate documents of this VME, read in advance by the
        portfolio; default all of them.
        """
        self.ensure_one()
        vme = self.sudo()
        today = today or self._card_today()
        if documents is None:
            documents = self.env["vme.document"].sudo().search(
                [("association_id", "=", vme.id), ("certificate_type", "!=", False)])
        apartments = len(vme.lot_ids.filtered(lambda lot: lot.lot_type == "apartment"))
        states = self._certificate_state_labels()
        result = []
        for code, label in self._certificate_type_labels():
            applies = certificate_applies(code, vme.region, vme.construction_year, apartments)
            if applies is False:
                continue
            entry = {"type": code, "label": label, "document": self.env["vme.document"],
                     "installation": self.env["vme.installation"], "valid_until": False}
            if applies is None:
                entry.update(state="unknown", message=self.env._(
                    "%s: vul het bouwjaar in om te weten of dit attest verplicht is.", label))
            elif code == "electrical":
                installations = vme.installation_ids.filtered(lambda i: i.installation_type == "electrical")
                entry["installation"] = installations.sorted(lambda i: i.next_inspection_date or date.min)[:1]
                entry.update(vme._certificate_state(label, entry["installation"].next_inspection_date,
                                                    bool(entry["installation"].last_inspection_date), today))
            else:
                document = documents.filtered(lambda d, c=code: d.certificate_type == c and d.association_id == vme)
                document = document.sorted(lambda d: (d.date, d.id))[-1:]
                entry["document"] = document
                entry.update(vme._certificate_state(label, document.valid_until, bool(document), today))
                if code == "asbestos" and entry["state"] == "missing":
                    entry["message"] += " " + self.env._(
                        "Verplicht bij elke verkoop van een kavel en uiterlijk op %s.",
                        format_date(self.env, ASBESTOS_DEADLINE))
            entry["state_label"] = states[entry["state"]]
            result.append(entry)
        return result

    @api.model
    def _certificate_state_labels(self):
        return {
            "ok": self.env._("In orde"),
            "expiring": self.env._("Vervalt binnenkort"),
            "expired": self.env._("Vervallen"),
            "missing": self.env._("Ontbreekt"),
            "unknown": self.env._("Bouwjaar ontbreekt"),
        }

    def _certificate_state(self, label, valid_until, present, today):
        if not present:
            return {"state": "missing", "message": self.env._("%s ontbreekt.", label)}
        values = {"valid_until": valid_until}
        if valid_until and valid_until < today:
            values.update(state="expired", message=self.env._(
                "%(label)s vervallen sinds %(date)s.", label=label, date=format_date(self.env, valid_until)))
        elif valid_until and valid_until <= today + relativedelta(days=CERTIFICATE_LEAD_DAYS):
            values.update(state="expiring", message=self.env._(
                "%(label)s geldig tot %(date)s.", label=label, date=format_date(self.env, valid_until)))
        else:
            values.update(state="ok", message=False)
        return values

    def _get_certificate_signal(self, today, documents=None):
        """Message for the signal "certificate", or False.

        An overdue electrical inspection is already the signal "inspection"; here only when
        the building has no electrical inspection at all.
        """
        problems = [
            entry["message"] for entry in self._get_certificate_status(today, documents)
            if entry["state"] == "missing" or (entry["state"] == "expired" and entry["type"] != "electrical")
        ]
        return " ".join(problems) or False

    # Insurance

    def _building_policies(self, policies=None):
        self.ensure_one()
        if policies is None:
            policies = self.sudo().insurance_policy_ids
        return policies.filtered(lambda p: p.association_id == self and p.policy_type == "building" and p.active)

    def _get_insurance_signal(self, today, policies=None):
        """Message when the building has no fire insurance or it is (nearly) due, or False."""
        self.ensure_one()
        # LEGAL-CHECK: art. 3.89 §5 BW en wet 4 april 2014 betreffende de verzekeringen - te
        # bevestigen: the co-ownership insures the building against fire; the provision that
        # imposes it is not yet checked.
        building = self._building_policies(policies)
        if not building:
            return self.env._("Geen brandverzekering van het gebouw geregistreerd.")
        due = building.filtered(
            lambda p: p.date_end and p.date_end <= today + relativedelta(days=INSURANCE_SIGNAL_DAYS)
        ).sorted("date_end")
        if len(due) < len(building) or not due:
            return False
        policy = due[0]
        if policy.date_end < today:
            return self.env._("%(policy)s is vervallen sinds %(date)s.",
                              policy=policy.display_name, date=format_date(self.env, policy.date_end))
        return self.env._("%(policy)s vervalt op %(date)s: verlenging nakijken bij %(insurer)s.",
                          policy=policy.display_name, date=format_date(self.env, policy.date_end),
                          insurer=policy.insurer_id.name)

    # Tasks

    @api.model
    def _cron_schedule_certificate_activities(self):
        """One open task per missing, expired or expiring certificate, on the VME."""
        today = fields.Date.context_today(self)
        todo = self.env.ref("mail.mail_activity_data_todo")
        vmes = self.search([])
        documents = self.env["vme.document"].sudo().search(
            [("association_id", "in", vmes.ids), ("certificate_type", "!=", False)])
        for vme in vmes:
            for entry in vme._get_certificate_status(today, documents):
                if entry["state"] not in ("missing", "expired", "expiring"):
                    continue
                # The inspection itself already has a task on the installation (vme_installation.py).
                if entry["type"] == "electrical" and entry["installation"]:
                    continue
                prefix = vme._certificate_task_prefix(entry["type"])
                if vme.activity_ids.filtered(lambda a, p=prefix: (a.summary or "").startswith(p)):
                    continue
                action = self.env._("laten opmaken") if entry["state"] == "missing" else self.env._("vernieuwen")
                vme.activity_schedule(
                    activity_type_id=todo.id,
                    date_deadline=max(entry["valid_until"] or today, today) if entry["state"] == "expiring"
                    else today + relativedelta(days=30),
                    summary=f"{prefix} {action}",
                    note=entry["message"],
                    # The cron runs as OdooBot: the case manager of the VME gets the task.
                    user_id=vme._vme_task_user().id,
                )

    # Form

    def _get_compliance_data(self, today=None):
        self.ensure_one()
        vme = self.sudo()
        today = today or self._card_today()
        return {
            "vme": vme,
            "today": today,
            "currency": vme.company_id.currency_id,
            "policies": vme.insurance_policy_ids.filtered("active").sorted(lambda p: (p.policy_type != "building", p.id)),
            "insurance_signal": vme._get_insurance_signal(today),
            "certificates": vme._get_certificate_status(today),
            "selection_label": self._selection_label,
        }

    @api.depends_context("vme_today")
    def _compute_compliance_html(self):
        QWeb = self.env["ir.qweb"]
        for vme in self:
            if not vme.id or not vme.company_id:
                vme.compliance_html = False
                continue
            vme.compliance_html = QWeb._render("vme_belgie.compliance_content", vme._get_compliance_data())

    def action_add_certificate(self):
        """Upload form for a certificate document, opened from the compliance tab."""
        self.ensure_one()
        certificate_type = self.env.context.get("certificate_type", "asbestos")
        folder = self.env.ref(CERTIFICATE_FOLDERS[certificate_type])
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Attest toevoegen"),
            "res_model": "vme.document",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_association_id": self.id,
                "default_folder_id": folder.id,
                "default_certificate_type": certificate_type,
                "default_name": dict(self._certificate_type_labels())[certificate_type],
            },
        }
