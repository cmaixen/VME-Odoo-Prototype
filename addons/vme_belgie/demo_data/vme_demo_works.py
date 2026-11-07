"""Fictitious works, insurance policies and damage claims for the demo (step 14)."""
import base64
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.fields import Command
from odoo.tools import file_open

from ..models.vme_compliance import CERTIFICATE_FOLDERS
from .vme_demo_portal import simple_pdf

# Fictitious contractors, insurer and expert: VAT numbers start with 0000 (valid check digits, cannot be real).
WORKS_PARTNERS = {
    "roofer": ("Dakrenovatie Fictief NV", "BE0000001186", "facturen@dakrenovatie.example.com", "Leiendekkersstraat 7"),
    "roofer_2": ("Dakwerken Voorbeeld BV", "BE0000001285", "offertes@dakwerken.example.com", "Pannenweg 3"),
    "builder": ("Bouwbedrijf Voorbeeld NV", "BE0000001384", "info@bouwbedrijf.example.com", "Bouwlaan 21"),
    "expert": ("Expertisebureau Voorbeeld BV", "BE0000001483", "dossiers@expertise.example.com", "Schattersplein 2"),
    "plumber": ("Loodgieter Voorbeeld BV", "BE0000001582", "herstel@loodgieter.example.com", "Buizenstraat 14"),
    # The three facade contractors: same data as their quote PDFs (ai/tools/maak_demo_offertes.py).
    "facade_1": ("Gevelwerken Fictief BV", "BE0000001681", "offertes@gevelwerken.example.com", "Voegenstraat 5"),
    "facade_2": ("Renovatiebedrijf Voorbeeld NV", "BE0000001780", "info@renovatiebedrijf.example.com", "Herstellaan 18"),
    "facade_3": ("Bouwonderneming Denkbeeld BV", "BE0000001879", "offerte@denkbeeld.example.com", "Metselaarsweg 2"),
}
# The insurer also bills the yearly premium in the demo history; it is created here once.
INSURER = ("Verzekeringen Voorbeeld NV", "BE0000000691", "facturen@verzekeringen.example.com", "Polislaan 5")

# Building insurance per VME: policy number, deductible, start of the running year, insured value,
# yearly premium. Kaaihuis is due on 1 December 2026, within 30 days of the demo date (signal).
POLICIES = {
    "Residentie Linde": ("BR-LINDE-2019-0042", 300, date(2026, 4, 1), 4250000, 4200),
    "Hof ter Beuken": ("BR-BEUKEN-2017-0117", 300, date(2026, 7, 1), 7900000, 6500),
    "Kaaihuis": ("BR-KAAI-2021-0009", 250, date(2025, 12, 2), 1650000, 1800),
}

# Certificates of the common parts (vme_compliance.py): vme, type, date, title, lines of the PDF.
# Hof ter Beuken (built 1978) has no asbestos certificate yet: the building card shows it.
CERTIFICATES = [
    ("Residentie Linde", "asbestos", date(2024, 9, 18), "Asbestattest gemene delen Residentie Linde",
     ["Fictief asbestattest voor de demo.", "Asbestinventaris van de gemene delen: geen asbest met risico."]),
    ("Residentie Linde", "epc_common", date(2022, 5, 3), "EPC gemeenschappelijke delen Residentie Linde",
     ["Fictief EPC gemeenschappelijke delen.", "Label C, aanbevelingen voor dakisolatie."]),
    ("Hof ter Beuken", "epc_common", date(2023, 2, 14), "EPC gemeenschappelijke delen Hof ter Beuken",
     ["Fictief EPC gemeenschappelijke delen.", "Label D, aanbevelingen voor de stookplaats."]),
    ("Kaaihuis", "epc_common", date(2021, 11, 30), "EPC gemeenschappelijke delen Kaaihuis",
     ["Fictief EPC gemeenschappelijke delen.", "Label B."]),
    ("Kaaihuis", "pid", date(2012, 10, 1), "Postinterventiedossier nieuwbouw Kaaihuis",
     ["Fictief postinterventiedossier van de nieuwbouw.", "Plannen, materialen en nutsleidingen."]),
]

# The roof works decided by the 2026 assembly of Residentie Linde: three quotes, awarded in June,
# execution from 16 November 2026 (after the demo date), so the works are still open.
DEMO_WORKS = {
    "vme": "Residentie Linde",
    "decision": "Dakwerken",
    "name": "Renovatie plat dak blok A",
    "description": "<p>Volledige vernieuwing van de dakbedekking van het platte dak van blok A (ongeveer 420 m²): "
                   "afbraak van de oude roofing, nieuwe isolatie van 16 cm, EPDM-dakbedekking, nieuwe dakranden "
                   "en aansluiting op de bestaande regenwaterafvoeren.</p>",
    "quote_deadline": date(2026, 5, 15),
    # (partner, date, reference, amount incl. VAT, weeks, notes)
    "quotes": [
        ("roofer_2", date(2026, 4, 14), "DV-2026-118", 39220.00, 6, "Zonder dakranden in aluminium."),
        ("roofer", date(2026, 4, 28), "DR-OFF-2026-031", 36450.00, 5, "Inclusief nieuwe dakranden en 10 jaar garantie."),
        ("builder", date(2026, 5, 6), "BV/26/0457", 41980.00, 7, "Bitumen in plaats van EPDM."),
    ],
    "award": "roofer",
    "award_date": date(2026, 6, 2),
    "planned_start": date(2026, 11, 16),
    "planned_end": date(2026, 12, 18),
}

# Facade renovation of Residentie Linde, to be put to the 2027 assembly: three quotes received as
# PDF (demo_data/offertes, made by ai/tools/maak_demo_offertes.py), not yet compared. The quotes
# differ on purpose: one leaves out the scaffolding, another charges 21% VAT instead of 6%.
DEMO_FACADE_WORKS = {
    "vme": "Residentie Linde",
    "name": "Gevelrenovatie voor- en achtergevel",
    "description": "<p>Reinigen van de voor- en achtergevel, herstel van het voegwerk, betonherstel aan balkons "
                   "en lateien en een waterafstotende behandeling. Voor te leggen aan de algemene vergadering "
                   "van 2027, met een vergelijking van de offertes.</p>",
    "budget": 50000.00,
    "quote_deadline": date(2026, 10, 15),
    # (partner, date, reference, amount incl. VAT as entered, weeks, PDF)
    "quotes": [
        ("facade_1", date(2026, 9, 22), "GF-2026-207", 48548.00, 9,
         "offerte_gevelwerken_fictief_GF-2026-207.pdf"),
        ("facade_2", date(2026, 10, 3), "RV/26/1189", 36941.00, 7,
         "offerte_renovatiebedrijf_voorbeeld_RV-26-1189.pdf"),
        # Entered without VAT by mistake (the quote says 53.240,00 incl. 21%): the comparison flags it.
        ("facade_3", date(2026, 10, 10), "BD-OF-2026-0611", 44000.00, 10,
         "offerte_bouwonderneming_denkbeeld_BD-OF-2026-0611.pdf"),
    ],
}

# Water damage in A4 of Residentie Linde, reported by mail (ai/inbox/01_lek_badkamer.eml).
DEMO_CLAIM = {
    "vme": "Residentie Linde",
    "name": "Waterschade badkamer A4",
    "mail_reference": "lek-a4-20261102@example.com",
    "event_date": date(2026, 11, 1),
    "report_date": date(2026, 11, 2),
    "reporter_lot": "A4",
    "lots": ["A4", "A7"],
    "cause": "Lek in de afvoer van het appartement erboven (A7)",
    "description": "Sinds 1 november loopt er water langs het plafond van de badkamer van A4: grote bruine vlek, "
                   "het druppelt op de vloer. Vermoedelijk lek uit A7. Loodgieter ging op 2 november ter plaatse "
                   "en dichtte een lekkende afvoer in de leidingkoker (gemeen deel).",
    "declaration_date": date(2026, 11, 3),
    "insurer_reference": "SCH-2026-08812",
    "expertise_date": date(2026, 11, 12),
    "estimated_amount": 2400.00,
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _demo_partner(self, name, vat, email, street):
        Partner = self.env["res.partner"]
        return Partner.search([("vat", "=", vat)], limit=1) or Partner.create({
            "name": name, "vat": vat, "email": email, "street": street, "zip": "2000", "city": "Voorbeeldstad",
            "is_company": True, "country_id": self.env.ref("base.be").id,
        })

    @api.model
    def _load_demo_works(self):
        """Insurance policies for every demo VME, the roof works and the water damage of Residentie Linde."""
        partners = {code: self._demo_partner(*vals) for code, vals in WORKS_PARTNERS.items()}
        insurer = self._demo_partner(*INSURER)
        for vme_name, (number, deductible, start, value, premium) in POLICIES.items():
            vme = self.search([("name", "=", vme_name)])
            self.env["vme.insurance.policy"].create({
                "association_id": vme.id, "name": "Brandverzekering gebouw", "policy_type": "building",
                "insurer_id": insurer.id, "policy_number": number, "deductible": deductible,
                "date_start": start, "date_end": start + relativedelta(years=1, days=-1),
                "insured_value": value, "valuation_basis": "abex", "premium": premium,
                "coverage": "Brand en aanverwante gevaren, waterschade, storm en hagel, glasbreuk, "
                            "burgerlijke aansprakelijkheid gebouw.",
            })
        self._load_demo_certificates()
        admin = self.env.ref("base.user_admin")
        works = self._load_demo_roof_works(partners, admin)
        self._load_demo_facade_works(partners, admin)
        claim = self._load_demo_water_damage(partners, admin)
        return works, claim

    @api.model
    def _load_demo_certificates(self):
        Document = self.env["vme.document"]
        for vme_name, certificate_type, day, title, lines in CERTIFICATES:
            Document.create({
                "name": title,
                "association_id": self.search([("name", "=", vme_name)]).id,
                "folder_id": self.env.ref(CERTIFICATE_FOLDERS[certificate_type]).id,
                "certificate_type": certificate_type,
                "date": day,
                "datas": base64.b64encode(simple_pdf(title, lines)),
                "filename": f"{title}.pdf",
            })

    @api.model
    def _load_demo_roof_works(self, partners, user):
        spec = DEMO_WORKS
        vme = self.search([("name", "=", spec["vme"])])
        decision = self.env["vme.assembly.item"].search([
            ("association_id", "=", vme.id), ("name", "=like", f"{spec['decision']}%")], limit=1)
        works = self.env["vme.works"].create({
            "association_id": vme.id, "decision_id": decision.id, "name": spec["name"],
            "description": spec["description"], "financing": "reserve", "user_id": user.id,
            "quote_deadline": spec["quote_deadline"],
            "planned_start": spec["planned_start"], "planned_end": spec["planned_end"],
        })
        works.action_request_quotes()
        works.quote_ids = [Command.create({
            "partner_id": partners[code].id, "date": day, "reference": reference, "amount": amount,
            "duration_weeks": weeks, "notes": notes,
        }) for code, day, reference, amount, weeks, notes in spec["quotes"]]
        quote = works.quote_ids.filtered(lambda q: q.partner_id == partners[spec["award"]])
        quote.action_award()
        works.award_date = spec["award_date"]
        # The confirmation to the contractor went out in June; only the start is still to follow up.
        works.activity_ids.filtered(lambda a: a.summary.startswith("Opdrachtbevestiging")).action_feedback(
            feedback="Opdrachtbevestiging verstuurd.")
        decision.activity_ids.action_feedback(feedback="Drie offertes ontvangen, gegund.")
        return works

    @api.model
    def _load_demo_facade_works(self, partners, user):
        spec = DEMO_FACADE_WORKS
        vme = self.search([("name", "=", spec["vme"])])
        works = self.env["vme.works"].create({
            "association_id": vme.id, "name": spec["name"], "description": spec["description"],
            "budget": spec["budget"], "financing": "reserve", "user_id": user.id,
            "quote_deadline": spec["quote_deadline"],
            "key_id": vme.key_ids.filtered(lambda k: k.key_type == "general")[:1].id,
        })
        works.action_request_quotes()
        for code, day, reference, amount, weeks, filename in spec["quotes"]:
            with file_open(f"vme_belgie/demo_data/offertes/{filename}", "rb") as f:
                pdf = self.env["ir.attachment"].create({
                    "name": filename, "datas": base64.b64encode(f.read()), "mimetype": "application/pdf",
                    "res_model": "vme.works", "res_id": works.id,
                })
            works.quote_ids = [Command.create({
                "partner_id": partners[code].id, "date": day, "reference": reference, "amount": amount,
                "duration_weeks": weeks, "attachment_ids": [Command.set(pdf.ids)],
            })]
        works.activity_ids.action_feedback(feedback="Drie offertes ontvangen.")
        return works

    @api.model
    def _load_demo_water_damage(self, partners, user):
        spec = DEMO_CLAIM
        vme = self.search([("name", "=", spec["vme"])])
        lots = vme.lot_ids.filtered(lambda lot: lot.name in spec["lots"])
        reporter = vme.lot_ids.filtered(lambda lot: lot.name == spec["reporter_lot"])._get_owner_on(spec["report_date"])
        claim = self.env["vme.damage.claim"].create({
            "association_id": vme.id, "name": spec["name"], "damage_type": "water", "source": "mail",
            "mail_reference": spec["mail_reference"], "event_date": spec["event_date"],
            "report_date": spec["report_date"], "reporter_id": reporter.id,
            "lot_ids": [Command.set(lots.ids)], "common_parts": True, "cause": spec["cause"],
            "description": spec["description"], "user_id": user.id,
            "repair_partner_id": partners["plumber"].id, "estimated_amount": spec["estimated_amount"],
        })
        claim.write({"declaration_date": spec["declaration_date"], "insurer_reference": spec["insurer_reference"]})
        claim.action_declare()
        claim.write({"expert_id": partners["expert"].id, "expertise_date": spec["expertise_date"]})
        claim.action_expertise()
        return claim
