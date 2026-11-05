from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round, formatLang

from .vme_meter import METER_TYPES

SHARES_PRECISION = 2
DEFAULT_FIXED_PERCENT = 30.0


class VmeKey(models.Model):
    _name = "vme.key"
    _description = "Verdeelsleutel"
    _order = "association_id, sequence, name"

    name = fields.Char(string="Naam", required=True)
    sequence = fields.Integer(default=10)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    key_type = fields.Selection(
        [
            ("general", "Algemeen"),
            ("elevator", "Lift"),
            ("heating", "Verwarming"),
            ("consumption", "Op verbruik"),
            ("other", "Andere"),
        ],
        string="Soort",
        required=True,
        default="general",
    )
    # LEGAL-CHECK: art. 3.85 §1 BW - the bylaws (reglement van mede-eigendom) set the criteria
    # and the calculation of the charges, so also a split by consumption and its fixed share.
    meter_type = fields.Selection(
        METER_TYPES,
        string="Tellers",
        default="heating",
        help="Welke tellers van de kavels het verbruik geven voor het variabele deel.",
    )
    fixed_percent = fields.Float(
        string="Vast deel (%)",
        default=DEFAULT_FIXED_PERCENT,
        digits=(5, 2),
        help="Dit deel van de kost wordt verdeeld volgens de quotiteiten van deze sleutel, "
             "de rest volgens het werkelijke verbruik in de kostperiode.",
    )
    variable_percent = fields.Float(string="Variabel deel (%)", compute="_compute_variable_percent", digits=(5, 2))
    total_shares = fields.Float(
        string="Totaal", required=True, default=1000.0, digits=(16, SHARES_PRECISION)
    )
    line_ids = fields.One2many("vme.key.line", "key_id", string="Quotiteiten", copy=True)
    shares_sum = fields.Float(
        string="Som quotiteiten", compute="_compute_shares_sum", digits=(16, SHARES_PRECISION)
    )
    shares_difference = fields.Float(
        string="Verschil", compute="_compute_shares_sum", digits=(16, SHARES_PRECISION)
    )
    is_balanced = fields.Boolean(string="Klopt", compute="_compute_shares_sum")

    @api.depends("fixed_percent")
    def _compute_variable_percent(self):
        for key in self:
            key.variable_percent = 100.0 - key.fixed_percent

    @api.constrains("key_type", "fixed_percent", "meter_type")
    def _check_consumption_settings(self):
        for key in self.filtered(lambda k: k.key_type == "consumption"):
            if not 0 <= key.fixed_percent <= 100:
                raise ValidationError(self.env._("Het vaste deel moet tussen 0 en 100% liggen."))
            if not key.meter_type and key.fixed_percent < 100:
                raise ValidationError(self.env._("Kies welke tellers het verbruik geven."))

    @api.depends("line_ids.shares", "total_shares")
    def _compute_shares_sum(self):
        for key in self:
            key.shares_sum = sum(key.line_ids.mapped("shares"))
            key.shares_difference = float_round(
                key.total_shares - key.shares_sum, precision_digits=SHARES_PRECISION
            )
            key.is_balanced = not float_compare(
                key.shares_sum, key.total_shares, precision_digits=SHARES_PRECISION
            )

    def write(self, vals):
        # Line commands are applied one by one; the key constraint checks the end result.
        return super(VmeKey, self.with_context(vme_skip_line_check=True)).write(vals)

    @api.constrains("total_shares", "line_ids")
    def _check_shares_sum(self):
        # LEGAL-CHECK: art. 3.85 §1 BW - the deed of division sets each lot's share
        # in the common parts; the shares of a key must add up to its total.
        for key in self:
            if float_compare(key.total_shares, 0.0, precision_digits=SHARES_PRECISION) <= 0:
                raise ValidationError(self.env._("Het totaal van een sleutel moet groter zijn dan 0."))
            if key.line_ids and not key.is_balanced:
                raise ValidationError(self.env._(
                    "De quotiteiten van sleutel '%(key)s' tellen op tot %(sum)s, "
                    "maar het totaal is %(total)s (verschil: %(diff)s).",
                    key=key.display_name,
                    sum=formatLang(self.env, key.shares_sum, digits=SHARES_PRECISION),
                    total=formatLang(self.env, key.total_shares, digits=SHARES_PRECISION),
                    diff=formatLang(self.env, key.shares_difference, digits=SHARES_PRECISION),
                ))


class VmeKeyLine(models.Model):
    _name = "vme.key.line"
    _description = "Quotiteit per kavel"
    _order = "key_id, lot_id"

    key_id = fields.Many2one("vme.key", string="Sleutel", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="key_id.association_id", store=True)
    company_id = fields.Many2one(related="key_id.company_id", store=True)
    lot_id = fields.Many2one(
        "vme.lot",
        string="Kavel",
        required=True,
        ondelete="restrict",
        domain="[('association_id', '=', association_id)]",
    )
    shares = fields.Float(string="Quotiteit", digits=(16, SHARES_PRECISION))
    percentage = fields.Float(string="Aandeel (%)", compute="_compute_percentage", digits=(16, 2))

    _unique_lot_per_key = models.Constraint(
        "UNIQUE (key_id, lot_id)",
        "Een kavel kan maar één keer voorkomen in een sleutel.",
    )

    @api.depends("shares", "key_id.total_shares")
    def _compute_percentage(self):
        for line in self:
            total = line.key_id.total_shares
            line.percentage = line.shares / total * 100 if total else 0.0

    def write(self, vals):
        # Lines edited outside their key's form bypass the key constraint, so re-check it.
        result = super().write(vals)
        if ("shares" in vals or "key_id" in vals) and not self.env.context.get("vme_skip_line_check"):
            self.key_id._check_shares_sum()
        return result

    def unlink(self):
        keys = self.key_id
        result = super().unlink()
        if not self.env.context.get("vme_skip_line_check"):
            keys.exists()._check_shares_sum()
        return result

    @api.constrains("lot_id", "key_id")
    def _check_lot_association(self):
        for line in self:
            if line.lot_id.association_id != line.key_id.association_id:
                raise ValidationError(self.env._(
                    "Kavel %(lot)s hoort niet bij dezelfde VME als sleutel %(key)s.",
                    lot=line.lot_id.display_name,
                    key=line.key_id.display_name,
                ))
