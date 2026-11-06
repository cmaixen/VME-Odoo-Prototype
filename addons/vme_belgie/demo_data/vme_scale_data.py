"""Fictitious portfolio of 200 VMEs to measure performance at the size of the pilot syndic.

Only for the separate database vme_scale (see docs/dev/schaal.md); never in the demo. Names are
"Residentie Test 001" and "Eigenaar T001-A1", KBO and VAT numbers start with 000 and IBANs use the
non-existent bank code 999, like the demo data. Every VME is generated from its own random seed,
so a rerun gives the same portfolio.

The chart of accounts of a new VME company only loads at commit, so loading is done in two
steps per batch, each followed by a commit (tools/scale_data.py does that):
1. _load_scale_data(): VMEs, lots, keys, owners, budgets, installations and assemblies;
2. _load_scale_history(): accounts on rules and budget lines, provision calls 2026 with payments,
   and a year of supplier bills, distributed automatically when posted.
"""
import base64
import math
import random
from datetime import date, timedelta

from odoo import api, models
from odoo.exceptions import UserError
from odoo.fields import Command

from .vme_demo_data import KEY_NAMES, TYPE_WEIGHT, distribute_shares, fake_iban
from .vme_demo_history import HISTORY_YEAR, QUARTERS, YEAR_PERIOD

SCALE_DB = "vme_scale"
SCALE_PREFIX = "Residentie Test"
# Bank account numbers far above those of the demo, so both can live in one database.
SCALE_ACCOUNT_OFFSET = 500000
SCALE_TODAY = date(2026, 11, 5)  # the demo date
# Placeholder file of the generated certificates.
SCALE_CERTIFICATE_PDF = base64.b64encode(b"%PDF-1.4\n% Fictief attest voor de schaaltest\n")

# Fictitious suppliers (VAT 0000 + number with valid check digits): key type, account, VAT on bill.
SCALE_SUPPLIERS = {
    "cleaning": ("Schoonmaak Test BV", 9001, "general", "611000", True),
    "insurance": ("Verzekeringen Test NV", 9002, "general", "614000", False),
    "energy": ("Energie Test NV", 9003, "general", "612500", True),
    "elevator": ("Liftonderhoud Test BV", 9004, "elevator", "611000", True),
    "inspection": ("Keuringsdienst Test vzw", 9005, None, None, False),
}

# Yearly working capital budget per apartment (euro), split over the budget lines below.
BUDGET_PER_APARTMENT = (650, 1100)
BUDGET_SHARES = [  # supplier, account, key type, description, share of the working capital budget
    ("cleaning", "611000", "general", "Schoonmaak gemene delen", 0.30),
    ("energy", "612500", "general", "Elektriciteit gemene delen", 0.20),
    ("insurance", "614000", "general", "Brandverzekering", 0.20),
    ("elevator", "611000", "elevator", "Onderhoud lift", 0.12),
]
# Share of VMEs whose reserve contribution stays under the 5% minimum (reserve signal).
LOW_RESERVE_RATE = 0.1
# Share of owners who did not pay provision calls 3 and 4 (arrears).
UNPAID_OWNER_RATE = 0.06
# Employees who lead the assemblies; Odoo allows each one a few assemblies per evening.
SCALE_STAFF = 10
# Share of VMEs without a held ordinary assembly in 2026 (assembly signal).
NO_ASSEMBLY_RATE = 0.05
# Share of VMEs built before 2001 without an asbestos certificate yet (certificate signal).
NO_ASBESTOS_RATE = 0.1


def _check_digits_number(number, digits=8):
    """Ten digits: number with Belgian mod-97 check digits, as used by KBO and VAT numbers."""
    base = f"{number:0{digits}d}"
    return base + f"{97 - int(base) % 97:02d}"


def scale_kbo(index):
    digits = _check_digits_number(100000 + index)
    return f"{digits[:4]}.{digits[4:7]}.{digits[7:]}"


def scale_name(index):
    return f"{SCALE_PREFIX} {index:03d}"


def scale_building(index):
    """Lots of building number index: 6 to 60 lots on 1 to 6 floors, sometimes with garages."""
    rng = random.Random(index)
    total = rng.randint(6, 60)
    garages = rng.choice([0, 0, total // 4])
    apartments = total - garages
    floors = max(1, min(6, math.ceil(apartments / rng.randint(2, 8))))
    per_floor = math.ceil(apartments / floors)
    areas = [rng.randint(55, 120) for _ in range(per_floor)]
    lots = []
    for number in range(apartments):
        floor = number // per_floor
        lots.append({
            "name": f"A{number + 1}", "lot_type": "apartment", "floor_number": floor,
            "floor": "Gelijkvloers" if floor == 0 else f"Verdieping {floor}",
            "area": areas[number % per_floor] + 2 * floor,
        })
    lots += [{"name": f"G{n}", "lot_type": "garage", "floor": "Kelder", "floor_number": -1, "area": 15}
             for n in range(1, garages + 1)]
    return {
        "rng": rng,
        "lots": lots,
        "elevator": floors >= 3,
        "apartments": apartments,
    }


def _weight(key_type, lot):
    if key_type == "general":
        return lot["area"] * TYPE_WEIGHT[lot["lot_type"]]
    # Lift: garages and the ground floor use it least, higher floors more.
    if lot["lot_type"] != "apartment":
        return 0
    return lot["area"] * (0.5 if lot["floor_number"] == 0 else 1 + 0.2 * (lot["floor_number"] - 1))


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _scale_staff(self):
        """Fictitious employees of the syndic who lead the assemblies (at most a few per evening)."""
        Users = self.env["res.users"].with_context(no_reset_password=True)
        return Users.browse([
            (Users.search([("login", "=", login)], limit=1) or Users.create({"name": name, "login": login})).id
            for name, login in ((f"Medewerker Test {n:02d}", f"medewerker.test.{n:02d}@example.com")
                                for n in range(1, SCALE_STAFF + 1))
        ])

    @api.model
    def _scale_assembly_slot(self, day, staff):
        """An online block on that evening of an employee who still has room for an assembly."""
        Slot = self.env["vme.assembly.slot"]
        slots = Slot.search([("date", "=", day), ("user_id", "in", staff.ids)])
        for slot in slots:
            if slot.free_count:
                return slot
        for slot in slots:
            if slot.max_assemblies < slot.user_id.vme_max_assemblies_per_evening:
                slot.max_assemblies += 1
                return slot
        free = staff - slots.user_id
        if not free:
            raise UserError(self.env._("Geen medewerker meer vrij op %s.", day))
        return Slot.create({"date": day, "time_start": 19.0, "location_type": "online", "user_id": free[0].id})

    def _check_scale_database(self):
        if self.env.cr.dbname != SCALE_DB and not self.env.context.get("vme_scale_allow"):
            raise UserError(self.env._("De schaaldata mag alleen in de database %s.", SCALE_DB))

    @api.model
    def _scale_suppliers(self):
        Partner = self.env["res.partner"]
        suppliers = {}
        for code, (name, number, _key, _account, _vat) in SCALE_SUPPLIERS.items():
            vat = f"BE{_check_digits_number(number)}"
            suppliers[code] = Partner.search([("vat", "=", vat)], limit=1) or Partner.create({
                "name": name, "vat": vat, "is_company": True,
                "email": f"facturen@{name.split()[0].lower()}-test.example.com",
                "country_id": self.env.ref("base.be").id,
            })
        return suppliers

    @api.model
    def _load_scale_data(self, start=1, count=200):
        """Create VMEs start .. start + count - 1 that do not exist yet. Returns the new VMEs."""
        self._check_scale_database()
        suppliers = self._scale_suppliers()
        existing = set(self.with_context(active_test=False).search([("name", "=like", f"{SCALE_PREFIX} %")]).mapped("name"))
        staff = self._scale_staff()
        vmes = self.browse()
        for index in range(start, start + count):
            if scale_name(index) in existing:
                continue
            vmes |= self._create_scale_vme(index, suppliers, staff)
        return vmes

    def _create_scale_vme(self, index, suppliers, staff):
        building = scale_building(index)
        rng = building["rng"]
        code = f"T{index:03d}"
        vme = self.create({
            "name": scale_name(index),
            "kbo_number": scale_kbo(index),
            "street": f"Teststraat {index}",
            "zip": "2000",
            "city": "Voorbeeldstad",
            "assembly_period_month": str(rng.randint(3, 6)),
            "assembly_period_day": rng.randint(1, 15),
            "arrears_signal_threshold": rng.choice([500, 1000, 1000, 2000]),
        })
        banks = self.env["res.partner.bank"].create([
            {"acc_number": fake_iban(SCALE_ACCOUNT_OFFSET + 2 * index + offset), "partner_id": vme.partner_id.id}
            for offset in (0, 1)
        ])
        vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        if all(bank._user_can_trust() for bank in banks):
            banks.allow_out_payment = True

        lots = self.env["vme.lot"].create([{
            "association_id": vme.id, "sequence": seq, "name": lot["name"],
            "lot_type": lot["lot_type"], "floor": lot["floor"],
        } for seq, lot in enumerate(building["lots"])])
        lot_by_name = dict(zip(lots.mapped("name"), lots))

        key_types = ["general"] + (["elevator"] if building["elevator"] else [])
        for key_type in key_types:
            pairs = [(lot, _weight(key_type, lot)) for lot in building["lots"]]
            pairs = [(lot, weight) for lot, weight in pairs if weight]
            shares = distribute_shares([weight for _lot, weight in pairs])
            self.env["vme.key"].create({
                "name": KEY_NAMES[key_type], "association_id": vme.id, "key_type": key_type, "total_shares": 1000,
                "line_ids": [Command.create({"lot_id": lot_by_name[lot["name"]].id, "shares": share})
                             for (lot, _weight), share in zip(pairs, shares)],
            })

        # Owners: one per apartment, an investor owns two neighbouring apartments now and then,
        # and the owner of apartment An also owns garage Gn.
        owners = {}
        for lot in building["lots"]:
            name = lot["name"]
            number = int(name[1:])
            if lot["lot_type"] == "garage" and f"A{number}" in owners:
                owners[name] = owners[f"A{number}"]
            elif number > 1 and name.startswith("A") and rng.random() < 0.08:
                owners[name] = owners[f"A{number - 1}"]
            else:
                owners[name] = {"name": f"Eigenaar {code}-{name}",
                                "email": f"eigenaar.{code.lower()}.{name.lower()}@example.com"}
        unique = {id(vals): vals for vals in owners.values()}
        partners = dict(zip(unique, self.env["res.partner"].create(list(unique.values()))))
        self.env["vme.ownership"].create([{
            "lot_id": lot_by_name[name].id,
            "partner_id": partners[id(vals)].id,
            "date_start": date(rng.randint(2000, 2025), rng.randint(1, 12), 1),
        } for name, vals in owners.items()])

        working = round(building["apartments"] * rng.randint(*BUDGET_PER_APARTMENT), -2)
        reserve_rate = 0.03 if rng.random() < LOW_RESERVE_RATE else rng.choice([0.05, 0.08, 0.10])
        self.env["vme.budget"].create([{
            "association_id": vme.id, "year": year, "working_capital_budget": working,
            "reserve_capital_contribution": round(working * reserve_rate, -1), "calls_per_year": "4",
        } for year in (HISTORY_YEAR, HISTORY_YEAR + 1)])

        # Installations: the lift and the fire extinguishers, inspected some time ago.
        specs = [("Brandblussers", "fire_extinguishers")] + ([("Lift", "elevator")] if building["elevator"] else [])
        for name, kind in specs:
            installation = self.env["vme.installation"].create({
                "association_id": vme.id, "name": name, "installation_type": kind,
                "maintenance_partner_id": suppliers["elevator"].id if kind == "elevator" else False,
                "inspection_partner_id": suppliers["inspection"].id,
            })
            self.env["vme.inspection"].create({
                "installation_id": installation.id, "kind": "inspection", "result": "compliant",
                "partner_id": suppliers["inspection"].id,
                # Mostly within the interval, about one in eight overdue.
                "date": SCALE_TODAY - timedelta(days=rng.randint(30, 420)),
            })

        # The ordinary assembly of 2026, held within its period (except a few VMEs).
        if rng.random() >= NO_ASSEMBLY_RATE:
            period_start, _period_end = vme._get_assembly_period(HISTORY_YEAR)
            slot = self._scale_assembly_slot(period_start + timedelta(days=rng.randint(0, 13)), staff)
            assembly = self.env["vme.assembly"].create({
                "association_id": vme.id, "year": HISTORY_YEAR, "slot_id": slot.id})
            assembly.state = "held"
        self._create_scale_compliance(vme, suppliers)
        return vme

    def _create_scale_compliance(self, vme, suppliers):
        """Building insurance, electrical inspection and certificates (vme_compliance.py).

        A separate random seed, so the portfolio generated before this step stays the same.
        """
        rng = random.Random(f"compliance-{vme.name}")
        vme.construction_year = rng.randint(1960, 2020)
        # The due dates are spread over the coming year: about one in twelve within 30 days.
        date_end = SCALE_TODAY + timedelta(days=rng.randint(1, 365))
        self.env["vme.insurance.policy"].create({
            "association_id": vme.id, "name": "Brandverzekering gebouw", "policy_type": "building",
            "insurer_id": suppliers["insurance"].id, "policy_number": f"BR-{vme.kbo_number}",
            "date_start": date_end - timedelta(days=364), "date_end": date_end,
            "insured_value": round(len(vme.lot_ids) * rng.randint(150000, 250000), -4),
        })
        electrical = self.env["vme.installation"].create({
            "association_id": vme.id, "name": "Elektrische installatie gemene delen", "installation_type": "electrical",
            "inspection_partner_id": suppliers["inspection"].id,
        })
        self.env["vme.inspection"].create({
            "installation_id": electrical.id, "kind": "inspection", "result": "compliant",
            "partner_id": suppliers["inspection"].id, "date": SCALE_TODAY - timedelta(days=rng.randint(60, 1500)),
        })
        certificates = [("epc_common", "vme_belgie.folder_certificates", "EPC gemeenschappelijke delen")]
        if vme.construction_year >= 2001:
            certificates.append(("pid", "vme_belgie.folder_pid", "Postinterventiedossier"))
        elif rng.random() >= NO_ASBESTOS_RATE:
            certificates.append(("asbestos", "vme_belgie.folder_certificates", "Asbestattest gemene delen"))
        self.env["vme.document"].create([{
            "name": title, "association_id": vme.id, "folder_id": self.env.ref(folder).id,
            "certificate_type": certificate_type, "datas": SCALE_CERTIFICATE_PDF, "filename": f"{title}.pdf",
            "date": SCALE_TODAY - timedelta(days=rng.randint(30, 3000)),
        } for certificate_type, folder, title in certificates])

    def _load_scale_history(self):
        """Accounts, provision calls with payments and supplier bills of 2026 for these VMEs.

        Needs the charts of accounts of the VMEs, so run it in a transaction after _load_scale_data().
        """
        self._check_scale_database()
        vmes = self.filtered(lambda v: not v.budget_ids.filtered(lambda b: b.year == HISTORY_YEAR).provision_call_ids)
        if not vmes:
            return vmes
        suppliers = self._scale_suppliers()
        for vme in vmes:
            company = vme.company_id
            Account = self.env["account.account"].with_company(company)
            accounts = {code: Account.search([("company_ids", "in", company.id), ("code", "=", code)], limit=1)
                        for code in {line[1] for line in BUDGET_SHARES}}
            keys = {key.key_type: key for key in vme.key_ids}
            for code, (_name, _number, key_type, account_code, _vat) in SCALE_SUPPLIERS.items():
                if key_type in keys:
                    self.env["vme.distribution.rule"].create({
                        "association_id": vme.id, "partner_id": suppliers[code].id,
                        "key_id": keys[key_type].id, "account_id": accounts[account_code].id,
                    })
            self.env["vme.budget.line"].create([{
                "budget_id": budget.id, "account_id": accounts[account].id, "key_id": keys[key_type].id,
                "name": name, "amount": round(budget.working_capital_budget * share, -1),
            } for budget in vme.budget_ids for _code, account, key_type, name, share in BUDGET_SHARES
                if key_type in keys])

        unpaid = {}
        for vme in vmes:
            rng = random.Random(f"unpaid-{vme.name}")
            for partner in vme.lot_ids.current_owner_id:
                if rng.random() < UNPAID_OWNER_RATE:
                    unpaid[partner.name] = {3, 4}
        self._demo_history_provisions(vmes, vmes._ensure_fund_bank_journals(), unpaid=unpaid)
        vmes._scale_history_bills(suppliers)
        return vmes

    def _scale_history_bills(self, suppliers):
        """Quarterly cleaning and energy, the yearly insurance and half-yearly lift maintenance."""
        for vme in self:
            rng = random.Random(f"bills-{vme.name}")
            company = vme.company_id
            purchase_tax = company.account_purchase_tax_id
            budget = vme.budget_ids.filtered(lambda b: b.year == HISTORY_YEAR)
            has_elevator = "elevator" in vme.key_ids.mapped("key_type")
            bills = []
            for code, _account, _key, description, share in BUDGET_SHARES:
                if code == "elevator" and not has_elevator:
                    continue
                # Costs between 80% and 120% of the budget, some VMEs clearly over.
                yearly = budget.working_capital_budget * share * rng.uniform(0.8, 1.2)
                if code == "insurance":
                    periods = [(date(HISTORY_YEAR, 1, 20), *YEAR_PERIOD)]
                elif code == "elevator":
                    periods = [(date(HISTORY_YEAR, 3, 15), date(HISTORY_YEAR, 1, 1), date(HISTORY_YEAR, 6, 30)),
                               (date(HISTORY_YEAR, 9, 15), date(HISTORY_YEAR, 7, 1), date(HISTORY_YEAR, 12, 31))]
                else:
                    periods = QUARTERS
                with_vat = SCALE_SUPPLIERS[code][4]
                amount = round(yearly / (len(periods) if code != "energy" else 4) / (1.21 if with_vat else 1), 2)
                for invoice_date, start, end in periods:
                    bills.append({
                        "move_type": "in_invoice",
                        "partner_id": suppliers[code].id,
                        "invoice_date": invoice_date,
                        "ref": f"{code.upper()}-{vme.name[-3:]}-{invoice_date:%Y%m%d}",
                        "vme_period_start": start,
                        "vme_period_end": end,
                        "invoice_line_ids": [Command.create({
                            "name": description, "quantity": 1, "price_unit": amount,
                            "tax_ids": [Command.set(purchase_tax.ids)] if with_vat else [Command.clear()],
                        })],
                    })
            moves = self.env["account.move"].with_company(company).create(bills)
            # Posting distributes every bill automatically through the distribution rules.
            moves.with_company(company).action_post()
