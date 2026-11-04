"""Fictitious demo data: three buildings with lots, keys, owners and one mid-year sale.

All names, addresses and numbers are made up. KBO numbers start with 0000 and IBANs
use the non-existent bank code 999, so they cannot belong to a real VME.
"""
from datetime import date

from odoo import api, models
from odoo.exceptions import UserError
from odoo.fields import Command

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

KEY_NAMES = {
    "general": "Algemene sleutel",
    "elevator": "Liftsleutel",
    "heating": "Verwarmingssleutel",
}


def distribute_shares(weights, total=1000):
    """Round weights to whole shares that add up exactly to total (largest remainder)."""
    weight_sum = sum(weights)
    exact = [w * total / weight_sum for w in weights]
    shares = [int(x) for x in exact]
    by_remainder = sorted(range(len(weights)), key=lambda i: exact[i] - shares[i], reverse=True)
    for i in by_remainder[: total - sum(shares)]:
        shares[i] += 1
    return shares


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

    @api.model
    def _load_demo_data(self):
        if self.with_context(active_test=False).search_count([("name", "=", BUILDINGS[0]["name"])]):
            raise UserError(self.env._("De demodata is al geladen."))

        Partner = self.env["res.partner"]
        account_number = 1
        start_years = iter(range(2008, 2026))
        vmes = self.browse()

        for building in BUILDINGS:
            vme = self.create({
                "name": building["name"],
                "kbo_number": building["kbo"],
                "street": building["street"],
                "zip": building["zip"],
                "city": building["city"],
            })
            banks = self.env["res.partner.bank"].create([
                {"acc_number": fake_iban(account_number + offset), "partner_id": vme.partner_id.id}
                for offset in (0, 1)
            ])
            account_number += 2
            vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})

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
            for key_type in building["keys"]:
                pairs = [(lot, _key_weight(key_type, lot, top_floor)) for lot in building["lots"]]
                pairs = [(lot, weight) for lot, weight in pairs if weight]
                shares = distribute_shares([weight for _lot, weight in pairs])
                self.env["vme.key"].create({
                    "name": KEY_NAMES[key_type],
                    "association_id": vme.id,
                    "key_type": key_type,
                    "total_shares": 1000,
                    "line_ids": [
                        Command.create({"lot_id": lot_by_name[lot["name"]].id, "shares": share})
                        for (lot, _weight), share in zip(pairs, shares)
                    ],
                })

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
