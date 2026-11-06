"""Access per role (see docs/dev/toegangsrechten.md).

Builds on the two VMEs of TestCouncil: the auditor has Residentie Raad, and a staff member with only
the company of Residentie Raad stands in for an employee who does not manage Residentie Ander.
"""
import base64
from datetime import date

from freezegun import freeze_time

from odoo.exceptions import AccessError
from odoo.fields import Command, Domain
from odoo.tests import tagged

from .test_council import TODAY, TestCouncil

# Shared configuration without a VME: every internal user reads it, the auditor writes none of it.
SHARED_MODELS = {
    "vme.assembly.room", "vme.assembly.slot", "vme.document.folder", "vme.request.type",
    "vme.communication.template", "vme.rent.index", "vme.rent.charge.category", "vme.consumer.price.index",
}
# Only through a wizard or for administrators; no company of its own.
NOT_FOR_USERS = {"vme.migration"}


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestAccessRules(TestCouncil):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff_a = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Alleen Raad", "login": "medewerker.alleen.raad@example.com",
            "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
            "company_id": cls.vme.company_id.id,
            "company_ids": [Command.set(cls.vme.company_id.ids)],
        })

    def _user_models(self):
        for name in sorted(self.env.registry):
            Model = self.env[name]
            if name.startswith("vme.") and not Model._abstract and not Model._transient and name not in NOT_FOR_USERS:
                yield name, Model

    def _can_write_anything(self, user, name):
        if not self.env["ir.model.access"].with_user(user).check(name, "write", raise_exception=False):
            return False
        return not self.env["ir.rule"].with_user(user)._compute_domain(name, "write").is_false()

    # Safety net for every model, also those added later

    def test_auditor_reads_only_his_vmes_and_writes_nothing(self):
        Rule = self.env["ir.rule"].with_user(self.auditor)
        for name, _model in self._user_models():
            with self.subTest(model=name):
                self.assertFalse(self._can_write_anything(self.auditor, name),
                                 f"De commissaris kan {name} wijzigen: voeg een rule_auditor_no_write toe.")
                if name not in SHARED_MODELS:
                    self.assertFalse(Rule._compute_domain(name, "read").is_true(),
                                     f"De commissaris leest {name} van alle VME's: voeg een leesregel toe.")

    def test_every_vme_model_is_limited_to_the_users_companies(self):
        Rule = self.env["ir.rule"].with_user(self.staff_a)
        for name, _model in self._user_models():
            if name in SHARED_MODELS:
                continue
            with self.subTest(model=name):
                self.assertFalse(Rule._compute_domain(name, "read").is_true(),
                                 f"{name} heeft geen globale company-regel (security/vme_company_security.xml).")

    # The auditor

    def test_auditor_cannot_read_or_change_records_of_another_vme(self):
        works = self.env["vme.works"].create({"association_id": self.other_vme.id, "name": "Dakwerken Ander"})
        contract = self.env["vme.contract"].create({
            "association_id": self.other_vme.id, "name": "Onderhoud lift", "contract_type": "maintenance",
            "partner_id": self.supplier.id})
        document = self.env["vme.document"].create({
            "association_id": self.other_vme.id, "name": "Basisakte Ander",
            "folder_id": self.env.ref("vme_belgie.folder_deed").id})
        for record in (works, contract, document):
            with self.subTest(model=record._name):
                self.assertFalse(record.with_user(self.auditor).search([("id", "=", record.id)]))
                with self.assertRaises(AccessError):
                    record.with_user(self.auditor).name = "Gewijzigd"
        own_works = self.env["vme.works"].create({"association_id": self.vme.id, "name": "Gevel Raad"})
        self.assertEqual(self.env["vme.works"].with_user(self.auditor).search([]), own_works)
        with self.assertRaises(AccessError):
            own_works.with_user(self.auditor).name = "Gewijzigd"

    def test_auditor_cannot_print_the_statement_of_another_vme(self):
        wizard = self.env["vme.annual.statement.wizard"].with_user(self.auditor).create(
            {"association_id": self.other_vme.id, "year": 2026})
        with self.assertRaises(AccessError):
            wizard._get_statement()
        own = self.env["vme.annual.statement.wizard"].with_user(self.auditor).create(
            {"association_id": self.vme.id, "year": 2026})
        self.assertIn("statements", own._get_statement())

    def test_buttons_that_write_as_superuser_refuse_the_auditor(self):
        communication = self.env["vme.communication"].create({"association_id": self.vme.id, "name": "Info"})
        reminder = self.env["vme.collection.reminder"].create({
            "collection_id": self.env["vme.collection"].create({
                "association_id": self.vme.id, "partner_id": self.owners[0].id}).id, "level": "1"})
        request = self.env["vme.request"].create({
            "association_id": self.vme.id, "request_type_id": self.env.ref("vme_belgie.request_type_key").id,
            "lot_id": self.apartments[0].id, "title": "Sleutel", "requester_id": self.owners[0].id})
        calls = {
            "action_vme_distribute": self.bill.with_user(self.auditor).action_vme_distribute,
            "action_prepare_recipients": communication.with_user(self.auditor).action_prepare_recipients,
            "action_update": reminder.with_user(self.auditor).action_update,
            "action_send_order": request.with_user(self.auditor).action_send_order,
        }
        for name, call in calls.items():
            with self.subTest(button=name), self.assertRaises(AccessError):
                call()

    def test_bank_import_needs_invoicing_rights(self):
        data = {"data_file": base64.b64encode(b"geen bestand"), "filename": "test.cod"}
        for user in (self.auditor, self._internal_user_without_accounting()):
            wizard = self.env["vme.bank.import.wizard"].with_user(user).create(data)
            with self.subTest(user=user.name), self.assertRaises(AccessError):
                wizard.action_import()

    def _internal_user_without_accounting(self):
        return self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Zonder Boekhouding", "login": "zonder.boekhouding@example.com",
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            "company_id": self.vme.company_id.id, "company_ids": [Command.set(self.vme.company_id.ids)],
        })

    # Staff with only some VME companies

    def test_staff_sees_only_the_vmes_of_his_companies(self):
        Lot = self.env["vme.lot"].with_user(self.staff_a)
        self.assertEqual(self.env["vme.association"].with_user(self.staff_a).search([]), self.vme)
        self.assertEqual(Lot.search([]), self.apartments | self.garages)
        self.assertFalse(self.env["vme.ownership"].with_user(self.staff_a).search(
            [("association_id", "=", self.other_vme.id)]))
        with self.assertRaises(AccessError):
            self.other_lot.with_user(self.staff_a).name = "B1 bis"
        with self.assertRaises(AccessError):
            self.env["vme.mandate"].with_user(self.staff_a).create({
                "association_id": self.other_vme.id, "role": "member", "partner_id": self.other_owner.id})
        # His own VME as usual.
        self.apartments[0].with_user(self.staff_a).name = "A1 bis"

    def test_staff_with_all_companies_sees_all_vmes_whatever_is_selected(self):
        # The company switcher does not hide VMEs: the rule uses the allowed companies of the user.
        Vme = self.env["vme.association"].with_user(self.staff).with_context(
            allowed_company_ids=self.vme.company_id.ids)
        self.assertEqual(Vme.search([]), self.vme | self.other_vme)

    def test_new_vme_goes_to_users_with_access_to_all_vmes(self):
        self.assertTrue(self.staff.has_group("vme_belgie.group_vme_all_companies"))
        new = self.env["vme.association"].create({"name": "Residentie Nieuw"})
        self.assertIn(new.company_id, self.staff.company_ids)
        self.assertNotIn(new.company_id, self.staff_a.company_ids)
        self.assertNotIn(new.company_id, self.auditor.company_ids)
        self.assertIn(new.company_id, self.env.ref("base.user_admin").company_ids)
