from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class VmeRentSettlement(models.Model):
    _name = "vme.rent.settlement"
    _inherit = ["mail.thread"]
    _description = "Afrekening van lasten aan de huurder"
    _order = "year desc, id desc"

    contract_id = fields.Many2one("vme.rent.contract", string="Huurcontract", required=True, ondelete="cascade",
                                  index=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True)
    currency_id = fields.Many2one(related="contract_id.currency_id")
    association_id = fields.Many2one(related="contract_id.association_id", store=True, string="VME")
    landlord_id = fields.Many2one(related="contract_id.landlord_id", store=True, string="Verhuurder")
    tenant_id = fields.Many2one(related="contract_id.tenant_id", store=True, string="Huurder")
    year = fields.Integer(string="Jaar", required=True)
    state = fields.Selection([("draft", "Concept"), ("invoiced", "Gefactureerd")], string="Status", default="draft",
                             required=True, tracking=True)
    date_from = fields.Date(string="Huur van")
    date_to = fields.Date(string="Huur tot")
    line_ids = fields.One2many("vme.rent.settlement.line", "settlement_id", string="Kosten")
    owner_total = fields.Monetary(string="Kosten van de verhuurder")
    tenant_total = fields.Monetary(string="Ten laste van de huurder")
    provisions = fields.Monetary(string="Provisies lasten")
    balance = fields.Monetary(string="Saldo", help="Positief: de huurder betaalt bij. Negatief: de huurder krijgt terug.")
    statement_incomplete = fields.Boolean(string="Jaarafrekening VME onvolledig")
    invoice_id = fields.Many2one("account.move", string="Factuur", readonly=True, copy=False)

    _unique_year = models.Constraint("UNIQUE (contract_id, year)", "Er is al een afrekening voor dit contract en jaar.")

    @api.depends("contract_id.name", "year")
    def _compute_display_name(self):
        for settlement in self:
            settlement.display_name = self.env._(
                "Afrekening lasten %(year)s - %(contract)s", year=settlement.year, contract=settlement.contract_id.name or "")

    def _lease_period(self):
        contract = self.contract_id
        ends = [d for d in (contract.date_end, contract.notice_end_date, contract.date_moved_out) if d]
        return contract.date_start, min(ends)

    def _prepare_values(self):
        """Tenant share of the landlord's annual statement of the VME, per bill and rubric.

        The bills, and the landlord's share in them, come from vme.association._get_annual_statement.
        Only the costs of the rented lots count, for the days of the cost period the lease ran,
        times the percentage of the rubric in the contract.
        """
        self.ensure_one()
        contract = self.contract_id
        # LEGAL-CHECK: art. 1728ter oud BW, art. 35 VWHD, art. 221 BHC, art. 32 Waals decreet 15-03-2018 - alleen werkelijke kosten worden
        # afgerekend, met de stukken; forfaitaire lasten worden nooit afgerekend.
        if contract.charges_type == "forfait":
            raise UserError(self.env._("Forfaitaire lasten worden niet afgerekend."))
        if not contract.association_id:
            raise UserError(self.env._("Alleen een contract voor kavels van een VME kan uit de jaarafrekening afrekenen."))
        currency = contract.currency_id
        lease_start, lease_end = self._lease_period()
        year_start, year_end = date(self.year, 1, 1), date(self.year, 12, 31)
        if lease_start > year_end or lease_end < year_start:
            raise UserError(self.env._("Het contract liep niet in %s.", self.year))

        statement = contract.association_id._get_annual_statement(self.year, partners=contract.landlord_id)
        owner = statement["statements"][0] if statement["statements"] else {"bills": [], "partner": contract.landlord_id}
        percents = {line.category_id: line.tenant_percent for line in contract.charge_line_ids}
        Category = self.env["vme.rent.charge.category"]
        lines = []
        for bill in owner["bills"]:
            move = bill["move"]
            allocations = move.vme_allocation_ids.filtered(
                lambda a: a.partner_id == contract.landlord_id and a.lot_id in contract.lot_ids)
            groups = {}
            for allocation in allocations:
                category = Category._match(allocation)
                group = groups.setdefault(category, {"owner": 0.0, "share": 0.0, "days": 0, "period": 0,
                                                     "lots": set(), "keys": set()})
                days = (allocation.date_to - allocation.date_from).days + 1
                overlap_start, overlap_end = max(allocation.date_from, lease_start), min(allocation.date_to, lease_end)
                overlap = max((overlap_end - overlap_start).days + 1, 0)
                group["owner"] += allocation.amount
                group["share"] += allocation.amount * overlap / days if days else 0.0
                group["days"] = max(group["days"], overlap)
                group["period"] = max(group["period"], days)
                group["lots"].add(allocation.lot_id.name)
                group["keys"].add(allocation.key_id.name)
            for category, group in groups.items():
                percent = percents.get(category, 0.0) if category else 0.0
                share = currency.round(group["share"])
                lines.append(Command.create({
                    "move_id": move.id,
                    "move_name": move.name,
                    "supplier": bill["supplier"],
                    "description": bill["description"],
                    "period_start": bill["period"][0],
                    "period_end": bill["period"][1],
                    "category_id": category.id if category else False,
                    "keys": ", ".join(sorted(group["keys"])),
                    "lots": ", ".join(sorted(group["lots"])),
                    "owner_amount": currency.round(group["owner"]),
                    "lease_days": group["days"],
                    "period_days": group["period"],
                    "lease_amount": share,
                    "tenant_percent": percent,
                    "tenant_amount": currency.round(share * percent / 100),
                }))

        provision_lines = contract.sudo().invoice_ids.filtered(
            lambda m: m.state == "posted" and m.rent_period and m.rent_period.year == self.year
        ).invoice_line_ids.filtered(lambda line: line.rent_line_type == "charges")
        provisions = currency.round(sum(provision_lines.mapped("price_subtotal")))
        tenant_total = currency.round(sum(command[2]["tenant_amount"] for command in lines))
        return {
            "date_from": max(lease_start, year_start),
            "date_to": min(lease_end, year_end),
            "line_ids": [Command.clear()] + lines,
            "owner_total": currency.round(sum(command[2]["owner_amount"] for command in lines)),
            "tenant_total": tenant_total,
            "provisions": provisions,
            "balance": currency.round(tenant_total - provisions),
            "statement_incomplete": not statement["is_complete"],
        }

    @api.model_create_multi
    def create(self, vals_list):
        settlements = super().create(vals_list)
        for settlement in settlements:
            settlement.write(settlement._prepare_values())
        return settlements

    def action_recompute(self):
        for settlement in self:
            if settlement.state != "draft":
                raise UserError(self.env._("Een gefactureerde afrekening wordt niet meer herberekend."))
            settlement.write(settlement._prepare_values())

    def action_create_invoice(self):
        """Draft invoice (or credit note) to the tenant. Nothing is posted or sent."""
        for settlement in self:
            if settlement.invoice_id:
                continue
            contract = settlement.contract_id
            currency = settlement.currency_id
            account = contract.company_id._rent_account()
            analytic = {str(contract.analytic_account_id.id): 100} if contract.analytic_account_id else False

            def line(name, amount):
                return Command.create({
                    "name": name, "quantity": 1, "price_unit": amount, "account_id": account.id,
                    "tax_ids": [Command.clear()], "analytic_distribution": analytic, "rent_line_type": "settlement",
                })

            if currency.compare_amounts(settlement.balance, 0) >= 0:
                move_type = "out_invoice"
                lines = []
                for category, amount in settlement._totals_per_category():
                    lines.append(line(self.env._("Lasten %(year)s: %(category)s", year=settlement.year,
                                                 category=category.name), amount))
                lines.append(line(self.env._("Provisies lasten %s", settlement.year), -settlement.provisions))
            else:
                move_type = "out_refund"
                lines = [line(self.env._("Teveel betaalde provisies lasten %s", settlement.year), -settlement.balance)]
            settlement.invoice_id = self.env["account.move"].with_company(contract.company_id).create({
                "move_type": move_type,
                "partner_id": contract.tenant_id.id,
                "invoice_date": fields.Date.context_today(self),
                "rent_contract_id": contract.id,
                "ref": self.env._("Afrekening lasten %s", settlement.year),
                "narration": self.env._("Afrekening in naam en voor rekening van %(landlord)s (verhuurder).",
                                        landlord=contract.landlord_id.name),
                "invoice_line_ids": lines,
            })
            settlement.state = "invoiced"
        return self[:1].action_open_invoice() if len(self) == 1 else True

    def _totals_per_category(self):
        totals = {}
        for line in self.line_ids.filtered(lambda l: l.category_id and not self.currency_id.is_zero(l.tenant_amount)):
            totals[line.category_id] = totals.get(line.category_id, 0.0) + line.tenant_amount
        return sorted(totals.items(), key=lambda item: (item[0].sequence, item[0].id))

    def action_open_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "context": {"allowed_company_ids": [self.company_id.id]},
        }

    def action_print(self):
        return self.env.ref("vme_rentmeester.action_report_rent_settlement").report_action(self)


class VmeRentSettlementLine(models.Model):
    _name = "vme.rent.settlement.line"
    _description = "Kost in de afrekening aan de huurder"
    _order = "settlement_id, period_start, id"

    settlement_id = fields.Many2one("vme.rent.settlement", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="settlement_id.currency_id")
    # The bill lives in the company of the VME: a link would fail for a user who only selected
    # the office's company, so the views show its number as text.
    move_id = fields.Many2one("account.move", string="Factuur VME")
    move_name = fields.Char(string="Factuur")
    supplier = fields.Char(string="Leverancier")
    description = fields.Char(string="Omschrijving")
    period_start = fields.Date(string="Periode van")
    period_end = fields.Date(string="Periode tot")
    category_id = fields.Many2one("vme.rent.charge.category", string="Rubriek")
    keys = fields.Char(string="Sleutel")
    lots = fields.Char(string="Kavels")
    owner_amount = fields.Monetary(string="Aandeel verhuurder")
    lease_days = fields.Integer(string="Dagen verhuurd", aggregator=None)
    period_days = fields.Integer(string="Dagen periode", aggregator=None)
    lease_amount = fields.Monetary(string="Tijdens de huur")
    tenant_percent = fields.Float(string="% huurder", digits=(5, 2), aggregator=None)
    tenant_amount = fields.Monetary(string="Ten laste van de huurder")
