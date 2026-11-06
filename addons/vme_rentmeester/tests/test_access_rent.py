from datetime import date

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRentAccess(TransactionCase):
    """Rent contracts live in the company of the rent office: only users with that company see them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.office = cls.env["res.company"].create({
            "name": "Rentmeesterkantoor Toegang", "country_id": cls.env.ref("base.be").id,
            "currency_id": cls.env.ref("base.EUR").id, "is_rent_management": True,
        })
        cls.env.user.company_ids |= cls.office
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Toegang"})
        cls.env.cr.precommit.run()
        lot = cls.env["vme.lot"].create({"association_id": cls.vme.id, "name": "A1"})
        landlord, tenant = cls.env["res.partner"].create([{"name": "Verhuurder Toegang"}, {"name": "Huurder Toegang"}])
        cls.env["vme.ownership"].create({"lot_id": lot.id, "partner_id": landlord.id, "date_start": date(2015, 1, 1)})
        cls.contract = cls.env["vme.rent.contract"].create({
            "company_id": cls.office.id, "lot_ids": [Command.set(lot.ids)], "landlord_id": landlord.id,
            "tenant_ids": [Command.set(tenant.ids)], "date_signed": date(2026, 3, 15),
            "date_start": date(2026, 4, 1), "duration_years": 9, "rent": 700, "charges_amount": 50,
        })
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.syndic_staff = Users.create({
            "name": "Medewerker Zonder Kantoor", "login": "zonder.kantoor@example.com",
            "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
            "company_id": cls.vme.company_id.id, "company_ids": [Command.set(cls.vme.company_id.ids)],
        })
        cls.office_staff = Users.create({
            "name": "Medewerker Kantoor", "login": "kantoor@example.com",
            "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
            "company_id": cls.office.id, "company_ids": [Command.set((cls.office | cls.vme.company_id).ids)],
        })
        partner = cls.env["res.partner"].create({"name": "Commissaris Toegang", "email": "commissaris.toegang@example.com"})
        mandate = cls.env["vme.mandate"].create({
            "association_id": cls.vme.id, "role": "auditor", "partner_id": partner.id, "date_start": date.today()})
        mandate.action_grant_access()
        cls.auditor = mandate.user_id

    def test_only_the_office_sees_rent_contracts(self):
        self.assertEqual(self.env["vme.rent.contract"].with_user(self.office_staff).search([]), self.contract)
        for user in (self.syndic_staff, self.auditor):
            with self.subTest(user=user.name):
                self.assertFalse(self.env["vme.rent.contract"].with_user(user).search([]))
                self.assertFalse(self.env["vme.rent.contract.charge"].with_user(user).search([]))
                with self.assertRaises(AccessError):
                    self.contract.with_user(user).rent = 1

    def test_auditor_never_writes_rent_records(self):
        self.auditor.company_ids |= self.office  # even if someone gives him the office by mistake
        with self.assertRaises(AccessError):
            self.contract.with_user(self.auditor).rent = 1
