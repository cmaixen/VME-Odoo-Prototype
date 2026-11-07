"""Fictitious documents, portal logins, an address change, a portal request and a survey for the owner portal (steps 15 and 27)."""
import base64
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.fields import Command

# Test logins for the owner portal. Fictitious and only for a local demo: they are in docs/demo.md.
PORTAL_PASSWORD = "portaal-demo"
PORTAL_OWNERS = [
    ("Residentie Linde", "Eigenaar Linde A1"),  # owns A1 and G1
    ("Residentie Linde", "Eigenaar Linde A5"),  # sold A5 and G5 on 1 July 2026
    ("Residentie Linde", "Eigenaar Linde A6"),  # owns A6 and G6; secretary of the hybrid assembly (step 24)
]

# (vme, folder xml id, lot or None, date, title, visible in the portal, lines of the fictitious PDF)
DOCUMENTS = [
    ("Residentie Linde", "folder_deed", None, date(1998, 5, 12), "Basisakte Residentie Linde", True,
     ["Fictieve basisakte voor de demo.", "20 kavels: 12 appartementen en 8 garages."]),
    ("Residentie Linde", "folder_deed", None, date(2019, 3, 5), "Reglement van orde", True,
     ["Fictief reglement van orde.", "Huisdieren, afval en gebruik van de gemene delen."]),
    ("Residentie Linde", "folder_minutes", None, date(2026, 3, 10), "Notulen gewone AV 10 maart 2026", True,
     ["Fictieve notulen van de gewone algemene vergadering.", "Jaarrekening 2025 goedgekeurd."]),
    ("Residentie Linde", "folder_insurance", None, date(2026, 1, 1), "Brandverzekering 2026", True,
     ["Fictieve polis brandverzekering gebouw.", "Verzekeraar Voorbeeld, polis 0000-001."]),
    ("Residentie Linde", "folder_insurance", None, date(2026, 10, 1), "Bijvoegsel brandverzekering: zonnepanelen", True,
     ["Fictief bijvoegsel bij de brandverzekering.", "Dekking voor de zonnepanelen op het dak."]),
    ("Residentie Linde", "folder_inspections", None, date(2026, 4, 15), "Keuringsverslag lift 2026", True,
     ["Fictief keuringsverslag van de lift.", "Geen inbreuken; volgende keuring over drie maanden."]),
    ("Residentie Linde", "folder_pid", None, date(2021, 9, 1), "Postinterventiedossier gevelrenovatie", True,
     ["Fictief postinterventiedossier.", "Plannen en gebruikte materialen van de gevelrenovatie."]),
    ("Residentie Linde", "folder_contracts", None, date(2025, 12, 1), "Onderhoudscontract lift", False,
     ["Fictief onderhoudscontract lift (intern).", "Prijsherziening jaarlijks op 1 januari."]),
    ("Residentie Linde", "folder_lot_property", "A1", date(2015, 1, 20), "Uittreksel akte van aankoop A1", True,
     ["Fictief uittreksel van de akte van aankoop van kavel A1 en G1."]),
    ("Residentie Linde", "folder_lot_letters", "A1", date(2026, 9, 15), "Brief over vochtplek in de kelderberging A1", True,
     ["Fictieve brief van de syndicus aan de eigenaar van A1.", "De dakdekker komt op 2 oktober kijken."]),
    ("Residentie Linde", "folder_lot_letters", "A2", date(2026, 5, 4), "Brief over lawaai bij A2", True,
     ["Fictieve brief aan de eigenaar van A2."]),
    ("Residentie Linde", "folder_lot_letters", "A5", date(2026, 2, 10), "Brief over het terras van A5", True,
     ["Fictieve brief aan de eigenaar van A5 (vóór de verkoop)."]),
    ("Residentie Linde", "folder_lot_property", "A5", date(2018, 4, 9), "Opmetingsplan kavel A5", True,
     ["Fictief opmetingsplan van appartement A5 en garage G5."]),
    ("Residentie Linde", "folder_lot_letters", "A5", date(2026, 7, 15), "Welkomstbrief nieuwe eigenaar A5", True,
     ["Fictieve welkomstbrief voor de koper van A5."]),
    ("Hof ter Beuken", "folder_deed", None, date(2004, 11, 3), "Basisakte Hof ter Beuken", True,
     ["Fictieve basisakte voor de demo."]),
    ("Hof ter Beuken", "folder_minutes", None, date(2026, 4, 20), "Notulen gewone AV 2026", True,
     ["Fictieve notulen van de gewone algemene vergadering van Hof ter Beuken."]),
    ("Kaaihuis", "folder_deed", None, date(2012, 6, 8), "Basisakte Kaaihuis", True,
     ["Fictieve basisakte voor de demo."]),
]

# Address change of Linde A1 that waits for the syndic.
# Portal login of a tenant (step 27): rents A6 in Residentie Linde (see vme_demo_requests.TENANTS).
PORTAL_TENANTS = ["Huurder Linde A6"]
# A request filed in the portal: (owner, lot, request type, subject, question).
PORTAL_REQUEST = ("Eigenaar Linde A1", "A1", "document", "Attest betaalde provisies 2026",
                  "Mijn bank vraagt een attest van de betaalde provisies van dit jaar. Kunt u mij dat bezorgen?")
# A survey that went out earlier, with answers: (lot of the owner, answer, note, via the portal).
PORTAL_SURVEY_ANSWERS = [
    ("A1", "Ja, binnen het jaar", "Graag op mijn garage G1.", True),
    ("A2", "Ja, later", "", False),
    ("A3", "Nee", "", False),
]

ADDRESS_REQUEST = ("Eigenaar Linde A1", {
    "street": "Voorbeeldstraat 12 bus 3", "zip": "9000", "city": "Gent", "phone": "+32 470 00 00 00",
})


def simple_pdf(title, lines):
    """A one-page PDF with a title and some lines of text, without any extra library."""
    def escape(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace")

    content = b"BT /F1 16 Tf 72 770 Td (" + escape(title) + b") Tj /F1 11 Tf"
    for line in ["", *lines, "", "Fictief document voor de demo van het VME-prototype."]:
        content += b" 0 -18 Td (" + escape(line) + b") Tj"
    content += b" ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return pdf


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_portal(self):
        vmes = {vme.name: vme for vme in self.search([])}
        Document = self.env["vme.document"]
        for vme_name, folder, lot_name, day, title, visible, lines in DOCUMENTS:
            vme = vmes[vme_name]
            Document.create({
                "name": title,
                "association_id": vme.id,
                "folder_id": self.env.ref(f"vme_belgie.{folder}").id,
                "lot_id": vme.lot_ids.filtered(lambda lot, n=lot_name: lot.name == n).id if lot_name else False,
                "date": day,
                "datas": base64.b64encode(simple_pdf(title, lines)),
                "filename": f"{title}.pdf",
                "portal_visible": visible,
            })

        portal_group = self.env.ref("base.group_portal")
        Partner = self.env["res.partner"]
        for vme_name, owner_name in PORTAL_OWNERS:
            owner = Partner.search([("name", "=", owner_name)], limit=1)
            if owner.user_ids:
                continue
            # Created directly with a password: no invitation mail is sent.
            self.env["res.users"].with_context(no_reset_password=True).create({
                "login": owner.email,
                "password": PORTAL_PASSWORD,
                "partner_id": owner.id,
                "group_ids": [Command.set(portal_group.ids)],
            })

        owner_name, values = ADDRESS_REQUEST
        owner = Partner.search([("name", "=", owner_name)], limit=1)
        self.env["vme.address.request"]._create_from_portal(
            owner, {**values, "country_id": self.env.ref("base.be").id, "email": owner.email})

    @api.model
    def _load_demo_portal_requests(self):
        """A tenant login, a request filed in the portal and a survey with answers (step 27). Nothing is sent."""
        Partner = self.env["res.partner"]
        portal_group = self.env.ref("base.group_portal")
        for name in PORTAL_TENANTS:
            tenant = Partner.search([("name", "=", name)], limit=1)
            if tenant and not tenant.user_ids:
                self.env["res.users"].with_context(no_reset_password=True).create({
                    "login": tenant.email, "password": PORTAL_PASSWORD, "partner_id": tenant.id,
                    "group_ids": [Command.set(portal_group.ids)],
                })

        def as_portal_user(partner):
            user = partner.user_ids[:1]
            return partner.with_user(user).with_context(allowed_company_ids=user.company_ids.ids)

        linde = self.search([("name", "=", "Residentie Linde")])
        lots = {lot.name: lot for lot in linde.lot_ids}
        owner_name, lot_name, type_code, subject, body = PORTAL_REQUEST
        owner = Partner.search([("name", "=", owner_name)], limit=1)
        as_portal_user(owner)._vme_portal_create_request(lots[lot_name], type_code, subject, body)

        # The survey on charging points went out three weeks ago; the letters are not sent again.
        template = self.env.ref("vme_belgie.communication_template_survey_charging")
        Communication = self.env["vme.communication"]
        today = fields.Date.context_today(self)
        survey = Communication.create({
            "association_id": linde.id, "template_id": template.id,
            "reference_date": today - timedelta(days=21), "answer_deadline": today + timedelta(days=14),
            **Communication._template_values(template),
        })
        survey.action_prepare_recipients()
        sent_on = today - timedelta(days=21)
        survey.log_ids.write({"state": "sent", "sent_date": sent_on, "date": sent_on})
        survey.write({"state": "sent", "sent_date": sent_on})
        options = {option.name: option for option in survey.option_ids}
        for lot_name, answer, note, via_portal in PORTAL_SURVEY_ANSWERS:
            partner = lots[lot_name]._get_owner_on(today)
            log = survey.log_ids.filtered(lambda line, p=partner: line.partner_id == p)
            if via_portal:
                as_portal_user(partner).env["vme.communication.log"].browse(log.id)._portal_answer(
                    partner, options[answer].id, note)
            else:
                log.write({"answer_option_id": options[answer].id, "answer_note": note or False})
