"""Outgoing payments of a VME: approval of vendor bills, SEPA credit transfers and direct debits.

Nothing is ever sent to a bank: the syndic downloads the file and uploads it in the bank's own
application. The payments stay "sent" until a bank statement (stap 12) confirms or returns them.
"""
import base64
import re
from datetime import timedelta
from decimal import Decimal

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

from .sepa_xml import (
    PAIN_001, PAIN_008, Party, Payment, PaymentGroup, SepaError, build_credit_transfer, build_direct_debit,
    creditor_identifier, creditor_identifier_is_valid, validate,
)
from .vme_provision_call import FUNDS

DEFAULT_APPROVAL_THRESHOLD = 2500.0
# LEGAL-CHECK: SEPA Core Direct Debit Rulebook (EPC) - the debtor is told the amount and date at least
# 14 calendar days before the collection, unless the mandate agrees on a shorter term.
PRE_NOTIFICATION_DAYS = 14

APPROVAL_STATES = [
    ("to_approve", "Te keuren"),
    ("first_approved", "Wacht op tweede goedkeuring"),
    ("approved", "Goedgekeurd"),
]
BATCH_TYPES = [("transfer", "Overschrijvingen (pain.001)"), ("direct_debit", "Domiciliëringen (pain.008)")]
BATCH_STATES = [
    ("draft", "Concept"),
    ("generated", "Bestand klaar"),
    ("sent", "Verstuurd"),
    ("done", "Afgehandeld"),
    ("cancel", "Geannuleerd"),
]
LINE_STATES = [
    ("draft", "Concept"),
    ("sent", "Verstuurd"),
    ("paid", "Bevestigd door de bank"),
    ("rejected", "Teruggekomen"),
]
# LEGAL-CHECK: Boek VII WER (omzetting art. 76 PSD2, richtlijn 2015/2366) - an owner can ask his bank to refund
# an authorised direct debit up to eight weeks after the collection; that comes back as MD06.
# ISO 20022 return reasons that occur most with direct debits (ExternalStatusReason1Code).
RETURN_REASONS = {
    "AC01": "Rekeningnummer onjuist",
    "AC04": "Rekening afgesloten",
    "AC06": "Rekening geblokkeerd",
    "AM04": "Onvoldoende saldo",
    "MD01": "Geen geldig mandaat",
    "MD06": "Terugbetaling gevraagd door de eigenaar",
    "MS02": "Geweigerd door de eigenaar",
    "MS03": "Reden niet opgegeven",
    "SL01": "Specifieke dienst van de bank",
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    currency_id = fields.Many2one(related="company_id.currency_id")
    payment_approval_threshold = fields.Monetary(
        string="Tweede goedkeuring vanaf", default=DEFAULT_APPROVAL_THRESHOLD,
        help="Leveranciersfacturen vanaf dit bedrag (btw inbegrepen) moeten ook door de tweede goedkeurder "
             "goedgekeurd worden voor ze betaald kunnen worden. 0 = nooit een tweede goedkeuring.")
    # LEGAL-CHECK: art. 3.90 §3 BW - the council of co-ownership supervises the syndic; a second approval
    # by a council member is an agreement of the AV or the syndic contract, not a legal obligation.
    payment_second_approver_id = fields.Many2one(
        "res.users", string="Tweede goedkeurder", domain=[("share", "=", False)],
        help="Bijvoorbeeld een lid van de raad van mede-eigendom. Keurt facturen boven het bedrag goed, "
             "na de eerste goedkeuring door een medewerker.")
    sepa_creditor_identifier = fields.Char(
        string="Schuldeiseridentificatie (SEPA)", compute="_compute_sepa_creditor_identifier", store=True,
        readonly=False,
        help="Nodig voor domiciliëringen. Voor een VME: BE, twee controlecijfers, ZZZ en het KBO-nummer. "
             "De bank bevestigt het nummer bij de aanvraag van het incassocontract.")
    mandate_ids = fields.One2many("vme.sepa.mandate", "association_id", string="SEPA-mandaten")

    @api.depends("kbo_number")
    def _compute_sepa_creditor_identifier(self):
        for vme in self:
            digits = re.sub(r"\D", "", vme.kbo_number or "")
            if not vme.sepa_creditor_identifier and len(digits) == 10:
                vme.sepa_creditor_identifier = creditor_identifier("BE", digits)

    @api.constrains("sepa_creditor_identifier")
    def _check_sepa_creditor_identifier(self):
        for vme in self:
            if vme.sepa_creditor_identifier and not creditor_identifier_is_valid(vme.sepa_creditor_identifier):
                raise ValidationError(self.env._(
                    "De schuldeiseridentificatie %s is ongeldig (formaat BE00ZZZ0123456789).",
                    vme.sepa_creditor_identifier))

    @api.constrains("payment_approval_threshold")
    def _check_payment_approval_threshold(self):
        if any(vme.payment_approval_threshold < 0 for vme in self):
            raise ValidationError(self.env._("Het bedrag voor de tweede goedkeuring mag niet negatief zijn."))

    def _fund_bank(self, fund):
        self.ensure_one()
        return self.working_capital_bank_id if fund == "working" else self.reserve_capital_bank_id


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_approval_state = fields.Selection(
        APPROVAL_STATES, string="Goedkeuring", compute="_compute_vme_approval_state", store=True, copy=False,
        tracking=True)
    vme_approved_by_id = fields.Many2one("res.users", string="Goedgekeurd door", copy=False, readonly=True)
    vme_approved_date = fields.Datetime(string="Goedgekeurd op", copy=False, readonly=True)
    vme_second_approved_by_id = fields.Many2one("res.users", string="Tweede goedkeuring door", copy=False, readonly=True)
    vme_second_approved_date = fields.Datetime(string="Tweede goedkeuring op", copy=False, readonly=True)
    vme_needs_second_approval = fields.Boolean(
        string="Tweede goedkeuring nodig", compute="_compute_vme_needs_second_approval")
    vme_payment_line_ids = fields.One2many("vme.payment.batch.line", "move_id", string="Betaalopdrachten", copy=False)
    vme_payment_status = fields.Selection(
        [("in_batch", "In betaalbatch"), ("sent", "Verstuurd"), ("rejected", "Teruggekomen")],
        string="Betaalopdracht", compute="_compute_vme_payment_status", store=True)

    def _vme_is_approvable(self):
        self.ensure_one()
        return self.vme_association_id and self.move_type == "in_invoice"

    @api.depends("move_type", "vme_association_id", "vme_approved_by_id", "vme_second_approved_by_id",
                 "amount_total", "vme_association_id.payment_approval_threshold")
    def _compute_vme_approval_state(self):
        for move in self:
            if not move._vme_is_approvable():
                move.vme_approval_state = False
            elif not move.vme_approved_by_id:
                move.vme_approval_state = "to_approve"
            elif move._vme_second_approval_required() and not move.vme_second_approved_by_id:
                move.vme_approval_state = "first_approved"
            else:
                move.vme_approval_state = "approved"

    @api.depends("amount_total", "vme_association_id.payment_approval_threshold")
    def _compute_vme_needs_second_approval(self):
        for move in self:
            move.vme_needs_second_approval = bool(move._vme_is_approvable()) and move._vme_second_approval_required()

    def _vme_second_approval_required(self):
        """Bills from the threshold on (VAT included) need a second person, 0 means never."""
        self.ensure_one()
        threshold = self.vme_association_id.payment_approval_threshold
        return bool(threshold) and self.currency_id.compare_amounts(self.amount_total, threshold) >= 0

    @api.depends("vme_payment_line_ids.state", "vme_payment_line_ids.batch_id.state")
    def _compute_vme_payment_status(self):
        for move in self:
            lines = move.vme_payment_line_ids.filtered(lambda l: l.batch_id.state != "cancel").sorted("id")
            last = lines[-1:]
            move.vme_payment_status = {"draft": "in_batch", "sent": "sent", "rejected": "rejected"}.get(last.state, False)

    def action_vme_approve(self):
        """First approval by an employee, second approval (above the threshold) by the second approver."""
        user = self.env.user
        for move in self:
            move._vme_check_approvable()
            if move.vme_approval_state == "to_approve":
                move.write({"vme_approved_by_id": user.id, "vme_approved_date": fields.Datetime.now()})
                if move.vme_approval_state == "first_approved":
                    move._vme_schedule_second_approval()
            elif move.vme_approval_state == "first_approved":
                vme = move.vme_association_id
                if user != vme.payment_second_approver_id:
                    raise UserError(self.env._(
                        "%(bill)s: alleen %(approver)s mag de tweede goedkeuring geven.",
                        bill=move.display_name, approver=vme.payment_second_approver_id.name or self.env._("de tweede goedkeurder")))
                if user == move.vme_approved_by_id:
                    raise UserError(self.env._(
                        "%s: de tweede goedkeuring moet van een andere persoon komen dan de eerste.", move.display_name))
                move.write({"vme_second_approved_by_id": user.id, "vme_second_approved_date": fields.Datetime.now()})
                move.activity_feedback(["mail.mail_activity_data_todo"], user_id=user.id)
            else:
                raise UserError(self.env._("%s is al goedgekeurd.", move.display_name))
            move.message_post(body=self.env._("Goedgekeurd voor betaling door %s.", user.name))
        return True

    def action_vme_reset_approval(self):
        for move in self:
            if move.vme_payment_line_ids.filtered(lambda l: l.state in ("draft", "sent") and l.batch_id.state != "cancel"):
                raise UserError(self.env._("%s zit in een betaalbatch: haal de factuur er eerst uit.", move.display_name))
        self._vme_clear_approval()
        return True

    def _vme_clear_approval(self):
        approved = self.filtered("vme_approved_by_id")
        approved.write({"vme_approved_by_id": False, "vme_approved_date": False,
                        "vme_second_approved_by_id": False, "vme_second_approved_date": False})
        for move in approved:
            move.message_post(body=self.env._("Goedkeuring voor betaling ingetrokken."))

    def _vme_check_approvable(self):
        self.ensure_one()
        if not self._vme_is_approvable():
            raise UserError(self.env._("Alleen leveranciersfacturen van een VME worden goedgekeurd voor betaling."))
        if self.state != "posted":
            raise UserError(self.env._("Bevestig %s eerst.", self.display_name))
        if self.payment_state in ("paid", "reversed"):
            raise UserError(self.env._("%s is al betaald.", self.display_name))
        if self._vme_second_approval_required() and not self.vme_association_id.payment_second_approver_id:
            raise UserError(self.env._(
                "%(bill)s vraagt een tweede goedkeuring, maar %(vme)s heeft geen tweede goedkeurder. "
                "Vul die in op de VME (tabblad Betalingen).", bill=self.display_name, vme=self.vme_association_id.name))

    def _vme_schedule_second_approval(self):
        approver = self.vme_association_id.payment_second_approver_id
        if approver:
            self.activity_schedule(
                "mail.mail_activity_data_todo", user_id=approver.id,
                summary=self.env._("Tweede goedkeuring voor betaling"),
                note=self.env._("%(bill)s van %(supplier)s, %(amount)s.", bill=self.display_name,
                                supplier=self.partner_id.name, amount=self.currency_id.format(self.amount_total)))

    def button_draft(self):
        # A changed bill must be approved again.
        self.filtered("vme_approved_by_id")._vme_clear_approval()
        return super().button_draft()


class VmeSepaMandate(models.Model):
    _name = "vme.sepa.mandate"
    _description = "SEPA-mandaat"
    _inherit = ["mail.thread"]
    _order = "association_id, partner_id"

    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Eigenaar", required=True, index=True)
    partner_bank_id = fields.Many2one(
        "res.partner.bank", string="Rekening van de eigenaar", required=True,
        domain="[('partner_id', '=', partner_id)]")
    reference = fields.Char(string="Mandaatreferentie", required=True, copy=False,
                            help="Unieke referentie (UMR), staat op het ondertekende mandaat.")
    signature_date = fields.Date(string="Ondertekend op", required=True, default=fields.Date.context_today)
    state = fields.Selection([("active", "Actief"), ("revoked", "Ingetrokken")], string="Status",
                             default="active", required=True, tracking=True)
    first_collection_done = fields.Boolean(
        string="Al geïnd", copy=False,
        help="De eerste inning is verstuurd: volgende inningen zijn van het type RCUR in plaats van FRST.")
    last_collection_date = fields.Date(string="Laatste inning", copy=False, readonly=True)

    _reference_unique = models.Constraint("UNIQUE (association_id, reference)", "Deze mandaatreferentie bestaat al.")

    @api.depends("reference", "partner_id.name")
    def _compute_display_name(self):
        for mandate in self:
            mandate.display_name = f"{mandate.reference} ({mandate.partner_id.name})"

    @api.constrains("state", "partner_id", "association_id")
    def _check_one_active(self):
        for mandate in self.filtered(lambda m: m.state == "active"):
            if self.search_count([("association_id", "=", mandate.association_id.id), ("partner_id", "=", mandate.partner_id.id),
                                  ("state", "=", "active"), ("id", "!=", mandate.id)]):
                raise ValidationError(self.env._("%s heeft al een actief mandaat bij deze VME.", mandate.partner_id.name))

    @api.model
    def _default_reference(self, vme, partner):
        base = re.sub(r"[^A-Z0-9]", "", (vme.name or "VME").upper())[:10]
        return f"{base}-{partner.id:06d}-{self.search_count([('association_id', '=', vme.id)]) + 1}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference") and vals.get("association_id") and vals.get("partner_id"):
                vals["reference"] = self._default_reference(
                    self.env["vme.association"].browse(vals["association_id"]), self.env["res.partner"].browse(vals["partner_id"]))
        return super().create(vals_list)

    def action_revoke(self):
        self.write({"state": "revoked"})


class VmePaymentBatch(models.Model):
    _name = "vme.payment.batch"
    _description = "Betaalbatch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Nummer", required=True, copy=False, readonly=True, default="/")
    batch_type = fields.Selection(BATCH_TYPES, string="Soort", required=True, default="transfer")
    association_id = fields.Many2one("vme.association", string="VME", required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    fund = fields.Selection(FUNDS, string="Fondsrekening", default="working",
                            help="Overschrijvingen: de rekening waarvan betaald wordt. Domiciliëringen gaan naar "
                                 "de rekening van het fonds van elke provisie.")
    provision_call_id = fields.Many2one("vme.provision.call", string="Provisieoproep", ondelete="restrict",
                                        domain="[('association_id', '=', association_id)]")
    due_until = fields.Date(string="Vervallen tot en met", default=lambda self: fields.Date.context_today(self) + timedelta(days=7),
                            help="Het betaalvoorstel neemt goedgekeurde facturen die uiterlijk op deze dag vervallen.")
    execution_date = fields.Date(string="Uitvoeringsdatum", required=True, default=fields.Date.context_today)
    state = fields.Selection(BATCH_STATES, string="Status", default="draft", required=True, tracking=True, copy=False)
    line_ids = fields.One2many("vme.payment.batch.line", "batch_id", string="Betalingen", copy=False)
    line_count = fields.Integer(string="Aantal", compute="_compute_totals", store=True)
    amount_total = fields.Monetary(string="Totaal", compute="_compute_totals", store=True)
    paid_count = fields.Integer(string="Bevestigd", compute="_compute_totals", store=True)
    rejected_count = fields.Integer(string="Teruggekomen", compute="_compute_totals", store=True)
    proposal_note = fields.Text(string="Niet opgenomen", readonly=True,
                                help="Facturen of provisies die niet in de batch staan, met de reden.")
    file_data = fields.Binary(string="Bestand", attachment=True, copy=False, readonly=True)
    file_name = fields.Char(string="Bestandsnaam", copy=False, readonly=True)
    message_ref = fields.Char(string="Berichtnummer (MsgId)", copy=False, readonly=True)
    generated_by_id = fields.Many2one("res.users", string="Bestand gemaakt door", copy=False, readonly=True)
    sent_by_id = fields.Many2one("res.users", string="Opgeladen door", copy=False, readonly=True)
    sent_date = fields.Date(string="Opgeladen op", copy=False, readonly=True)

    @api.depends("line_ids.amount", "line_ids.state")
    def _compute_totals(self):
        for batch in self:
            batch.line_count = len(batch.line_ids)
            batch.amount_total = sum(batch.line_ids.mapped("amount"))
            batch.paid_count = len(batch.line_ids.filtered(lambda l: l.state == "paid"))
            batch.rejected_count = len(batch.line_ids.filtered(lambda l: l.state == "rejected"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                code = "vme.payment.batch.debit" if vals.get("batch_type") == "direct_debit" else "vme.payment.batch.transfer"
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code(code) or "/"
        return super().create(vals_list)

    def unlink(self):
        if any(batch.state not in ("draft", "cancel") for batch in self):
            raise UserError(self.env._("Alleen een concept of een geannuleerde batch kan verwijderd worden."))
        return super().unlink()

    def _check_draft(self):
        for batch in self:
            if batch.state != "draft":
                raise UserError(self.env._("%s is geen concept meer.", batch.name))

    def _bank(self, fund=None):
        self.ensure_one()
        return self.association_id._fund_bank(fund or self.fund or "working")

    # ------------------------------------------------------------------
    # Proposal
    # ------------------------------------------------------------------

    def action_fill_proposal(self):
        """Fill a draft with what can be paid or collected now; list what is left out and why."""
        for batch in self:
            batch._check_draft()
            batch.line_ids.unlink()
            if batch.batch_type == "transfer":
                vals, skipped = batch._transfer_proposal()
            else:
                vals, skipped = batch._direct_debit_proposal()
            batch.write({"line_ids": [Command.create(v) for v in vals], "proposal_note": "\n".join(skipped) or False})
        return True

    def _active_line_moves(self):
        """Invoices already in a batch that is not cancelled and not returned."""
        return self.env["vme.payment.batch.line"].sudo().search([
            ("company_id", "=", self.company_id.id), ("state", "in", ("draft", "sent")),
            ("batch_id.state", "!=", "cancel"), ("batch_id", "!=", self.id),
        ]).move_id

    def _transfer_proposal(self):
        self.ensure_one()
        bills = self.env["account.move"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
            ("invoice_date_due", "<=", self.due_until),
        ], order="invoice_date_due, id")
        in_batch = self._active_line_moves()
        vals, skipped = [], []
        for bill in bills:
            # Bills without a fund are paid from the working capital.
            if (bill.vme_fund or "working") != self.fund or bill in in_batch:
                continue
            reason = None
            if bill.vme_approval_state == "to_approve":
                reason = self.env._("nog niet goedgekeurd")
            elif bill.vme_approval_state == "first_approved":
                reason = self.env._("wacht op de tweede goedkeuring (%s)", self.association_id.payment_second_approver_id.name or "-")
            elif not bill.partner_bank_id:
                reason = self.env._("geen rekeningnummer van de leverancier op de factuur")
            elif not bill.partner_bank_id.allow_out_payment:
                # Odoo's own protection: a person with the right permissions trusts an account first.
                reason = self.env._("rekening %s van de leverancier is niet bevestigd", bill.partner_bank_id.acc_number)
            if reason:
                skipped.append(f"{bill.name} ({bill.partner_id.name}): {reason}")
                continue
            vals.append({
                "move_id": bill.id,
                "partner_id": bill.partner_id.id,
                "partner_bank_id": bill.partner_bank_id.id,
                "amount": bill.amount_residual,
                "communication": bill.payment_reference or bill.ref or bill.name,
            })
        return vals, skipped

    def _direct_debit_proposal(self):
        self.ensure_one()
        if not self.provision_call_id:
            raise UserError(self.env._("Kies de provisieoproep die u wilt innen."))
        mandates = self.env["vme.sepa.mandate"].sudo().search(
            [("association_id", "=", self.association_id.id), ("state", "=", "active")])
        by_partner = {m.partner_id: m for m in mandates}
        in_batch = self._active_line_moves()
        vals, skipped = [], []
        invoices = self.provision_call_id.invoice_ids.sudo().filtered(
            lambda m: m.state == "posted" and m.move_type == "out_invoice").sorted(lambda m: (m.partner_id.name, m.vme_fund))
        for invoice in invoices:
            if invoice.payment_state not in ("not_paid", "partial") or invoice in in_batch:
                continue
            mandate = by_partner.get(invoice.partner_id)
            if not mandate:
                skipped.append(f"{invoice.name} ({invoice.partner_id.name}): {self.env._('geen actief SEPA-mandaat')}")
                continue
            vals.append({
                "move_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "partner_bank_id": mandate.partner_bank_id.id,
                "mandate_id": mandate.id,
                "amount": invoice.amount_residual,
                "communication": invoice.payment_reference or invoice.name,
            })
        return vals, skipped

    # ------------------------------------------------------------------
    # File
    # ------------------------------------------------------------------

    def action_generate_file(self):
        """Write and validate the SEPA file. Nothing is sent: the user uploads it in the bank."""
        for batch in self:
            batch._check_draft()
            if not batch.line_ids:
                raise UserError(self.env._("De batch is leeg: vul eerst het voorstel."))
            if batch.execution_date < fields.Date.context_today(batch):
                raise UserError(self.env._("De uitvoeringsdatum ligt in het verleden."))
            for line in batch.line_ids:
                line.end_to_end_id = f"{batch.name}-{line.sequence_number}"
            message_ref = f"{batch.name}-{fields.Datetime.now():%Y%m%d%H%M%S}"
            try:
                if batch.batch_type == "transfer":
                    xml = batch._build_transfer_file(message_ref)
                    validate(xml, PAIN_001)
                else:
                    xml = batch._build_direct_debit_file(message_ref)
                    validate(xml, PAIN_008)
            except SepaError as error:
                raise UserError(str(error)) from error
            batch.write({
                "state": "generated",
                "file_data": base64.b64encode(xml),
                "file_name": f"{re.sub(r'[^A-Za-z0-9-]', '_', batch.name)}.xml",
                "message_ref": message_ref,
                "generated_by_id": self.env.user.id,
            })
            batch.message_post(body=self.env._(
                "SEPA-bestand gemaakt en gevalideerd (%(count)s betalingen, %(amount)s). Laad het op in de bank.",
                count=batch.line_count, amount=batch.currency_id.format(batch.amount_total)))
        return True

    def _check_transfer_lines(self):
        """Last checks right before the file: approval and trusted accounts may have changed."""
        self.ensure_one()
        debtor_bank = self._bank()
        if not debtor_bank:
            raise UserError(self.env._("%s heeft geen rekening voor dit fonds.", self.association_id.name))
        if not debtor_bank.allow_out_payment:
            raise UserError(self.env._(
                "De rekening %s van de VME is nog niet bevestigd. Bevestig ze eerst op de VME.", debtor_bank.acc_number))
        for line in self.line_ids:
            bill = line.move_id
            if bill.vme_approval_state != "approved":
                raise UserError(self.env._("%s is niet (volledig) goedgekeurd.", bill.name))
            if bill.payment_state not in ("not_paid", "partial"):
                raise UserError(self.env._("%s is al betaald: haal de factuur uit de batch.", bill.name))
            if not line.partner_bank_id.allow_out_payment:
                raise UserError(self.env._(
                    "De rekening %(account)s van %(supplier)s is niet bevestigd. Een gebruiker met het recht om "
                    "rekeningen te bevestigen doet dat eerst op de leverancier.",
                    account=line.partner_bank_id.acc_number, supplier=line.partner_id.name))

    def _vme_party(self, bank):
        return Party(self.association_id.name, bank.sanitized_acc_number, bank.bank_bic or "")

    def _build_transfer_file(self, message_ref):
        self._check_transfer_lines()
        payments = [
            Payment(line.end_to_end_id, Decimal(str(line.amount)),
                    Party(line.partner_id.name, line.partner_bank_id.sanitized_acc_number, line.partner_bank_id.bank_bic or ""),
                    line.communication or "")
            for line in self.line_ids
        ]
        group = PaymentGroup(f"{self.name}-1", self._vme_party(self._bank()), self.execution_date, payments)
        return build_credit_transfer(message_ref, self.association_id.name, [group])

    def _build_direct_debit_file(self, message_ref):
        self.ensure_one()
        vme = self.association_id
        call_date = self.provision_call_id.date
        if call_date and self.execution_date < call_date + timedelta(days=PRE_NOTIFICATION_DAYS):
            raise UserError(self.env._(
                "De inning mag ten vroegste %(days)s dagen na de provisieoproep (%(date)s): de eigenaars moeten "
                "vooraf weten wanneer en hoeveel er geïnd wordt.", days=PRE_NOTIFICATION_DAYS,
                date=call_date))
        groups = {}
        for line in self.line_ids:
            mandate = line.mandate_id
            if mandate.state != "active":
                raise UserError(self.env._("Het mandaat van %s is ingetrokken.", line.partner_id.name))
            fund = line.move_id.vme_fund or "working"
            sequence_type = "RCUR" if mandate.first_collection_done else "FRST"
            key = (fund, sequence_type)
            if key not in groups:
                bank = vme._fund_bank(fund)
                if not bank:
                    raise UserError(self.env._("%s heeft geen rekening voor dit fonds.", vme.name))
                groups[key] = PaymentGroup(f"{self.name}-{fund[0].upper()}-{sequence_type}", self._vme_party(bank),
                                           self.execution_date, [], sequence_type)
            groups[key].payments.append(Payment(
                line.end_to_end_id, Decimal(str(line.amount)),
                Party(line.partner_id.name, line.partner_bank_id.sanitized_acc_number, line.partner_bank_id.bank_bic or ""),
                line.communication or "", mandate.reference, mandate.signature_date))
        if not vme.sepa_creditor_identifier:
            raise UserError(self.env._("Vul de schuldeiseridentificatie van %s in.", vme.name))
        return build_direct_debit(message_ref, vme.name, vme.sepa_creditor_identifier, list(groups.values()))

    def action_download(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(self.env._("Er is nog geen bestand."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/vme.payment.batch/{self.id}/file_data/{self.file_name}?download=true",
            "target": "self",
        }

    def action_mark_sent(self):
        """The user confirms the file was uploaded in the bank; the payments are now 'sent'."""
        for batch in self:
            if batch.state != "generated":
                raise UserError(self.env._("Maak eerst het bestand van %s.", batch.name))
            batch.line_ids.filtered(lambda l: l.state == "draft").write({"state": "sent"})
            if batch.batch_type == "direct_debit":
                batch.line_ids.mandate_id.write({"first_collection_done": True, "last_collection_date": batch.execution_date})
            batch.write({"state": "sent", "sent_by_id": self.env.user.id, "sent_date": fields.Date.context_today(self)})
            batch.message_post(body=self.env._("Opgeladen in de bank door %s.", self.env.user.name))
        return True

    def action_back_to_draft(self):
        for batch in self:
            if batch.state != "generated":
                raise UserError(self.env._("Alleen een batch waarvan het bestand nog niet opgeladen is, kan terug naar concept."))
            batch.write({"state": "draft", "file_data": False, "file_name": False, "message_ref": False})
        return True

    def action_cancel(self):
        for batch in self:
            if batch.state not in ("draft", "generated"):
                raise UserError(self.env._("Een verstuurde batch annuleert u in de bank, niet in Odoo."))
            batch.state = "cancel"
        return True

    def _update_done(self):
        for batch in self.filtered(lambda b: b.state in ("generated", "sent")):
            if batch.line_ids and all(line.state in ("paid", "rejected") for line in batch.line_ids):
                batch.state = "done"
                batch.message_post(body=self.env._(
                    "Alle betalingen teruggekoppeld door de bank: %(paid)s bevestigd, %(rejected)s teruggekomen.",
                    paid=batch.paid_count, rejected=batch.rejected_count))


class VmePaymentBatchLine(models.Model):
    _name = "vme.payment.batch.line"
    _description = "Betaling in een betaalbatch"
    _order = "batch_id, id"

    batch_id = fields.Many2one("vme.payment.batch", string="Betaalbatch", required=True, ondelete="cascade", index=True)
    batch_type = fields.Selection(related="batch_id.batch_type", store=True)
    company_id = fields.Many2one(related="batch_id.company_id", store=True)
    currency_id = fields.Many2one(related="batch_id.currency_id")
    move_id = fields.Many2one("account.move", string="Factuur", required=True, index=True, ondelete="restrict")
    move_name = fields.Char(related="move_id.name", string="Factuurnummer")
    date_due = fields.Date(related="move_id.invoice_date_due", string="Vervaldag")
    partner_id = fields.Many2one("res.partner", string="Begunstigde of eigenaar", required=True)
    partner_bank_id = fields.Many2one("res.partner.bank", string="Rekening", required=True)
    mandate_id = fields.Many2one("vme.sepa.mandate", string="Mandaat")
    amount = fields.Monetary(string="Bedrag", required=True)
    communication = fields.Char(string="Mededeling")
    end_to_end_id = fields.Char(string="Referentie (EndToEndId)", copy=False, index=True, readonly=True)
    sequence_number = fields.Integer(compute="_compute_sequence_number")
    state = fields.Selection(LINE_STATES, string="Status", default="draft", required=True, index=True)
    statement_line_id = fields.Many2one("account.bank.statement.line", string="Bankbeweging", readonly=True, copy=False,
                                        index="btree_not_null")
    return_statement_line_id = fields.Many2one("account.bank.statement.line", string="Terugboeking", readonly=True,
                                               copy=False, index="btree_not_null")
    return_reason = fields.Char(string="Reden", readonly=True)

    def _compute_sequence_number(self):
        for line in self:
            line.sequence_number = (line.batch_id.line_ids.ids.index(line.id) + 1) if line.id in line.batch_id.line_ids.ids else 0

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(self.env._("Het bedrag van een betaling moet groter zijn dan nul."))

    def unlink(self):
        if any(line.batch_id.state != "draft" for line in self):
            raise UserError(self.env._("Betalingen verwijdert u alleen uit een concept."))
        return super().unlink()

    def _mark_paid(self, statement_line):
        self.write({"state": "paid", "statement_line_id": statement_line.id})
        self.batch_id._update_done()

    def _mark_returned(self, statement_line, reason):
        label = RETURN_REASONS.get(reason or "", reason or "")
        self.write({"state": "rejected", "return_statement_line_id": statement_line.id,
                    "return_reason": f"{reason} {label}".strip() if reason else self.env._("Teruggekomen")})
        self.batch_id._update_done()


class VmeProvisionCall(models.Model):
    _inherit = "vme.provision.call"

    direct_debit_batch_ids = fields.One2many("vme.payment.batch", "provision_call_id", string="Incassobestanden")
    direct_debit_batch_count = fields.Integer(compute="_compute_direct_debit_batch_count")

    def _compute_direct_debit_batch_count(self):
        for call in self:
            call.direct_debit_batch_count = len(call.direct_debit_batch_ids.filtered(lambda b: b.state != "cancel"))

    def _default_collection_date(self):
        """Not before the due date, the pre-notification term, and tomorrow (SEPA Core: D-1)."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        return max(self.date_due, self.date + timedelta(days=PRE_NOTIFICATION_DAYS), today + timedelta(days=1))

    def action_create_direct_debit_batch(self):
        """A draft collection file for the open provisions of owners with a mandate."""
        self.ensure_one()
        batch = self.env["vme.payment.batch"].create({
            "batch_type": "direct_debit",
            "association_id": self.association_id.id,
            "provision_call_id": self.id,
            "fund": False,
            "execution_date": self._default_collection_date(),
        })
        batch.action_fill_proposal()
        return {
            "type": "ir.actions.act_window",
            "res_model": "vme.payment.batch",
            "res_id": batch.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    def action_open_direct_debit_batches(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_direct_debit_batch_action")
        action["domain"] = [("provision_call_id", "in", self.ids)]
        action["context"] = {"default_batch_type": "direct_debit"}
        return action
