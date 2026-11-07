from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    rent_contract_id = fields.Many2one("vme.rent.contract", string="Huurcontract", index=True, copy=False,
                                       readonly=True, check_company=True)
    rent_period = fields.Date(string="Huurmaand", copy=False, readonly=True)
    rent_landlord_id = fields.Many2one(related="rent_contract_id.landlord_id", store=True, string="Verhuurder")
    rent_remittance_id = fields.Many2one("vme.rent.remittance", string="Doorstorting", index="btree_not_null",
                                         copy=False, readonly=True, check_company=True)

    @api.onchange("rent_contract_id")
    def _onchange_rent_contract_cost(self):
        """A bill paid for a landlord goes to his account 489100, so the next remittance deducts it."""
        if self.move_type not in ("in_invoice", "in_refund") or not self.rent_contract_id:
            return
        contract = self.rent_contract_id
        account = contract.company_id._rent_account()
        analytic = {str(contract.analytic_account_id.id): 100} if contract.analytic_account_id else False
        for line in self.invoice_line_ids:
            line.account_id = account
            line.analytic_distribution = analytic
            line.rent_line_type = "cost"

    def _vme_is_approvable(self):
        # The payout to a landlord is approved like a vendor bill of a VME before it goes into a batch.
        return super()._vme_is_approvable() or (
            self.move_type == "in_invoice" and bool(self.rent_remittance_id))

    @api.depends("rent_remittance_id")
    def _compute_vme_approval_state(self):
        return super()._compute_vme_approval_state()

    def _vme_second_approval_required(self):
        # No second approver for the office yet (an extension, see docs/dev/rentmeester.md).
        if self.rent_remittance_id:
            return False
        return super()._vme_second_approval_required()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    rent_line_type = fields.Selection(
        [("rent", "Huur"), ("charges", "Lasten"), ("settlement", "Afrekening lasten"),
         ("cost", "Kost voor de verhuurder"), ("fee", "Ereloon rentmeester"), ("remittance", "Doorstorting")],
        string="Soort huurlijn", copy=False,
    )
