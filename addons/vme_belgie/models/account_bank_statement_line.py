import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from .bank_formats import find_structured, format_structured
from .vme_access import check_not_auditor
from .vme_payment import RETURN_REASONS

MATCH_STATES = [
    ("auto", "Automatisch gekoppeld"),
    ("manual", "Manueel gekoppeld"),
    ("suggested", "Voorstel"),
    ("todo", "Te koppelen"),
]
EXCEPTIONS = [
    ("no_reference", "Geen mededeling"),
    ("wrong_reference", "Foute mededeling"),
    ("already_paid", "Al betaald"),
    ("wrong_fund", "Rekening van het andere fonds"),
    ("underpaid", "Te weinig betaald"),
    ("overpaid", "Te veel betaald"),
    ("unknown", "Onbekende betaling"),
    ("dd_returned", "Domiciliëring teruggekomen"),
]
OPEN_ACCOUNT_TYPES = ("asset_receivable", "liability_payable")


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    # The name is translated ("van" / "du"): duplicates are recognised on this key instead.
    vme_import_key = fields.Char(
        string="Importsleutel", readonly=True, copy=False, index=True,
        help="Formaat, nummer en datum van het ingelezen afschrift.")


class AccountBankStatementLine(models.Model):
    """Matching of imported bank movements with provisions and vendor bills of a VME.

    Odoo Community stores statement lines on the suspense account of the bank journal but has no
    reconciliation screen (that is the Enterprise app account_accountant). This adds automatic
    matching on the structured communication, proposals for the rest, and a few buttons to link.
    """
    _inherit = "account.bank.statement.line"

    vme_bank_fund = fields.Selection(
        [("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")],
        string="Fondsrekening", compute="_compute_vme_bank_fund", store=True,
    )
    vme_match_state = fields.Selection(MATCH_STATES, string="Koppeling", default="todo", copy=False, index=True)
    vme_exception = fields.Selection(EXCEPTIONS, string="Uitzondering", copy=False)
    vme_days_late = fields.Integer(string="Dagen te laat", copy=False)
    vme_match_note = fields.Char(string="Toelichting", copy=False)
    vme_structured_reference = fields.Char(string="Gestructureerde mededeling", copy=False)
    vme_candidate_move_ids = fields.Many2many(
        "account.move", "vme_bank_line_candidate_rel", "line_id", "move_id",
        string="Voorstel", copy=False,
        help="De facturen waarmee deze betaling gekoppeld wordt als u op Koppelen klikt. "
             "Pas de lijst aan als het voorstel niet klopt.",
    )
    vme_matched_move_ids = fields.Many2many(
        "account.move", string="Gekoppeld met", compute="_compute_vme_matched_move_ids",
    )
    vme_end_to_end_id = fields.Char(
        string="SEPA-referentie", copy=False, index="btree_not_null",
        help="EndToEndId van een betaling uit een betaalbatch van de VME, zoals de bank ze teruggeeft.")
    vme_return_reason = fields.Char(string="Reden terugboeking", copy=False)
    vme_payment_batch_line_ids = fields.One2many(
        "vme.payment.batch.line", "statement_line_id", string="Betaling uit batch", readonly=True)
    vme_follow_up = fields.Boolean(
        string="Op te volgen", compute="_compute_vme_follow_up", store=True,
        help="Nog te koppelen, of gekoppeld maar te laat, te weinig of te veel betaald.",
    )

    @api.depends("journal_id.bank_account_id")
    def _compute_vme_bank_fund(self):
        vmes = self.env["vme.association"].sudo().with_context(active_test=False).search(
            [("company_id", "in", self.company_id.ids)])
        by_company = {vme.company_id: vme for vme in vmes}
        for line in self:
            vme = by_company.get(line.company_id)
            bank = line.journal_id.bank_account_id
            if vme and bank and bank == vme.working_capital_bank_id:
                line.vme_bank_fund = "working"
            elif vme and bank and bank == vme.reserve_capital_bank_id:
                line.vme_bank_fund = "reserve"
            else:
                line.vme_bank_fund = False

    @api.depends("vme_match_state", "vme_exception", "vme_days_late")
    def _compute_vme_follow_up(self):
        for line in self:
            line.vme_follow_up = (
                line.vme_match_state in ("todo", "suggested")
                or line.vme_exception in ("underpaid", "overpaid", "wrong_fund", "dd_returned")
                or line.vme_days_late > 0
            )

    def _compute_vme_matched_move_ids(self):
        for line in self:
            counterparts = line.line_ids.matched_debit_ids.debit_move_id | line.line_ids.matched_credit_ids.credit_move_id
            line.vme_matched_move_ids = counterparts.move_id - line.move_id

    # ------------------------------------------------------------------
    # Automatic matching
    # ------------------------------------------------------------------

    def _vme_match(self):
        """Match each unreconciled line automatically, or leave a proposal and an exception.

        Runs as superuser: it writes journal items of invoices and bank lines in the company of the
        VME, whatever companies the user has selected (the buttons check the user's rights first).
        """
        for line in self.sudo().filtered(lambda l: not l.is_reconciled and l.vme_match_state != "manual"):
            line.write({
                "vme_match_state": "todo", "vme_exception": False, "vme_days_late": 0,
                "vme_match_note": False, "vme_candidate_move_ids": [Command.clear()],
            })
            if line._vme_match_payment_batch():
                continue
            if line.amount > 0:
                line._vme_match_receipt()
            elif line.amount < 0:
                line._vme_match_supplier_payment()
        return True

    def _vme_open_moves(self, move_types, extra_domain=()):
        self.ensure_one()
        return self.env["account.move"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", move_types),
            ("state", "=", "posted"),
            ("payment_state", "not in", ("paid", "in_payment", "reversed")),
            *extra_domain,
        ], order="invoice_date_due, invoice_date, id")

    def _vme_moves_by_reference(self, digits, move_types):
        return self.env["account.move"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", move_types),
            ("state", "=", "posted"),
            ("sanitize_payment_reference", "=", digits),
        ], order="id")

    def _vme_match_receipt(self):
        """Money in: provisions (and later settlements) are customer invoices of the VME company."""
        self.ensure_one()
        digits, valid = find_structured(self.payment_ref)
        if digits:
            self.vme_structured_reference = format_structured(digits)
        if not digits:
            self.vme_exception = "no_reference"
        elif not valid:
            self.vme_exception = "wrong_reference"
            self.vme_match_note = self.env._("De controlecijfers van de mededeling kloppen niet (tikfout?).")
        else:
            moves = self._vme_moves_by_reference(digits, ("out_invoice",))
            open_moves = moves.filtered(lambda m: m.payment_state not in ("paid", "in_payment", "reversed"))
            if not moves:
                self.vme_exception = "wrong_reference"
                self.vme_match_note = self.env._("Geen factuur van deze VME met deze mededeling.")
            elif not open_moves:
                self.vme_exception = "already_paid"
                self.vme_match_note = self.env._(
                    "%(invoice)s is al betaald: dubbele betaling? Boek het bedrag als tegoed van de eigenaar "
                    "of betaal het terug.", invoice=moves[0].name)
                if not self.partner_id:
                    self.partner_id = moves[0].partner_id
            else:
                move = open_moves[0]
                if self.vme_bank_fund and move.vme_fund and move.vme_fund != self.vme_bank_fund:
                    # LEGAL-CHECK: art. 3.89 §5 BW - working and reserve capital on separate accounts:
                    # never book a provision of one fund silently on the account of the other.
                    self.write({
                        "vme_exception": "wrong_fund",
                        "vme_match_state": "suggested",
                        "vme_candidate_move_ids": [Command.set(move.ids)],
                        "vme_match_note": self.env._(
                            "%(invoice)s is een provisie %(fund)s maar werd op de rekening %(account)s betaald. "
                            "Na het koppelen het bedrag overschrijven naar de juiste rekening.",
                            invoice=move.name, fund=dict(move._fields["vme_fund"].selection)[move.vme_fund].lower(),
                            account=dict(self._fields["vme_bank_fund"].selection)[self.vme_bank_fund].lower()),
                    })
                    if not self.partner_id:
                        self.partner_id = move.partner_id
                    return
                if not self.partner_id:
                    self.partner_id = move.partner_id  # before reconciling: it rewrites the journal items
                self._vme_reconcile(move, state="auto")
                return
        self._vme_suggest_receipt()

    def _vme_identify_partners(self):
        """Owners this movement probably comes from: by bank account, by name, or by a lot in the text."""
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        if self.partner_id:
            return self.partner_id, self.env._("eigenaar van de betaling")
        if self.account_number:
            banks = self.env["res.partner.bank"].sudo().search([
                ("sanitized_acc_number", "=", re.sub(r"\W", "", self.account_number).upper()),
                ("partner_id", "!=", self.company_id.partner_id.id),
            ])
            if banks.partner_id:
                return banks.partner_id, self.env._("rekeningnummer van de eigenaar")
        vme = self.vme_association_id.sudo()
        owners = vme.lot_ids.ownership_ids.partner_id
        if self.partner_name:
            by_name = owners.filtered(lambda p: p.name.lower() == self.partner_name.strip().lower())
            if by_name:
                return by_name, self.env._("naam van de eigenaar")
        if self.payment_ref:
            lots = vme.lot_ids.filtered(
                lambda lot: re.search(rf"(?<![\w]){re.escape(lot.name)}(?![\w])", self.payment_ref, re.IGNORECASE))
            by_lot = Partner.browse()
            for lot in lots:
                by_lot |= lot._get_owner_on(self.date) or Partner.browse()
            if by_lot:
                return by_lot, self.env._("kavel %s in de mededeling", ", ".join(lots.mapped("name")))
        return Partner.browse(), ""

    def _vme_suggest_receipt(self):
        self.ensure_one()
        currency = self.currency_id
        fund_domain = [("vme_fund", "=", self.vme_bank_fund)] if self.vme_bank_fund else []
        partners, how = self._vme_identify_partners()
        candidates = self.env["account.move"]
        note = ""
        if partners:
            open_moves = self._vme_open_moves(("out_invoice",), [("partner_id", "in", partners.ids), *fund_domain])
            exact = open_moves.filtered(lambda m: currency.is_zero(m.amount_residual - self.amount))
            if exact:
                candidates = exact[0]
                note = self.env._("Bedrag gelijk aan de openstaande provisie (%(how)s).", how=how)
                if len(exact) > 1:
                    note = self.env._(
                        "%(count)s openstaande provisies van dit bedrag (%(how)s): voorstel is de oudste.",
                        count=len(exact), how=how)
            elif open_moves and currency.is_zero(sum(open_moves.mapped("amount_residual")) - self.amount):
                candidates = open_moves
                note = self.env._("Bedrag gelijk aan alle openstaande provisies samen (%(how)s).", how=how)
            elif open_moves:
                candidates = open_moves
                note = self.env._(
                    "Bedrag wijkt af van de openstaande provisies (%(how)s): kijk na voor u koppelt.", how=how)
            else:
                note = self.env._("Geen openstaande provisies van deze eigenaar (%(how)s).", how=how)
            if len(partners) == 1 and not self.partner_id:
                self.partner_id = partners
        else:
            same_amount = self._vme_open_moves(("out_invoice",), fund_domain).filtered(
                lambda m: currency.is_zero(m.amount_residual - self.amount))
            if len(same_amount) == 1:
                candidates = same_amount
                note = self.env._("Onbekende afzender; enige openstaande provisie van dit bedrag (%s).",
                                  same_amount.partner_id.name)
            elif same_amount:
                note = self.env._("Onbekende afzender; %s openstaande provisies van dit bedrag.", len(same_amount))
            else:
                note = self.env._("Onbekende afzender en geen openstaande provisie van dit bedrag.")
        self.write({
            "vme_match_state": "suggested" if candidates else "todo",
            "vme_candidate_move_ids": [Command.set(candidates.ids)],
            "vme_exception": self.vme_exception or "unknown",
            "vme_match_note": " ".join(filter(None, [self.vme_match_note, note])),
        })

    def _vme_match_supplier_payment(self):
        """Money out: link to a posted vendor bill by reference, or by supplier and amount."""
        self.ensure_one()
        currency = self.currency_id
        open_bills = self._vme_open_moves(("in_invoice",))
        digits, valid = find_structured(self.payment_ref)
        by_reference = self.env["account.move"]
        if digits and valid:
            self.vme_structured_reference = format_structured(digits)
            by_reference = open_bills.filtered(lambda m: m.sanitize_payment_reference == digits)
        if not by_reference and self.payment_ref:
            text = self.payment_ref.lower()
            by_reference = open_bills.filtered(lambda m: m.ref and m.ref.lower() in text)
        partners = self.env["res.partner"]
        if self.account_number:
            partners = self.env["res.partner.bank"].sudo().search([
                ("sanitized_acc_number", "=", re.sub(r"\W", "", self.account_number).upper())]).partner_id
        if not partners and self.partner_name:
            partners = open_bills.partner_id.filtered(lambda p: p.name.lower() == self.partner_name.strip().lower())
        candidates = by_reference or open_bills.filtered(lambda m: m.partner_id in partners)
        exact = candidates.filtered(lambda m: currency.is_zero(m.amount_residual + self.amount))
        if len(exact) == 1 and (by_reference or partners):
            if not self.partner_id:
                self.partner_id = exact.partner_id
            self._vme_reconcile(exact, state="auto")
            return
        if candidates:
            note = self.env._("Bedrag of factuur niet eenduidig: kijk het voorstel na.")
            candidates = exact[:1] or candidates
        else:
            note = self.env._("Geen geboekte leveranciersfactuur gevonden voor deze betaling.")
        if len(candidates.partner_id) == 1 and not self.partner_id:
            self.partner_id = candidates.partner_id
        self.write({
            "vme_match_state": "suggested" if candidates else "todo",
            "vme_candidate_move_ids": [Command.set(candidates.ids)],
            "vme_exception": "unknown" if not candidates else False,
            "vme_match_note": note,
        })

    # ------------------------------------------------------------------
    # Payments from our own SEPA files (stap 20)
    # ------------------------------------------------------------------

    def _vme_batch_lines(self, moves, batch_type, states=("draft", "sent")):
        """Lines of active payment batches (file made or uploaded) for these invoices."""
        return self.env["vme.payment.batch.line"].sudo().search([
            ("move_id", "in", moves.ids), ("batch_type", "=", batch_type), ("state", "in", states),
            ("batch_id.state", "in", ("generated", "sent", "done")),
        ])

    def _vme_find_batch_line(self):
        """The payment of a batch this movement is about: by SEPA reference, else by amount and communication."""
        self.ensure_one()
        Line = self.env["vme.payment.batch.line"].sudo()
        domain = [("company_id", "=", self.company_id.id), ("batch_id.state", "in", ("generated", "sent", "done"))]
        if self.vme_end_to_end_id:
            return Line.search(domain + [("end_to_end_id", "=", self.vme_end_to_end_id)], limit=1)
        if self.amount > 0:
            # Collected provision: its structured communication comes back as the communication.
            domain += [("batch_type", "=", "direct_debit"), ("state", "in", ("draft", "sent"))]
        elif self.vme_return_reason:
            domain += [("batch_type", "=", "direct_debit"), ("state", "in", ("sent", "paid"))]
        else:
            domain += [("batch_type", "=", "transfer"), ("state", "in", ("draft", "sent"))]
        digits, valid = find_structured(self.payment_ref)
        text = (self.payment_ref or "").lower()
        for line in Line.search(domain, order="id"):
            if not self.currency_id.is_zero(line.amount - abs(self.amount)):
                continue
            line_digits, _valid = find_structured(line.communication)
            if (digits and valid and line_digits == digits) or (
                    not line_digits and line.communication and line.communication.lower() in text):
                return line
        return Line

    def _vme_match_payment_batch(self):
        """Confirm or return a payment of one of our SEPA files. Returns True if this line was one."""
        self.ensure_one()
        batch_line = self._vme_find_batch_line()
        if not batch_line:
            return False
        if not self.partner_id:
            self.partner_id = batch_line.partner_id  # before reconciling: it rewrites the journal items
        is_return = self.amount < 0 and batch_line.batch_type == "direct_debit"
        if is_return:
            self._vme_return_direct_debit(batch_line)
            return True
        if batch_line.state not in ("draft", "sent") or (self.amount > 0) != (batch_line.batch_type == "direct_debit"):
            return False
        invoice = batch_line.move_id
        if invoice.payment_state in ("paid", "in_payment", "reversed"):
            self.write({"vme_exception": "already_paid", "vme_match_note": self.env._(
                "%(invoice)s uit %(batch)s was al betaald: dubbele betaling?", invoice=invoice.name,
                batch=batch_line.batch_id.name)})
            if self.amount > 0:
                self._vme_suggest_receipt()
            return True
        self._vme_reconcile(invoice, state="auto")
        if batch_line.batch_type == "direct_debit":
            self.vme_days_late = 0  # the syndic chose the collection date, not the owner
        if self.vme_match_note:
            self.vme_match_note = self.env._("%(batch)s: %(note)s", batch=batch_line.batch_id.name, note=self.vme_match_note)
        else:
            self.vme_match_note = self.env._("Betaling uit %s bevestigd door de bank.", batch_line.batch_id.name)
        batch_line._mark_paid(self)
        return True

    def _vme_return_direct_debit(self, batch_line):
        """A collection came back: reopen the provision and hand it to the collection of arrears (stap 10).

        The return is matched with the earlier collection on the owner's receivable account, so both bank
        movements are settled and the provision is open again with its own due date.
        """
        self.ensure_one()
        invoice = batch_line.move_id
        reason = self.vme_return_reason or ""
        label = " ".join(filter(None, [reason, RETURN_REASONS.get(reason)]))
        collected = batch_line.statement_line_id
        if collected and collected.is_reconciled:
            receivable = invoice.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
            counterparts = collected.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable"
                and (l.matched_debit_ids.debit_move_id | l.matched_credit_ids.credit_move_id) & receivable)
            counterparts.remove_move_reconcile()
            self._vme_reconcile(collected.move_id, state="auto")
            note = self.env._(
                "Domiciliëring teruggekomen (%(reason)s): %(invoice)s is weer open en staat in de invordering.",
                reason=label or self.env._("geen reden"), invoice=invoice.name)
        else:
            note = self.env._(
                "Domiciliëring van %(invoice)s teruggekomen (%(reason)s), maar de inning zelf is nog niet gekoppeld: "
                "koppel eerst de inning en daarna deze terugboeking.", invoice=invoice.name, reason=label or "-")
        self.write({"vme_exception": "dd_returned", "vme_match_note": note,
                    "vme_match_state": "auto" if self.is_reconciled else "todo"})
        batch_line._mark_returned(self, reason)
        invoice.message_post(body=note)
        vme = invoice.vme_association_id
        Collection = self.env["vme.collection"].sudo()
        collection = Collection.search([("association_id", "=", vme.id), ("partner_id", "=", batch_line.partner_id.id),
                                        ("state", "!=", "closed")], limit=1)
        if not collection:
            collection = Collection.create({"association_id": vme.id, "partner_id": batch_line.partner_id.id})
        collection.message_post(body=note)

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _vme_reconcile(self, moves, state, leftover_on_partner=None):
        """Replace the suspense line by counterparts on the open receivable/payable lines of moves.

        Oldest due date first. A remainder stays on the suspense account, or goes to the partner's
        receivable/payable as a credit when leftover_on_partner (default: for an overpayment with
        a known partner). Sets the exception (under/overpaid) and the days late.
        """
        self.ensure_one()
        _liquidity, suspense, _other = self._seek_for_lines()
        if not suspense or self.is_reconciled:
            raise UserError(self.env._("Deze betaling is al gekoppeld. Maak de koppeling eerst ongedaan."))
        currency = self.company_id.currency_id
        open_lines = moves.sudo().line_ids.filtered(
            lambda l: l.account_id.account_type in OPEN_ACCOUNT_TYPES and not l.reconciled
            and not currency.is_zero(l.amount_residual)
        ).sorted(lambda l: (l.date_maturity or l.date, l.id))
        sign = 1 if self.amount > 0 else -1  # receipt: counterparts are credits
        remaining = abs(sum(suspense.mapped("balance")))
        open_total = abs(sum(open_lines.mapped("amount_residual")))
        commands = [Command.delete(line.id) for line in suspense]
        pairs = []
        for open_line in open_lines:
            if currency.is_zero(remaining):
                break
            part = min(remaining, abs(open_line.amount_residual))
            remaining = currency.round(remaining - part)
            pairs.append((open_line, part))
            commands.append(Command.create(self._vme_counterpart_vals(
                open_line.account_id, open_line.partner_id, -sign * part, open_line.move_id.name)))
        partner = self.partner_id or open_lines.partner_id[:1]
        if leftover_on_partner is None:
            leftover_on_partner = bool(open_lines) and bool(partner)
        if not currency.is_zero(remaining):
            if leftover_on_partner and partner:
                partner = partner.with_company(self.company_id)
                account = partner.property_account_receivable_id if sign > 0 else partner.property_account_payable_id
                name = self.env._("Tegoed %s", partner.name)
            else:
                account, partner, name = suspense[0].account_id, self.partner_id, self.payment_ref
            commands.append(Command.create(self._vme_counterpart_vals(account, partner, -sign * remaining, name)))
        before = self.move_id.line_ids
        self.move_id.sudo().with_context(skip_readonly_check=True, force_delete=True).write({"line_ids": commands})
        created = self.move_id.line_ids - before
        for open_line, part in pairs:
            new_line = created.filtered(
                lambda l, o=open_line, p=part: l.account_id == o.account_id and l.partner_id == o.partner_id
                and currency.is_zero(abs(l.balance) - p))[:1]
            created -= new_line
            (new_line | open_line).reconcile()

        vals = {"vme_match_state": state, "vme_candidate_move_ids": [Command.clear()]}
        paid = abs(self.amount)
        if open_lines and not self.vme_exception:
            if currency.compare_amounts(paid, open_total) < 0:
                vals["vme_exception"] = "underpaid"
                vals["vme_match_note"] = self.env._(
                    "Te weinig betaald: nog %s open.", currency.format(open_total - paid))
            elif currency.compare_amounts(paid, open_total) > 0:
                vals["vme_exception"] = "overpaid"
                vals["vme_match_note"] = self.env._(
                    "Te veel betaald: %s als tegoed van de eigenaar.", currency.format(paid - open_total))
        due = min(filter(None, moves.mapped("invoice_date_due")), default=None)
        if sign > 0 and due and self.date > due:
            vals["vme_days_late"] = (self.date - due).days
        self.write(vals)
        if sign < 0:
            # A bill paid from a batch file, matched on its reference or supplier: the bank confirmed it.
            self._vme_batch_lines(moves, "transfer").filtered(
                lambda l: l.move_id.payment_state in ("paid", "in_payment"))._mark_paid(self)

    def _vme_counterpart_vals(self, account, partner, balance, name):
        return {
            "account_id": account.id,
            "partner_id": partner.id,
            "name": name,
            "balance": balance,
            "amount_currency": balance,
            "currency_id": self.company_id.currency_id.id,
        }

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def action_vme_reconcile(self):
        """Link with the moves in the proposal (possibly changed by the user)."""
        check_not_auditor(self.env)
        self.check_access("write")
        for line in self.sudo():
            if not line.vme_candidate_move_ids:
                raise UserError(self.env._("Kies eerst in het voorstel met welke factuur u deze betaling koppelt."))
            other = line.vme_candidate_move_ids.filtered(lambda m: m.company_id != line.company_id)
            if other:
                raise UserError(self.env._("%s hoort bij een andere VME.", ", ".join(other.mapped("name"))))
            if not line.partner_id and len(line.vme_candidate_move_ids.partner_id) == 1:
                line.partner_id = line.vme_candidate_move_ids.partner_id
            exception = line.vme_exception if line.vme_exception == "wrong_fund" else False
            line.write({"vme_exception": exception, "vme_match_note": False if not exception else line.vme_match_note})
            line._vme_reconcile(line.vme_candidate_move_ids, state="manual")
            line._vme_learn_bank_account()
        return True

    def action_vme_book_on_partner(self):
        """Book the whole amount as a credit (receipt) or debt (payment) of the partner, without invoice."""
        check_not_auditor(self.env)
        self.check_access("write")
        for line in self.sudo():
            if not line.partner_id:
                raise UserError(self.env._("Vul eerst de eigenaar of leverancier in."))
            line.write({"vme_exception": False, "vme_match_note": self.env._(
                "Geboekt op %s zonder factuur.", line.partner_id.name)})
            line._vme_reconcile(self.env["account.move"], state="manual", leftover_on_partner=True)
            line._vme_learn_bank_account()
        return True

    def action_vme_undo(self):
        check_not_auditor(self.env)
        self.check_access("write")
        lines = self.sudo()
        lines.action_undo_reconciliation()
        lines.write({"vme_match_state": "todo", "vme_days_late": 0})
        lines._vme_match()
        return True

    def action_vme_rematch(self):
        check_not_auditor(self.env)
        self.check_access("write")
        self._vme_match()
        return True

    def _vme_learn_bank_account(self):
        # Like Odoo's own reconciliation: remember the counterparty account, so the next payment
        # from this account is recognised.
        if self.account_number and self.partner_id:
            self.sudo()._find_or_create_bank_account()
