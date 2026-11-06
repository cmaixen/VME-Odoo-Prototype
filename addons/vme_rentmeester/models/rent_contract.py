import calendar

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import format_date

from . import rent_rules

ANALYTIC_PLAN_XMLID = "vme_rentmeester.analytic_plan_landlords"
INDEXATION_LEAD_DAYS = 45
NOTICE_LEAD_DAYS = 30


class VmeRentContract(models.Model):
    _name = "vme.rent.contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Huurcontract"
    _order = "date_start desc, id desc"

    name = fields.Char(string="Contract", required=True, copy=False, default=lambda self: self.env._("Nieuw"))
    company_id = fields.Many2one(
        "res.company", string="Rentmeesterkantoor", required=True, default=lambda self: self._default_company(),
        help="De huurfacturen en afrekeningen komen in de boekhouding van deze company.",
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    state = fields.Selection(
        [("draft", "Concept"), ("active", "Lopend"), ("notice", "Opgezegd"), ("ended", "Beëindigd")],
        string="Status", default="draft", required=True, tracking=True,
    )

    # The rented property: lots of a VME, or an address for a house outside a VME.
    lot_ids = fields.Many2many("vme.lot", string="Kavels", help="Appartement en eventueel garage of berging.")
    association_id = fields.Many2one("vme.association", string="VME", compute="_compute_association", store=True)
    property_address = fields.Char(string="Adres van het pand", compute="_compute_property_address", store=True,
                                   readonly=False)
    region = fields.Selection(rent_rules.REGIONS, string="Gewest", compute="_compute_region", store=True,
                              readonly=False,
                              help="De huurwetgeving verschilt per gewest; afgeleid uit de postcode van de VME.")

    landlord_id = fields.Many2one("res.partner", string="Verhuurder", required=True, tracking=True, index=True)
    tenant_ids = fields.Many2many("res.partner", "vme_rent_contract_tenant_rel", "contract_id", "partner_id",
                                  string="Huurders", required=True)
    tenant_id = fields.Many2one("res.partner", string="Huurder", compute="_compute_tenant_id", store=True,
                                help="De eerste huurder ontvangt de facturen.")
    analytic_account_id = fields.Many2one("account.analytic.account", string="Analytische rekening verhuurder",
                                          readonly=True, copy=False)

    date_signed = fields.Date(string="Ondertekend op", required=True,
                              help="De aanvangsindex is de gezondheidsindex van de maand vóór deze datum.")
    date_start = fields.Date(string="Ingangsdatum", required=True, tracking=True)
    duration_years = fields.Integer(string="Duur (jaren)", required=True, default=9)
    date_end = fields.Date(string="Einddatum", compute="_compute_date_end", store=True)
    lease_type = fields.Selection(
        [("short", "Kortlopend (hoogstens 3 jaar)"), ("nine", "Negen jaar"), ("long", "Lange duur (meer dan 9 jaar)"),
         ("other", "Andere duur")],
        string="Soort contract", compute="_compute_date_end", store=True,
    )
    is_written = fields.Boolean(string="Schriftelijk contract", default=True)
    indexation_excluded = fields.Boolean(string="Indexering uitgesloten in het contract")
    epc_label = fields.Selection(rent_rules.EPC_LABELS, string="EPC-label", default="none", required=True,
                                 help="Het label tijdens de indexstop van 2022-2023 bepaalt de correctiefactor.")

    rent = fields.Monetary(string="Basishuur per maand", required=True, tracking=True,
                           help="De huur in het contract, zonder lasten. De indexering vertrekt altijd hiervan.")
    current_rent = fields.Monetary(string="Huidige huur", compute="_compute_current_rent")
    charges_type = fields.Selection([("provision", "Provisie, jaarlijks afgerekend"), ("forfait", "Forfait")],
                                    string="Lasten", default="provision", required=True)
    charges_amount = fields.Monetary(string="Lasten per maand")
    deposit_amount = fields.Monetary(string="Huurwaarborg")
    deposit_type = fields.Selection(
        [("blocked_account", "Geblokkeerde rekening"), ("bank_guarantee", "Bankwaarborg"),
         ("public_guarantee", "Waarborg via OCMW of fonds")],
        string="Soort waarborg", default="blocked_account",
    )
    deposit_reference = fields.Char(string="Rekening of referentie waarborg")
    deposit_warning = fields.Char(compute="_compute_deposit_warning")

    notice_date = fields.Date(string="Opzeg gegeven op", tracking=True, copy=False)
    notice_party = fields.Selection([("landlord", "Verhuurder"), ("tenant", "Huurder")], string="Opzeg door",
                                    copy=False)
    notice_months = fields.Integer(string="Opzegtermijn (maanden)", default=3, copy=False)
    notice_end_date = fields.Date(string="Einde na opzeg", compute="_compute_notice_end_date", store=True)
    notice_deadline = fields.Date(
        string="Uiterste opzegdatum", compute="_compute_notice_deadline", store=True,
        help="Uiterlijk op deze dag opzeggen, anders loopt het contract verder (een kortlopend contract wordt dan "
             "een contract van negen jaar).",
    )
    activity_notice_deadline = fields.Date(copy=False)
    date_moved_out = fields.Date(string="Einde huur", tracking=True, copy=False)

    charge_line_ids = fields.One2many("vme.rent.contract.charge", "contract_id", string="Lasten per rubriek",
                                      copy=True)
    indexation_ids = fields.One2many("vme.rent.indexation", "contract_id", string="Indexeringen")
    invoice_ids = fields.One2many("account.move", "rent_contract_id", string="Huurfacturen")
    settlement_ids = fields.One2many("vme.rent.settlement", "contract_id", string="Afrekeningen")
    invoice_count = fields.Integer(compute="_compute_counts")
    indexation_count = fields.Integer(compute="_compute_counts")
    settlement_count = fields.Integer(compute="_compute_counts")
    next_anniversary = fields.Date(string="Volgende verjaardag", compute="_compute_next_anniversary")
    notes = fields.Html(string="Notities")

    _positive_rent = models.Constraint("CHECK (rent >= 0)", "De huur kan niet negatief zijn.")

    @api.model
    def _default_company(self):
        return self.env["res.company"].search([("is_rent_management", "=", True)], limit=1) or self.env.company

    @api.depends("lot_ids.association_id")
    def _compute_association(self):
        for contract in self:
            contract.association_id = contract.lot_ids.association_id[:1]

    @api.depends("association_id")
    def _compute_property_address(self):
        for contract in self:
            vme = contract.association_id
            if vme and not contract.property_address:
                contract.property_address = f"{vme.street or ''}, {vme.zip or ''} {vme.city or ''}".strip(", ")

    @api.depends("association_id.zip")
    def _compute_region(self):
        for contract in self:
            region = rent_rules.region_from_zip(contract.association_id.zip)
            contract.region = region or contract.region or "flanders"

    @api.depends("tenant_ids")
    def _compute_tenant_id(self):
        for contract in self:
            contract.tenant_id = contract.tenant_ids[:1]

    @api.depends("date_start", "duration_years")
    def _compute_date_end(self):
        for contract in self:
            years = contract.duration_years
            contract.date_end = contract.date_start and years and (
                contract.date_start + relativedelta(years=years) - relativedelta(days=1))
            contract.lease_type = ("short" if 0 < years <= 3 else "nine" if years == 9
                                   else "long" if years > 9 else "other")

    @api.depends("notice_date", "notice_months")
    def _compute_notice_end_date(self):
        for contract in self:
            contract.notice_end_date = contract.notice_date and rent_rules.notice_end_date(
                contract.notice_date, contract.notice_months)

    @api.depends("date_end", "lease_type")
    def _compute_notice_deadline(self):
        for contract in self:
            contract.notice_deadline = contract.date_end and rent_rules.notice_deadline(
                contract.date_end, contract.lease_type)

    @api.depends("rent", "indexation_ids.state", "indexation_ids.effective_date", "indexation_ids.new_rent")
    def _compute_current_rent(self):
        today = fields.Date.context_today(self)
        for contract in self:
            contract.current_rent = contract._get_rent_on(today)

    @api.depends("deposit_amount", "deposit_type", "rent", "region")
    def _compute_deposit_warning(self):
        for contract in self:
            limit = rent_rules.DEPOSIT_MAX_MONTHS.get(contract.region, {}).get(contract.deposit_type)
            warning = False
            if limit and contract.rent and contract.deposit_amount > limit * contract.rent + 0.005:
                warning = self.env._(
                    "De waarborg is hoger dan %(months)s maanden huur, het maximum voor deze soort waarborg in %(region)s.",
                    months=limit, region=dict(rent_rules.REGIONS)[contract.region])
            contract.deposit_warning = warning

    def _compute_counts(self):
        for contract in self:
            # The invoices live in the office's company: count them whatever companies are selected.
            contract.invoice_count = len(contract.sudo().invoice_ids)
            contract.indexation_count = len(contract.indexation_ids)
            contract.settlement_count = len(contract.settlement_ids)

    @api.depends("date_start")
    def _compute_next_anniversary(self):
        today = fields.Date.context_today(self)
        for contract in self:
            contract.next_anniversary = contract.date_start and contract._anniversary_after(today)

    @api.constrains("lot_ids")
    def _check_one_vme(self):
        for contract in self:
            if len(contract.lot_ids.association_id) > 1:
                raise ValidationError(self.env._("Alle kavels van een huurcontract liggen in dezelfde VME."))

    @api.constrains("duration_years")
    def _check_duration(self):
        for contract in self:
            if contract.duration_years <= 0:
                raise ValidationError(self.env._("De duur van een huurcontract is minstens één jaar."))

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        for contract in contracts:
            if contract.name == self.env._("Nieuw"):
                contract.name = contract._default_name()
            if not contract.charge_line_ids:
                contract.charge_line_ids = [Command.create({
                    "category_id": category.id, "tenant_percent": category.default_tenant_percent,
                }) for category in self.env["vme.rent.charge.category"].search([])]
            contract.analytic_account_id = contract._landlord_analytic_account()
        return contracts

    def write(self, vals):
        result = super().write(vals)
        if "landlord_id" in vals:
            for contract in self:
                contract.analytic_account_id = contract._landlord_analytic_account()
        return result

    def _default_name(self):
        place = ", ".join(self.lot_ids.mapped("name")) or self.property_address or ""
        if self.association_id:
            place = f"{self.association_id.name} {place}"
        return self.env._("Huur %(place)s - %(tenant)s", place=place, tenant=self.tenant_id.name or "")

    def _landlord_analytic_account(self):
        """Analytic account of the landlord: the dimension that splits the office's books per landlord."""
        self.ensure_one()
        plan = self.env.ref(ANALYTIC_PLAN_XMLID)
        Analytic = self.env["account.analytic.account"].sudo()
        account = Analytic.search([("plan_id", "=", plan.id), ("partner_id", "=", self.landlord_id.id)], limit=1)
        return account or Analytic.create({
            "name": self.landlord_id.name, "plan_id": plan.id, "partner_id": self.landlord_id.id,
        })

    # Rent and anniversaries

    def _get_rent_on(self, day):
        """Monthly rent in force on a day: the base rent or the last confirmed indexation."""
        self.ensure_one()
        indexations = self.indexation_ids.filtered(
            lambda i: i.state == "confirmed" and i.effective_date and i.effective_date <= day)
        last = indexations.sorted(lambda i: (i.effective_date, i.anniversary_date))[-1:]
        return last.new_rent if last else self.rent

    def _anniversary_after(self, day):
        """First anniversary of the start date on or after day."""
        self.ensure_one()
        candidate = rent_rules.anniversary(self.date_start, day.year)
        if candidate < day:
            candidate = rent_rules.anniversary(self.date_start, day.year + 1)
        return max(candidate, rent_rules.anniversary(self.date_start, self.date_start.year + 1))

    def _check_can_index(self):
        self.ensure_one()
        # LEGAL-CHECK: art. 1728bis oud BW, art. 34 VWHD, art. 224 BHC, art. 26 Waals decreet 15-03-2018 - alleen
        # een schriftelijk contract dat indexering niet uitsluit, kan geïndexeerd worden.
        if not self.is_written:
            raise UserError(self.env._("Een mondeling huurcontract kan niet geïndexeerd worden."))
        if self.indexation_excluded:
            raise UserError(self.env._("Het contract sluit indexering uit."))

    def _create_indexation(self, anniversary_date, request_date=None):
        self.ensure_one()
        self._check_can_index()
        existing = self.indexation_ids.filtered(
            lambda i: i.anniversary_date == anniversary_date and i.state != "cancelled")
        if existing:
            return existing[:1]
        request_date = request_date or fields.Date.context_today(self)
        Indexation = self.env["vme.rent.indexation"]
        return Indexation.create({
            "contract_id": self.id,
            "anniversary_date": anniversary_date,
            "request_date": request_date,
            **Indexation._prepare_amounts(self, anniversary_date, request_date),
        })

    def action_create_indexation(self):
        """Indexation for the next anniversary, or the last one if it has none yet."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        last = rent_rules.anniversary(self.date_start, today.year)
        if last > today or last <= self.date_start:
            last = self._anniversary_after(today)
        indexation = self._create_indexation(last)
        return indexation._get_form_action()

    # Invoices

    def _rent_invoice_vals(self, month):
        """Values of the rent invoice of a month, pro rata when the lease starts or ends in it."""
        self.ensure_one()
        first = month.replace(day=1)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        end = min(d for d in (self.date_end, self.notice_end_date, self.date_moved_out, last) if d)
        start = max(first, self.date_start)
        if start > end:
            return False
        days, month_days = (end - start).days + 1, (last - first).days + 1
        ratio = days / month_days
        rent = self._get_rent_on(start)
        currency = self.currency_id
        # The invoice goes to the tenant: line texts in the tenant's language.
        tenant_env = self.with_context(lang=self.tenant_id.lang).env
        period = format_date(tenant_env, first, date_format="MMMM y")
        suffix = "" if days == month_days else tenant_env._(" (%(days)s van %(total)s dagen)", days=days, total=month_days)
        account = self.company_id._rent_account()
        analytic = {str(self.analytic_account_id.id): 100} if self.analytic_account_id else False
        lines = [Command.create({
            "name": tenant_env._("Huur %(period)s", period=period) + suffix,
            "quantity": 1,
            "price_unit": currency.round(rent * ratio),
            "account_id": account.id,
            "tax_ids": [Command.clear()],
            "analytic_distribution": analytic,
            "rent_line_type": "rent",
        })]
        if self.charges_amount:
            label = (self.env._("Provisie lasten %(period)s", period=period) if self.charges_type == "provision"
                     else self.env._("Forfaitaire lasten %(period)s", period=period))
            lines.append(Command.create({
                "name": label + suffix,
                "quantity": 1,
                "price_unit": currency.round(self.charges_amount * ratio),
                "account_id": account.id,
                "tax_ids": [Command.clear()],
                "analytic_distribution": analytic,
                "rent_line_type": "charges",
            }))
        return {
            "move_type": "out_invoice",
            "partner_id": self.tenant_id.id,
            "invoice_date": first,
            # Rent is paid in advance: due on the first day of the month.
            "invoice_date_due": first,
            "rent_contract_id": self.id,
            "rent_period": first,
            "ref": self.env._("Huur %(period)s", period=period),
            "narration": self.env._("Geïnd in naam en voor rekening van %(landlord)s (verhuurder).",
                                    landlord=self.landlord_id.name),
            "invoice_line_ids": lines,
        }

    def _create_rent_invoices(self, month, post=False):
        """Draft (or posted) rent invoices of a month, at most one per contract and month."""
        first = month.replace(day=1)
        moves = self.env["account.move"]
        for contract in self:
            if contract.state not in ("active", "notice"):
                continue
            # sudo: an invoice of the office's company must block a second one even when that
            # company is not selected in the company switcher.
            if contract.sudo().invoice_ids.filtered(lambda m: m.rent_period == first and m.state != "cancel"):
                continue
            vals = contract._rent_invoice_vals(first)
            if not vals:
                continue
            moves |= self.env["account.move"].with_company(contract.company_id).create(vals)
        if post:
            for company in moves.company_id:
                moves.filtered(lambda m, c=company: m.company_id == c).with_company(company).action_post()
        return moves

    @api.model
    def _cron_rent_invoices(self):
        """Draft invoices of the current month for every running lease. Nothing is sent."""
        today = fields.Date.context_today(self)
        self.search([("state", "in", ("active", "notice"))])._create_rent_invoices(today)

    # Notice and end

    def action_activate(self):
        for contract in self:
            if not contract.tenant_ids or not contract.rent:
                raise UserError(self.env._("Vul huurders en huur in voor je het contract activeert."))
            contract.state = "active"

    def action_register_notice(self):
        for contract in self:
            if not contract.notice_date or not contract.notice_party:
                raise UserError(self.env._("Vul de datum van de opzeg en wie opzegt in."))
            contract.state = "notice"
            contract.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=contract.notice_end_date,
                summary=self.env._("Einde huur: plaatsbeschrijving en huurwaarborg"),
                note=self.env._(
                    "De huur eindigt op %(date)s. Plan de plaatsbeschrijving bij vertrek, de opname van de meters "
                    "en de vrijgave van de huurwaarborg.", date=format_date(self.env, contract.notice_end_date)),
                user_id=self.env.user.id,
            )

    def action_end(self):
        today = fields.Date.context_today(self)
        for contract in self:
            contract.write({"state": "ended", "date_moved_out": contract.date_moved_out or contract.notice_end_date or today})

    @api.model
    def _cron_rent_reminders(self):
        """Tasks before a notice deadline and draft indexations before an anniversary."""
        today = fields.Date.context_today(self)
        todo = self.env.ref("mail.mail_activity_data_todo")
        running = self.search([("state", "=", "active")])
        for contract in running.filtered(
                lambda c: c.notice_deadline and today <= c.notice_deadline <= today + relativedelta(days=NOTICE_LEAD_DAYS)
                and c.activity_notice_deadline != c.notice_deadline):
            if contract.lease_type == "short":
                note = self.env._(
                    "Wie het kortlopende contract wil laten eindigen op %(end)s, moet uiterlijk op %(deadline)s opzeggen. "
                    "Anders wordt het een contract van negen jaar vanaf de ingangsdatum.",
                    end=format_date(self.env, contract.date_end), deadline=format_date(self.env, contract.notice_deadline))
            else:
                note = self.env._(
                    "Wil de verhuurder het contract laten eindigen op %(end)s, dan moet de opzeg uiterlijk op %(deadline)s "
                    "vertrekken (zes maanden; de huurder heeft drie maanden).",
                    end=format_date(self.env, contract.date_end), deadline=format_date(self.env, contract.notice_deadline))
            contract.activity_schedule(
                activity_type_id=todo.id, date_deadline=contract.notice_deadline,
                summary=self.env._("Opzegtermijn verstrijkt: %s", contract.name), note=note, user_id=self.env.user.id,
            )
            contract.activity_notice_deadline = contract.notice_deadline
        for contract in running.filtered(lambda c: c.is_written and not c.indexation_excluded):
            anniversary = contract._anniversary_after(today)
            if anniversary > today + relativedelta(days=INDEXATION_LEAD_DAYS):
                continue
            if contract.indexation_ids.filtered(lambda i, a=anniversary: i.anniversary_date == a):
                continue
            try:
                indexation = contract._create_indexation(anniversary)
            except UserError:
                continue  # index of the month before the anniversary not published yet: try again tomorrow
            contract.activity_schedule(
                activity_type_id=todo.id, date_deadline=anniversary,
                summary=self.env._("Indexatiebrief nakijken en versturen"),
                note=self.env._("De conceptbrief voor de indexering op %s staat klaar.", format_date(self.env, anniversary)),
                user_id=self.env.user.id,
            )
            indexation.message_post(body=self.env._("Concept aangemaakt door de dagelijkse controle."))

    # Smart buttons

    def action_open_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Huurfacturen"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("rent_contract_id", "=", self.id)],
            "context": {"default_move_type": "out_invoice", "allowed_company_ids": [self.company_id.id]},
        }

    def action_open_indexations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Indexeringen"),
            "res_model": "vme.rent.indexation",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id},
        }

    def action_open_settlements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Afrekeningen lasten"),
            "res_model": "vme.rent.settlement",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id},
        }

    def action_open_settlement_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Afrekening lasten huurder"),
            "res_model": "vme.rent.settlement.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }


class VmeRentContractCharge(models.Model):
    _name = "vme.rent.contract.charge"
    _description = "Lasten per rubriek in een huurcontract"
    _order = "sequence, id"

    contract_id = fields.Many2one("vme.rent.contract", required=True, ondelete="cascade", index=True)
    category_id = fields.Many2one("vme.rent.charge.category", string="Rubriek", required=True)
    sequence = fields.Integer(related="category_id.sequence", store=True)
    tenant_percent = fields.Float(string="Ten laste van de huurder (%)", digits=(5, 2))

    _unique_category = models.Constraint("UNIQUE (contract_id, category_id)", "Elke rubriek staat maar één keer in een contract.")
    _percent_range = models.Constraint("CHECK (tenant_percent >= 0 AND tenant_percent <= 100)",
                                       "Het aandeel van de huurder ligt tussen 0 en 100%.")

