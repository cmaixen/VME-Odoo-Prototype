from odoo import api, fields, models
from odoo.exceptions import ValidationError

from . import remittance_rules as rules


class VmeRentMandate(models.Model):
    _name = "vme.rent.mandate"
    _inherit = ["mail.thread"]
    _description = "Beheermandaat van een verhuurder"
    _order = "landlord_id, date_start desc, id desc"

    name = fields.Char(string="Mandaat", compute="_compute_name", store=True)
    landlord_id = fields.Many2one("res.partner", string="Verhuurder", required=True, index=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Rentmeesterkantoor", required=True,
        default=lambda self: self.env["vme.rent.contract"]._default_company())
    currency_id = fields.Many2one(related="company_id.currency_id")
    date_start = fields.Date(string="Begin", required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string="Einde", tracking=True)
    active = fields.Boolean(default=True)
    fee_type = fields.Selection([("percent", "Percentage van de ontvangen huur"), ("fixed", "Vast bedrag per maand")],
                                string="Ereloon", required=True, default="percent", tracking=True)
    fee_percent = fields.Float(string="Percentage", digits=(5, 2), default=7.0, tracking=True)
    fee_on_charges = fields.Boolean(
        string="Ook op de lasten",
        help="Het percentage geldt dan op huur en lasten samen; anders alleen op de huur.")
    fee_amount = fields.Monetary(string="Vast bedrag per maand", tracking=True, help="Zonder btw.")
    fee_tax_id = fields.Many2one(
        "account.tax", string="Btw op het ereloon", default=lambda self: self._default_fee_tax(),
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', company_id)]")
    partner_bank_id = fields.Many2one(
        "res.partner.bank", string="Rekening van de verhuurder", tracking=True,
        domain="[('partner_id', '=', landlord_id)]",
        help="Hierop wordt het saldo doorgestort. Odoo betaalt alleen naar een bevestigde rekening.")
    bank_untrusted = fields.Boolean(compute="_compute_bank_untrusted")
    contract_ids = fields.One2many("vme.rent.contract", "mandate_id", string="Huurcontracten")
    notes = fields.Html(string="Notities")

    _fee_percent_range = models.Constraint("CHECK (fee_percent >= 0 AND fee_percent <= 100)",
                                           "Het percentage ligt tussen 0 en 100.")
    _fee_amount_positive = models.Constraint("CHECK (fee_amount >= 0)", "Het vaste ereloon kan niet negatief zijn.")

    @api.model
    def _default_fee_tax(self):
        company = self.env["vme.rent.contract"]._default_company()
        return company._rent_fee_tax()

    @api.depends("landlord_id.name", "date_start")
    def _compute_name(self):
        for mandate in self:
            mandate.name = self.env._("Beheermandaat %(landlord)s", landlord=mandate.landlord_id.name or "")

    @api.depends("partner_bank_id.allow_out_payment")
    def _compute_bank_untrusted(self):
        for mandate in self:
            mandate.bank_untrusted = bool(mandate.partner_bank_id) and not mandate.partner_bank_id.allow_out_payment

    @api.constrains("landlord_id", "company_id", "date_start", "date_end", "active")
    def _check_overlap(self):
        for mandate in self.filtered("active"):
            if mandate.date_end and mandate.date_end < mandate.date_start:
                raise ValidationError(self.env._("Het einde van het mandaat ligt vóór het begin."))
            others = self.search([
                ("id", "!=", mandate.id), ("landlord_id", "=", mandate.landlord_id.id),
                ("company_id", "=", mandate.company_id.id),
            ])
            for other in others:
                if (not other.date_end or other.date_end >= mandate.date_start) and \
                        (not mandate.date_end or mandate.date_end >= other.date_start):
                    raise ValidationError(self.env._(
                        "%s heeft al een beheermandaat in die periode.", mandate.landlord_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        mandates = super().create(vals_list)
        for mandate in mandates:
            contracts = self.env["vme.rent.contract"].search([
                ("landlord_id", "=", mandate.landlord_id.id), ("company_id", "=", mandate.company_id.id),
                ("mandate_id", "=", False)])
            contracts.mandate_id = mandate
        return mandates

    def _get_fee_tax(self):
        """The VAT of the mandate, or 21% on services of the office when it was left empty."""
        self.ensure_one()
        return self.fee_tax_id or self.company_id._rent_fee_tax()

    def _fee_untaxed(self, rent, charges, month, last_charged=None):
        """Fee without VAT for the rent and charges received in a remittance (see remittance_rules)."""
        self.ensure_one()
        if self.fee_type == "percent":
            base = rent + (charges if self.fee_on_charges else 0.0)
            return rules.percent_fee(base, self.fee_percent), base, 0
        months = rules.months_to_charge(month, self.date_start, last_charged, self.date_end)
        return rules.fixed_fee(self.fee_amount, months), 0.0, months

    def action_open_remittances(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Doorstortingen"),
            "res_model": "vme.rent.remittance",
            "view_mode": "list,form",
            "domain": [("landlord_id", "=", self.landlord_id.id)],
            "context": {"default_landlord_id": self.landlord_id.id},
        }


class VmeRentContract(models.Model):
    _inherit = "vme.rent.contract"

    mandate_id = fields.Many2one(
        "vme.rent.mandate", string="Beheermandaat", index=True, tracking=True,
        domain="[('landlord_id', '=', landlord_id), ('company_id', '=', company_id)]",
        help="Bepaalt het ereloon van de rentmeester en de rekening waarop de huur doorgestort wordt.")

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        for contract in contracts.filtered(lambda c: not c.mandate_id):
            contract.mandate_id = contract._find_mandate()
        return contracts

    def write(self, vals):
        result = super().write(vals)
        if "landlord_id" in vals and "mandate_id" not in vals:
            for contract in self:
                contract.mandate_id = contract._find_mandate()
        return result

    def _find_mandate(self):
        self.ensure_one()
        return self.env["vme.rent.mandate"].search([
            ("landlord_id", "=", self.landlord_id.id), ("company_id", "=", self.company_id.id)],
            order="date_start desc", limit=1)

    def action_open_remittances(self):
        self.ensure_one()
        return self.mandate_id.action_open_remittances() if self.mandate_id else {
            "type": "ir.actions.act_window",
            "name": self.env._("Doorstortingen"),
            "res_model": "vme.rent.remittance",
            "view_mode": "list,form",
            "domain": [("landlord_id", "=", self.landlord_id.id)],
        }
