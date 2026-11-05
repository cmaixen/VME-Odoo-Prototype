import base64
import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from ..models.bank_formats import BankFileError, parse_statement_file


class VmeBankImportWizard(models.TransientModel):
    _name = "vme.bank.import.wizard"
    _description = "Bankafschriften inlezen"

    data_file = fields.Binary(string="Bestand", required=True)
    filename = fields.Char(string="Bestandsnaam")

    def action_import(self):
        self.ensure_one()
        lines = self._import_file(base64.b64decode(self.data_file), self.filename or "")
        return self._action_open_lines(lines)

    @api.model
    def _import_file(self, data, filename):
        """Create a bank statement per account in the file, in the bank journal of that account.

        The account number decides the VME and the fund: each fund account of a VME has its own
        bank journal. Statements that were already imported are skipped. Returns the new lines.
        """
        try:
            file_format, statements = parse_statement_file(data)
        except BankFileError as error:
            raise UserError(str(error)) from error
        if not statements:
            raise UserError(self.env._("Het bestand bevat geen rekeninguittreksels."))

        lines = self.env["account.bank.statement.line"]
        for parsed in statements:
            journal = self._journal_for_account(parsed.account_number)
            name = self.env._("%(format)s %(number)s van %(date)s", format=file_format,
                              number=parsed.number, date=parsed.date.strftime("%d/%m/%Y"))
            Statement = self.env["account.bank.statement"].sudo().with_company(journal.company_id)
            if Statement.search_count([("journal_id", "=", journal.id), ("name", "=", name)]):
                continue
            statement = Statement.create({
                "name": name,
                "reference": filename,
                "journal_id": journal.id,
                "date": parsed.date,
                "balance_start": float(parsed.balance_start),
                "balance_end_real": float(parsed.balance_end),
                "line_ids": [Command.create({
                    "journal_id": journal.id,
                    "date": transaction.date,
                    "amount": float(transaction.amount),
                    "payment_ref": transaction.communication or "/",
                    "partner_name": transaction.counterparty_name or False,
                    "account_number": transaction.counterparty_account or False,
                    "ref": transaction.bank_reference or False,
                    "vme_end_to_end_id": transaction.end_to_end_id or False,
                    "vme_return_reason": transaction.return_reason or False,
                }) for transaction in parsed.transactions],
            })
            lines |= statement.line_ids
        lines._vme_match()
        return lines

    @api.model
    def _journal_for_account(self, account_number):
        sanitized = re.sub(r"\W", "", account_number or "").upper()
        Journal = self.env["account.journal"].sudo()
        journal = Journal.search([("type", "=", "bank"), ("bank_account_id.sanitized_acc_number", "=", sanitized)], limit=1)
        if journal:
            return journal
        # A fund account of a VME without its bank journal yet (journals are made on first use).
        vme = self.env["vme.association"].sudo().search([
            "|", ("working_capital_bank_id.sanitized_acc_number", "=", sanitized),
            ("reserve_capital_bank_id.sanitized_acc_number", "=", sanitized),
        ], limit=1)
        if vme:
            journals = vme._ensure_fund_bank_journals()[vme]
            return journals["working"] if vme.working_capital_bank_id.sanitized_acc_number == sanitized else journals["reserve"]
        raise UserError(self.env._(
            "De rekening %s is geen rekening van een VME. Vul ze in als rekening werk- of reservekapitaal "
            "van de juiste VME en lees het bestand opnieuw in.", account_number))

    @api.model
    def _action_open_lines(self, lines):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_bank_line_action")
        action["domain"] = [("id", "in", lines.ids)]
        action["context"] = {"search_default_group_state": 1}
        action["name"] = self.env._("Ingelezen bankbewegingen")
        if not lines:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("Niets nieuws"),
                    "message": self.env._("Deze rekeninguittreksels waren al ingelezen."),
                    "type": "warning",
                },
            }
        return action
