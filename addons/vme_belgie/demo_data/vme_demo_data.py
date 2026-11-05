"""Fictitious demo data: three buildings with lots, keys, owners and one mid-year sale.

All names, addresses and numbers are made up. KBO numbers start with 0000 and IBANs
use the non-existent bank code 999, so they cannot belong to a real VME.
"""
from datetime import date

from odoo import api, models
from odoo.exceptions import UserError
from odoo.fields import Command

from ..models.allocation_tools import largest_remainder

SALE_DATE_END = date(2026, 6, 30)
SALE_DATE_START = date(2026, 7, 1)

# Weight of a lot in the general key, per m², relative to an apartment.
TYPE_WEIGHT = {"apartment": 1.0, "garage": 0.4}

# Heavier lift share per floor; the ground floor uses the lift least.
LIFT_FLOOR_FACTOR = {0: 0.5, 1: 1.0, 2: 1.2, 3: 1.4}

# Ground and top floor lose more heat, so they weigh more in the heating key.
HEATING_OUTER_FLOOR_FACTOR = 1.15


def _apartments(prefix, floors, areas):
    """Apartments numbered prefix1..N, len(areas) per floor, slightly larger higher up."""
    lots = []
    for floor in range(floors):
        for area in areas:
            lots.append({
                "name": f"{prefix}{len(lots) + 1}",
                "lot_type": "apartment",
                "floor": "Gelijkvloers" if floor == 0 else f"Verdieping {floor}",
                "floor_number": floor,
                "area": area + 2 * floor,
            })
    return lots


BUILDINGS = [
    {
        "name": "Residentie Linde",
        "kbo": "0000.000.097",
        "street": "Lindedreef 12",
        "zip": "2000",
        "city": "Voorbeeldstad",
        "lots": _apartments("A", 4, [72, 95, 68])
        + [{"name": f"G{i}", "lot_type": "garage", "floor": "Kelder", "floor_number": -1, "area": 15}
           for i in range(1, 9)],
        "keys": ["general", "elevator"],
        # Owner of apartment A<n> also owns garage G<n>.
        "garage_owner_of": {f"G{i}": f"A{i}" for i in range(1, 9)},
        "sold_lots": ["A5", "G5"],
    },
    {
        "name": "Hof ter Beuken",
        "kbo": "0000.000.196",
        "street": "Beukenhof 3",
        "zip": "9000",
        "city": "Voorbeeldstad",
        "lots": _apartments("B", 6, [85, 110, 78, 92]),
        "keys": ["general", "heating"],
        # One investor owns both top-floor apartments B23 and B24.
        "shared_owner": {"B24": "B23"},
    },
    {
        "name": "Kaaihuis",
        "kbo": "0000.000.295",
        "street": "Kaaistraat 7",
        "zip": "8000",
        "city": "Voorbeeldstad",
        "lots": _apartments("K", 3, [64, 88]),
        "keys": ["general"],
    },
]

# Fictitious suppliers: VAT numbers start with 0000 (valid check digits, cannot be real).
SUPPLIERS = {
    "energy": {
        "name": "Energieleverancier Voorbeeld NV",
        "vat": "BE0000000394",
        "email": "facturen@energieleverancier.example.com",
        "street": "Stroomlaan 1",
        "zip": "1000",
        "city": "Voorbeeldstad",
    },
    "elevator": {
        "name": "Liftonderhoud Voorbeeld BV",
        "vat": "BE0000000493",
        "email": "facturen@liftonderhoud.example.com",
        "street": "Kabelweg 4",
        "zip": "2000",
        "city": "Voorbeeldstad",
    },
}

# Confirmed accounts of suppliers (bank code 999 does not exist).
SUPPLIER_IBANS = {
    "energy": "BE86999000900150",
    "elevator": "BE75999000900251",
}

INSPECTION_SUPPLIERS = {
    "inspection_body": {
        "name": "Keuringsdienst Voorbeeld vzw",
        "vat": "BE0000000889",
        "email": "verslagen@keuringsdienst.example.com",
        "street": "Controleweg 9",
        "zip": "1000",
        "city": "Voorbeeldstad",
    },
    "fire_safety": {
        "name": "Brandbeveiliging Voorbeeld BV",
        "vat": "BE0000000988",
        "email": "planning@brandbeveiliging.example.com",
        "street": "Blusserstraat 2",
        "zip": "2000",
        "city": "Voorbeeldstad",
    },
    "heating": {
        "name": "Verwarming Voorbeeld BV",
        "vat": "BE0000001087",
        "email": "onderhoud@verwarming.example.com",
        "street": "Ketellaan 5",
        "zip": "9000",
        "city": "Voorbeeldstad",
    },
}

# Installations per VME (relative to the demo date 5 November 2026):
# name, type, location, maintenance supplier, inspection body, contract (ref, end), reports.
# A report is (date, kind, result, [(remark, severity, deadline, responsible)]).
INSTALLATIONS = {
    "Residentie Linde": [
        ("Lift blok A", "elevator", "Trappenhal", "elevator", "inspection_body", ("LO-2023-117", date(2027, 12, 31)), [
            (date(2012, 1, 15), "risk_analysis", "compliant", []),  # next risk analysis 15-01-2027
            (date(2025, 11, 10), "inspection", "compliant", []),
            (date(2026, 5, 12), "inspection", "remarks", [  # next inspection 12-11-2026
                ("Noodverlichting in de liftkooi werkt niet", "major", date(2026, 8, 31), "maintenance"),
                ("Smering van de geleiders onvoldoende", "minor", date(2026, 12, 31), "maintenance"),
            ]),
        ]),
        ("Brandblussers", "fire_extinguishers", "Alle verdiepingen", "fire_safety", "fire_safety", None, [
            (date(2025, 10, 1), "inspection", "compliant", []),  # overdue since 01-10-2026
        ]),
        ("Elektrische installatie gemene delen", "electrical", "Kelder", None, "inspection_body", None, [
            (date(2022, 3, 10), "inspection", "compliant", []),
        ]),
    ],
    "Hof ter Beuken": [
        ("Centrale verwarmingsketel", "heating_boiler", "Stookplaats", "heating", "heating", ("CV-2024-031", date(2027, 6, 30)), [
            (date(2025, 9, 15), "inspection", "compliant", []),
        ]),
        ("Brandblussers", "fire_extinguishers", "Alle verdiepingen", "fire_safety", "fire_safety", None, [
            (date(2025, 12, 20), "inspection", "compliant", []),  # due within 60 days
        ]),
        ("Rookluiken", "smoke_vents", "Dak trappenhal", "fire_safety", "fire_safety", None, [
            (date(2025, 11, 25), "inspection", "compliant", []),  # due within 30 days
        ]),
    ],
    "Kaaihuis": [
        ("Brandblussers", "fire_extinguishers", "Gelijkvloers", "fire_safety", "fire_safety", None, [
            (date(2026, 3, 1), "inspection", "compliant", []),
        ]),
    ],
}

# Distribution rules: supplier, key type and PCMN expense account (only where the key exists).
RULES = [
    ("energy", "general", "612500"),  # Water, elektriciteit en gas
    ("elevator", "elevator", "611000"),  # Onderhoudskosten en herstellingen
]

# Yearly budgets (working capital, reserve contribution) for 2026 and 2027, called per quarter.
# Hof ter Beuken deliberately stays under the 5% reserve minimum to show the warning.
BUDGETS = {
    "Residentie Linde": (24000, 2400),
    "Hof ter Beuken": (48000, 1800),
    "Kaaihuis": (9000, 900),
}
BUDGET_YEARS = (2026, 2027)

# Fifteen-day period of the ordinary general assembly (month, first day) per VME.
# Linde (4-18 March) and Kaaihuis (10-24 March) both fit on 17 March, which only has room
# for one meeting: the planner must give it to Linde, whose period ends first.
ASSEMBLY_PERIODS = {
    "Residentie Linde": ("3", 4),
    "Hof ter Beuken": ("4", 12),
    "Kaaihuis": ("3", 10),
}

# Fictitious meeting rooms of the syndic.
ASSEMBLY_ROOMS = [
    ("Vergaderzaal kantoor syndicus", "Kantoorlaan 1, 2000 Voorbeeldstad", 40),
    ("Buurtzaal Voorbeeld", "Pleinstraat 5, 9000 Voorbeeldstad", 80),
]

# Blocks for the 2027 season: date, start hour, room index (None = online), employee, max meetings.
# Employee "admin" is the demo administrator, "staff" a fictitious employee of the syndic.
ASSEMBLY_BLOCKS = [
    (date(2027, 3, 17), 19.0, 0, "admin", 1),
    (date(2027, 3, 23), 19.5, None, "staff", 2),
    (date(2027, 4, 20), 19.0, 1, "staff", 2),
    (date(2027, 5, 11), 19.0, None, "admin", 2),
]
# A held assembly of Residentie Linde in 2026 (step 11): attendance per apartment, votes and decisions.
# Garage owners are the owners of the apartment with the same number. Apartment numbers that are
# not listed are absent; "represented" maps an apartment to the apartment of its proxy holder.
DEMO_ASSEMBLY_2026 = {
    "vme": "Residentie Linde",
    "block": (date(2026, 3, 10), 19.0, 0),
    "present": ["A1", "A2", "A3", "A4", "A6", "A8", "A10"],
    "represented": {"A5": "A1", "A7": "A1", "A11": "A2"},
    "chair": "A2",
    "secretary": "A6",
    "convocation_sent": date(2026, 2, 18),
    # (title, majority, apartments voting against, apartments abstaining, decision, follow-up)
    "extra_items": [
        ("Dakwerken: renovatie van het platte dak, raming 38.000 euro uit het reservekapitaal", "two_thirds",
         ["A8"], ["A10"], "De AV beslist het platte dak te renoveren, gefinancierd uit het reservekapitaal.",
         "Drie offertes vragen voor de dakwerken"),
        ("Statutenwijziging: gemeenschappelijke tuin enkel voor bewoners van het gelijkvloers", "four_fifths",
         ["A4", "A6", "A8", "A10"], [], "Het voorstel haalt de vereiste vier vijfde niet.", False),
    ],
}

# A sale in progress (step 9): the notary asked for information on 28 October 2026, so the answer
# is due on 12 November 2026, a week after the demo date. A3 has an unpaid call in the demo history
# and pays its share of the roof works decided at the 2026 assembly.
DEMO_SALE = {
    "vme": "Residentie Linde",
    "lots": ["A3", "G3"],
    "notary": {"name": "Notariskantoor Voorbeeld", "is_company": True, "email": "akten@notaris-voorbeeld.example.com",
               "street": "Notarisplein 1", "zip": "2000", "city": "Voorbeeldstad"},
    "notary_reference": "2026/1187/VB",
    "buyer": {"name": "Koper Voorbeeld Linde A3", "email": "koper.a3@example.com"},
    "first_request_date": date(2026, 10, 28),
    "roof_works": ("Dakwerken", 38000),
    "legal_proceedings": "<p>Geen procedures als eiser of verweerder. Lopend minnelijk overleg met de "
                         "aannemer van de gevelwerken (2024) over vochtplekken in blok A; geen dagvaarding.</p>",
}

STAFF_USER = {"name": "Medewerker Voorbeeld", "login": "medewerker.voorbeeld@example.com"}

KEY_NAMES = {
    "general": "Algemene sleutel",
    "elevator": "Liftsleutel",
    "heating": "Verwarmingssleutel",
}


def distribute_shares(weights, total=1000):
    """Round weights to whole shares that add up exactly to total."""
    return largest_remainder(total, weights)


def fake_iban(account_number):
    """Valid Belgian IBAN on the unassigned bank code 999."""
    first10 = f"999{account_number:07d}"
    bban = first10 + f"{int(first10) % 97 or 97:02d}"
    check = 98 - int(bban + "111400") % 97  # "BE00" moved to the end, B=11, E=14
    return f"BE{check:02d}{bban}"


def _key_weight(key_type, lot, top_floor):
    if key_type == "general":
        return lot["area"] * TYPE_WEIGHT[lot["lot_type"]]
    if key_type == "elevator":
        return lot["area"] * LIFT_FLOOR_FACTOR[lot["floor_number"]] if lot["lot_type"] == "apartment" else 0
    if key_type == "heating":
        outer = lot["floor_number"] in (0, top_floor)
        return lot["area"] * (HEATING_OUTER_FLOOR_FACTOR if outer else 1.0)
    raise ValueError(key_type)


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    def _demo_installations(self, vme, suppliers):
        installations = self.env["vme.installation"]
        for name, kind, location, maintenance, body, contract, reports in INSTALLATIONS.get(vme.name, []):
            installation = self.env["vme.installation"].create({
                "association_id": vme.id,
                "name": name,
                "installation_type": kind,
                "location": location,
                "maintenance_partner_id": suppliers[maintenance].id if maintenance else False,
                "maintenance_contract_ref": contract[0] if contract else False,
                "maintenance_contract_end": contract[1] if contract else False,
                "inspection_partner_id": suppliers[body].id,
            })
            for report_date, report_kind, result, remarks in reports:
                self.env["vme.inspection"].create({
                    "installation_id": installation.id,
                    "date": report_date,
                    "kind": report_kind,
                    "result": result,
                    "partner_id": suppliers[body].id,
                    "remark_ids": [Command.create({
                        "name": text, "severity": severity, "deadline": deadline, "responsible": responsible,
                    }) for text, severity, deadline, responsible in remarks],
                })
            installations |= installation
        return installations

    def _demo_supplier_banks(self, suppliers):
        """Confirmed bank accounts of the suppliers whose bills are read from PDF (step 21).

        The AI reading compares the IBAN on a bill with these; the energy supplier's one is the
        IBAN in its UBL bills.
        """
        banks = self.env["res.partner.bank"].create([
            {"acc_number": iban, "partner_id": suppliers[code].id} for code, iban in SUPPLIER_IBANS.items()
        ])
        if all(bank._user_can_trust() for bank in banks):
            banks.allow_out_payment = True

    @api.model
    def _load_demo_data(self):
        if self.with_context(active_test=False).search_count([("name", "=", BUILDINGS[0]["name"])]):
            raise UserError(self.env._("De demodata is al geladen."))

        Partner = self.env["res.partner"]
        account_number = 1
        start_years = iter(range(2008, 2026))
        vmes = self.browse()
        suppliers = {
            code: Partner.create({**vals, "is_company": True, "country_id": self.env.ref("base.be").id})
            for code, vals in {**SUPPLIERS, **INSPECTION_SUPPLIERS}.items()
        }
        self._demo_supplier_banks(suppliers)
        rule_accounts = []  # (rule, account code): set once the chart of accounts exists

        for building in BUILDINGS:
            vme = self.create({
                "name": building["name"],
                "kbo_number": building["kbo"],
                "street": building["street"],
                "zip": building["zip"],
                "city": building["city"],
                "assembly_period_month": ASSEMBLY_PERIODS[building["name"]][0],
                "assembly_period_day": ASSEMBLY_PERIODS[building["name"]][1],
            })
            banks = self.env["res.partner.bank"].create([
                {"acc_number": fake_iban(account_number + offset), "partner_id": vme.partner_id.id}
                for offset in (0, 1)
            ])
            account_number += 2
            vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
            # Odoo only lets a person with the right permissions trust bank accounts, never a
            # script running as the system user; then the VME form asks to confirm them.
            if all(bank._user_can_trust() for bank in banks):
                banks.allow_out_payment = True

            lots = self.env["vme.lot"].create([
                {
                    "association_id": vme.id,
                    "sequence": index,
                    "name": lot["name"],
                    "lot_type": lot["lot_type"],
                    "floor": lot["floor"],
                }
                for index, lot in enumerate(building["lots"])
            ])
            lot_by_name = dict(zip(lots.mapped("name"), lots))

            top_floor = max(lot["floor_number"] for lot in building["lots"])
            key_by_type = {}
            for key_type in building["keys"]:
                pairs = [(lot, _key_weight(key_type, lot, top_floor)) for lot in building["lots"]]
                pairs = [(lot, weight) for lot, weight in pairs if weight]
                shares = distribute_shares([weight for _lot, weight in pairs])
                key_by_type[key_type] = self.env["vme.key"].create({
                    "name": KEY_NAMES[key_type],
                    "association_id": vme.id,
                    "key_type": key_type,
                    "total_shares": 1000,
                    "line_ids": [
                        Command.create({"lot_id": lot_by_name[lot["name"]].id, "shares": share})
                        for (lot, _weight), share in zip(pairs, shares)
                    ],
                })

            for supplier_code, key_type, account_code in RULES:
                if key_type in key_by_type:
                    rule = self.env["vme.distribution.rule"].create({
                        "association_id": vme.id,
                        "partner_id": suppliers[supplier_code].id,
                        "key_id": key_by_type[key_type].id,
                    })
                    rule_accounts.append((rule, account_code))

            installations = self._demo_installations(vme, suppliers)
            elevator = installations.filtered(lambda i: i.installation_type == "elevator")
            if elevator and "elevator" in key_by_type:
                # Bills of the inspection body register the elevator inspection automatically.
                rule = self.env["vme.distribution.rule"].create({
                    "association_id": vme.id,
                    "partner_id": suppliers["inspection_body"].id,
                    "key_id": key_by_type["elevator"].id,
                    "installation_id": elevator.id,
                })
                rule_accounts.append((rule, "611000"))

            working, reserve = BUDGETS[building["name"]]
            self.env["vme.budget"].create([{
                "association_id": vme.id,
                "year": year,
                "working_capital_budget": working,
                "reserve_capital_contribution": reserve,
                "calls_per_year": "4",
            } for year in BUDGET_YEARS])

            short_name = building["name"].split()[-1]
            owner_by_lot = {}
            for lot in building["lots"]:
                name = lot["name"]
                same_owner_as = building.get("garage_owner_of", {}).get(name) or building.get("shared_owner", {}).get(name)
                if same_owner_as:
                    owner_by_lot[name] = owner_by_lot[same_owner_as]
                    continue
                owner_by_lot[name] = Partner.create({
                    "name": f"Eigenaar {short_name} {name}",
                    "email": f"eigenaar.{short_name.lower()}.{name.lower()}@example.com",
                })

            buyer = None
            if building.get("sold_lots"):
                first = building["sold_lots"][0]
                buyer = Partner.create({
                    "name": f"Nieuwe eigenaar {short_name} {first}",
                    "email": f"nieuwe.eigenaar.{short_name.lower()}.{first.lower()}@example.com",
                })

            ownership_vals = []
            start_by_owner = {}
            for lot in building["lots"]:
                owner = owner_by_lot[lot["name"]]
                if owner not in start_by_owner:
                    start_by_owner[owner] = date(next(start_years, 2015), 1 + len(start_by_owner) % 12, 1)
                sold = lot["name"] in building.get("sold_lots", [])
                ownership_vals.append({
                    "lot_id": lot_by_name[lot["name"]].id,
                    "partner_id": owner.id,
                    "date_start": start_by_owner[owner],
                    "date_end": SALE_DATE_END if sold else False,
                })
                if sold:
                    ownership_vals.append({
                        "lot_id": lot_by_name[lot["name"]].id,
                        "partner_id": buyer.id,
                        "date_start": SALE_DATE_START,
                    })
            self.env["vme.ownership"].create(ownership_vals)
            vmes |= vme

        self._load_demo_assembly_blocks()
        self._load_demo_assembly_2026()
        self._load_demo_sale()

        def set_rule_accounts():
            # Runs at commit, after the chart of accounts of the new companies is loaded.
            for rule, code in rule_accounts:
                rule.account_id = self.env["account.account"].with_company(rule.company_id).search(
                    [("company_ids", "in", rule.company_id.id), ("code", "=", code)], limit=1
                )
        self.env.cr.precommit.add(set_rule_accounts)

        # Tasks for inspections that are (nearly) due, as the daily cron would create them.
        self.env["vme.installation"]._cron_schedule_inspection_activities()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Demodata geladen"),
                "message": self.env._("%s VME's met kavels, sleutels en eigenaars.", len(vmes)),
                "type": "success",
                "next": self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_association_action"),
            },
        }

    @api.model
    def _load_demo_sale(self):
        spec = DEMO_SALE
        vme = self.search([("name", "=", spec["vme"])])
        vme.legal_proceedings = spec["legal_proceedings"]
        title, amount = spec["roof_works"]
        self.env["vme.assembly.item"].search([
            ("association_id", "=", vme.id), ("name", "=like", f"{title}%")]).works_amount = amount
        Partner = self.env["res.partner"]
        return self.env["vme.sale.file"].create({
            "association_id": vme.id,
            "lot_ids": [Command.set(vme.lot_ids.filtered(lambda lot: lot.name in spec["lots"]).ids)],
            "notary_id": Partner.create({**spec["notary"], "country_id": self.env.ref("base.be").id}).id,
            "notary_reference": spec["notary_reference"],
            "buyer_id": Partner.create(spec["buyer"]).id,
            "first_request_date": spec["first_request_date"],
            "user_id": self.env.ref("base.user_admin").id,
        })

    @api.model
    def _load_demo_assembly_blocks(self):
        """Rooms, one fictitious employee and free blocks for the 2027 general assemblies."""
        rooms = self.env["vme.assembly.room"].create([
            {"name": name, "address": address, "capacity": capacity} for name, address, capacity in ASSEMBLY_ROOMS
        ])
        staff = self.env["res.users"].search([("login", "=", STAFF_USER["login"])]) or \
            self.env["res.users"].with_context(no_reset_password=True).create(STAFF_USER)
        users = {"admin": self.env.ref("base.user_admin"), "staff": staff}
        self.env["vme.assembly.slot"].create([{
            "date": day,
            "time_start": hour,
            "location_type": "online" if room_index is None else "room",
            "room_id": False if room_index is None else rooms[room_index].id,
            "user_id": users[user].id,
            "max_assemblies": capacity,
        } for day, hour, room_index, user, capacity in ASSEMBLY_BLOCKS])

    @api.model
    def _load_demo_assembly_2026(self):
        """The ordinary assembly of Residentie Linde held on 10 March 2026, with votes and decisions."""
        spec = DEMO_ASSEMBLY_2026
        vme = self.search([("name", "=", spec["vme"])])
        day, hour, room_index = spec["block"]
        room = self.env["vme.assembly.room"].search([("name", "=", ASSEMBLY_ROOMS[room_index][0])])
        slot = self.env["vme.assembly.slot"].create({
            "date": day, "time_start": hour, "room_id": room.id, "user_id": self.env.ref("base.user_admin").id,
        })
        assembly = self.env["vme.assembly"].create({"association_id": vme.id, "year": day.year, "slot_id": slot.id})
        assembly.action_confirm()
        assembly.convocation_sent_date = spec["convocation_sent"]
        assembly.action_create_attendance_list()
        # The first lot of each attendee is its apartment (lots are sorted, garages come last).
        by_apartment = {a.lot_names.split(", ")[0]: a for a in assembly.attendee_ids}
        for apartment in spec["present"]:
            by_apartment[apartment].attendance = "present"
        for apartment, holder in spec["represented"].items():
            by_apartment[apartment].write({
                "attendance": "represented", "proxy_holder_id": by_apartment[holder].partner_id.id})
        assembly.write({
            "chair_id": by_apartment[spec["chair"]].partner_id.id,
            "secretary_id": by_apartment[spec["secretary"]].partner_id.id,
        })
        next_sequence = max(assembly.item_ids.mapped("sequence")) + 1
        votes_against, votes_abstain = {}, {}
        for offset, (title, majority, against, abstain, decision, follow_up) in enumerate(spec["extra_items"]):
            item = self.env["vme.assembly.item"].create({
                "assembly_id": assembly.id, "sequence": next_sequence + offset, "name": title,
                "majority": majority, "decision": decision, "follow_up_summary": follow_up,
                "follow_up_deadline": date(2026, 5, 15) if follow_up else False,
                "follow_up_user_id": self.env.ref("base.user_admin").id if follow_up else False,
            })
            votes_against[item], votes_abstain[item] = against, abstain
        assembly.action_prepare_votes()
        for item, against in votes_against.items():
            for vote in item.vote_ids:
                apartment = vote.lot_names.split(", ")[0]
                if apartment in against:
                    vote.vote = "against"
                elif apartment in votes_abstain[item]:
                    vote.vote = "abstain"
        assembly.action_mark_held()
        return assembly
