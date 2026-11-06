from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import format_date

from . import remittance_rules as rules

LINE_TYPES = [
    ("rent", "Huur"),
    ("charges", "Lasten"),
    ("settlement", "Afrekening lasten"),
    ("cost", "Kost voor rekening van de verhuurder"),
    ("fee", "Ereloon rentmeester"),
]
RECEIVED_TYPES = ("rent", "charges", "settlement")


class VmeRentRemittance(models.Model):
    _name = "vme.rent.remittance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Doorstorting aan de verhuurder"
    _order = "month desc, landlord_id, id desc"

    name = fields.Char(string="Doorstorting", compute="_compute_name", store=True)
    landlord_id = fields.Many2one("res.partner", string="Verhuurder", required=True, index=True)
    company_id = fields.Many2one("res.company", string="Rentmeesterkantoor", required=True,
                                 default=lambda self: self.env["vme.rent.contract"]._default_company())
    currency_id = fields.Many2one(related="company_id.currency_id")
    month = fields.Date(string="Maand", required=True,
                        help="Neemt alles mee wat tot het einde van deze maand ontvangen of betaald is en nog niet "
                             "doorgestort werd.")
    state = fields.Selection([("draft", "Concept"), ("confirmed", "Bevestigd"), ("cancel", "Overgedragen")],
                             string="Status", default="draft", required=True, tracking=True, copy=False)
    line_ids = fields.One2many("vme.rent.remittance.line", "remittance_id", string="Regels", copy=False)
    received = fields.Monetary(string="Ontvangen huur en lasten", compute="_compute_totals", store=True)
    costs = fields.Monetary(string="Kosten voor de verhuurder", compute="_compute_totals", store=True)
    fee_untaxed = fields.Monetary(string="Ereloon zonder btw", compute="_compute_totals", store=True)
    fee_tax = fields.Monetary(string="Btw op het ereloon", compute="_compute_totals", store=True)
    fee_total = fields.Monetary(string="Ereloon met btw", compute="_compute_totals", store=True)
    balance = fields.Monetary(string="Door te storten", compute="_compute_totals", store=True,
                              help="Ontvangen huur en lasten min kosten min ereloon met btw.")
    partner_bank_id = fields.Many2one("res.partner.bank", string="Rekening van de verhuurder",
                                      compute="_compute_partner_bank_id", store=True, readonly=False,
                                      domain="[('partner_id', '=', landlord_id)]")
    bank_untrusted = fields.Boolean(compute="_compute_payment_status")
    note = fields.Text(string="Opmerkingen", readonly=True)

    fee_invoice_id = fields.Many2one("account.move", string="Ereloonfactuur", readonly=True, copy=False)
    payout_move_id = fields.Many2one("account.move", string="Doorstortingsstuk", readonly=True, copy=False,
                                     help="Het stuk dat de huur op 489100 afboekt; dit staat in de betaalbatch.")
    offset_move_id = fields.Many2one("account.move", string="Verrekening ereloon", readonly=True, copy=False)
    payment_status = fields.Selection(
        [("none", "Niets door te storten"), ("to_approve", "Goed te keuren"), ("to_pay", "Klaar voor betaalbatch"),
         ("in_batch", "In betaalbatch"), ("sent", "Verstuurd"), ("paid", "Doorgestort"),
         ("rejected", "Teruggekomen")],
        string="Betaling", compute="_compute_payment_status")

    @api.depends("landlord_id.name", "month")
    def _compute_name(self):
        for remittance in self:
            period = format_date(self.env, remittance.month, date_format="MMMM y") if remittance.month else ""
            remittance.name = self.env._("Doorstorting %(period)s - %(landlord)s", period=period,
                                         landlord=remittance.landlord_id.name or "")

    @api.depends("line_ids.amount", "line_ids.tax_amount", "line_ids.line_type")
    def _compute_totals(self):
        for remittance in self:
            lines = remittance.line_ids
            received = sum(lines.filtered(lambda l: l.line_type in RECEIVED_TYPES).mapped("amount"))
            costs = sum(lines.filtered(lambda l: l.line_type == "cost").mapped("amount"))
            fees = lines.filtered(lambda l: l.line_type == "fee")
            remittance.received = rules.money(received)
            remittance.costs = rules.money(costs)
            remittance.fee_untaxed = rules.money(sum(fees.mapped("amount")))
            remittance.fee_tax = rules.money(sum(fees.mapped("tax_amount")))
            remittance.fee_total = rules.money(remittance.fee_untaxed + remittance.fee_tax)
            remittance.balance = rules.balance(received, costs, remittance.fee_total)

    @api.depends("landlord_id", "line_ids.contract_id.mandate_id.partner_bank_id")
    def _compute_partner_bank_id(self):
        for remittance in self:
            mandates = remittance.line_ids.contract_id.mandate_id or remittance._mandates()
            remittance.partner_bank_id = mandates.partner_bank_id[:1] or remittance.partner_bank_id

    @api.depends("state", "partner_bank_id.allow_out_payment", "payout_move_id.payment_state",
                 "payout_move_id.vme_payment_status", "payout_move_id.vme_approval_state")
    def _compute_payment_status(self):
        for remittance in self:
            payout = remittance.sudo().payout_move_id
            remittance.bank_untrusted = bool(remittance.partner_bank_id) and \
                not remittance.partner_bank_id.allow_out_payment
            if remittance.state != "confirmed" or not payout:
                status = "none" if remittance.state == "confirmed" else False
            elif payout.payment_state in ("paid", "in_payment"):
                status = "paid"
            elif payout.vme_payment_status:
                status = payout.vme_payment_status
            elif payout.vme_approval_state != "approved":
                status = "to_approve"
            else:
                status = "to_pay"
            remittance.payment_status = status

    _unique_month = models.UniqueIndex("(landlord_id, company_id, month) WHERE state != 'cancel'",
                                       "Er is al een doorstorting voor deze verhuurder en maand.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("month"):
                vals["month"] = fields.Date.to_date(vals["month"]).replace(day=1)
        remittances = super().create(vals_list)
        remittances._recompute_lines()
        return remittances

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------

    def _mandates(self):
        return self.env["vme.rent.mandate"].search([
            ("landlord_id", "=", self.landlord_id.id), ("company_id", "=", self.company_id.id)])

    def _contracts(self):
        return self.env["vme.rent.contract"].with_context(active_test=False).search([
            ("landlord_id", "=", self.landlord_id.id), ("company_id", "=", self.company_id.id)])

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        # Its lines mark what was already paid out: without them the next remittance pays it again.
        if confirmed := self.filtered(lambda r: r.state == "confirmed"):
            raise UserError(self.env._(
                "Een bevestigde doorstorting kan niet verwijderd worden: %s.", ", ".join(confirmed.mapped("name"))))

    def _done_lines(self):
        """Lines already in a confirmed remittance: never taken twice."""
        return self.env["vme.rent.remittance.line"].sudo().search([
            ("remittance_id.landlord_id", "=", self.landlord_id.id),
            ("remittance_id.company_id", "=", self.company_id.id),
            ("remittance_id.state", "=", "confirmed"), ("remittance_id", "!=", self.id),
        ])

    def _received_line_vals(self, contracts, done):
        """Rent, charges and settlements received from the tenants and not yet transferred.

        Received = total - residual of each tenant invoice dated up to the end of the month;
        a partial payment pays rent and charges in proportion.
        """
        end = rules.month_end(self.month)
        # sudo: the invoices live in the office's company, whatever companies the user selected.
        invoices = self.env["account.move"].sudo().search([
            ("rent_contract_id", "in", contracts.ids), ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("out_invoice", "out_refund")), ("state", "=", "posted"),
            ("invoice_date", "<=", end),
        ], order="invoice_date, id")
        already = {}
        for line in done.filtered(lambda l: l.line_type in RECEIVED_TYPES):
            already[line.move_id] = already.get(line.move_id, 0.0) + line.amount
        vals = []
        for invoice in invoices:
            sign = -1 if invoice.move_type == "out_refund" else 1
            received = sign * (invoice.amount_total - invoice.amount_residual)
            new = rules.money(received - already.get(invoice, 0.0))
            if self.currency_id.is_zero(new):
                continue
            by_type = {}
            for line in invoice.invoice_line_ids:
                key = line.rent_line_type if line.rent_line_type in RECEIVED_TYPES else "rent"
                by_type[key] = by_type.get(key, 0.0) + sign * line.price_subtotal
            if "settlement" in by_type:
                parts = {"settlement": new}
            else:
                rent, charges = rules.split_received(new, by_type.get("rent", 0.0), by_type.get("charges", 0.0))
                parts = {"rent": rent, "charges": charges}
            period = invoice.rent_period and format_date(self.env, invoice.rent_period, date_format="MMMM y")
            for line_type, amount in parts.items():
                if self.currency_id.is_zero(amount):
                    continue
                vals.append({
                    "line_type": line_type,
                    "contract_id": invoice.rent_contract_id.id,
                    "move_id": invoice.id,
                    "move_name": invoice.name,
                    "date": invoice.invoice_date,
                    "description": "%s %s" % (dict(LINE_TYPES)[line_type], period or invoice.ref or ""),
                    "amount": amount,
                })
        return vals

    def _cost_line_vals(self, contracts, done):
        """Bills the office paid for the landlord: booked on 489100 with the lease, not yet deducted."""
        end = rules.month_end(self.month)
        bills = self.env["account.move"].sudo().search([
            ("rent_contract_id", "in", contracts.ids), ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("in_invoice", "in_refund")), ("state", "=", "posted"),
            ("invoice_date", "<=", end), ("id", "not in", done.move_id.ids),
        ], order="invoice_date, id")
        return [{
            "line_type": "cost",
            "contract_id": bill.rent_contract_id.id,
            "move_id": bill.id,
            "move_name": bill.name,
            "date": bill.invoice_date,
            "description": f"{bill.partner_id.name}: {bill.ref or bill.invoice_line_ids[:1].name or ''}",
            "amount": (-1 if bill.move_type == "in_refund" else 1) * bill.amount_total,
        } for bill in bills]

    def _fee_line_vals(self, received_vals, done):
        """Fee per mandate: a percentage of the rent (and charges) received, or a fixed amount per month."""
        vals = []
        Contract = self.env["vme.rent.contract"]
        mandates = Contract.browse([v["contract_id"] for v in received_vals]).mandate_id
        mandates |= self._mandates().filtered(lambda m: m.fee_type == "fixed" and m.active and (
            not m.date_end or m.date_end >= self.month) and m.date_start <= rules.month_end(self.month))
        for mandate in mandates:
            contracts = mandate.contract_ids
            mine = [v for v in received_vals if v["contract_id"] in contracts.ids]
            rent = sum(v["amount"] for v in mine if v["line_type"] == "rent")
            charges = sum(v["amount"] for v in mine if v["line_type"] in ("charges", "settlement"))
            charged = done.filtered(lambda l, m=mandate: l.line_type == "fee" and l.mandate_id == m)
            last = max(charged.remittance_id.mapped("month"), default=None)
            untaxed, base, months = mandate._fee_untaxed(rent, charges, self.month, last)
            if self.currency_id.is_zero(untaxed):
                continue
            tax = mandate._get_fee_tax()
            tax_amount = rules.money(tax.compute_all(untaxed, self.currency_id)["total_included"] - untaxed) \
                if tax else 0.0
            if mandate.fee_type == "percent":
                description = self.env._("%(percent)s %% op %(base)s", percent=f"{mandate.fee_percent:g}",
                                         base=self.currency_id.format(base))
            else:
                description = self.env._("%(months)s x %(amount)s per maand", months=months,
                                         amount=self.currency_id.format(mandate.fee_amount))
            vals.append({
                "line_type": "fee",
                "mandate_id": mandate.id,
                "description": description,
                "fee_base": base,
                "fee_months": months,
                "amount": untaxed,
                "tax_amount": tax_amount,
            })
        return vals

    def _recompute_lines(self):
        for remittance in self:
            # The taxes and bills live in the office's company, whatever companies the user selected.
            remittance = remittance.with_company(remittance.company_id)
            if remittance.state != "draft":
                raise UserError(self.env._("Alleen een concept wordt herberekend."))
            contracts = remittance._contracts()
            done = remittance._done_lines()
            received = remittance._received_line_vals(contracts, done)
            costs = remittance._cost_line_vals(contracts, done)
            fees = remittance._fee_line_vals(received, done)
            notes = []
            without = contracts.filtered(lambda c: not c.mandate_id and c.id in [v["contract_id"] for v in received])
            if without:
                notes.append(self.env._("Geen beheermandaat, dus geen ereloon: %s", ", ".join(without.mapped("name"))))
            remittance.write({
                "line_ids": [Command.clear()] + [Command.create(v) for v in received + costs + fees],
                "note": "\n".join(notes) or False,
            })
            remittance._compute_partner_bank_id()

    def action_recompute(self):
        self._recompute_lines()
        return True

    # ------------------------------------------------------------------
    # Confirmation: fee invoice, payout document and offset. Nothing is sent or paid.
    # ------------------------------------------------------------------

    def action_confirm(self):
        for remittance in self:
            remittance = remittance.with_company(remittance.company_id)
            if remittance.state != "draft":
                raise UserError(self.env._("%s is al bevestigd.", remittance.name))
            remittance._recompute_lines()
            currency = remittance.currency_id
            if currency.compare_amounts(remittance.balance, 0) < 0:
                raise UserError(self.env._(
                    "Het saldo van %(name)s is negatief (%(balance)s): er valt niets door te storten. Kies "
                    "\"Overdragen\"; de volgende doorstorting neemt alles mee.",
                    name=remittance.name, balance=currency.format(remittance.balance)))
            if not remittance.line_ids:
                raise UserError(self.env._("%s is leeg: er is niets ontvangen of betaald.", remittance.name))
            office = remittance.company_id
            Move = self.env["account.move"].with_company(office)
            fee_invoice = payout = offset = Move
            if not currency.is_zero(remittance.fee_untaxed):
                fee_invoice = Move.create(remittance._fee_invoice_vals())
                fee_invoice.action_post()
            if not currency.is_zero(remittance.received - remittance.costs):
                payout = Move.create(remittance._payout_vals())
                payout.action_post()
            if fee_invoice and payout:
                offset = remittance._offset(fee_invoice, payout)
            remittance.write({
                "state": "confirmed", "fee_invoice_id": fee_invoice.id, "payout_move_id": payout.id,
                "offset_move_id": offset.id,
            })
            remittance.message_post(body=self.env._(
                "Bevestigd: %(balance)s door te storten. De ereloonfactuur is geboekt maar niet verstuurd; de "
                "doorstorting gebeurt pas via een goedgekeurde betaalbatch.", balance=currency.format(remittance.balance)))
        return True

    def _analytic(self, contract=None):
        contract = contract or self.line_ids.contract_id[:1] or self._contracts()[:1]
        return {str(contract.analytic_account_id.id): 100} if contract.analytic_account_id else False

    def _booking_date(self):
        # The demo history books its remittances on past dates.
        return self.env.context.get("rent_remittance_date") or fields.Date.context_today(self)

    def _period(self):
        return format_date(self.env, self.month, date_format="MMMM y")

    def _fee_invoice_vals(self):
        account = self.company_id._rent_fee_account()
        lines = []
        for line in self.line_ids.filtered(lambda l: l.line_type == "fee"):
            lines.append(Command.create({
                "name": self.env._("Ereloon rentmeester %(period)s: %(description)s", period=self._period(),
                                   description=line.description),
                "quantity": 1,
                "price_unit": line.amount,
                "account_id": account.id,
                "tax_ids": [Command.set(line.mandate_id._get_fee_tax().ids)],
                "analytic_distribution": self._analytic(line.mandate_id.contract_ids[:1]),
                "rent_line_type": "fee",
            }))
        return {
            "move_type": "out_invoice",
            "partner_id": self.landlord_id.id,
            "invoice_date": self._booking_date(),
            "rent_remittance_id": self.id,
            "ref": self.env._("Ereloon %s", self._period()),
            "narration": self.env._("Verrekend met de doorstorting van %s.", self._period()),
            "invoice_line_ids": lines,
        }

    def _payout_vals(self):
        """Self-billed document that moves the landlord's money off 489100: received minus costs."""
        account = self.company_id._rent_account()
        lines = []
        for line in self.line_ids.filtered(lambda l: l.line_type != "fee"):
            sign = -1 if line.line_type == "cost" else 1
            lines.append(Command.create({
                "name": f"{line.contract_id.name}: {line.description}" if line.contract_id else line.description,
                "quantity": 1,
                "price_unit": sign * line.amount,
                "account_id": account.id,
                "tax_ids": [Command.clear()],
                "analytic_distribution": self._analytic(line.contract_id),
                "rent_line_type": "remittance",
            }))
        today = self._booking_date()
        return {
            "move_type": "in_invoice",
            "partner_id": self.landlord_id.id,
            "partner_bank_id": self.partner_bank_id.id,
            "invoice_date": today,
            "invoice_date_due": today,
            "rent_remittance_id": self.id,
            "ref": self.env._("Doorstorting %s", self._period()),
            "payment_reference": self.env._("Doorstorting huur %s", self._period()),
            "invoice_line_ids": lines,
        }

    def _offset(self, fee_invoice, payout):
        """Offset the fee against the money owed to the landlord, and reconcile both documents."""
        # LEGAL-CHECK: art. 5.250 e.v. BW (schuldvergelijking) - het ereloon wordt verrekend met de huur die het
        # kantoor aan de verhuurder verschuldigd is; nakijken of het beheermandaat dat uitdrukkelijk moet toelaten.
        receivable = fee_invoice.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        payable = payout.line_ids.filtered(lambda l: l.account_id.account_type == "liability_payable")
        amount = min(fee_invoice.amount_residual, payout.amount_residual)
        journal = self.env["account.journal"].search([
            ("company_id", "=", self.company_id.id), ("type", "=", "general")], limit=1)
        offset = self.env["account.move"].with_company(self.company_id).create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": self._booking_date(),
            "ref": self.env._("Verrekening ereloon %(period)s - %(landlord)s", period=self._period(),
                              landlord=self.landlord_id.name),
            "rent_remittance_id": self.id,
            "line_ids": [
                Command.create({"name": self.env._("Ereloon verrekend"), "account_id": payable.account_id.id,
                                "partner_id": self.landlord_id.id, "debit": amount, "credit": 0.0}),
                Command.create({"name": self.env._("Ereloon verrekend"), "account_id": receivable.account_id.id,
                                "partner_id": self.landlord_id.id, "debit": 0.0, "credit": amount}),
            ],
        })
        offset.action_post()
        (payable | offset.line_ids.filtered(lambda l: l.account_id == payable.account_id)).reconcile()
        (receivable | offset.line_ids.filtered(lambda l: l.account_id == receivable.account_id)).reconcile()
        return offset

    def action_carry_over(self):
        """Nothing to transfer this month: the next remittance takes everything along."""
        for remittance in self:
            if remittance.state != "draft":
                raise UserError(self.env._("Alleen een concept wordt overgedragen."))
            remittance.write({"state": "cancel"})
            remittance.message_post(body=self.env._("Overgedragen naar de volgende doorstorting."))
        return True

    def action_reset_draft(self):
        for remittance in self:
            if remittance.state != "cancel":
                raise UserError(self.env._("Een bevestigde doorstorting gaat niet terug naar concept."))
            remittance.state = "draft"
            remittance._recompute_lines()
        return True

    def action_approve_payout(self):
        """First approval of the payout document, as for a vendor bill (vme_belgie, step 20)."""
        approved = False
        for remittance in self:
            payout = remittance.with_company(remittance.company_id).payout_move_id
            if payout.vme_approval_state == "to_approve":
                payout.action_vme_approve()
                approved = True
        if not approved:
            raise UserError(self.env._("Er is niets goed te keuren."))
        return True

    def action_create_payment_batch(self):
        """Draft SEPA batch with the approved payouts of this office. Nothing is sent."""
        offices = self.company_id
        if len(offices) != 1:
            raise UserError(self.env._("Kies doorstortingen van één kantoor."))
        if not self.filtered(lambda r: r.payment_status == "to_pay"):
            raise UserError(self.env._("Geen van deze doorstortingen is goedgekeurd en klaar voor betaling."))
        self = self.with_company(offices)
        batch = self.env["vme.payment.batch"].create({
            "batch_type": "transfer", "rent_company_id": offices.id,
            "due_until": max(self.payout_move_id.mapped("invoice_date_due")),
        })
        batch.with_context(rent_remittance_ids=self.ids).action_fill_proposal()
        return {
            "type": "ir.actions.act_window",
            "res_model": "vme.payment.batch",
            "res_id": batch.id,
            "view_mode": "form",
            "context": {"allowed_company_ids": (offices | self.env.user.company_id).ids},
        }

    def action_print(self):
        return self.env.ref("vme_rentmeester.action_report_rent_remittance").report_action(self)

    def _open_move(self, move):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "context": {"allowed_company_ids": [self.company_id.id]},
        }

    def action_open_fee_invoice(self):
        return self._open_move(self.fee_invoice_id)

    def action_open_payout(self):
        return self._open_move(self.payout_move_id)

    @api.model
    def _create_for_month(self, month, company=None, landlords=None):
        """Draft remittance per landlord with leases at the office; an existing draft is recomputed."""
        month = month.replace(day=1)
        company = company or self.env["vme.rent.contract"]._default_company()
        contracts = self.env["vme.rent.contract"].search([("company_id", "=", company.id), ("state", "!=", "draft")])
        landlords = landlords or contracts.landlord_id
        remittances = self.browse()
        for landlord in landlords:
            existing = self.search([("landlord_id", "=", landlord.id), ("company_id", "=", company.id),
                                    ("month", "=", month), ("state", "!=", "cancel")], limit=1)
            if existing:
                if existing.state == "draft":
                    existing._recompute_lines()
                remittances |= existing
                continue
            remittance = self.create({"landlord_id": landlord.id, "company_id": company.id, "month": month})
            if remittance.line_ids:
                remittances |= remittance
            else:
                remittance.unlink()
        return remittances


class VmeRentRemittanceLine(models.Model):
    _name = "vme.rent.remittance.line"
    _description = "Regel van een doorstorting"
    _order = "remittance_id, sequence, date, id"

    remittance_id = fields.Many2one("vme.rent.remittance", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="remittance_id.currency_id")
    line_type = fields.Selection(LINE_TYPES, string="Soort", required=True)
    sequence = fields.Integer(compute="_compute_sequence", store=True)
    contract_id = fields.Many2one("vme.rent.contract", string="Huurcontract")
    mandate_id = fields.Many2one("vme.rent.mandate", string="Beheermandaat")
    # The invoice of the tenant or the bill paid for the landlord, in the office's company.
    move_id = fields.Many2one("account.move", string="Stuk", index="btree_not_null")
    move_name = fields.Char(string="Nummer")
    date = fields.Date(string="Datum")
    description = fields.Char(string="Omschrijving")
    fee_base = fields.Monetary(string="Basis ereloon")
    fee_months = fields.Integer(string="Maanden", aggregator=None)
    amount = fields.Monetary(string="Bedrag", help="Ereloon: zonder btw.")
    tax_amount = fields.Monetary(string="Btw")

    @api.depends("line_type")
    def _compute_sequence(self):
        order = [code for code, _label in LINE_TYPES]
        for line in self:
            line.sequence = order.index(line.line_type) if line.line_type in order else 99
