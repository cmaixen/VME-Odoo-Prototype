from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VmeOwnership(models.Model):
    _name = "vme.ownership"
    _description = "Eigendom van een kavel"
    _order = "lot_id, date_start desc"

    lot_id = fields.Many2one("vme.lot", string="Kavel", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="lot_id.association_id", store=True)
    company_id = fields.Many2one(related="lot_id.company_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Eigenaar", required=True, index=True)
    date_start = fields.Date(string="Begindatum", required=True)
    date_end = fields.Date(string="Einddatum", help="Leeg laten zolang deze persoon eigenaar is.")

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for ownership in self:
            if ownership.date_end and ownership.date_end < ownership.date_start:
                raise ValidationError(self.env._("De einddatum moet na de begindatum liggen."))

    @api.constrains("lot_id", "date_start", "date_end")
    def _check_no_overlap(self):
        # Prototype simplification: one owner per lot at a time, so a sale is an
        # ownership ending the day before the next one starts.
        for ownership in self:
            others = ownership.lot_id.ownership_ids - ownership
            for other in others:
                starts_before_other_ends = not other.date_end or ownership.date_start <= other.date_end
                ends_after_other_starts = not ownership.date_end or ownership.date_end >= other.date_start
                if starts_before_other_ends and ends_after_other_starts:
                    raise ValidationError(self.env._(
                        "Kavel %(lot)s heeft al een eigenaar in deze periode (%(owner)s).",
                        lot=ownership.lot_id.display_name,
                        owner=other.partner_id.display_name,
                    ))
