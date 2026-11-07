from datetime import date, timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tools import formatLang

from .account_chart_template import VME_FUND_ACCOUNTS
from .vme_access import check_not_auditor

STATES = [("draft", "Te controleren"), ("prepared", "Afrekening voorbereid"), ("closed", "Afgesloten")]
# Written only by the buttons (as superuser), never directly: the state skips the checks otherwise, and the
# snapshot is the proof of what was carried forward.
PROTECTED_FIELDS = {
    "state", "closed_by_id", "closed_on", "lock_date_before", "working_result", "reserve_result", "working_capital",
    "reserve_capital", "owner_receivable", "supplier_payable", "bank_working", "bank_reserve",
}


class VmeFiscalClosing(models.Model):
    """Closing of one financial year of one VME: settle the balance per owner, show the
    carry-forward to the new year and lock the year. Every step is a click by an employee."""

    _name = "vme.fiscal.closing"
    _description = "Afsluiting boekjaar"
    _inherit = ["mail.thread"]
    _order = "year desc, association_id"

    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True, string="Company")
    currency_id = fields.Many2one(related="company_id.currency_id")
    year = fields.Integer(string="Boekjaar", required=True, default=lambda self: fields.Date.today().year - 1, tracking=True)
    state = fields.Selection(STATES, string="Status", default="draft", required=True, tracking=True, copy=False)
    date_end = fields.Date(string="Einde boekjaar", compute="_compute_date_end")
    settlement_move_ids = fields.One2many(
        "account.move", "vme_fiscal_closing_id", string="Afrekeningsdocumenten", readonly=True)
    settlement_html = fields.Html(string="Documenten", compute="_compute_settlement", sanitize=False)
    company_selected = fields.Boolean(compute="_compute_settlement")
    settlement_count = fields.Integer(compute="_compute_settlement")
    settlement_draft_count = fields.Integer(string="Nog in concept", compute="_compute_settlement")
    settlement_total = fields.Monetary(
        string="Totaal afrekening", compute="_compute_settlement",
        help="Bijbetalingen min teruggaven: het verschil tussen de kosten en de gevraagde werkkapitaalprovisies.")
    check_html = fields.Html(string="Controles", compute="_compute_check_html", sanitize=False)
    summary_html = fields.Html(string="Resultaat en overdracht", compute="_compute_summary_html", sanitize=False)
    can_prepare = fields.Boolean(compute="_compute_check_html")
    can_close = fields.Boolean(compute="_compute_check_html")
    closed_by_id = fields.Many2one("res.users", string="Afgesloten door", readonly=True, copy=False)
    closed_on = fields.Datetime(string="Afgesloten op", readonly=True, copy=False)
    # Snapshot of the carry-forward, stored when the year is locked.
    working_result = fields.Monetary(string="Resultaat werkkapitaal", readonly=True, copy=False)
    reserve_result = fields.Monetary(string="Resultaat reservekapitaal", readonly=True, copy=False)
    working_capital = fields.Monetary(string="Overgedragen werkkapitaal", readonly=True, copy=False)
    reserve_capital = fields.Monetary(string="Overgedragen reservekapitaal", readonly=True, copy=False)
    owner_receivable = fields.Monetary(string="Open vorderingen op eigenaars", readonly=True, copy=False)
    supplier_payable = fields.Monetary(string="Schulden aan leveranciers", readonly=True, copy=False)
    bank_working = fields.Monetary(string="Bank werkkapitaal", readonly=True, copy=False)
    bank_reserve = fields.Monetary(string="Bank reservekapitaal", readonly=True, copy=False)
    # Lock date of the company before this closing, restored when the year is reopened.
    lock_date_before = fields.Date(readonly=True, copy=False)

    _association_year_unique = models.Constraint(
        "UNIQUE (association_id, year)", "Er bestaat al een afsluiting voor deze VME en dit jaar.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(PROTECTED_FIELDS & set(vals) - {"state"} or vals.get("state", "draft") != "draft"
                                   for vals in vals_list):
            raise AccessError(self.env._("Een afsluiting begint altijd als concept."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and PROTECTED_FIELDS & set(vals):
            raise AccessError(self.env._("Status en overdracht van een afsluiting wijzigen alleen via de knoppen."))
        return super().write(vals)

    @api.depends("association_id.name", "year")
    def _compute_display_name(self):
        for closing in self:
            closing.display_name = f"{closing.association_id.name or ''} - {closing.year}"

    @api.depends("year")
    def _compute_date_end(self):
        for closing in self:
            closing.date_end = date(closing.year, 12, 31) if closing.year else False

    def _settlement_moves(self):
        """The settlement documents, whatever companies the user selected: the record rules of
        Odoo hide the moves of a company that is not selected, also in settlement_move_ids."""
        self.ensure_one()
        if not self._origin.id:
            return self.env["account.move"]
        return self.env["account.move"].sudo().search([("vme_fiscal_closing_id", "=", self._origin.id)])

    def _settlement_moves_as_user(self):
        """The same documents in the user's environment, in the company of the VME, to post or delete them."""
        return self.env["account.move"].with_company(self.company_id).browse(self._settlement_moves().ids)

    @api.depends("company_id", "settlement_move_ids.state", "settlement_move_ids.amount_total")
    @api.depends_context("allowed_company_ids")
    def _compute_settlement(self):
        for closing in self:
            all_moves = closing._settlement_moves()
            moves = all_moves.filtered(lambda m: m.state != "cancel")
            currency = closing.currency_id
            closing.settlement_count = len(moves)
            closing.settlement_draft_count = len(moves.filtered(lambda m: m.state == "draft"))
            total = sum(_signed(m) for m in moves)
            # A new form has no VME yet, and so no currency.
            closing.settlement_total = currency.round(total) if currency else total
            closing.company_selected = closing.company_id in self.env.companies
            states = dict(all_moves._fields["state"]._description_selection(self.env)) if all_moves else {}
            rows = Markup("").join(
                Markup("<tr><td>%s</td><td>%s</td><td>%s</td><td class='text-end'>%s</td><td>%s</td></tr>") % (
                    move.name if move.name and move.name != "/" else "", move.partner_id.name,
                    self.env._("Factuur") if move.move_type == "out_invoice" else self.env._("Creditnota"),
                    formatLang(self.env, move.amount_total, currency_obj=currency), states.get(move.state, ""))
                for move in all_moves.sorted(lambda m: m.partner_id.name or ""))
            alert = Markup("<div class='alert alert-info' role='status'>%s</div>") % self.env._(
                "Zet bovenaan rechts het bedrijf %s aan om de documenten te openen of apart te bevestigen.",
                closing.company_id.name) if all_moves and not closing.company_selected else Markup("")
            closing.settlement_html = alert + Markup(
                "<table class='table table-sm'><thead><tr><th>%s</th><th>%s</th><th>%s</th>"
                "<th class='text-end'>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>") % (
                self.env._("Nummer"), self.env._("Eigenaar"), self.env._("Soort"), self.env._("Bedrag"),
                self.env._("Status"), rows) if all_moves else False

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _get_checks(self):
        """The checks before preparing and closing, as a list of dicts.

        `blocking` says which step the check blocks ("prepare" blocks both, "close" only the lock,
        False is a warning); the employee decides on warnings. Read as sudo: the VME lives in its
        own company, whatever companies the user has selected. Also used by the year cycle.
        """
        self.ensure_one()
        vme = self.association_id._origin.sudo()
        year = self.year
        if not vme or not year:
            return []
        company = vme.company_id
        start, end = date(year, 1, 1), date(year, 12, 31)
        Move = self.env["account.move"].sudo()
        statement = vme._get_annual_statement(year)
        currency = statement["currency"]
        checks = []

        def add(code, ok, blocking, message, records=None):
            checks.append({"code": code, "ok": bool(ok), "blocking": blocking, "message": message,
                           "records": records if records is not None else self.env["account.move"]})

        def money(amount):
            return formatLang(self.env, amount, currency_obj=currency)

        if statement["is_complete"]:
            add("complete", True, "prepare", self.env._(
                "Afrekening compleet: alle geboekte kosten van %(year)s (%(total)s) zijn verdeeld.",
                year=year, total=money(statement["bills_total"])))
        else:
            add("complete", False, "prepare", self.env._(
                "Afrekening niet compleet: geboekte kosten %(bills)s, verdeeld %(allocated)s. Niet verdeeld: %(moves)s.",
                bills=money(statement["bills_total"]), allocated=money(statement["allocated_total"]),
                moves=", ".join(statement["undistributed_bills"].mapped("display_name")) or "-"),
                statement["undistributed_bills"])
        draft_bills = Move.search([
            ("company_id", "=", company.id), ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "draft"), ("invoice_date", ">=", start), ("invoice_date", "<=", end)])
        add("draft_bills", not draft_bills, "prepare", self.env._(
            "Leveranciersfacturen van %(year)s in concept: %(count)s.", year=year, count=len(draft_bills))
            if draft_bills else self.env._("Geen leveranciersfacturen van %s meer in concept.", year), draft_bills)
        draft_provisions = Move.search([
            ("company_id", "=", company.id), ("vme_provision_call_id.budget_id.year", "=", year), ("state", "=", "draft")])
        add("draft_provisions", not draft_provisions, "prepare", self.env._(
            "Provisiefacturen van %(year)s in concept: %(count)s.", year=year, count=len(draft_provisions))
            if draft_provisions else self.env._("Alle provisieoproepen van %s zijn geboekt.", year), draft_provisions)
        # Same domain as Odoo's own check when it sets a lock date, so we can say it in Dutch first.
        lines = self.env["account.bank.statement.line"].sudo().search(company._get_unreconciled_statement_lines_domain(end))
        add("bank", not lines, "close", self.env._(
            "Bankafschriften tot 31/12/%(year)s nog niet afgepunt: %(count)s lijnen.", year=year, count=len(lines))
            if lines else self.env._("Alle bankafschriften tot 31/12/%s zijn afgepunt.", year), lines.move_id)
        if self.state == "draft":
            add("settlement", False, "close", self.env._("De afrekening per eigenaar is nog niet voorbereid."))
        else:
            drafts = self._settlement_moves().filtered(lambda m: m.state == "draft")
            add("settlement", not drafts, "close", self.env._(
                "Afrekeningsdocumenten nog in concept: %s. Kijk ze na en bevestig ze.", len(drafts))
                if drafts else self.env._("Alle afrekeningsdocumenten zijn bevestigd."), drafts)
        today = fields.Date.context_today(self)
        add("year_over", today > end, False, self.env._("Het boekjaar %s is voorbij.", year) if today > end
            else self.env._("Het boekjaar %(year)s loopt nog tot 31/12/%(year)s. Afsluiten kan, maar een latere factuur "
                            "van %(year)s komt dan in de boekhouding en de afrekening van %(next)s.", year=year, next=year + 1))
        previous = self.search([("association_id", "=", vme.id), ("year", "=", year - 1)], limit=1)
        has_older = Move.search_count([("company_id", "=", company.id), ("state", "=", "posted"),
                                       ("date", "<", start)], limit=1)
        previous_ok = (previous and previous.state == "closed") or not has_older
        add("previous", previous_ok, False, self.env._("Het vorige boekjaar is afgesloten of heeft geen boekingen.")
            if previous_ok else self.env._("Het boekjaar %s is nog niet afgesloten.", year - 1))
        return checks

    def _blocking_failures(self, step):
        steps = ("prepare",) if step == "prepare" else ("prepare", "close")
        return [check for check in self._get_checks() if not check["ok"] and check["blocking"] in steps]

    def _record_links(self, records, limit=10):
        """Links to the records behind a failed check, so the employee can open and fix them."""
        if not records:
            return ""
        links = Markup(", ").join(
            Markup("<a href='/odoo/%s/%s' target='_blank'>%s</a>") % (record._name, record.id, record.display_name)
            for record in records[:limit])
        more = Markup(" …") if len(records) > limit else ""
        return Markup("<div class='ms-4 small'>%s%s</div>") % (links, more)

    @api.depends("association_id", "year", "state", "settlement_move_ids.state")
    def _compute_check_html(self):
        for closing in self:
            if not closing.association_id or not closing.year:
                closing.check_html = False
                closing.can_prepare = closing.can_close = False
                continue
            checks = closing._get_checks()
            rows = Markup("").join(
                Markup("<li class='%s'><i class='fa %s me-2'/>%s%s</li>") % (
                    "text-success" if check["ok"] else "text-danger" if check["blocking"] else "text-warning",
                    "fa-check" if check["ok"] else "fa-times" if check["blocking"] else "fa-exclamation-triangle",
                    check["message"], closing._record_links(check["records"]) if not check["ok"] else "")
                for check in checks)
            closing.check_html = Markup("<ul class='list-unstyled mb-0'>%s</ul>") % rows
            failed = {check["blocking"] for check in checks if not check["ok"]}
            closing.can_prepare = closing.state != "closed" and "prepare" not in failed
            closing.can_close = closing.state == "prepared" and not failed & {"prepare", "close"}

    # ------------------------------------------------------------------
    # Result and carry-forward
    # ------------------------------------------------------------------

    def _get_carry_forward(self):
        """Result of the year per fund and the balances that carry over to 1 January.

        No closing entry is booked: Odoo carries balance accounts over by itself, and the result of
        the year stays on the cost and income accounts (see docs/beslissingen.md). The opening
        balances of the new year are therefore the balances on 31 December.
        """
        self.ensure_one()
        # LEGAL-CHECK: KB 12 juli 2012, bijlage - the result of the year goes to the funds to carry
        # forward (489, entry 693). We show it here instead of booking it; see docs/beslissingen.md.
        vme = self.association_id._origin.sudo()
        end = date(self.year, 12, 31)
        company = vme.company_id
        currency = company.currency_id
        history = vme._get_capital_history(end)
        entry = next((e for e in history["years"] if e["year"] == self.year), None)
        empty = {"opening": 0.0, "in": 0.0, "out": 0.0, "closing": 0.0}
        working = entry["working"] if entry else dict(empty, opening=history["working"], closing=history["working"])
        reserve = entry["reserve"] if entry else dict(empty, opening=history["reserve"], closing=history["reserve"])
        MoveLine = self.env["account.move.line"].sudo()

        def balance(account_type):
            return currency.round(sum(MoveLine.search([
                ("company_id", "=", company.id), ("parent_state", "=", "posted"), ("date", "<=", end),
                ("account_id.account_type", "=", account_type)]).mapped("balance")))

        return {
            "currency": currency,
            "working": working,
            "reserve": reserve,
            "working_result": currency.round(working["in"] - working["out"]),
            "reserve_result": currency.round(reserve["in"] - reserve["out"]),
            "owner_receivable": balance("asset_receivable"),
            "supplier_payable": -balance("liability_payable"),
            "bank": history["bank"],
        }

    @api.depends("association_id", "year", "state", "settlement_move_ids.state", "settlement_move_ids.amount_total")
    def _compute_summary_html(self):
        for closing in self:
            if not closing.association_id or not closing.year:
                closing.summary_html = False
                continue
            data = closing._get_carry_forward()
            currency = data["currency"]

            def money(amount, currency=currency):
                return formatLang(self.env, amount, currency_obj=currency)

            def row(label, *amounts, bold=False):
                cells = Markup("").join(Markup("<td class='text-end'>%s</td>") % (money(a) if a is not None else "")
                                        for a in amounts)
                return Markup("<tr class='%s'><td>%s</td>%s</tr>") % ("fw-bold" if bold else "", label, cells)

            working, reserve = data["working"], data["reserve"]
            funds = Markup(
                "<table class='table table-sm'><thead><tr><th/><th class='text-end'>%s</th><th class='text-end'>%s</th>"
                "</tr></thead><tbody>%s</tbody></table>") % (
                self.env._("Werkkapitaal"), self.env._("Reservekapitaal"), Markup("").join([
                    row(self.env._("Stand op 1/1/%s", closing.year), working["opening"], reserve["opening"]),
                    row(self.env._("Gevraagd (provisies en afrekening)"), working["in"], reserve["in"]),
                    row(self.env._("Kosten, teruggaven en werken"), -working["out"], -reserve["out"]),
                    row(self.env._("Resultaat van %s", closing.year), data["working_result"], data["reserve_result"], bold=True),
                    row(self.env._("Over te dragen naar 1/1/%s", closing.year + 1), working["closing"], reserve["closing"], bold=True),
                ]))
            bank = data["bank"]
            balances = Markup("<table class='table table-sm'><tbody>%s</tbody></table>") % Markup("").join([
                row(self.env._("Open vorderingen op eigenaars"), data["owner_receivable"]),
                row(self.env._("Schulden aan leveranciers"), data["supplier_payable"]),
                row(self.env._("Bank werkkapitaal"), bank.get("working") or 0.0),
                row(self.env._("Bank reservekapitaal"), bank.get("reserve") or 0.0),
            ])
            note = Markup("<p class='text-muted small'>%s</p>") % self.env._(
                "Er komt geen afsluitboeking: de saldi op 31/12 zijn de openingssaldi van het nieuwe jaar. "
                "Het reservekapitaal wordt niet afgerekend en niet terugbetaald.")
            closing.summary_html = funds + balances + note

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _raise_failures(self, step):
        failures = self._blocking_failures(step)
        if failures:
            raise UserError(self.env._("Dit kan nog niet:\n%s", "\n".join("- " + f["message"] for f in failures)))

    def action_prepare(self):
        """Book the balance per owner as drafts: an invoice for an extra payment, a credit note for a refund.

        Amount = share in the costs - working capital provisions invoiced (not paid): an unpaid
        provision stays an open invoice of its own, so nothing is asked twice. Drafts from an earlier
        preparation are replaced; posted documents stay, and only a difference is added.
        """
        self.ensure_one()
        if self.state == "closed":
            raise UserError(self.env._("Het boekjaar %s is al afgesloten.", self.year))
        self._raise_failures("prepare")
        vme = self.association_id.sudo()
        company = vme.company_id
        end = date(self.year, 12, 31)
        Move = self.env["account.move"].with_company(company)
        journal = self.env["account.journal"].with_company(company).search(
            [("company_id", "=", company.id), ("type", "=", "sale")], limit=1)
        account = self.env["account.account"].with_company(company).search(
            [("company_ids", "in", company.id), ("code", "=", VME_FUND_ACCOUNTS["working"][0])], limit=1)
        if not journal or not account:
            raise UserError(self.env._("Het rekeningstelsel van %s is nog niet volledig geladen.", vme.name))
        self._settlement_moves_as_user().filtered(lambda m: m.state == "draft").unlink()
        booked = {}
        for move in self._settlement_moves().filtered(lambda m: m.state == "posted"):
            booked[move.partner_id] = booked.get(move.partner_id, 0.0) + _signed(move)

        statement = vme._get_annual_statement(self.year)
        currency = statement["currency"]
        due = max(fields.Date.context_today(self), end) + timedelta(days=30)
        values = []
        partners = [st["partner"] for st in statement["statements"]]
        partners += [partner for partner in booked if partner not in partners]
        by_partner = {st["partner"]: st for st in statement["statements"]}
        for partner in partners:
            st = by_partner.get(partner)
            # LEGAL-CHECK: art. 3.86 §3 BW - only the working capital is settled; the reserve
            # capital stays with the VME and is not refunded, also not to an owner who sold.
            amount = currency.round((st["cost_total"] - st["working"]["invoiced"] if st else 0.0) - booked.get(partner, 0.0))
            if currency.is_zero(amount):
                continue
            lots = ", ".join(st["ownerships"].lot_id.mapped("name")) if st else ""
            label = self.env._("Afrekening werkkapitaal %(year)s - %(vme)s", year=self.year, vme=vme.name)
            if lots:
                label = self.env._("%(label)s - kavel %(lots)s", label=label, lots=lots)
            values.append({
                "move_type": "out_invoice" if amount > 0 else "out_refund",
                "journal_id": journal.id,
                "partner_id": partner.id,
                "invoice_date": end,
                "date": end,
                "invoice_date_due": due,
                "vme_fund": "working",
                "vme_fiscal_closing_id": self.id,
                "invoice_line_ids": [Command.create({
                    "name": label, "quantity": 1, "price_unit": abs(amount),
                    "account_id": account.id, "tax_ids": [Command.clear()],
                })],
            })
        moves = Move.create(values)
        self.sudo().state = "prepared"
        self.message_post(body=self.env._(
            "Afrekening voorbereid: %(count)s concepten, samen %(total)s.",
            count=len(moves), total=formatLang(self.env, self.settlement_total, currency_obj=currency)))
        return True

    def action_post_settlements(self):
        """Post the drafts after the employee looked at them. Nothing is sent."""
        self.ensure_one()
        drafts = self._settlement_moves_as_user().filtered(lambda m: m.state == "draft")
        if not drafts:
            raise UserError(self.env._("Er zijn geen afrekeningsdocumenten in concept."))
        drafts.action_post()
        self.message_post(body=self.env._("%s afrekeningsdocumenten bevestigd (niet verstuurd).", len(drafts)))
        return True

    def _check_manager(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(self.env._("Alleen een beheerder van de boekhouding mag een boekjaar afsluiten of heropenen."))

    def action_close(self):
        """Lock the year with the fiscal lock date of Odoo (a soft lock that an administrator can lift)."""
        self.ensure_one()
        check_not_auditor(self.env)  # the lock date is written as superuser
        self._check_manager()
        if self.state != "prepared":
            raise UserError(self.env._("Bereid eerst de afrekening voor."))
        self._raise_failures("close")
        company = self.company_id.sudo()
        end = date(self.year, 12, 31)
        data = self._get_carry_forward()
        lock_before = company.fiscalyear_lock_date
        if not lock_before or lock_before < end:
            company.fiscalyear_lock_date = end
        self.sudo().write({
            "state": "closed",
            "lock_date_before": lock_before,
            "closed_by_id": self.env.user.id,
            "closed_on": fields.Datetime.now(),
            "working_result": data["working_result"],
            "reserve_result": data["reserve_result"],
            "working_capital": data["working"]["closing"],
            "reserve_capital": data["reserve"]["closing"],
            "owner_receivable": data["owner_receivable"],
            "supplier_payable": data["supplier_payable"],
            "bank_working": data["bank"].get("working") or 0.0,
            "bank_reserve": data["bank"].get("reserve") or 0.0,
        })
        self.message_post(body=self.env._("Boekjaar %(year)s afgesloten: vergrendeld tot en met %(date)s.",
                                          year=self.year, date=end.strftime("%d/%m/%Y")))
        return True

    def action_reopen(self):
        """Lift the lock back to the end of the previous year, so corrections in this year are possible."""
        self.ensure_one()
        check_not_auditor(self.env)  # the lock date is written as superuser
        self._check_manager()
        if self.state != "closed":
            raise UserError(self.env._("Dit boekjaar is niet afgesloten."))
        later = self.search([("association_id", "=", self.association_id.id), ("year", ">", self.year),
                             ("state", "=", "closed")], limit=1)
        if later:
            raise UserError(self.env._("Heropen eerst het boekjaar %s.", later.year))
        # Back to the lock date from before the closing, and only if nobody moved the lock since: a lock
        # set by the accountant or after a migration is never lifted here.
        company = self.company_id.sudo()
        if company.fiscalyear_lock_date == date(self.year, 12, 31):
            # A closing from before lock_date_before existed: back to the end of a closed previous year.
            previous = self.search([("association_id", "=", self.association_id.id), ("year", "=", self.year - 1),
                                    ("state", "=", "closed")], limit=1)
            company.fiscalyear_lock_date = self.lock_date_before or (date(self.year - 1, 12, 31) if previous else False)
            body = self.env._("Boekjaar %s heropend.", self.year)
        else:
            body = self.env._("Boekjaar %s heropend; de vergrendeling van de boekhouding is niet gewijzigd, want ze "
                              "werd intussen verlegd.", self.year)
        self.sudo().write({"state": "prepared", "closed_by_id": False, "closed_on": False, "lock_date_before": False})
        self.message_post(body=body)
        return True

    def action_open_settlements(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("account.action_move_out_invoice")
        action.update({
            "name": self.env._("Afrekening %s", self.display_name),
            "domain": [("vme_fiscal_closing_id", "=", self.id)],
            "context": {"default_move_type": "out_invoice", "create": False},
        })
        return action

    def action_open_annual_statement(self):
        self.ensure_one()
        action = self.association_id.action_open_annual_statement()
        action["context"] = dict(action["context"], default_year=self.year)
        return action


def _signed(move):
    """Amount of a settlement document: positive for an extra payment, negative for a refund."""
    return move.amount_total if move.move_type == "out_invoice" else -move.amount_total


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    fiscal_closing_ids = fields.One2many("vme.fiscal.closing", "association_id", string="Afsluitingen")

    def _get_fiscal_closing(self, year):
        """The closing of `year` for this VME, created when it does not exist yet. Used by the year cycle."""
        self.ensure_one()
        Closing = self.env["vme.fiscal.closing"]
        return Closing.search([("association_id", "=", self.id), ("year", "=", year)], limit=1) \
            or Closing.create({"association_id": self.id, "year": year})

    def action_open_fiscal_closing(self, year=None):
        """Open the closing of `year`; without a year the closing in progress, or a new one for the
        first year that is not closed yet."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": self.env._("Afsluiting boekjaar"),
            "res_model": "vme.fiscal.closing",
            "view_mode": "form",
            "target": "current",
        }
        if year:
            action["res_id"] = self._get_fiscal_closing(year).id
            return action
        closings = self.env["vme.fiscal.closing"].search([("association_id", "=", self.id)])
        in_progress = closings.filtered(lambda c: c.state != "closed").sorted("year")[:1]
        if in_progress:
            action["res_id"] = in_progress.id
            return action
        closed_years = closings.mapped("year")
        next_year = max(closed_years) + 1 if closed_years else fields.Date.context_today(self).year - 1
        action["context"] = {"default_association_id": self.id, "default_year": next_year}
        return action


class VmeCycleStep(models.Model):
    _inherit = "vme.cycle.step"

    def _prepare_closing(self, today):
        """Link the step "Boekjaar afsluiten" to the closing of the previous year (a draft dossier: it
        only checks and prepares nothing), so that "Open" goes to it. The step is done once the year is
        locked (`_cycle_fiscal_year_closed`), which `action_close` does."""
        self._link(self.association_id.sudo()._get_fiscal_closing(self.year - 1))
        return super()._prepare_closing(today)


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_fiscal_closing_id = fields.Many2one(
        "vme.fiscal.closing", string="Afsluiting boekjaar", index=True, ondelete="restrict", copy=False, readonly=True,
        check_company=True)
