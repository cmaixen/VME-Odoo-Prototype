"""Links between records of two VMEs are refused, also outside the views (import, RPC, sudo)."""
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCheckCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme_a, cls.vme_b = cls.env["vme.association"].create([
            {"name": "Residentie Company A"}, {"name": "Residentie Company B"}])
        cls.env.cr.precommit.run()  # load the charts of accounts
        cls.lot_b = cls.env["vme.lot"].create({"association_id": cls.vme_b.id, "name": "B1"})
        cls.key_b = cls.env["vme.key"].create({
            "name": "Algemeen B", "association_id": cls.vme_b.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": cls.lot_b.id, "shares": 1000})],
        })
        cls.supplier = cls.env["res.partner"].create({"name": "Leverancier Company", "is_company": True})

    def _expense_account(self, vme):
        return self.env["account.account"].with_company(vme.company_id).search([
            ("company_ids", "in", vme.company_id.id), ("account_type", "=", "expense")], limit=1)

    def _bill(self, vme):
        return self.env["account.move"].with_company(vme.company_id).create({
            "move_type": "in_invoice", "partner_id": self.supplier.id, "invoice_date": date(2026, 3, 1),
            "invoice_line_ids": [Command.create({"name": "Onderhoud", "price_unit": 100, "tax_ids": [Command.clear()]})],
        })

    def test_distribution_rule_account_of_another_vme(self):
        rule = self.env["vme.distribution.rule"].create({
            "association_id": self.vme_a.id, "partner_id": self.supplier.id,
            "key_id": self.vme_a.key_ids[:1].id or self.env["vme.key"].create({
                "name": "Algemeen A", "association_id": self.vme_a.id, "key_type": "general"}).id,
            "account_id": self._expense_account(self.vme_a).id,
        })
        with self.assertRaises(UserError):
            rule.account_id = self._expense_account(self.vme_b)

    def test_budget_line_of_another_vme(self):
        budget = self.env["vme.budget"].create({
            "association_id": self.vme_a.id, "year": 2026, "working_capital_budget": 1000,
            "reserve_capital_contribution": 50})
        vals = {"budget_id": budget.id, "account_id": self._expense_account(self.vme_a).id, "amount": 100}
        self.env["vme.budget.line"].create(vals)
        with self.assertRaises(UserError):
            self.env["vme.budget.line"].create(dict(vals, account_id=self._expense_account(self.vme_b).id))
        with self.assertRaises(UserError):
            self.env["vme.budget.line"].create(dict(vals, key_id=self.key_b.id))

    def test_bill_paid_from_the_reserve_of_another_vme(self):
        bill = self._bill(self.vme_a)
        with self.assertRaises(UserError):
            bill.vme_reserve_move_id = self._bill(self.vme_b)

    def test_bank_account_of_another_vme(self):
        bank_b = self.env["res.partner.bank"].create({
            "acc_number": "BE68 5390 0754 7034", "partner_id": self.vme_b.partner_id.id})
        with self.assertRaises(ValidationError):
            self.vme_a.working_capital_bank_id = bank_b
        owner = self.env["res.partner"].create({"name": "Eigenaar Company"})
        with self.assertRaises(ValidationError):
            self.env["vme.sepa.mandate"].create({
                "association_id": self.vme_a.id, "partner_id": owner.id, "partner_bank_id": bank_b.id,
                "reference": "VME-COMPANY-1",
            })

    # Damage claims, installations and contracts

    def test_damage_claim_links_of_another_vme(self):
        insurer = self.env["res.partner"].create({"name": "Verzekeraar Company", "is_company": True})
        policy_b = self.env["vme.insurance.policy"].create({
            "association_id": self.vme_b.id, "name": "Brandverzekering B", "policy_type": "building",
            "insurer_id": insurer.id, "policy_number": "BR-COMPANY-B"})
        claim_a = self.env["vme.damage.claim"].create({
            "association_id": self.vme_a.id, "name": "Waterschade A", "event_date": date(2026, 11, 1)})
        with self.assertRaises(UserError):
            claim_a.lot_ids = self.lot_b
        with self.assertRaises(UserError):
            claim_a.policy_id = policy_b
        claim_b = self.env["vme.damage.claim"].create({
            "association_id": self.vme_b.id, "name": "Waterschade B", "event_date": date(2026, 11, 1)})
        with self.assertRaises(UserError):
            self._bill(self.vme_a).vme_damage_claim_id = claim_b

    def test_inspection_invoice_of_another_vme(self):
        installation_a = self.env["vme.installation"].create({
            "association_id": self.vme_a.id, "name": "Lift A", "installation_type": "elevator"})
        with self.assertRaises(UserError):
            self.env["vme.inspection"].create({
                "installation_id": installation_a.id, "date": date(2026, 6, 1), "move_id": self._bill(self.vme_b).id})

    def test_contract_links_of_another_vme(self):
        installation_b = self.env["vme.installation"].create({
            "association_id": self.vme_b.id, "name": "Lift B", "installation_type": "elevator"})
        contract_a = self.env["vme.contract"].create({
            "association_id": self.vme_a.id, "name": "Onderhoud lift A", "partner_id": self.supplier.id,
            "contract_type": "maintenance"})
        with self.assertRaises(UserError):
            contract_a.installation_id = installation_b
        assembly_b = self.env["vme.assembly"].create({"association_id": self.vme_b.id, "year": 2027})
        with self.assertRaises(UserError):
            self.env["vme.contract.evaluation"].create({
                "contract_id": contract_a.id, "date": date(2026, 11, 1), "assembly_id": assembly_b.id})
