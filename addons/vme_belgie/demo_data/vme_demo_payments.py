"""Demo of the outgoing payments (stap 20): approvers, supplier accounts, mandates, approvals.

Runs after the demo data and the demo history 2026 (the bank statements of stap 12 are optional).
A second action writes a fictitious CAMT.053 statement that confirms the batches the user uploaded,
with one returned direct debit, and reads it in like a real statement.
"""
from datetime import timedelta
from decimal import Decimal

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from ..models.bank_formats import Statement, Transaction, write_camt053
from .vme_demo_data import fake_iban

# Fictitious accounts on bank code 999; the same numbers as tools/make_demo_bank_files.py.
SUPPLIER_ACCOUNTS = {
    "Liftonderhoud Voorbeeld BV": 2001,
    "Schoonmaak Voorbeeld BV": 2002,
    "Gasleverancier Voorbeeld NV": 2003,
    "Verzekeringen Voorbeeld NV": 2004,
}
# Owners who signed a SEPA mandate: (VME, owner, account number).
MANDATES = [
    ("Residentie Linde", "Eigenaar Linde A1", 1101),
    ("Residentie Linde", "Eigenaar Linde A3", 1001),
    ("Hof ter Beuken", "Eigenaar Beuken B1", 1102),
    ("Hof ter Beuken", "Eigenaar Beuken B7", 1002),
    ("Kaaihuis", "Eigenaar Kaaihuis K1", 1103),
]
EMPLOYEE_LOGIN = "medewerker.demo@example.com"
# The demo statement returns the collection of this owner: insufficient funds.
RETURNED_OWNER, RETURN_REASON = "Eigenaar Beuken B7", "AM04"


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_payments(self):
        vmes = self.search([("name", "in", sorted({m[0] for m in MANDATES}))])
        if len(vmes) != 3 or not self.env["vme.provision.call"].search_count([("association_id", "in", vmes.ids)]):
            raise UserError(self.env._("Laad eerst de demodata en de demohistoriek 2026."))
        if self.env["vme.sepa.mandate"].search_count([("association_id", "in", vmes.ids)]):
            raise UserError(self.env._("Het demo betalingsverkeer is al geladen."))
        approver = self.env.user if not self.env.su else self.env.ref("base.user_admin")
        employee = self._demo_payment_employee(vmes)
        vmes.write({"payment_second_approver_id": approver.id})

        # Supplier accounts, trusted by the person loading the demo (Odoo's own check, never bypassed).
        Bank = self.env["res.partner.bank"]
        supplier_banks = Bank
        for name, number in SUPPLIER_ACCOUNTS.items():
            supplier = self.env["res.partner"].search([("name", "=", name)], limit=1)
            if not supplier:
                continue
            iban = fake_iban(number)
            bank = Bank.search([("sanitized_acc_number", "=", iban), ("partner_id", "=", supplier.id)], limit=1) \
                or Bank.create({"acc_number": iban, "partner_id": supplier.id})
            supplier_banks |= bank
        if all(bank._user_can_trust() for bank in supplier_banks):
            supplier_banks.filtered(lambda b: not b.allow_out_payment).allow_out_payment = True

        bills = self.env["account.move"].search([
            ("company_id", "in", vmes.company_id.ids), ("move_type", "=", "in_invoice"), ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
        ], order="invoice_date, id")
        for bill in bills:
            bank = supplier_banks.filtered(lambda b, p=bill.partner_id: b.partner_id == p.commercial_partner_id)[:1]
            if bank and not bill.partner_bank_id:
                bill.partner_bank_id = bank
        # The employee approves every open bill; above the threshold the second approval waits for the user.
        # Only the VME companies: the companies selected in the browser may include one the employee cannot use.
        bills.with_user(employee).with_context(allowed_company_ids=vmes.company_id.ids).action_vme_approve()

        Mandate = self.env["vme.sepa.mandate"]
        for vme_name, owner_name, number in MANDATES:
            vme = vmes.filtered(lambda v, n=vme_name: v.name == n)
            owner = vme.lot_ids.ownership_ids.partner_id.filtered(lambda p, n=owner_name: p.name == n)[:1]
            if not owner:
                continue
            iban = fake_iban(number)
            bank = Bank.search([("sanitized_acc_number", "=", iban)], limit=1) \
                or Bank.create({"acc_number": iban, "partner_id": owner.id})
            Mandate.create({"association_id": vme.id, "partner_id": owner.id, "partner_bank_id": bank.id,
                            "signature_date": fields.Date.to_date("2026-01-01")})

        waiting = bills.filtered(lambda m: m.vme_approval_state == "first_approved")
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_bill_approval_action")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Demo betalingsverkeer geladen"),
                "message": self.env._(
                    "%(approved)s facturen goedgekeurd door de medewerker, %(waiting)s wachten op uw tweede goedkeuring; "
                    "%(mandates)s SEPA-mandaten.", approved=len(bills), waiting=len(waiting),
                    mandates=Mandate.search_count([("association_id", "in", vmes.ids)])),
                "type": "success",
                "next": action,
            },
        }

    def _demo_payment_employee(self, vmes):
        Users = self.env["res.users"].with_context(no_reset_password=True)
        employee = Users.search([("login", "=", EMPLOYEE_LOGIN)], limit=1)
        if not employee:
            employee = Users.create({
                "name": "Medewerker Syndicus (demo)",
                "login": EMPLOYEE_LOGIN,
                "email": EMPLOYEE_LOGIN,
                "company_id": vmes[0].company_id.id,
                "company_ids": [Command.set(vmes.company_id.ids)],
                "group_ids": [Command.link(self.env.ref("account.group_account_invoice").id)],
            })
        return employee

    @api.model
    def _load_demo_payment_statement(self):
        """Fictitious CAMT.053 per fund account for the batches whose file was made: the bank confirms them."""
        batches = self.env["vme.payment.batch"].search([("state", "in", ("generated", "sent"))], order="id")
        if not batches:
            raise UserError(self.env._(
                "Er is geen betaalbatch met een SEPA-bestand. Maak eerst een batch en het bestand."))
        movements = {}  # bank account -> [Transaction]
        returned = False
        for batch in batches:
            for line in batch.line_ids.filtered(lambda l: l.state in ("draft", "sent")):
                fund = batch.fund if batch.batch_type == "transfer" else (line.move_id.vme_fund or "working")
                account = batch.association_id._fund_bank(fund)
                sign = -1 if batch.batch_type == "transfer" else 1
                communication = line.communication or ""
                tx = Transaction(batch.execution_date, sign * Decimal(str(line.amount)), communication,
                                 communication.startswith("+++"), line.partner_id.name,
                                 line.partner_bank_id.sanitized_acc_number, f"DEMO-{line.end_to_end_id}",
                                 line.end_to_end_id)
                movements.setdefault(account, []).append(tx)
                if batch.batch_type == "direct_debit" and line.partner_id.name == RETURNED_OWNER and not returned:
                    returned = True
                    movements[account].append(Transaction(
                        batch.execution_date + timedelta(days=2), -tx.amount, communication, tx.structured,
                        line.partner_id.name, tx.counterparty_account, f"DEMO-R-{line.end_to_end_id}",
                        line.end_to_end_id, RETURN_REASON))
        Wizard = self.env["vme.bank.import.wizard"]
        lines = self.env["account.bank.statement.line"]
        for account, transactions in movements.items():
            journal = Wizard._journal_for_account(account.sanitized_acc_number)
            last = self.env["account.bank.statement"].sudo().search([("journal_id", "=", journal.id)], order="date desc, id desc", limit=1)
            opening = Decimal(str(last.balance_end_real or 0.0))
            day = max(t.date for t in transactions)
            statement = Statement(account.sanitized_acc_number, "EUR", f"D{journal.id}{len(lines) + 1:02d}{day:%m%d}",
                                  day, opening, opening + sum(t.amount for t in transactions), transactions)
            data = write_camt053(statement, holder=journal.company_id.name).encode()
            lines |= Wizard._import_file(data, f"demo_betaalbatches_{account.sanitized_acc_number}.xml")
        return Wizard._action_open_lines(lines)
