"""Fictitious bookkeeping year 2026 for the demo: provision calls, payments and supplier bills.

Runs after the demo data, once the charts of accounts of the VME companies are loaded.
"""
from datetime import date, timedelta

from odoo import api, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import file_open

HISTORY_YEAR = 2026
CALL_DATES = [date(2026, 1, 5), date(2026, 4, 5), date(2026, 7, 5), date(2026, 10, 5)]

# Owners who did not pay some provision calls (both funds), to show open amounts.
UNPAID_CALLS = {
    "Eigenaar Linde A3": {4},
    "Eigenaar Beuken B7": {3, 4},
}

# Fictitious suppliers (VAT numbers start with 0000) and their rule per VME: key type, account.
HISTORY_SUPPLIERS = {
    "cleaning": ("Schoonmaak Voorbeeld BV", "BE0000000592", "general", "611000"),
    "insurance": ("Verzekeringen Voorbeeld NV", "BE0000000691", "general", "614000"),
    "gas": ("Gasleverancier Voorbeeld NV", "BE0000000790", "consumption", "612500"),
    # Wage costs of the concierge of Hof ter Beuken, invoiced by an external social secretariat.
    "payroll": ("Sociaal Secretariaat Voorbeeld vzw", "BE0000018014", "general", "620300"),  # Bezoldigingen arbeiders
}

# Bills per VME: supplier code, invoice date, cost period, [(description, amount excl. VAT)], VAT.
# Supplier codes "energy" and "elevator" come from the base demo data.
QUARTERS = [(date(2026, 3, 31), date(2026, 1, 1), date(2026, 3, 31)),
            (date(2026, 6, 30), date(2026, 4, 1), date(2026, 6, 30)),
            (date(2026, 9, 30), date(2026, 7, 1), date(2026, 9, 30))]
YEAR_PERIOD = (date(2026, 1, 1), date(2026, 12, 31))
MONTH_NAMES = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september"]
# Month m of 2026 runs from day one to the day before the first of month m + 1.
MONTHS = [(date(2026, m + 1, 1) - timedelta(days=1), date(2026, m, 1), date(2026, m + 1, 1) - timedelta(days=1))
          for m in range(1, 10)]

HISTORY_BILLS = {
    "Residentie Linde": [
        ("elevator", date(2026, 3, 15), date(2026, 1, 1), date(2026, 6, 30), [("Onderhoudscontract lift 1e halfjaar", 1500)], True),
        ("elevator", date(2026, 9, 15), date(2026, 7, 1), date(2026, 12, 31), [("Onderhoudscontract lift 2e halfjaar", 1500)], True),
        *[("cleaning", d, s, e, [("Schoonmaak gemene delen", 1500)], True) for d, s, e in QUARTERS],
        ("insurance", date(2026, 1, 20), *YEAR_PERIOD, [("Brandverzekering gebouw 2026", 4200)], False),
    ],
    "Hof ter Beuken": [
        *[("gas", d, s, e, [("Aardgas centrale verwarming", 12000)], True) for d, s, e in QUARTERS],
        *[("cleaning", d, s, e, [("Schoonmaak gemene delen", 2400)], True) for d, s, e in QUARTERS],
        ("insurance", date(2026, 1, 20), *YEAR_PERIOD, [("Brandverzekering gebouw 2026", 6500)], False),
        # Wages carry no VAT. October comes as a Peppol file to upload during the demo.
        *[("payroll", d, s, e, [(f"Loonkost conciërge {month} 2026: brutoloon en werkgeversbijdragen RSZ", 3250)], False)
          for month, (d, s, e) in zip(MONTH_NAMES, MONTHS)],
    ],
    "Kaaihuis": [
        *[("cleaning", d, s, e, [("Schoonmaak gemene delen", 600)], True) for d, s, e in QUARTERS],
        ("insurance", date(2026, 1, 20), *YEAR_PERIOD, [("Brandverzekering gebouw 2026", 1800)], False),
    ],
}

# Peppol/UBL electricity invoices from the base demo (period 01-11-2025 to 31-10-2026).
UBL_FILES = {
    "Residentie Linde": "elektriciteit_residentie_linde_2026.xml",
    "Hof ter Beuken": "elektriciteit_hof_ter_beuken_2026.xml",
    "Kaaihuis": "elektriciteit_kaaihuis_2026.xml",
}


# Readings of the meter reading company (heat cost allocators), read in before the bills.
# hof_ter_beuken_2026-10-31.csv is left for the demo: read it in by hand via VME > Verbruik.
METER_FILES = {
    "Hof ter Beuken": "hof_ter_beuken_2026-09-30.csv",
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_history(self):
        vmes = self.search([("name", "in", list(HISTORY_BILLS))])
        if len(vmes) != len(HISTORY_BILLS):
            raise UserError(self.env._("Laad eerst de demodata."))
        if self.env["vme.provision.call"].search_count([("association_id", "in", vmes.ids), ("budget_id.year", "=", HISTORY_YEAR)]):
            raise UserError(self.env._("De demohistoriek %s is al geladen.", HISTORY_YEAR))
        if vmes.untrusted_fund_bank_ids:
            raise UserError(self.env._(
                "De bankrekeningen van de demo-VME's zijn nog niet bevestigd. Laad de demodata als beheerder."))

        journals = vmes._ensure_fund_bank_journals()
        self._demo_history_provisions(vmes, journals)
        self._demo_history_meter_readings(vmes)
        self._demo_history_bills(vmes)
        self._load_demo_collection()
        self._load_demo_syndic_history()
        self._load_demo_cycle()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Demohistoriek geladen"),
                "message": self.env._("Provisies, betalingen, leveranciersfacturen, invorderingen en jaarcyclus van %s.", HISTORY_YEAR),
                "type": "success",
                "next": self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_annual_statement_wizard_action"),
            },
        }

    def _demo_history_provisions(self, vmes, journals, unpaid=None):
        """Provision calls 1-4 of the history year, paid except the calls in unpaid (owner name -> numbers)."""
        unpaid = UNPAID_CALLS if unpaid is None else unpaid
        for number, call_date in enumerate(CALL_DATES, start=1):
            self.env["vme.provision.call.wizard"].create({
                "association_ids": [Command.set(vmes.ids)],
                "year": HISTORY_YEAR,
                "number": number,
                "invoice_date": call_date,
                "date_due": call_date + timedelta(days=30),
                "post_invoices": True,
            }).action_create_calls()

        for vme in vmes:
            calls = vme.budget_ids.filtered(lambda b: b.year == HISTORY_YEAR).provision_call_ids
            for call in calls:
                for fund in ("working", "reserve"):
                    invoices = call.invoice_ids.filtered(
                        lambda m, f=fund, n=call.number: m.vme_fund == f
                        and n not in unpaid.get(m.partner_id.name, set())
                    )
                    if not invoices:
                        continue
                    self.env["account.payment.register"].with_company(vme.company_id).with_context(
                        active_model="account.move", active_ids=invoices.ids,
                    ).create({
                        "journal_id": journals[vme][fund].id,
                        "payment_date": call.date_due - timedelta(days=10),
                        "group_payment": False,
                    }).action_create_payments()

    def _demo_history_meter_readings(self, vmes):
        Wizard = self.env["vme.meter.import.wizard"]
        for vme in vmes.filtered(lambda v: v.name in METER_FILES):
            with file_open(f"vme_belgie/demo_data/meterstanden/{METER_FILES[vme.name]}", "rb") as f:
                Wizard._import_file(vme, f.read(), METER_FILES[vme.name])

    @api.model
    def _demo_history_supplier(self, code):
        """Supplier of the demo history; the demo contracts may have created it already."""
        name, vat, _key, _account = HISTORY_SUPPLIERS[code]
        Partner = self.env["res.partner"]
        return Partner.search([("vat", "=", vat)], limit=1) or Partner.create({
            "name": name, "vat": vat, "is_company": True,
            "email": f"facturen@{name.split()[0].lower()}.example.com",
            "country_id": self.env.ref("base.be").id,
        })

    def _demo_history_bills(self, vmes):
        Partner = self.env["res.partner"]
        suppliers = {code: self._demo_history_supplier(code) for code in HISTORY_SUPPLIERS}
        suppliers["energy"] = Partner.search([("vat", "=", "BE0000000394")], limit=1)
        suppliers["elevator"] = Partner.search([("vat", "=", "BE0000000493")], limit=1)

        for vme in vmes:
            company = vme.company_id
            Account = self.env["account.account"].with_company(company)
            for code, (_name, _vat, key_type, account_code) in HISTORY_SUPPLIERS.items():
                key = vme.key_ids.filtered(lambda k, t=key_type: k.key_type == t)[:1]
                if key and any(bill[0] == code for bill in HISTORY_BILLS[vme.name]):
                    self.env["vme.distribution.rule"].create({
                        "association_id": vme.id,
                        "partner_id": suppliers[code].id,
                        "key_id": key.id,
                        "account_id": Account.search([("company_ids", "in", company.id), ("code", "=", account_code)], limit=1).id,
                    })

            purchase_tax = company.account_purchase_tax_id
            bills = self.env["account.move"]
            for supplier_code, invoice_date, start, end, lines, with_vat in HISTORY_BILLS[vme.name]:
                bills |= self.env["account.move"].with_company(company).create({
                    "move_type": "in_invoice",
                    "partner_id": suppliers[supplier_code].id,
                    "invoice_date": invoice_date,
                    "ref": f"{supplier_code.upper()}-{invoice_date:%Y%m%d}",
                    "vme_period_start": start,
                    "vme_period_end": end,
                    "invoice_line_ids": [Command.create({
                        "name": description,
                        "quantity": 1,
                        "price_unit": amount,
                        "tax_ids": [Command.set(purchase_tax.ids)] if with_vat else [Command.clear()],
                    }) for description, amount in lines],
                })

            journal = self.env["account.journal"].search([("company_id", "=", company.id), ("type", "=", "purchase")], limit=1)
            with file_open(f"vme_belgie/demo_data/facturen/{UBL_FILES[vme.name]}", "rb") as f:
                attachment = self.env["ir.attachment"].create({
                    "name": UBL_FILES[vme.name], "raw": f.read(), "mimetype": "application/xml",
                })
            bills |= journal.with_company(company)._create_document_from_attachment(attachment.ids)
            # Posting distributes every bill automatically through the distribution rules.
            bills.with_company(company).action_post()
