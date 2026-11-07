"""Links between records of two companies, or to a bank account of someone else, are refused (B-F7)."""
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCheckCompanyRent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.office_a, cls.office_b = Company.create([
            {"name": "Rentmeester Company A", "is_rent_management": True},
            {"name": "Rentmeester Company B", "is_rent_management": True}])
        cls.env.user.company_ids |= cls.office_a | cls.office_b
        cls.landlord = cls.env["res.partner"].create({"name": "Verhuurder Company"})
        cls.tenant = cls.env["res.partner"].create({"name": "Huurder Company"})
        cls.stranger_bank = cls.env["res.partner.bank"].create({
            "acc_number": "BE71 0961 2345 6769", "partner_id": cls.tenant.id})

    def _lease(self, company):
        return self.env["vme.rent.contract"].create({
            "company_id": company.id, "landlord_id": self.landlord.id, "tenant_ids": [(6, 0, self.tenant.ids)],
            "property_address": "Companystraat 1", "region": "flanders", "date_signed": date(2025, 1, 10),
            "date_start": date(2025, 2, 1), "duration_years": 9, "rent": 800,
        })

    def _mandate(self, company, **vals):
        return self.env["vme.rent.mandate"].create({
            "company_id": company.id, "landlord_id": self.landlord.id, "fee_tax_id": False, **vals})

    def test_mandate_of_another_office(self):
        contract = self._lease(self.office_a)
        mandate_b = self._mandate(self.office_b)
        with self.assertRaises(UserError):
            contract.mandate_id = mandate_b

    def test_invoice_of_another_office(self):
        contract = self._lease(self.office_a)
        # A bill in the books of a VME (a company with a chart of accounts), not of the office.
        vme = self.env["vme.association"].create({"name": "Residentie Company Rent"})
        self.env.cr.precommit.run()
        bill = self.env["account.move"].with_company(vme.company_id).create({
            "move_type": "entry", "date": date(2026, 3, 1)})
        with self.assertRaises(UserError):
            bill.rent_contract_id = contract

    def test_bank_account_of_someone_else(self):
        with self.assertRaises(ValidationError):
            self._mandate(self.office_a, partner_bank_id=self.stranger_bank.id)
        with self.assertRaises(ValidationError):
            self.office_a.rent_bank_id = self.stranger_bank
        own = self.env["res.partner.bank"].create({
            "acc_number": "BE62 5100 0754 7061", "partner_id": self.landlord.id})
        self.assertEqual(self._mandate(self.office_a, partner_bank_id=own.id).partner_bank_id, own)
