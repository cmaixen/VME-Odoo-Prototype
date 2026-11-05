"""Fictitious rental demo: two rented apartments in Residentie Linde and one in Hof ter Beuken.

Loaded together with the VME demo data (contracts and past indexations) and the 2026 demo
history (rent invoices and payments). All names and amounts are made up.
"""
import functools
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.fields import Command

from ..models import rent_rules

OFFICE = {"name": "Rentmeester Voorbeeld BV", "company_registry": "0000.000.394", "street": "Huurlaan 8",
          "zip": "2000", "city": "Voorbeeldstad"}

# Demo date 5 November 2026:
# - Linde A2 (+ garage G2): anniversary 1 November 2026, the draft indexation letter is ready.
#   EPC E during the freeze, so a correction factor applies.
# - Linde A7: short lease ending 28 February 2027; notice deadline 30 November 2026 (a task).
# - Beuken B23: nine-year lease since 2019, EPC D, indexed every September.
DEMO_CONTRACTS = [
    {"vme": "Residentie Linde", "lots": ["A2", "G2"], "tenant": "Huurder Linde A2",
     "date_signed": date(2021, 10, 15), "date_start": date(2021, 11, 1), "years": 9, "rent": 850, "charges": 90,
     "deposit": 1700, "epc": "E", "draft_anniversary": date(2026, 11, 1)},
    {"vme": "Residentie Linde", "lots": ["A7"], "tenant": "Huurder Linde A7",
     "date_signed": date(2024, 2, 10), "date_start": date(2024, 3, 1), "years": 3, "rent": 780, "charges": 75,
     "deposit": 1560, "epc": "C"},
    {"vme": "Hof ter Beuken", "lots": ["B23"], "tenant": "Huurder Beuken B23",
     "date_signed": date(2019, 8, 12), "date_start": date(2019, 9, 1), "years": 9, "rent": 920, "charges": 160,
     "deposit": 1840, "epc": "D"},
]
DEMO_TODAY = date(2026, 11, 5)
HISTORY_YEAR = 2026
HISTORY_MONTHS = range(1, 11)  # January to October 2026 are invoiced and paid
UNPAID_RENT = {("Huurder Linde A7", 10)}  # one open month, to show an arrear


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_data(self):
        result = super()._load_demo_data()
        self._load_demo_rentals()
        return result

    @api.model
    def _load_demo_history(self):
        result = super()._load_demo_history()
        self._load_demo_rent_history()
        return result

    @api.model
    def _demo_rent_office(self):
        company = self.env["res.company"].search([("is_rent_management", "=", True)], limit=1)
        if company:
            return company
        company = self.env["res.company"].sudo().create({
            **OFFICE, "is_rent_management": True, "country_id": self.env.ref("base.be").id,
            "currency_id": self.env.ref("base.EUR").id,
        })
        self.env.cr.precommit.add(functools.partial(self._load_vme_chart, company.id))
        internal_users = self.env["res.users"].sudo().search([("share", "=", False)]) | self.env.user
        # The auditor of the accounts (vme_belgie, step 16) only sees his own VME.
        internal_users = internal_users.filtered(lambda u: not u.has_group("vme_belgie.group_vme_auditor"))
        internal_users.sudo().write({"company_ids": [Command.link(company.id)]})
        return company

    @api.model
    def _load_demo_rentals(self):
        office = self._demo_rent_office()
        Partner = self.env["res.partner"]
        contracts = self.env["vme.rent.contract"]
        for spec in DEMO_CONTRACTS:
            vme = self.search([("name", "=", spec["vme"])])
            lots = vme.lot_ids.filtered(lambda lot, names=spec["lots"]: lot.name in names)
            short = spec["tenant"].split()[-1].lower()
            tenant = Partner.create({
                "name": spec["tenant"], "email": f"huurder.{spec['vme'].split()[-1].lower()}.{short}@example.com",
            })
            contract = self.env["vme.rent.contract"].create({
                "company_id": office.id,
                "lot_ids": [Command.set(lots.ids)],
                "landlord_id": lots[:1]._get_owner_on(spec["date_start"]).id,
                "tenant_ids": [Command.set(tenant.ids)],
                "date_signed": spec["date_signed"],
                "date_start": spec["date_start"],
                "duration_years": spec["years"],
                "rent": spec["rent"],
                "charges_type": "provision",
                "charges_amount": spec["charges"],
                "deposit_amount": spec["deposit"],
                "deposit_type": "blocked_account",
                "deposit_reference": "Geblokkeerde rekening op naam van de huurder",
                "epc_label": spec["epc"],
            })
            contract.action_activate()
            # Past anniversaries: indexed and confirmed, each with its letter a week before.
            anniversary = rent_rules.anniversary(contract.date_start, contract.date_start.year + 1)
            while anniversary < DEMO_TODAY and anniversary != spec.get("draft_anniversary"):
                contract._create_indexation(anniversary, request_date=anniversary - timedelta(days=7)).action_confirm()
                anniversary += relativedelta(years=1)
            if spec.get("draft_anniversary"):
                contract._create_indexation(spec["draft_anniversary"], request_date=DEMO_TODAY)
            contracts |= contract

        self.env["vme.rent.contract"]._demo_reminders(contracts)
        return contracts

    @api.model
    def _load_demo_rent_history(self):
        contracts = self.env["vme.rent.contract"].search([
            ("tenant_ids.name", "in", [spec["tenant"] for spec in DEMO_CONTRACTS])])
        if not contracts:
            return
        # The cleaning company only exists once the 2026 history is loaded: link it to its rubric now.
        cleaning = self.env["res.partner"].search([("name", "=", "Schoonmaak Voorbeeld BV")], limit=1)
        category = self.env.ref("vme_rentmeester.charge_category_cleaning")
        if cleaning:
            category.partner_ids = [Command.link(cleaning.id)]
        office = contracts.company_id
        journal = self.env["account.journal"].search([("company_id", "=", office.id), ("type", "=", "bank")], limit=1)
        for month in HISTORY_MONTHS:
            first = date(HISTORY_YEAR, month, 1)
            moves = contracts._create_rent_invoices(first, post=True)
            paid = moves.filtered(lambda m, n=month: (m.partner_id.name, n) not in UNPAID_RENT)
            if paid:
                self.env["account.payment.register"].with_company(office).with_context(
                    active_model="account.move", active_ids=paid.ids,
                ).create({"journal_id": journal.id, "payment_date": first + timedelta(days=3),
                          "group_payment": False}).action_create_payments()


class VmeRentContract(models.Model):
    _inherit = "vme.rent.contract"

    @api.model
    def _demo_reminders(self, contracts):
        """The tasks the daily check makes around the demo date, whatever today's date is."""
        todo = self.env.ref("mail.mail_activity_data_todo")
        for contract in contracts.filtered(lambda c: c.lease_type == "short" and c.notice_deadline):
            contract.activity_schedule(
                activity_type_id=todo.id, date_deadline=contract.notice_deadline,
                summary=self.env._("Opzegtermijn verstrijkt: %s", contract.name), user_id=self.env.user.id,
            )
            contract.activity_notice_deadline = contract.notice_deadline
        for indexation in contracts.indexation_ids.filtered(lambda i: i.state == "draft"):
            indexation.contract_id.activity_schedule(
                activity_type_id=todo.id, date_deadline=indexation.anniversary_date + timedelta(days=30),
                summary=self.env._("Indexatiebrief nakijken en versturen"), user_id=self.env.user.id,
            )
