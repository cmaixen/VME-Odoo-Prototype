"""The syndic's own business: management agreement and fee per VME, extra services, fee invoices, mandate.

The syndic's office is its own company (``res.company.is_syndic_office``). Its fee invoices are customer
invoices there; confirming one prepares the matching draft vendor bill in the company of the VME, where a
person checks and confirms it before it is split over the owners. Nothing is posted on the VME side or sent
by itself.
"""
import base64
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import format_date

SERVICE_TYPES = [
    ("extraordinary_assembly", "Buitengewone AV"),
    ("sale_file", "Verkoopdossier en inlichtingen notaris"),
    ("damage_claim", "Schadedossier"),
    ("registered_mail", "Aangetekende zending"),
    ("extra_meeting", "Bijkomende vergadering"),
    ("other", "Andere prestatie"),
]
# Price list of a new agreement (euro, VAT excluded); the syndic adapts it per agreement.
DEFAULT_RATES = {
    "extraordinary_assembly": 250.0,
    "sale_file": 225.0,
    "damage_claim": 120.0,
    "registered_mail": 18.0,
    "extra_meeting": 150.0,
}
# Chart of accounts (l10n_be): revenue of the office, fee expense of the VME, 21% VAT on services.
OFFICE_REVENUE_ACCOUNT = "a7001"  # Diensten in België
VME_FEE_ACCOUNT = "a61329"  # Andere erelonen
OFFICE_SALE_TAX = "attn_VAT-OUT-21-S"
VME_PURCHASE_TAX = "attn_VAT-IN-V82-21-S"

# LEGAL-CHECK: art. 3.89 §1 BW - the mandate of the syndic lasts at most three years and can be
# renewed by the general assembly.
MANDATE_MAX_YEARS = 3
# Signal the renewal from six months before the assembly period, urgent from two months before.
RENEWAL_PLAN_MONTHS = 6
RENEWAL_URGENT_MONTHS = 2
RENEWAL_ITEM_TITLE = "Herbenoeming van de syndicus en goedkeuring van de beheerovereenkomst"
# LEGAL-CHECK: art. 3.89 §2 BW - an extract of the appointment is posted at the entrance of the
# building within eight days after the mandate starts.
POSTING_DAYS = 8


def _month_start(day):
    return day.replace(day=1)


def _months(date_from, date_to):
    """First days of the months that lie completely within [date_from, date_to]."""
    month = _month_start(date_from)
    if month < date_from:
        month += relativedelta(months=1)
    while month + relativedelta(months=1, days=-1) <= date_to:
        yield month
        month += relativedelta(months=1)


class ResCompany(models.Model):
    _inherit = "res.company"

    is_syndic_office = fields.Boolean(
        string="Kantoor van de syndicus",
        help="De company van het syndicuskantoor zelf: hier staan de ereloonfacturen aan de VME's (zijn omzet).",
    )


class VmeConsumerPriceIndex(models.Model):
    _name = "vme.consumer.price.index"
    _description = "Consumptieprijsindex"
    _order = "month desc"
    _rec_name = "month"

    month = fields.Date(string="Maand", required=True, help="Eerste dag van de maand.")
    value = fields.Float(string="Consumptieprijsindex", required=True, digits=(16, 2),
                         help="Consumptieprijsindex zoals Statbel die elke maand publiceert.")

    _unique_month = models.Constraint("UNIQUE (month)", "Elke maand heeft maar één indexcijfer.")
    _positive_value = models.Constraint("CHECK (value > 0)", "Een indexcijfer is groter dan nul.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("month"):
                vals["month"] = _month_start(fields.Date.to_date(vals["month"]))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("month"):
            vals["month"] = _month_start(fields.Date.to_date(vals["month"]))
        return super().write(vals)

    @api.model
    def _lookup(self, month):
        record = self.search([("month", "=", _month_start(month))], limit=1)
        if not record:
            raise UserError(self.env._(
                "De consumptieprijsindex van %s staat nog niet in de tabel. Vul hem aan onder "
                "VME > Configuratie > Consumptieprijsindex.", format_date(self.env, month, date_format="MMMM y")))
        return record.value


class VmeManagementAgreement(models.Model):
    _name = "vme.management.agreement"
    _description = "Beheerovereenkomst"
    _inherit = ["mail.thread"]
    _order = "association_id, date_start desc"

    # LEGAL-CHECK: art. 3.89 §1 BW - the assignment of the syndic and his fee are laid down in a written
    # agreement, with the fixed (forfait) services and the price of the additional services.
    name = fields.Char(string="Overeenkomst", compute="_compute_name", store=True)
    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade",
                                     index=True, tracking=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    syndic_company_id = fields.Many2one(
        "res.company", string="Kantoor syndicus", required=True, domain="[('is_syndic_office', '=', True)]",
        default=lambda self: self.env["res.company"].sudo().search([("is_syndic_office", "=", True)], limit=1),
    )
    syndic_partner_id = fields.Many2one(related="syndic_company_id.partner_id", string="Syndicus")
    currency_id = fields.Many2one(related="syndic_company_id.currency_id")
    active = fields.Boolean(string="Actief", default=True)
    date_start = fields.Date(string="Begin", required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string="Einde", tracking=True, help="Leeg zolang de overeenkomst loopt.")
    fee_basis = fields.Selection([("lot", "Per kavel"), ("vme", "Per VME")], string="Vast ereloon",
                                 required=True, default="lot", tracking=True)
    fee_amount = fields.Monetary(string="Bedrag per maand", required=True, tracking=True,
                                 help="Basisbedrag per maand, zonder btw: per kavel of voor de hele VME.")
    billing_period = fields.Selection([("month", "Per maand"), ("quarter", "Per kwartaal")],
                                      string="Facturatie", required=True, default="quarter", tracking=True)
    indexation = fields.Selection(
        [("none", "Geen indexering"), ("cpi", "Consumptieprijsindex"), ("percent", "Vast percentage per jaar")],
        string="Indexering", required=True, default="cpi", tracking=True,
        help="Op elke verjaardag van de begindatum: basisbedrag × index van de maand vóór de verjaardag / "
             "basisindex, of basisbedrag × (1 + percentage) per verstreken jaar.",
    )
    index_base_month = fields.Date(
        string="Basismaand index", compute="_compute_index_base_month", store=True, readonly=False,
        help="Standaard de maand vóór het begin van de overeenkomst.")
    index_base_value = fields.Float(
        string="Basisindex", digits=(16, 2), compute="_compute_index_base_value", store=True, readonly=False)
    index_percent = fields.Float(string="Percentage per jaar", digits=(16, 2))
    index_rates = fields.Boolean(string="Prijslijst mee indexeren", default=True)
    rate_ids = fields.One2many("vme.service.rate", "agreement_id", string="Prijslijst extra prestaties", copy=True)
    service_line_ids = fields.One2many("vme.service.line", "agreement_id", string="Prestaties")
    fee_invoice_ids = fields.One2many("account.move", "vme_fee_agreement_id", string="Ereloonfacturen")
    fee_invoice_count = fields.Integer(compute="_compute_counts")
    service_to_invoice_count = fields.Integer(string="Te factureren prestaties", compute="_compute_counts")
    unit_count = fields.Integer(string="Kavels", compute="_compute_current_fee")
    current_factor = fields.Float(string="Indexfactor vandaag", digits=(16, 4), compute="_compute_current_fee")
    current_unit_fee = fields.Monetary(string="Ereloon per eenheid vandaag", compute="_compute_current_fee")
    current_monthly_fee = fields.Monetary(string="Vast ereloon per maand vandaag", compute="_compute_current_fee")
    note = fields.Text(string="Opmerkingen")

    @api.depends("association_id.name", "date_start")
    def _compute_name(self):
        for agreement in self:
            agreement.name = self.env._(
                "Beheerovereenkomst %(vme)s vanaf %(date)s", vme=agreement.association_id.name or "",
                date=format_date(self.env, agreement.date_start) if agreement.date_start else "")

    @api.depends("date_start")
    def _compute_index_base_month(self):
        for agreement in self:
            if agreement.date_start and not agreement.index_base_month:
                agreement.index_base_month = _month_start(agreement.date_start - relativedelta(months=1))

    @api.depends("index_base_month", "indexation")
    def _compute_index_base_value(self):
        Index = self.env["vme.consumer.price.index"]
        for agreement in self:
            if agreement.indexation == "cpi" and agreement.index_base_month and not agreement.index_base_value:
                record = Index.search([("month", "=", _month_start(agreement.index_base_month))], limit=1)
                agreement.index_base_value = record.value

    def _compute_counts(self):
        # The invoices live in the office company: count them whatever companies are selected.
        Move = self.env["account.move"].sudo()
        for agreement in self:
            agreement.fee_invoice_count = Move.search_count([("vme_fee_agreement_id", "=", agreement.id)])
            agreement.service_to_invoice_count = len(
                agreement.service_line_ids.filtered(lambda s: s.state == "to_invoice"))

    def _compute_current_fee(self):
        today = fields.Date.context_today(self)
        for agreement in self:
            agreement.unit_count = agreement._unit_count()
            try:
                factor = agreement._fee_factor(max(today, agreement.date_start or today))
            except UserError:
                factor = 0.0
            agreement.current_factor = factor
            agreement.current_unit_fee = agreement.currency_id.round(agreement.fee_amount * factor)
            agreement.current_monthly_fee = agreement.current_unit_fee * agreement.unit_count

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "rate_ids" not in vals:
                vals["rate_ids"] = [Command.create({"service_type": code, "price": price})
                                    for code, price in DEFAULT_RATES.items()]
        agreements = super().create(vals_list)
        agreements._ensure_fee_rule()
        return agreements

    @api.constrains("association_id", "date_start", "date_end", "active")
    def _check_overlap(self):
        for agreement in self.filtered("active"):
            if agreement.date_end and agreement.date_end < agreement.date_start:
                raise ValidationError(self.env._("Het einde van de overeenkomst ligt vóór het begin."))
            others = self.search([("association_id", "=", agreement.association_id.id), ("id", "!=", agreement.id)])
            for other in others:
                if (not other.date_end or other.date_end >= agreement.date_start) and \
                        (not agreement.date_end or agreement.date_end >= other.date_start):
                    raise ValidationError(self.env._(
                        "%(vme)s heeft al een beheerovereenkomst in die periode (%(other)s).",
                        vme=agreement.association_id.name, other=other.name))

    @api.constrains("indexation", "index_base_value", "index_percent")
    def _check_indexation(self):
        for agreement in self:
            if agreement.indexation == "percent" and agreement.index_percent < 0:
                raise ValidationError(self.env._("Het indexpercentage kan niet negatief zijn."))

    def _is_active_on(self, day):
        self.ensure_one()
        return self.date_start <= day and (not self.date_end or self.date_end >= day)

    def _unit_count(self):
        self.ensure_one()
        return len(self.association_id.lot_ids) if self.fee_basis == "lot" else 1

    def _fee_factor(self, day):
        """Indexation factor on a day: unchanged until the first anniversary of the start."""
        self.ensure_one()
        years = relativedelta(day, self.date_start).years if day >= self.date_start else 0
        if self.indexation == "none" or years <= 0:
            return 1.0
        if self.indexation == "percent":
            return (1 + self.index_percent / 100.0) ** years
        anniversary = self.date_start + relativedelta(years=years)
        if not self.index_base_value:
            raise UserError(self.env._("Vul de basisindex in op %s.", self.name))
        index = self.env["vme.consumer.price.index"]._lookup(anniversary - relativedelta(months=1))
        return index / self.index_base_value

    def _unit_fee(self, month):
        """Indexed fee per lot (or per VME) for a month, rounded to the cent."""
        self.ensure_one()
        return self.currency_id.round(self.fee_amount * self._fee_factor(month))

    def _rate_price(self, service_type, day):
        self.ensure_one()
        rate = self.rate_ids.filtered(lambda r: r.service_type == service_type)[:1]
        factor = self._fee_factor(day) if self.index_rates else 1.0
        return self.currency_id.round(rate.price * factor)

    def _billing_periods(self, date_from, date_to):
        """Complete billing periods (start, end) of this agreement within [date_from, date_to]."""
        self.ensure_one()
        periods = []
        step = 3 if self.billing_period == "quarter" else 1
        for month in _months(date_from, date_to):
            if (month.month - 1) % step:
                continue
            end = month + relativedelta(months=step, days=-1)
            if end > date_to:
                continue
            if end < self.date_start or (self.date_end and month > self.date_end):
                continue
            periods.append((month, end))
        return periods

    def _fixed_fee_lines(self, period_start, period_end):
        """Invoice lines of the fixed fee: one line per run of months with the same price."""
        self.ensure_one()
        units = self._unit_count()
        runs = []  # [first month, last month, price]
        for month in _months(period_start, period_end):
            if month + relativedelta(months=1, days=-1) < self.date_start or (self.date_end and month > self.date_end):
                continue
            price = self._unit_fee(max(month, self.date_start))
            if runs and runs[-1][2] == price:
                runs[-1][1] = month
            else:
                runs.append([month, month, price])
        lines = []
        for first, last, price in runs:
            count = (last.year - first.year) * 12 + last.month - first.month + 1
            period = format_date(self.env, first, date_format="MMMM y") if first == last else \
                f"{format_date(self.env, first, date_format='MMMM y')} - {format_date(self.env, last, date_format='MMMM y')}"
            unit = self.env._("%s kavels", units) if self.fee_basis == "lot" else self.env._("de VME")
            lines.append({
                "name": self.env._("Vast ereloon %(period)s (%(unit)s × %(months)s maand(en))",
                                   period=period, unit=unit, months=count),
                "quantity": units * count,
                "price_unit": price,
            })
        return lines

    def _ensure_fee_rule(self):
        """Distribution rule in the VME: bills of the office go on the general key, account "Andere erelonen"."""
        Rule = self.env["vme.distribution.rule"].sudo()
        for agreement in self:
            vme = agreement.association_id
            partner = agreement.syndic_partner_id
            if not partner:
                continue
            rule = Rule.with_context(active_test=False).search(
                [("association_id", "=", vme.id), ("partner_id", "=", partner.id)], limit=1)
            key = vme.key_ids.filtered(lambda k: k.key_type == "general")[:1]
            if not rule and key:
                rule = Rule.create({"association_id": vme.id, "partner_id": partner.id, "key_id": key.id,
                                    "note": self.env._("Ereloon van de syndicus")})
            if rule and not rule.account_id:
                rule.account_id = agreement._chart_ref(agreement.company_id, VME_FEE_ACCOUNT)

    @api.model
    def _chart_ref(self, company, xmlid):
        """Record of the l10n_be chart in a company; empty while its chart is not loaded yet."""
        record = self.env["account.chart.template"].with_company(company).ref(xmlid, raise_if_not_found=False)
        return record or self.env["account.account"]

    def _fee_invoices_overlapping(self, period_start, period_end):
        self.ensure_one()
        return self.env["account.move"].sudo().search([
            ("vme_fee_agreement_id", "=", self.id), ("move_type", "=", "out_invoice"), ("state", "!=", "cancel"),
            ("vme_period_start", "<=", period_end), ("vme_period_end", ">=", period_start),
        ])

    def _create_fee_invoice(self, period_start, period_end):
        """Draft customer invoice of the office to the VME: fixed fee plus the services to invoice."""
        self.ensure_one()
        if self._fee_invoices_overlapping(period_start, period_end):
            raise UserError(self.env._(
                "Voor %(vme)s bestaat al een ereloonfactuur voor (een deel van) %(start)s - %(end)s.",
                vme=self.association_id.name, start=format_date(self.env, period_start),
                end=format_date(self.env, period_end)))
        office = self.syndic_company_id
        account = self._chart_ref(office, OFFICE_REVENUE_ACCOUNT)
        tax = self._chart_ref(office, OFFICE_SALE_TAX)
        services = self.service_line_ids.filtered(lambda s: s.state == "to_invoice" and s.date <= period_end)
        # The lines are for the VME: in its language (see docs/dev/vertaling.md).
        vme_lang = self.association_id.partner_id.lang or self.env.lang
        line_vals = self.with_context(lang=vme_lang)._fixed_fee_lines(period_start, period_end)
        line_vals += [{
            "name": service.with_context(lang=vme_lang)._invoice_label(),
            "quantity": service.quantity,
            "price_unit": service.price_unit,
            "vme_service_line_id": service.id,
        } for service in services.sorted("date")]
        for vals in line_vals:
            vals.update({"tax_ids": [Command.set(tax.ids)]})
            if account:
                vals["account_id"] = account.id
        invoice = self.env["account.move"].with_company(office).create({
            "move_type": "out_invoice",
            "company_id": office.id,
            "partner_id": self.association_id.partner_id.id,
            "invoice_date": period_end,
            "vme_period_start": period_start,
            "vme_period_end": period_end,
            "vme_fee_agreement_id": self.id,
            "invoice_line_ids": [Command.create(vals) for vals in line_vals],
        })
        for line in invoice.invoice_line_ids.filtered("vme_service_line_id"):
            line.vme_service_line_id.invoice_line_id = line
        return invoice

    def action_open_fee_invoices(self):
        """The invoices live in the office company: they show once the office is selected in the company switcher."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_fee_invoice_action")
        action["domain"] = [("vme_fee_agreement_id", "=", self.id)]
        return action

    def action_open_services(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Prestaties"),
            "res_model": "vme.service.line",
            "view_mode": "list,form",
            "domain": [("agreement_id", "=", self.id)],
            "context": {"default_association_id": self.association_id.id},
        }

    def action_create_fee_invoice(self):
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Ereloonfactuur maken"),
            "res_model": "vme.fee.invoice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_association_ids": self.association_id.ids},
        }


class VmeServiceRate(models.Model):
    _name = "vme.service.rate"
    _description = "Prijs extra prestatie"
    _order = "agreement_id, service_type"

    agreement_id = fields.Many2one("vme.management.agreement", string="Overeenkomst", required=True,
                                   ondelete="cascade", index=True)
    service_type = fields.Selection(SERVICE_TYPES, string="Prestatie", required=True)
    price = fields.Monetary(string="Prijs (zonder btw)")
    currency_id = fields.Many2one(related="agreement_id.currency_id")

    _unique_type = models.Constraint("UNIQUE (agreement_id, service_type)",
                                     "Elke prestatie staat maar één keer in de prijslijst.")


class VmeServiceLine(models.Model):
    _name = "vme.service.line"
    _description = "Prestatie van de syndicus"
    _order = "date desc, id desc"

    name = fields.Char(string="Omschrijving", required=True)
    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    agreement_id = fields.Many2one(
        "vme.management.agreement", string="Overeenkomst", compute="_compute_agreement_id", store=True,
        readonly=False, ondelete="restrict", index=True, domain="[('association_id', '=', association_id)]")
    currency_id = fields.Many2one(related="agreement_id.currency_id")
    service_type = fields.Selection(SERVICE_TYPES, string="Prestatie", required=True, default="other")
    date = fields.Date(string="Datum", required=True, default=fields.Date.context_today)
    quantity = fields.Float(string="Aantal", default=1.0, digits=(16, 2))
    price_unit = fields.Monetary(string="Eenheidsprijs", compute="_compute_price_unit", store=True, readonly=False,
                                 help="Uit de prijslijst van de overeenkomst, geïndexeerd; aan te passen.")
    amount = fields.Monetary(string="Bedrag (zonder btw)", compute="_compute_amount", store=True)
    res_model = fields.Char(string="Bronmodel", readonly=True)
    res_id = fields.Integer(string="Bron-ID", readonly=True)
    source_name = fields.Char(string="Bron", readonly=True)
    recharge_partner_id = fields.Many2one(
        "res.partner", string="Door te rekenen aan",
        help="Wie de kost uiteindelijk draagt, bv. de verkoper bij de inlichtingen aan de notaris.")
    no_charge = fields.Boolean(string="Niet aanrekenen")
    invoice_line_id = fields.Many2one("account.move.line", string="Factuurlijn", readonly=True, copy=False,
                                      ondelete="set null", index=True)
    invoice_id = fields.Many2one(related="invoice_line_id.move_id", string="Ereloonfactuur", store=True)
    state = fields.Selection(
        [("to_invoice", "Te factureren"), ("invoiced", "Gefactureerd"), ("no_charge", "Niet aangerekend")],
        string="Status", compute="_compute_state", store=True)

    _unique_source = models.UniqueIndex(
        "(res_model, res_id, service_type) WHERE res_model IS NOT NULL",
        "Deze bron heeft al een prestatie van deze soort.",
    )

    @api.depends("association_id", "date")
    def _compute_agreement_id(self):
        for line in self:
            if line.association_id and line.date:
                line.agreement_id = line.association_id._get_management_agreement_on(line.date)

    @api.depends("agreement_id", "service_type", "date")
    def _compute_price_unit(self):
        for line in self:
            if line.agreement_id and line.service_type and line.date and line.state != "invoiced":
                # A missing index figure must never block the declaration, deposit or meeting behind it:
                # the price stays empty and the invoice wizard asks for the figure.
                try:
                    line.price_unit = line.agreement_id._rate_price(line.service_type, line.date)
                except UserError:
                    line.price_unit = 0.0

    @api.depends("quantity", "price_unit")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.price_unit

    @api.depends("no_charge", "invoice_line_id", "invoice_line_id.parent_state")
    def _compute_state(self):
        for line in self:
            if line.invoice_line_id and line.invoice_line_id.parent_state != "cancel":
                line.state = "invoiced"
            elif line.no_charge:
                line.state = "no_charge"
            else:
                line.state = "to_invoice"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_invoiced(self):
        if self.filtered(lambda line: line.state == "invoiced"):
            raise UserError(self.env._("Een gefactureerde prestatie kan niet verwijderd worden."))

    def _invoice_label(self):
        self.ensure_one()
        kind = dict(self._fields["service_type"]._description_selection(self.env))[self.service_type]
        source = dict(self._fields["service_type"].selection)[self.service_type]
        if self.name.startswith(kind):
            label = self.name
        elif self.name.startswith(source):
            # A name made in Dutch (before the VME was set to French): translate its prefix.
            label = kind + self.name[len(source):]
        else:
            label = f"{kind}: {self.name}"
        return f"{label} ({format_date(self.env, self.date)})"

    @api.model
    def _register_from_source(self, source, service_type, day, name, recharge_partner=None):
        """Service line for an event in another record; only if its VME has an agreement on that day."""
        vme = source.association_id
        agreement = vme._get_management_agreement_on(day)
        if not agreement:
            return self.browse()
        existing = self.sudo().search([("res_model", "=", source._name), ("res_id", "=", source.id),
                                       ("service_type", "=", service_type)], limit=1)
        if existing:
            return existing
        line = self.sudo().create({
            "association_id": vme.id,
            "agreement_id": agreement.id,
            "service_type": service_type,
            "date": day,
            "name": name,
            "res_model": source._name,
            "res_id": source.id,
            "source_name": source.display_name,
            "recharge_partner_id": recharge_partner.id if recharge_partner else False,
        })
        source.message_post(body=self.env._(
            "Prestatie van de syndicus geregistreerd: %(name)s (%(amount)s, zonder btw), te factureren met het "
            "volgende ereloon.", name=name, amount=f"€ {line.amount:.2f}"))
        return line

    def action_open_source(self):
        self.ensure_one()
        if not self.res_model:
            return False
        return {"type": "ir.actions.act_window", "res_model": self.res_model, "res_id": self.res_id,
                "view_mode": "form"}


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_fee_agreement_id = fields.Many2one("vme.management.agreement", string="Beheerovereenkomst",
                                           index=True, copy=False, ondelete="restrict")
    vme_fee_bill_id = fields.Many2one("account.move", string="Leveranciersfactuur in de VME", copy=False,
                                      readonly=True, index=True)
    vme_fee_invoice_id = fields.Many2one("account.move", string="Ereloonfactuur van de syndicus", copy=False,
                                         readonly=True, index=True)

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered(lambda m: m.vme_fee_agreement_id and m.move_type == "out_invoice")._vme_prepare_fee_bill()
        return posted

    def _vme_prepare_fee_bill(self):
        """Draft vendor bill in the VME for each confirmed fee invoice; the VME side stays a draft."""
        for invoice in self:
            agreement = invoice.vme_fee_agreement_id
            vme_company = agreement.company_id
            bill = invoice.vme_fee_bill_id
            if bill.state == "posted":
                invoice.message_post(body=self.env._(
                    "De leveranciersfactuur %s in de VME is al bevestigd; pas ze daar aan met een creditnota.",
                    bill.name))
                continue
            agreement._ensure_fee_rule()
            rule = self.env["vme.distribution.rule"].sudo()._find_rule(vme_company, agreement.syndic_partner_id)
            tax = agreement._chart_ref(vme_company, VME_PURCHASE_TAX)
            line_vals = [{
                "name": line.name,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                "tax_ids": [Command.set(tax.ids)],
                **({"account_id": rule.account_id.id} if rule.account_id else {}),
                **({"vme_key_id": rule.key_id.id} if rule.key_id else {}),
            } for line in invoice.invoice_line_ids.filtered(lambda l: l.display_type == "product")]
            vals = {
                "partner_id": agreement.syndic_partner_id.id,
                "invoice_date": invoice.invoice_date,
                "ref": invoice.name,
                "vme_period_start": invoice.vme_period_start,
                "vme_period_end": invoice.vme_period_end,
                "vme_fee_invoice_id": invoice.id,
                "invoice_line_ids": [Command.clear()] + [Command.create(v) for v in line_vals],
            }
            Move = self.env["account.move"].with_company(vme_company)
            if bill and bill.state == "draft":
                bill.with_company(vme_company).write(vals)
            else:
                bill = Move.create({**vals, "move_type": "in_invoice", "company_id": vme_company.id})
                invoice.vme_fee_bill_id = bill
            bill.message_post(body=self.env._(
                "Ereloonfactuur %s van de syndicus. Kijk ze na en bevestig ze; daarna wordt ze verdeeld "
                "over de eigenaars.", invoice.name))
            invoice.message_post(body=self.env._(
                "Leveranciersfactuur in %s klaargezet als concept.", agreement.association_id.name))

    def action_open_vme_fee_bill(self):
        self.ensure_one()
        move = self.vme_fee_bill_id or self.vme_fee_invoice_id
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": move.id,
                "view_mode": "form", "context": {"allowed_company_ids": move.company_id.ids}}


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    vme_service_line_id = fields.Many2one("vme.service.line", string="Prestatie", copy=False, index="btree_not_null")


class VmeSyndicMandate(models.Model):
    _name = "vme.syndic.mandate"
    _description = "Mandaat van de syndicus"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "association_id, date_start desc"

    name = fields.Char(string="Mandaat", compute="_compute_name", store=True)
    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade",
                                     index=True, tracking=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    partner_id = fields.Many2one(
        "res.partner", string="Syndicus", required=True, tracking=True,
        default=lambda self: self.env["res.company"].sudo().search(
            [("is_syndic_office", "=", True)], limit=1).partner_id)
    date_start = fields.Date(string="Begin mandaat", required=True, tracking=True)
    date_end = fields.Date(string="Einde mandaat", compute="_compute_date_end", store=True, readonly=False,
                           tracking=True, help="Standaard drie jaar na het begin, het wettelijke maximum.")
    appointment_item_id = fields.Many2one(
        "vme.assembly.item", string="Benoemd door", domain="[('association_id', '=', association_id)]",
        help="Beslissing van de AV die de syndicus (her)benoemde.")
    previous_mandate_id = fields.Many2one("vme.syndic.mandate", string="Vorig mandaat", ondelete="set null",
                                          domain="[('association_id', '=', association_id)]")
    next_mandate_id = fields.Many2one("vme.syndic.mandate", string="Volgend mandaat", compute="_compute_next_mandate")
    is_current = fields.Boolean(string="Lopend", compute="_compute_is_current", search="_search_is_current")
    renewal_assembly_year = fields.Integer(
        string="AV voor herbenoeming", compute="_compute_renewal_assembly_year", store=True,
        help="Jaar van de laatste gewone AV binnen het mandaat: die beslist over de herbenoeming.")
    renewal_period_start = fields.Date(string="Periode AV herbenoeming", compute="_compute_renewal_assembly_year",
                                       store=True)
    renewal_assembly_id = fields.Many2one("vme.assembly", string="AV herbenoeming", compute="_compute_renewal")
    renewal_item_id = fields.Many2one("vme.assembly.item", string="Agendapunt herbenoeming",
                                      compute="_compute_renewal")
    renewal_state = fields.Selection(
        [("ok", "In orde"), ("plan", "Herbenoeming plannen"), ("urgent", "Herbenoeming dringend"),
         ("decided", "Herbenoeming beslist"), ("renewed", "Hernieuwd"), ("expired", "Verlopen")],
        string="Signaal herbenoeming", compute="_compute_renewal", search="_search_renewal_state")
    renewal_text = fields.Char(string="Herbenoeming", compute="_compute_renewal")
    # LEGAL-CHECK: art. 3.89 §2 BW - extract of the appointment posted at the entrance within eight days.
    posting_deadline = fields.Date(string="Aanplakken uiterlijk", compute="_compute_posting_deadline", store=True)
    posted_date = fields.Date(string="Aangeplakt op", tracking=True, copy=False)
    posting_document_id = fields.Many2one("vme.document", string="Aanplakbrief", readonly=True, copy=False)
    posting_state = fields.Selection(
        [("posted", "Aangeplakt"), ("todo", "Aan te plakken"), ("late", "Te laat")],
        string="Aanplakking", compute="_compute_posting_state", search="_search_posting_state")

    @api.depends("association_id.name", "date_start", "date_end")
    def _compute_name(self):
        for mandate in self:
            mandate.name = self.env._(
                "Mandaat syndicus %(vme)s %(start)s - %(end)s", vme=mandate.association_id.name or "",
                start=format_date(self.env, mandate.date_start) if mandate.date_start else "",
                end=format_date(self.env, mandate.date_end) if mandate.date_end else "")

    @api.depends("date_start")
    def _compute_date_end(self):
        for mandate in self:
            if mandate.date_start and not mandate.date_end:
                mandate.date_end = mandate.date_start + relativedelta(years=MANDATE_MAX_YEARS, days=-1)

    @api.depends("date_start", "date_end", "association_id.assembly_period_month",
                 "association_id.assembly_period_day")
    def _compute_renewal_assembly_year(self):
        for mandate in self:
            year, start = False, False
            vme = mandate.association_id
            if vme and mandate.date_start and mandate.date_end:
                for candidate in range(mandate.date_end.year, mandate.date_start.year - 1, -1):
                    period_start, _end = vme._get_assembly_period(candidate)
                    if period_start and mandate.date_start <= period_start <= mandate.date_end:
                        year, start = candidate, period_start
                        break
            mandate.renewal_assembly_year = year
            mandate.renewal_period_start = start

    @api.depends("date_start")
    def _compute_posting_deadline(self):
        for mandate in self:
            mandate.posting_deadline = mandate.date_start and mandate.date_start + timedelta(days=POSTING_DAYS)

    def _compute_next_mandate(self):
        for mandate in self:
            mandate.next_mandate_id = self.search([("previous_mandate_id", "=", mandate.id)], limit=1) if mandate.id \
                else False

    def _compute_is_current(self):
        today = fields.Date.context_today(self)
        for mandate in self:
            mandate.is_current = mandate.date_start <= today <= mandate.date_end

    def _search_is_current(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return NotImplemented
        today = fields.Date.context_today(self)
        domain = [("date_start", "<=", today), ("date_end", ">=", today)]
        return domain if (operator == "=") == value else ["!", "&"] + domain

    def _renewal_assembly(self):
        self.ensure_one()
        if not self.renewal_assembly_year:
            return self.env["vme.assembly"]
        return self.env["vme.assembly"].search([
            ("association_id", "=", self.association_id.id), ("year", "=", self.renewal_assembly_year),
            ("assembly_type", "=", "ordinary"), ("state", "!=", "cancelled")], limit=1)

    def _compute_renewal(self):
        today = fields.Date.context_today(self)
        for mandate in self:
            assembly = mandate._renewal_assembly() if mandate.id else self.env["vme.assembly"]
            item = assembly.item_ids.filtered(lambda i: i.name == RENEWAL_ITEM_TITLE)[:1]
            mandate.renewal_assembly_id = assembly
            mandate.renewal_item_id = item
            start = mandate.renewal_period_start
            nxt = mandate.next_mandate_id
            if nxt:
                state = "renewed"
                text = self.env._("Hernieuwd tot %s.", format_date(self.env, nxt.date_end))
            elif mandate.date_end and mandate.date_end < today:
                state = "expired"
                text = self.env._("Mandaat verlopen op %s: de VME heeft geen syndicus meer.",
                                  format_date(self.env, mandate.date_end))
            elif item.outcome == "adopted":
                state = "decided"
                text = self.env._("De AV besliste de herbenoeming: maak het nieuwe mandaat.")
            elif start and today >= start - relativedelta(months=RENEWAL_PLAN_MONTHS):
                state = "urgent" if today >= start - relativedelta(months=RENEWAL_URGENT_MONTHS) else "plan"
                text = self.env._(
                    "Herbenoeming op de AV van %(month)s (periode vanaf %(date)s), mandaat loopt tot %(end)s. %(item)s",
                    month=format_date(self.env, start, date_format="MMMM y"), date=format_date(self.env, start),
                    end=format_date(self.env, mandate.date_end),
                    item=self.env._("Agendapunt staat klaar.") if item else self.env._("Nog geen agendapunt."))
            else:
                state = "ok"
                text = self.env._("Herbenoeming op de AV van %s.", mandate.renewal_assembly_year) \
                    if mandate.renewal_assembly_year else self.env._("Geen gewone AV binnen het mandaat.")
            mandate.renewal_state = state
            mandate.renewal_text = text

    def _search_renewal_state(self, operator, value):
        if operator not in ("=", "in"):
            return NotImplemented
        values = [value] if operator == "=" else value
        mandates = self.search([]).filtered(lambda m: m.renewal_state in values)
        return [("id", "in", mandates.ids)]

    @api.depends("posted_date", "posting_deadline")
    def _compute_posting_state(self):
        today = fields.Date.context_today(self)
        for mandate in self:
            if mandate.posted_date:
                mandate.posting_state = "posted"
            elif mandate.posting_deadline and today > mandate.posting_deadline:
                mandate.posting_state = "late"
            else:
                mandate.posting_state = "todo"

    def _search_posting_state(self, operator, value):
        if operator not in ("=", "in"):
            return NotImplemented
        values = [value] if operator == "=" else value
        mandates = self.search([]).filtered(lambda m: m.posting_state in values)
        return [("id", "in", mandates.ids)]

    @api.constrains("date_start", "date_end")
    def _check_duration(self):
        # LEGAL-CHECK: art. 3.89 §1 BW - at most three years, renewable by the general assembly.
        for mandate in self:
            if mandate.date_end < mandate.date_start:
                raise ValidationError(self.env._("Het einde van het mandaat ligt vóór het begin."))
            if mandate.date_end > mandate.date_start + relativedelta(years=MANDATE_MAX_YEARS, days=-1):
                raise ValidationError(self.env._(
                    "Een mandaat van de syndicus duurt hoogstens drie jaar (tot %s). De AV kan het daarna hernieuwen.",
                    format_date(self.env, mandate.date_start + relativedelta(years=MANDATE_MAX_YEARS, days=-1))))
            overlap = self.search_count([
                ("association_id", "=", mandate.association_id.id), ("id", "!=", mandate.id),
                ("date_start", "<=", mandate.date_end), ("date_end", ">=", mandate.date_start)])
            if overlap:
                raise ValidationError(self.env._("%s heeft al een mandaat van de syndicus in die periode.",
                                                 mandate.association_id.name))

    def _ensure_renewal_item(self, assembly):
        """Add the renewal point to the agenda of this assembly, once."""
        self.ensure_one()
        if assembly.state in ("held", "cancelled"):
            raise UserError(self.env._("De AV %s is al gehouden of geannuleerd.", assembly.name))
        item = assembly.item_ids.filtered(lambda i: i.name == RENEWAL_ITEM_TITLE)[:1]
        if item:
            return item
        # LEGAL-CHECK: art. 3.89 §1 BW - the general assembly appoints the syndic; absolute majority
        # (art. 3.87 §8 BW) is assumed for the renewal.
        return self.env["vme.assembly.item"].create({
            "assembly_id": assembly.id,
            "sequence": max(assembly.item_ids.mapped("sequence") or [0]) + 1,
            "name": RENEWAL_ITEM_TITLE,
            "majority": "absolute",
            "description": self.env._(
                "Het mandaat van %(syndic)s loopt tot %(end)s. Voorstel: herbenoeming voor drie jaar, vanaf %(next)s, "
                "en goedkeuring van de beheerovereenkomst.", syndic=self.partner_id.name,
                end=format_date(self.env, self.date_end), next=format_date(self.env, self.date_end + timedelta(days=1))),
        })

    def action_add_renewal_item(self):
        self.ensure_one()
        assembly = self._renewal_assembly()
        if not assembly:
            raise UserError(self.env._(
                "Er is nog geen gewone AV %(year)s voor %(vme)s. Plan ze eerst; het agendapunt komt er dan vanzelf bij.",
                year=self.renewal_assembly_year, vme=self.association_id.name))
        item = self._ensure_renewal_item(assembly)
        return {"type": "ir.actions.act_window", "res_model": "vme.assembly", "res_id": assembly.id,
                "view_mode": "form", "context": {"vme_focus_item": item.id}}

    def action_renew(self):
        """Prepare the next mandate after the general assembly renewed the syndic (a person checks it)."""
        self.ensure_one()
        if self.next_mandate_id:
            raise UserError(self.env._("Dit mandaat is al hernieuwd."))
        item = self.renewal_item_id
        if item and item.outcome != "adopted":
            raise UserError(self.env._("Het agendapunt over de herbenoeming is niet aangenomen."))
        mandate = self.create({
            "association_id": self.association_id.id,
            "partner_id": self.partner_id.id,
            "date_start": self.date_end + timedelta(days=1),
            "appointment_item_id": item.id,
            "previous_mandate_id": self.id,
        })
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": mandate.id, "view_mode": "form"}

    def action_make_posting(self):
        """Make the posting notice as a PDF and keep it in the VME documents (it is printed and posted by a person)."""
        folder = self.env.ref("vme_belgie.folder_syndic")
        for mandate in self:
            pdf, _ = self.env["ir.actions.report"]._render_qweb_pdf(
                "vme_belgie.action_report_syndic_posting", mandate.ids)
            vme_env = mandate.with_context(lang=mandate.company_id.partner_id.lang or self.env.lang).env
            title = vme_env._("Aanplakking aanstelling syndicus %s", format_date(vme_env, mandate.date_start))
            vals = {"name": title, "datas": base64.b64encode(pdf), "filename": f"{title}.pdf",
                    "date": mandate.date_start}
            if mandate.posting_document_id:
                mandate.posting_document_id.write(vals)
            else:
                mandate.posting_document_id = self.env["vme.document"].create({
                    **vals, "folder_id": folder.id, "association_id": mandate.association_id.id})
            mandate.message_post(body=self.env._(
                "Aanplakbrief klaar in de documenten van de VME. Druk hem af, hang hem aan de ingang en "
                "klik op \"Aangeplakt\"."))
        return True

    def action_print_posting(self):
        return self.env.ref("vme_belgie.action_report_syndic_posting").report_action(self)

    def action_mark_posted(self):
        for mandate in self.filtered(lambda m: not m.posted_date):
            mandate.posted_date = fields.Date.context_today(self)
            mandate.activity_ids.filtered(lambda a: a.summary == mandate._posting_summary()).action_feedback(
                feedback=self.env._("Aangeplakt."))

    def _renewal_summary(self):
        return self.env._("Herbenoeming syndicus voorbereiden (AV %s)", self.renewal_assembly_year)

    def _posting_summary(self):
        return self.env._("Aanstelling syndicus aanplakken aan de ingang")

    @api.model
    def _cron_schedule_mandate_activities(self):
        """Tasks for a renewal that must be put on the agenda, and for a posting that is missing."""
        todo = self.env.ref("mail.mail_activity_data_todo")
        for mandate in self.search([("renewal_state", "in", ["plan", "urgent", "decided"])]):
            summary = mandate._renewal_summary()
            if not mandate.activity_ids.filtered(lambda a, s=summary: a.summary == s):
                mandate.activity_schedule(
                    activity_type_id=todo.id, summary=summary, note=mandate.renewal_text,
                    date_deadline=mandate.renewal_period_start - relativedelta(months=RENEWAL_URGENT_MONTHS),
                    user_id=mandate.association_id._vme_task_user().id)
        for mandate in self.search([("posting_state", "in", ["todo", "late"]), ("is_current", "=", True)]):
            summary = mandate._posting_summary()
            if not mandate.activity_ids.filtered(lambda a, s=summary: a.summary == s):
                mandate.activity_schedule(activity_type_id=todo.id, summary=summary,
                                          date_deadline=mandate.posting_deadline,
                                          user_id=mandate.association_id._vme_task_user().id)

    def _posting_values(self):
        """What the posting notice states, for the report."""
        self.ensure_one()
        partner = self.partner_id
        company = self.env["res.company"].sudo().search([("partner_id", "=", partner.id)], limit=1)
        return {
            "syndic": partner.name,
            "address": ", ".join(filter(None, [partner.street, " ".join(filter(None, [partner.zip, partner.city]))])),
            "kbo": company.company_registry or partner.company_registry or partner.vat or "",
            "email": partner.email or "",
            "phone": partner.phone or "",
            "appointment": self.appointment_item_id.assembly_id.display_name if self.appointment_item_id else "",
        }


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    management_agreement_ids = fields.One2many("vme.management.agreement", "association_id",
                                               string="Beheerovereenkomsten")
    syndic_mandate_ids = fields.One2many("vme.syndic.mandate", "association_id", string="Mandaten syndicus")
    service_line_ids = fields.One2many("vme.service.line", "association_id", string="Prestaties syndicus")
    current_agreement_id = fields.Many2one("vme.management.agreement", string="Beheerovereenkomst",
                                           compute="_compute_current_syndic")
    current_syndic_mandate_id = fields.Many2one("vme.syndic.mandate", string="Mandaat syndicus",
                                                compute="_compute_current_syndic")
    syndic_renewal_state = fields.Selection(
        lambda self: self.env["vme.syndic.mandate"]._fields["renewal_state"].selection,
        string="Signaal herbenoeming", compute="_compute_current_syndic")
    syndic_renewal_text = fields.Char(string="Herbenoeming", compute="_compute_current_syndic")

    def _compute_current_syndic(self):
        today = fields.Date.context_today(self)
        for vme in self:
            vme.current_agreement_id = vme._get_management_agreement_on(today)
            mandate = vme._get_syndic_mandate_on(today)
            vme.current_syndic_mandate_id = mandate
            vme.syndic_renewal_state = mandate.renewal_state
            vme.syndic_renewal_text = mandate.renewal_text

    def _get_management_agreement_on(self, day):
        self.ensure_one()
        return self.management_agreement_ids.filtered(lambda a: a.active and a._is_active_on(day))[:1]

    def _get_syndic_mandate_on(self, day):
        """Mandate of the syndic running on a day (empty if there is none): used by the yearly cycle too."""
        self.ensure_one()
        return self.syndic_mandate_ids.filtered(lambda m: m.date_start <= day <= m.date_end)[:1]

    def action_open_agreements(self):
        return self._action_open_related("vme.management.agreement", self.env._("Beheerovereenkomsten"))

    def action_open_syndic_mandates(self):
        return self._action_open_related("vme.syndic.mandate", self.env._("Mandaten syndicus"))

    def action_open_service_lines(self):
        return self._action_open_related("vme.service.line", self.env._("Prestaties syndicus"))


# --- Where the services arise ------------------------------------------------------------------
# The name of a service ends up on the fee invoice to the VME: in the language of the VME.


def _vme_env(record):
    return record.with_context(lang=record.association_id.partner_id.lang or record.env.lang).env


class VmeSaleFile(models.Model):
    _inherit = "vme.sale.file"

    def _answer(self, which):
        result = super()._answer(which)
        if which == "first":
            for sale in self:
                # LEGAL-CHECK: art. 3.94 §1 BW - the costs of the information to the notary are borne by
                # the selling co-owner; the VME pays the syndic and recharges the seller (not automated yet).
                self.env["vme.service.line"]._register_from_source(
                    sale, "sale_file", sale.first_answer_date,
                    _vme_env(sale)._("Verkoopdossier %s", sale.name), recharge_partner=sale.seller_id)
        return result


class VmeDamageClaim(models.Model):
    _inherit = "vme.damage.claim"

    def action_declare(self):
        result = super().action_declare()
        for claim in self:
            self.env["vme.service.line"]._register_from_source(
                claim, "damage_claim", claim.declaration_date, _vme_env(claim)._("Schadedossier %s", claim.display_name))
        return result


class VmeAssembly(models.Model):
    _inherit = "vme.assembly"

    @api.model_create_multi
    def create(self, vals_list):
        assemblies = super().create(vals_list)
        # The ordinary assembly that decides on the renewal gets the agenda point straight away.
        Mandate = self.env["vme.syndic.mandate"]
        for assembly in assemblies.filtered(lambda a: a.assembly_type == "ordinary"):
            mandates = Mandate.search([("association_id", "=", assembly.association_id.id),
                                       ("renewal_assembly_year", "=", assembly.year)])
            for mandate in mandates.filtered(lambda m: not m.next_mandate_id):
                mandate._ensure_renewal_item(assembly)
        return assemblies

    def action_mark_held(self):
        result = super().action_mark_held()
        for assembly in self.filtered(lambda a: a.state == "held"):
            day = assembly.date or fields.Date.context_today(self)
            if assembly.second_session:
                self.env["vme.service.line"]._register_from_source(
                    assembly, "extra_meeting", day, _vme_env(assembly)._("Tweede vergadering %s", assembly.name))
            elif assembly.assembly_type == "extraordinary":
                self.env["vme.service.line"]._register_from_source(assembly, "extraordinary_assembly", day, assembly.name)
        return result


class VmeRegisteredMail(models.Model):
    _inherit = "vme.registered.mail"

    def _register_service(self):
        for registered in self.filtered(lambda r: r.state != "prepared"):
            self.env["vme.service.line"]._register_from_source(
                registered, "registered_mail", registered.deposit_date or registered.date,
                _vme_env(registered)._("Aangetekende zending %(name)s aan %(partner)s",
                           name=registered.name, partner=registered.partner_id.name))

    def action_deposit(self):
        result = super().action_deposit()
        self._register_service()
        return result

    def action_send_electronic(self):
        result = super().action_send_electronic()
        self._register_service()
        return result


def previous_quarter(today):
    """(first day, last day) of the quarter before the one of today."""
    first = date(today.year, 3 * ((today.month - 1) // 3) + 1, 1) - relativedelta(months=3)
    return first, first + relativedelta(months=3, days=-1)
