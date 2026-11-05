from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

METER_TYPES = [
    ("water", "Water"),
    ("heating", "Verwarming (kostenverdeler)"),
    ("electricity", "Elektriciteit"),
]
METER_UNITS = {"water": "m³", "heating": "eenheden", "electricity": "kWh"}


class MissingReading(Exception):
    """A meter has no reading before or after a date, so its index there is unknown."""

    def __init__(self, meter, day):
        super().__init__(meter, day)
        self.meter = meter
        self.day = day


class VmeMeter(models.Model):
    _name = "vme.meter"
    _description = "Teller"
    _order = "association_id, lot_id, meter_type, name"

    name = fields.Char(string="Tellernummer", required=True)
    active = fields.Boolean(string="Actief", default=True)
    lot_id = fields.Many2one("vme.lot", string="Kavel", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="lot_id.association_id", store=True, index=True)
    company_id = fields.Many2one(related="lot_id.company_id", store=True)
    meter_type = fields.Selection(METER_TYPES, string="Soort", required=True, default="heating")
    factor = fields.Float(
        string="Coëfficiënt",
        default=1.0,
        aggregator=None,
        digits=(16, 4),
        help="Verbruik = verschil in meterstand × coëfficiënt. Voor een kostenverdeler is dat de "
             "coëfficiënt van de radiator; voor een water- of elektriciteitsteller meestal 1.",
    )
    location = fields.Char(string="Plaats", help="bv. Woonkamer, Keuken")
    unit = fields.Char(string="Eenheid", compute="_compute_unit")
    reading_ids = fields.One2many("vme.meter.reading", "meter_id", string="Meterstanden")
    last_reading_date = fields.Date(string="Laatste opname", compute="_compute_last_reading")
    last_reading_value = fields.Float(
        string="Laatste stand", compute="_compute_last_reading", digits=(16, 3), aggregator=None
    )

    _unique_name_per_association = models.Constraint(
        "UNIQUE (association_id, name)",
        "Een tellernummer kan maar één keer voorkomen binnen de VME.",
    )

    @api.depends("meter_type")
    def _compute_unit(self):
        for meter in self:
            meter.unit = METER_UNITS.get(meter.meter_type, "")

    @api.depends("reading_ids.date", "reading_ids.value")
    def _compute_last_reading(self):
        for meter in self:
            last = meter.reading_ids.sorted("date")[-1:]
            meter.last_reading_date = last.date
            meter.last_reading_value = last.value

    @api.constrains("factor")
    def _check_factor(self):
        for meter in self:
            if meter.factor <= 0:
                raise ValidationError(self.env._("De coëfficiënt van teller %s moet groter zijn dan 0.", meter.name))

    def _index_at(self, day):
        """Meter index at the end of `day`.

        A reading dated d is the index at the end of day d. Between two readings the index is
        interpolated linearly per day; before the first or after the last reading it is unknown.
        """
        self.ensure_one()
        readings = self.reading_ids.sorted("date")
        before = readings.filtered(lambda r: r.date <= day)[-1:]
        if before and before.date == day:
            return before.value
        after = readings.filtered(lambda r: r.date > day)[:1]
        if not before or not after:
            raise MissingReading(self, day)
        span = (after.date - before.date).days
        return before.value + (after.value - before.value) * (day - before.date).days / span

    def _consumption(self, date_from, date_to):
        """Consumption from the start of `date_from` to the end of `date_to`, times the factor."""
        self.ensure_one()
        return (self._index_at(date_to) - self._index_at(date_from - timedelta(days=1))) * self.factor


class VmeMeterReading(models.Model):
    _name = "vme.meter.reading"
    _description = "Meterstand"
    _order = "meter_id, date desc"
    _rec_name = "date"

    meter_id = fields.Many2one("vme.meter", string="Teller", required=True, ondelete="cascade", index=True)
    lot_id = fields.Many2one(related="meter_id.lot_id", store=True)
    association_id = fields.Many2one(related="meter_id.association_id", store=True)
    meter_type = fields.Selection(related="meter_id.meter_type", store=True)
    unit = fields.Char(related="meter_id.unit")
    date = fields.Date(string="Datum", required=True, help="Stand op het einde van deze dag.")
    # Summing meter indexes means nothing, so no group totals.
    value = fields.Float(string="Stand", required=True, digits=(16, 3), aggregator=None)
    source = fields.Selection(
        [("manual", "Manueel"), ("import", "Import")], string="Bron", required=True, default="manual"
    )
    import_ref = fields.Char(string="Importbestand")

    _unique_date_per_meter = models.Constraint(
        "UNIQUE (meter_id, date)",
        "Een teller kan maar één meterstand per dag hebben.",
    )

    @api.constrains("value", "date", "meter_id")
    def _check_increasing(self):
        # A meter that is replaced or reset gets a new meter record, so readings only go up.
        for reading in self:
            others = reading.meter_id.reading_ids - reading
            lower_later = others.filtered(
                lambda r: r.date > reading.date and float_compare(r.value, reading.value, precision_digits=3) < 0
            )
            higher_earlier = others.filtered(
                lambda r: r.date < reading.date and float_compare(r.value, reading.value, precision_digits=3) > 0
            )
            if lower_later or higher_earlier:
                raise ValidationError(self.env._(
                    "De stand %(value)s van teller %(meter)s op %(date)s is lager dan een vroegere stand "
                    "of hoger dan een latere. Is de teller vervangen, maak dan een nieuwe teller aan.",
                    value=reading.value, meter=reading.meter_id.name, date=reading.date.strftime("%d/%m/%Y"),
                ))
