from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from .rent_rules import IndexMissing


class VmeRentIndex(models.Model):
    _name = "vme.rent.index"
    _description = "Gezondheidsindex"
    _order = "month desc"
    _rec_name = "month"

    month = fields.Date(string="Maand", required=True, help="Eerste dag van de maand.")
    value = fields.Float(string="Gezondheidsindex", required=True, digits=(16, 2),
                         help="Gezondheidsindex met basis 2013 = 100, zoals Statbel die elke maand publiceert.")

    _unique_month = models.Constraint("UNIQUE (month)", "Elke maand heeft maar één indexcijfer.")
    _positive_value = models.Constraint("CHECK (value > 0)", "Een indexcijfer is groter dan nul.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("month"):
                vals["month"] = fields.Date.to_date(vals["month"]).replace(day=1)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("month"):
            vals["month"] = fields.Date.to_date(vals["month"]).replace(day=1)
        return super().write(vals)

    @api.model
    def _lookup(self, month):
        """Health index of a month; raises IndexMissing when the table has no figure yet."""
        record = self.search([("month", "=", month.replace(day=1))], limit=1)
        if not record:
            raise IndexMissing(month)
        return record.value

    @api.model
    def _missing_error(self, month):
        return UserError(self.env._(
            "De gezondheidsindex van %s staat nog niet in de tabel. Vul hem aan onder "
            "Rentmeester > Configuratie > Gezondheidsindex.", format_date(self.env, month, date_format="MMMM y")))
