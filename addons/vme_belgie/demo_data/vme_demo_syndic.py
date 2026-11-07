"""Demo of the syndic's own business: the office, an agreement and a mandate per demo VME, a few services."""
import functools
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.fields import Command


SYNDIC_OFFICE = {
    "name": "Syndicus Voorbeeld BV", "company_registry": "0000.000.592", "street": "Kantoorlaan 1",
    "zip": "2000", "city": "Voorbeeldstad", "email": "kantoor@syndicus-voorbeeld.example.com",
    "phone": "+32 3 000 00 00",
}

# Fictitious consumer price index figures (not the real Statbel series): from December 2023 at 128.50,
# about 0.2% more every month.
CPI_FIRST_MONTH = date(2023, 12, 1)
CPI_MONTHS = 35  # up to October 2026
CPI_START, CPI_GROWTH = 128.50, 1.002

AGREEMENTS = {
    "Residentie Linde": {"date_start": date(2024, 1, 1), "fee_basis": "lot", "fee_amount": 14.0,
                         "billing_period": "quarter", "indexation": "cpi"},
    "Hof ter Beuken": {"date_start": date(2025, 1, 1), "fee_basis": "vme", "fee_amount": 480.0,
                       "billing_period": "month", "indexation": "percent", "index_percent": 2.0},
    "Kaaihuis": {"date_start": date(2026, 1, 1), "fee_basis": "lot", "fee_amount": 18.0,
                 "billing_period": "quarter", "indexation": "none"},
}

# Linde: renewal at the assembly of March 2027 (signal now). Kaaihuis: the posting is missing.
MANDATES = {
    "Residentie Linde": {"date_start": date(2024, 3, 12), "posted_date": date(2024, 3, 15)},
    "Hof ter Beuken": {"date_start": date(2025, 4, 15), "posted_date": date(2025, 4, 18)},
    "Kaaihuis": {"date_start": date(2026, 3, 17)},
}

# Services entered by hand; others arise in the demo itself (the water damage claim of Linde A4).
MANUAL_SERVICES = [
    ("Hof ter Beuken", "extra_meeting", date(2026, 9, 15), "Extra vergadering met de raad over de conciërge"),
    ("Kaaihuis", "registered_mail", date(2026, 8, 20), "Aangetekende zending aan de aannemer van de dakgoot"),
]


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _demo_syndic_office(self):
        company = self.env["res.company"].search([("is_syndic_office", "=", True)], limit=1)
        if company:
            return company
        company = self.env["res.company"].sudo().create({
            **SYNDIC_OFFICE, "is_syndic_office": True, "country_id": self.env.ref("base.be").id,
            "currency_id": self.env.ref("base.EUR").id,
        })
        self.env.cr.precommit.add(functools.partial(self._load_vme_chart, company.id))
        internal_users = self.env["res.users"].sudo().search([("share", "=", False)]) | self.env.user
        internal_users = internal_users.filtered(lambda u: not u.has_group("vme_belgie.group_vme_auditor"))
        internal_users.sudo().write({"company_ids": [Command.link(company.id)]})
        return company

    @api.model
    def _load_demo_syndic(self):
        office = self._demo_syndic_office()
        Index = self.env["vme.consumer.price.index"]
        if not Index.search_count([]):
            Index.create([{"month": CPI_FIRST_MONTH + relativedelta(months=i),
                           "value": round(CPI_START * CPI_GROWTH ** i, 2)} for i in range(CPI_MONTHS)])
        for name, vals in AGREEMENTS.items():
            vme = self.search([("name", "=", name)])
            self.env["vme.management.agreement"].create({**vals, "association_id": vme.id,
                                                         "syndic_company_id": office.id})
            self.env["vme.syndic.mandate"].create({**MANDATES[name], "association_id": vme.id,
                                                   "partner_id": office.partner_id.id})
        for name, service_type, day, label in MANUAL_SERVICES:
            self.env["vme.service.line"].create({
                "association_id": self.search([("name", "=", name)]).id, "service_type": service_type,
                "date": day, "name": label})
        self.env["vme.syndic.mandate"]._cron_schedule_mandate_activities()

    @api.model
    def _load_demo_syndic_history(self):
        """Fee invoices of the third quarter of 2026, confirmed by the office: the VME bills stay drafts to approve.

        The VME side stays a draft on purpose, so the costs of the demo year do not change.
        """
        date_from, date_to = date(2026, 7, 1), date(2026, 9, 30)
        invoices = self.env["account.move"]
        for agreement in self.env["vme.management.agreement"].search(
                [("association_id.name", "in", list(AGREEMENTS))]):
            for start, end in agreement._billing_periods(date_from, date_to):
                invoices |= agreement._create_fee_invoice(start, end)
        for invoice in invoices:
            invoice.with_company(invoice.company_id).action_post()
        return invoices
