"""Sale of a lot: the information the notary asks the syndic, and the transfer of ownership at the deed."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, format_date

from .account_chart_template import VME_FUND_ACCOUNTS

# LEGAL-CHECK: art. 3.94 §1 BW - the syndic answers the notary's first request within 15 days.
FIRST_ANSWER_DAYS = 15
# LEGAL-CHECK: art. 3.94 §2 BW - the syndic answers the second request (after the compromise) within 30 days.
SECOND_ANSWER_DAYS = 30
# Days before the deadline at which a file turns orange in the list.
WARNING_DAYS = 7
# LEGAL-CHECK: art. 3.94 §1 BW - the notary receives the minutes of the assemblies of the last three years.
ASSEMBLY_YEARS = 3


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    legal_proceedings = fields.Html(
        string="Lopende gerechtelijke procedures",
        help="Wordt overgenomen in de inlichtingen aan de notaris bij elke verkoop.",
    )
    sale_file_ids = fields.One2many("vme.sale.file", "association_id", string="Verkoopdossiers")


class VmeLot(models.Model):
    _inherit = "vme.lot"

    def action_start_sale(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Verkoopdossier"),
            "res_model": "vme.sale.file",
            "view_mode": "form",
            "context": {
                "default_association_id": self.association_id.id,
                "default_lot_ids": self.ids,
            },
        }


class VmeAssemblyItem(models.Model):
    _inherit = "vme.assembly.item"

    # Works decided by the assembly: the notary must know which are not executed yet.
    works_amount = fields.Monetary(
        string="Geraamde kostprijs werken", currency_field="currency_id",
        help="Raming van de werken die deze beslissing goedkeurt. Komt in de inlichtingen aan de notaris "
        "zolang de werken niet uitgevoerd zijn.",
    )
    works_key_id = fields.Many2one(
        "vme.key", string="Sleutel werken", domain="[('association_id', '=', association_id)]",
        help="Sleutel om het aandeel van een kavel in de werken te berekenen. Leeg: de algemene sleutel.",
    )
    works_done = fields.Boolean(string="Werken uitgevoerd")
    currency_id = fields.Many2one(related="company_id.currency_id")


class VmeSaleFile(models.Model):
    _name = "vme.sale.file"
    _description = "Verkoopdossier"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "answer_deadline, id desc"

    name = fields.Char(string="Dossier", compute="_compute_name", store=True)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    lot_ids = fields.Many2many(
        "vme.lot", string="Verkochte kavels", required=True,
        domain="[('association_id', '=', association_id)]",
    )
    seller_id = fields.Many2one(
        "res.partner", string="Verkoper", compute="_compute_seller", store=True, readonly=False, tracking=True,
        help="De eigenaar van de verkochte kavels op vandaag.",
    )
    buyer_id = fields.Many2one("res.partner", string="Koper", tracking=True)
    notary_id = fields.Many2one("res.partner", string="Notaris", tracking=True)
    notary_reference = fields.Char(string="Referentie notaris")
    user_id = fields.Many2one(
        "res.users", string="Verantwoordelijke", default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )
    state = fields.Selection(
        [("new", "Eerste vraag ontvangen"), ("first_answered", "Eerste vraag beantwoord"),
         ("second_received", "Tweede vraag ontvangen"), ("second_answered", "Tweede vraag beantwoord"),
         ("done", "Akte verleden"), ("cancelled", "Geannuleerd")],
        string="Status", required=True, default="new", tracking=True,
    )

    first_request_date = fields.Date(
        string="Eerste vraag ontvangen op", required=True, default=fields.Date.context_today, tracking=True)
    first_deadline = fields.Date(string="Antwoord eerste vraag uiterlijk", compute="_compute_deadlines", store=True)
    first_answer_date = fields.Date(string="Eerste vraag beantwoord op", readonly=True, copy=False)
    second_request_date = fields.Date(string="Tweede vraag ontvangen op", tracking=True, copy=False)
    second_deadline = fields.Date(string="Antwoord tweede vraag uiterlijk", compute="_compute_deadlines", store=True)
    second_answer_date = fields.Date(string="Tweede vraag beantwoord op", readonly=True, copy=False)
    deed_date = fields.Date(string="Datum akte", tracking=True, copy=False)

    answer_deadline = fields.Date(
        string="Antwoord uiterlijk", compute="_compute_answer_deadline", store=True,
        help="Uiterste datum van de vraag van de notaris die nog open staat.",
    )
    deadline_state = fields.Selection(
        [("none", "Geen open vraag"), ("ok", "Op tijd"), ("warning", "Binnenkort"), ("danger", "Te laat")],
        string="Termijn", compute="_compute_deadline_state",
    )
    deadline_text = fields.Char(string="Signaal termijn", compute="_compute_deadline_state")
    legal_proceedings = fields.Html(
        string="Lopende gerechtelijke procedures", compute="_compute_legal_proceedings", store=True, readonly=False,
    )
    information_html = fields.Html(string="Voorbeeld antwoord", compute="_compute_information_html", sanitize=False)
    key_register_ids = fields.Many2many(
        "vme.lot.key", string="Sleutels en badges", compute="_compute_key_register_ids",
        help="Uitgereikte sleutels en badges van de verkochte kavels die nog in gebruik zijn.",
    )

    @api.depends("lot_ids.name", "association_id.name")
    def _compute_name(self):
        for sale in self:
            lots = ", ".join(sale.lot_ids.sorted(lambda lot: (lot.sequence, lot.name)).mapped("name"))
            sale.name = self.env._("Verkoop %(lots)s %(vme)s", lots=lots, vme=sale.association_id.name or "")

    @api.depends("lot_ids")
    def _compute_seller(self):
        for sale in self:
            if not sale.seller_id:
                sale.seller_id = sale.lot_ids[:1]._origin.current_owner_id

    @api.depends("first_request_date", "second_request_date")
    def _compute_deadlines(self):
        for sale in self:
            sale.first_deadline = sale.first_request_date and sale.first_request_date + timedelta(days=FIRST_ANSWER_DAYS)
            sale.second_deadline = sale.second_request_date and sale.second_request_date + timedelta(days=SECOND_ANSWER_DAYS)

    @api.depends("state", "first_deadline", "second_deadline")
    def _compute_answer_deadline(self):
        for sale in self:
            sale.answer_deadline = {
                "new": sale.first_deadline, "second_received": sale.second_deadline,
            }.get(sale.state, False)

    @api.depends("answer_deadline")
    def _compute_deadline_state(self):
        today = fields.Date.context_today(self)
        for sale in self:
            deadline = sale.answer_deadline
            sale.deadline_text = False
            if not deadline:
                sale.deadline_state = "none"
            elif deadline < today:
                sale.deadline_state = "danger"
                sale.deadline_text = self.env._(
                    "De wettelijke termijn om de notaris te antwoorden is verstreken op %s.", format_date(self.env, deadline))
            elif deadline <= today + timedelta(days=WARNING_DAYS):
                sale.deadline_state = "warning"
                sale.deadline_text = self.env._(
                    "Antwoord de notaris uiterlijk op %(date)s (nog %(days)s dagen).",
                    date=format_date(self.env, deadline), days=(deadline - today).days)
            else:
                sale.deadline_state = "ok"

    @api.depends("lot_ids.key_register_ids.state")
    def _compute_key_register_ids(self):
        for sale in self:
            sale.key_register_ids = sale.lot_ids.key_register_ids.filtered(lambda k: k.state == "active")

    @api.depends("association_id")
    def _compute_legal_proceedings(self):
        for sale in self:
            sale.legal_proceedings = sale.association_id.legal_proceedings

    @api.depends("lot_ids", "seller_id", "legal_proceedings", "state")
    def _compute_information_html(self):
        for sale in self:
            if not sale.association_id or not sale._origin.id or not sale.lot_ids:
                sale.information_html = False
                continue
            sale.information_html = self.env["ir.qweb"]._render(
                "vme_belgie.notary_information_body",
                {"info": sale._origin._get_notary_information(), "format_date": lambda d, lang=False: format_date(self.env, d, lang_code=lang)},
            )

    @api.constrains("lot_ids", "association_id")
    def _check_lots(self):
        for sale in self:
            if sale.lot_ids.association_id - sale.association_id:
                raise UserError(self.env._("Alle verkochte kavels moeten tot de VME van het dossier behoren."))

    @api.model_create_multi
    def create(self, vals_list):
        sales = super().create(vals_list)
        for sale in sales:
            sale._schedule_answer_activity("first")
            if sale.second_request_date:
                sale.state = "second_received"
                sale._schedule_answer_activity("second")
        return sales

    def write(self, vals):
        new_second = self.filtered(lambda s: not s.second_request_date) if vals.get("second_request_date") else self.browse()
        result = super().write(vals)
        for sale in new_second:
            if sale.state in ("new", "first_answered"):
                sale.state = "second_received"
            sale._schedule_answer_activity("second")
        return result

    # Tasks with the legal deadline

    def _activity_summary(self, which):
        return self.env._("Inlichtingen notaris: eerste vraag beantwoorden") if which == "first" \
            else self.env._("Inlichtingen notaris: tweede vraag beantwoorden")

    def _schedule_answer_activity(self, which):
        self.ensure_one()
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=self.first_deadline if which == "first" else self.second_deadline,
            summary=self._activity_summary(which),
            note=self.env._("Wettelijke termijn: %(days)s dagen na de vraag van %(notary)s.",
                            days=FIRST_ANSWER_DAYS if which == "first" else SECOND_ANSWER_DAYS,
                            notary=self.notary_id.name or self.env._("de notaris")),
            user_id=(self.user_id or self.env.user).id,
        )

    # The answer

    def _get_notary_information(self, on_date=None):
        """Everything the syndic tells the notary about the sold lots, read as sudo.

        Amounts are on ``on_date`` (default today). The share of the sold lots in the reserve
        capital and in decided works follows the general key, or the key of the works.
        """
        self.ensure_one()
        sale = self.sudo()
        vme = sale.association_id
        company = vme.company_id
        currency = company.currency_id
        on_date = on_date or fields.Date.context_today(self)
        lots = sale.lot_ids.sorted(lambda lot: (lot.sequence, lot.name))

        keys = []
        for key in vme.key_ids.sorted("sequence"):
            shares = sum(key.line_ids.filtered(lambda line: line.lot_id in lots).mapped("shares"))
            if shares:
                keys.append({"key": key, "shares": shares, "total": key.total_shares})
        general = vme.key_ids.filtered(lambda k: k.key_type == "general")[:1]

        def lot_share(key, amount):
            key = key or general
            if not key or not key.total_shares:
                return 0.0
            shares = sum(key.line_ids.filtered(lambda line: line.lot_id in lots).mapped("shares"))
            return currency.round(amount * shares / key.total_shares)

        # LEGAL-CHECK: art. 3.94 §1, 1° BW - the reserve capital stays with the VME; the notary
        # reports the share of the lot, not a refund to the seller (art. 3.86 §4 BW).
        # The account code depends on the company, so search within the VME's company.
        reserve_account = self.env["account.account"].sudo().with_company(company).search([
            ("company_ids", "in", company.id), ("code", "=", VME_FUND_ACCOUNTS["reserve"][0])], limit=1)
        reserve_lines = self.env["account.move.line"].sudo().search([
            ("account_id", "=", reserve_account.id), ("company_id", "=", company.id),
            ("parent_state", "=", "posted"), ("date", "<=", on_date),
        ]) if reserve_account else self.env["account.move.line"]
        reserve_balance = currency.round(-sum(reserve_lines.mapped("balance")))

        statement = vme._get_annual_statement(on_date.year, partners=sale.seller_id)["statements"] \
            if sale.seller_id else []
        statement = statement[0] if statement else None

        # LEGAL-CHECK: art. 3.94 §1, 3° BW - unpaid contributions of the seller.
        arrears = self.env["account.move"].sudo().search([
            ("company_id", "=", company.id), ("partner_id", "=", sale.seller_id.id),
            ("vme_provision_call_id", "!=", False), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"),
        ], order="invoice_date_due, name").filtered(
            lambda m: not float_is_zero(m.amount_residual, precision_rounding=currency.rounding))

        # LEGAL-CHECK: art. 3.94 §1, 2° en §2 BW - works decided by the assembly before the sale.
        works = self.env["vme.assembly.item"].sudo().search([
            ("association_id", "=", vme.id), ("outcome", "=", "adopted"),
            ("works_amount", ">", 0), ("works_done", "=", False),
        ], order="year, sequence")

        assemblies = self.env["vme.assembly"].sudo().search([
            ("association_id", "=", vme.id), ("state", "=", "held"),
            ("date", ">=", on_date.replace(year=on_date.year - ASSEMBLY_YEARS)), ("date", "<=", on_date),
        ], order="date desc")

        # LEGAL-CHECK: art. 3.94 §1 BW en Vlaamse verkoopplicht (Materialendecreet, Energiebesluit) -
        # the notary needs the asbestos certificate and EPC of the common parts and the
        # post-intervention file; a missing certificate is stated explicitly.
        lang = sale.notary_id.lang or company.partner_id.lang
        certificates = vme.with_context(lang=lang)._get_certificate_status(on_date)

        return {
            "sale": sale,
            "vme": vme,
            "certificates": certificates,
            "insurance": vme._building_policies(),
            "currency": currency,
            "date": on_date,
            "lots": lots,
            "keys": keys,
            "general_key": general,
            "reserve_balance": reserve_balance,
            "reserve_share": lot_share(general, reserve_balance),
            "statement": statement,
            "arrears": [{"move": m, "due": m.invoice_date_due, "amount": m.amount_residual,
                         "fund": m.vme_fund} for m in arrears],
            "arrears_total": currency.round(sum(arrears.mapped("amount_residual"))),
            "works": [{"item": item, "amount": item.works_amount,
                       "share": lot_share(item.works_key_id, item.works_amount)} for item in works],
            "legal_proceedings": sale.legal_proceedings,
            "assemblies": assemblies,
            "keys_issued": lots.sudo().key_register_ids.filtered(lambda k: k.state == "active").sorted(
                lambda k: (k.lot_id.sequence, k.lot_id.name, k.kind, k.number)),
        }

    def _render_answer(self, which):
        self.ensure_one()
        pdf, _ = self.env["ir.actions.report"]._render_qweb_pdf(
            "vme_belgie.action_report_notary_information", self.ids, data={"answer": which})
        return pdf

    def _answer(self, which):
        """Make the PDF, put it in the chatter and close the task. Nothing is sent: the staff
        member forwards the PDF to the notary from the chatter."""
        today = fields.Date.context_today(self)
        for sale in self:
            pdf = sale._render_answer(which)
            title = self.env._("Inlichtingen notaris %(which)s vraag %(name)s",
                               which=self.env._("eerste") if which == "first" else self.env._("tweede"),
                               name=sale.name)
            sale.message_post(
                body=self.env._("Antwoord aan de notaris klaar. Kijk het na en stuur het door aan %s.",
                                sale.notary_id.name or self.env._("de notaris")),
                attachments=[(f"{title}.pdf", pdf)],
            )
            sale.activity_ids.filtered(lambda a: a.summary == sale._activity_summary(which)).action_feedback(
                feedback=self.env._("Antwoord opgemaakt."))
            if which == "first":
                sale.write({"first_answer_date": today,
                            "state": "first_answered" if sale.state == "new" else sale.state})
            else:
                sale.write({"second_answer_date": today, "state": "second_answered"})
        return True

    def action_answer_first(self):
        return self._answer("first")

    def action_answer_second(self):
        if self.filtered(lambda s: not s.second_request_date):
            raise UserError(self.env._("Vul eerst de datum van de tweede vraag in."))
        return self._answer("second")

    def action_print(self):
        return self.env.ref("vme_belgie.action_report_notary_information").report_action(self)

    def action_cancel(self):
        self.activity_ids.action_feedback(feedback=self.env._("Verkoop geannuleerd."))
        self.state = "cancelled"

    # The deed

    def action_deed_done(self):
        """Transfer the ownership of the sold lots to the buyer on the deed date."""
        for sale in self:
            if not sale.deed_date or not sale.buyer_id:
                raise UserError(self.env._("Vul de datum van de akte en de koper in."))
            Ownership = self.env["vme.ownership"]
            for lot in sale.lot_ids:
                current = lot.ownership_ids.filtered(
                    lambda o: o.date_start < sale.deed_date and (not o.date_end or o.date_end >= sale.deed_date))
                if current.partner_id != sale.seller_id:
                    raise UserError(self.env._(
                        "%(lot)s is op %(date)s niet van de verkoper %(seller)s.",
                        lot=lot.display_name, date=format_date(self.env, sale.deed_date), seller=sale.seller_id.name))
                current.date_end = sale.deed_date - timedelta(days=1)
                Ownership.create({"lot_id": lot.id, "partner_id": sale.buyer_id.id, "date_start": sale.deed_date})
            # Keys and badges of the seller go to the buyer; those of a tenant stay with the tenant.
            keys = sale.key_register_ids.filtered(lambda k: k.partner_id == sale.seller_id)
            keys._transfer_to(sale.buyer_id, self.env._(
                "Overgedragen aan %(buyer)s bij de akte van %(date)s.",
                buyer=sale.buyer_id.name, date=format_date(self.env, sale.deed_date)))
            sale.activity_ids.action_feedback(feedback=self.env._("Akte verleden."))
            sale.state = "done"
            message = self.env._(
                "Akte verleden op %(date)s: %(lots)s gaat van %(seller)s naar %(buyer)s.",
                date=format_date(self.env, sale.deed_date), lots=", ".join(sale.lot_ids.mapped("name")),
                seller=sale.seller_id.name, buyer=sale.buyer_id.name)
            if keys:
                message += " " + self.env._("Over te dragen sleutels en badges: %s.",
                                            ", ".join(keys.mapped("display_name")))
            sale.message_post(body=message)
            sale.association_id.message_post(body=message)
        return True
