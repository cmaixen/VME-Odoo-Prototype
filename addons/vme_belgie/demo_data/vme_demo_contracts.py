"""Fictitious running contracts of the three demo buildings (step 18).

Dates are chosen around the demo date of 5 November 2026: the cleaning contract of Residentie
Linde and the gas contract of Hof ter Beuken must be cancelled by 30 November 2026, the insurance
of Residentie Linde and the cleaning of Kaaihuis by 31 December 2026, so the daily cron shows
tasks right away. Hof ter Beuken has a concierge whose wages a social secretariat invoices.
"""
from datetime import date

from odoo import api, models
from odoo.fields import Command

# Evaluations: (date, rating, outcome, note). On the date of the 2026 assembly of Residentie
# Linde (10 March 2026) they are linked to that assembly.
GOOD = (date(2026, 3, 10), "good", "continue", "")

# Per VME: description, type, supplier code, reference, start, end of the current period,
# tacit renewal, notice in months (None = default of the type), estimated yearly cost,
# installation name, evaluations.
CONTRACTS = {
    "Residentie Linde": [
        ("Onderhoud lift blok A", "elevator", "elevator", "LO-2023-117", date(2024, 1, 1), date(2027, 12, 31),
         True, None, 3000, "Lift blok A",
         [(date(2026, 3, 10), "good", "continue", "Storingen telkens binnen de afgesproken vier uur verholpen.")]),
        ("Schoonmaak gemene delen", "cleaning", "cleaning", "SV-2025-044", date(2025, 1, 1), date(2026, 12, 31),
         True, 1, 6000, None,
         [(date(2026, 3, 10), "sufficient", "tender",
           "Klachten over de kelder en de fietsenberging. Nieuwe offertes vragen vóór de opzegtermijn.")]),
        ("Brandverzekering gebouw", "insurance", "insurance", "BP-2019-4471", date(2019, 4, 1), date(2027, 3, 31),
         True, None, 4200, None, [GOOD]),
        ("Elektriciteit gemene delen", "energy", "energy", "EL-LIN-2025", date(2025, 11, 1), date(2027, 10, 31),
         True, None, 1900, None, []),  # never evaluated: the yearly evaluation is overdue
    ],
    "Hof ter Beuken": [
        ("Onderhoud centrale verwarmingsketel", "maintenance", "heating", "CV-2024-031", date(2024, 7, 1),
         date(2027, 6, 30), True, 3, 1400, "Centrale verwarmingsketel",
         [(date(2025, 11, 25), "good", "continue", "")]),
        ("Aardgas centrale verwarming", "energy", "gas", "GAS-BEU-2024", date(2024, 1, 1), date(2026, 12, 31),
         True, 1, 48000, None,
         [(date(2025, 11, 25), "sufficient", "renegotiate",
           "Prijs ligt boven het marktgemiddelde; vergelijken vóór de opzegtermijn.")]),
        ("Schoonmaak gemene delen", "cleaning", "cleaning", "SV-2023-112", date(2023, 1, 1), date(2027, 12, 31),
         True, 3, 9600, None, [(date(2025, 11, 25), "good", "continue", "")]),
        ("Brandverzekering gebouw", "insurance", "insurance", "BP-2021-0815", date(2021, 7, 1), date(2027, 6, 30),
         True, None, 6500, None, [(date(2025, 11, 25), "good", "continue", "")]),
        # Employment contract of indefinite duration: no notice deadline is computed.
        ("Conciërge (loonadministratie)", "staff", "payroll", "SS-BEU-0042", date(2019, 9, 1), False,
         False, None, 39500, None,
         [(date(2025, 11, 25), "good", "continue",
           "Conciërge 30 uur per week. Loonkosten maandelijks via het sociaal secretariaat.")]),
    ],
    "Kaaihuis": [
        ("Schoonmaak gemene delen", "cleaning", "cleaning", "SV-2024-207", date(2024, 4, 1), date(2027, 3, 31),
         True, 3, 2400, None, [(date(2026, 3, 24), "good", "continue", "")]),
        ("Brandverzekering gebouw", "insurance", "insurance", "BP-2022-3310", date(2022, 10, 1), date(2027, 9, 30),
         True, None, 1800, None, [(date(2026, 3, 24), "good", "continue", "")]),
        ("Elektriciteit gemene delen", "energy", "energy", "EL-KAA-2025", date(2025, 11, 1), date(2027, 10, 31),
         True, None, 700, None, [(date(2026, 3, 24), "good", "continue", "")]),
    ],
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_contracts(self, suppliers):
        """Contracts of the demo VMEs; suppliers of the demo history are created here if needed."""
        suppliers = dict(suppliers)
        for code in ("cleaning", "insurance", "gas", "payroll"):
            suppliers[code] = self._demo_history_supplier(code)
        admin = self.env.ref("base.user_admin")
        contracts = self.env["vme.contract"]
        for vme in self.search([("name", "in", list(CONTRACTS))]):
            assemblies = self.env["vme.assembly"].search([("association_id", "=", vme.id), ("state", "=", "held")])
            for (name, kind, supplier, reference, start, end, renew, notice, amount, installation,
                 evaluations) in CONTRACTS[vme.name]:
                vals = {
                    "association_id": vme.id,
                    "name": name,
                    "contract_type": kind,
                    "partner_id": suppliers[supplier].id,
                    "reference": reference,
                    "date_start": start,
                    "date_end": end,
                    "auto_renew": renew,
                    "annual_amount": amount,
                    "responsible_user_id": admin.id,
                    "installation_id": vme.installation_ids.filtered(lambda i, n=installation: i.name == n).id
                    if installation else False,
                    "evaluation_ids": [Command.create({
                        "date": day, "rating": rating, "outcome": outcome, "note": note or False, "user_id": admin.id,
                        "assembly_id": assemblies.filtered(lambda a, d=day: a.slot_id.date == d)[:1].id,
                    }) for day, rating, outcome, note in evaluations],
                }
                if notice:
                    vals["notice_period_months"] = notice
                contracts |= self.env["vme.contract"].create(vals)
        return contracts
