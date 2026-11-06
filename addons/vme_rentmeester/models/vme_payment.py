"""The SEPA payment batches of vme_belgie (step 20), also for the payouts of the rental office.

A batch belongs to a VME or, here, to the rental office: then it pays the approved payout documents
of the remittances from the office's third-party account. Everything else (file, validation, the
check on trusted accounts, upload by a person) stays the batch of step 20.
"""
from decimal import Decimal

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.vme_belgie.models.sepa_xml import Party, Payment, PaymentGroup, build_credit_transfer


class VmePaymentBatch(models.Model):
    _inherit = "vme.payment.batch"

    association_id = fields.Many2one(required=False)
    rent_company_id = fields.Many2one(
        "res.company", string="Rentmeesterkantoor", index="btree_not_null", ondelete="restrict",
        domain=[("is_rent_management", "=", True)],
        help="Een betaalbatch van het rentmeesterkantoor: doorstortingen aan verhuurders.")
    company_id = fields.Many2one("res.company", related=None, compute="_compute_company_id", store=True, readonly=True)

    @api.depends("association_id.company_id", "rent_company_id")
    def _compute_company_id(self):
        for batch in self:
            batch.company_id = batch.rent_company_id or batch.association_id.company_id

    @api.constrains("association_id", "rent_company_id", "batch_type")
    def _check_owner(self):
        for batch in self:
            if bool(batch.association_id) == bool(batch.rent_company_id):
                raise ValidationError(self.env._("Een betaalbatch hoort bij een VME of bij het rentmeesterkantoor."))
            if batch.rent_company_id and batch.batch_type != "transfer":
                raise ValidationError(self.env._("Het rentmeesterkantoor doet alleen overschrijvingen."))

    def _in_own_company(self, method):
        """Run a button of step 20 in the office's company: the payouts are not visible from another one."""
        for batch in self:
            env_batch = batch.with_company(batch.company_id) if batch.rent_company_id else batch
            getattr(super(VmePaymentBatch, env_batch), method)()
        return True

    def action_fill_proposal(self):
        return self._in_own_company("action_fill_proposal")

    def action_generate_file(self):
        return self._in_own_company("action_generate_file")

    def action_mark_sent(self):
        return self._in_own_company("action_mark_sent")

    def _bank(self, fund=None):
        self.ensure_one()
        if self.rent_company_id:
            return self.rent_company_id.rent_bank_id
        return super()._bank(fund)

    def _vme_party(self, bank):
        if self.rent_company_id:
            return Party(self.rent_company_id.name, bank.sanitized_acc_number, bank.bank_bic or "")
        return super()._vme_party(bank)

    def _transfer_proposal(self):
        """Approved payouts of the office that are due; the others are listed with the reason."""
        self.ensure_one()
        if not self.rent_company_id:
            return super()._transfer_proposal()
        domain = [
            ("company_id", "=", self.company_id.id), ("move_type", "=", "in_invoice"),
            ("rent_remittance_id", "!=", False), ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")), ("invoice_date_due", "<=", self.due_until),
        ]
        if self.env.context.get("rent_remittance_ids"):
            domain.append(("rent_remittance_id", "in", self.env.context["rent_remittance_ids"]))
        payouts = self.env["account.move"].sudo().search(domain, order="invoice_date_due, id")
        in_batch = self._active_line_moves()
        vals, skipped = [], []
        for payout in payouts:
            if payout in in_batch:
                continue
            reason = None
            if payout.vme_approval_state != "approved":
                reason = self.env._("nog niet goedgekeurd")
            elif not payout.partner_bank_id:
                reason = self.env._("geen rekening van de verhuurder in het beheermandaat")
            elif not payout.partner_bank_id.allow_out_payment:
                # Odoo's own protection: a person with the right permissions trusts an account first.
                reason = self.env._("rekening %s van de verhuurder is niet bevestigd", payout.partner_bank_id.acc_number)
            if reason:
                skipped.append(f"{payout.rent_remittance_id.name}: {reason}")
                continue
            vals.append({
                "move_id": payout.id,
                "partner_id": payout.partner_id.id,
                "partner_bank_id": payout.partner_bank_id.id,
                "amount": payout.amount_residual,
                "communication": payout.payment_reference or payout.ref or payout.name,
            })
        return vals, skipped

    def _check_transfer_lines(self):
        self.ensure_one()
        if self.rent_company_id and not self._bank():
            raise UserError(self.env._(
                "Vul de derdenrekening van %s in (Rentmeester > Configuratie > Kantoor).", self.rent_company_id.name))
        return super()._check_transfer_lines()

    def _build_transfer_file(self, message_ref):
        if not self.rent_company_id:
            return super()._build_transfer_file(message_ref)
        self._check_transfer_lines()
        payments = [
            Payment(line.end_to_end_id, Decimal(str(line.amount)),
                    Party(line.partner_id.name, line.partner_bank_id.sanitized_acc_number, line.partner_bank_id.bank_bic or ""),
                    line.communication or "")
            for line in self.line_ids
        ]
        group = PaymentGroup(f"{self.name}-1", self._vme_party(self._bank()), self.execution_date, payments)
        return build_credit_transfer(message_ref, self.rent_company_id.name, [group])


class VmePaymentBatchLine(models.Model):
    _inherit = "vme.payment.batch.line"

    rent_remittance_id = fields.Many2one(related="move_id.rent_remittance_id", string="Doorstorting")
