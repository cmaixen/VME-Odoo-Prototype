from odoo import api, fields, models

KEY_TYPES = [
    ("general", "Algemeen"),
    ("elevator", "Lift"),
    ("heating", "Verwarming"),
    ("consumption", "Op verbruik"),
    ("other", "Andere"),
]


class VmeRentChargeCategory(models.Model):
    _name = "vme.rent.charge.category"
    _description = "Rubriek van lasten voor huurders"
    _order = "sequence, id"

    name = fields.Char(string="Rubriek", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    default_tenant_percent = fields.Float(
        string="Standaard ten laste van de huurder (%)", digits=(5, 2),
        help="Overgenomen in elk nieuw huurcontract; per contract aan te passen.",
    )
    partner_ids = fields.Many2many(
        "res.partner", string="Leveranciers",
        help="Kosten van deze leveranciers horen altijd in deze rubriek.",
    )
    key_type = fields.Selection(
        KEY_TYPES, string="Soort sleutel",
        help="Kosten verdeeld met een sleutel van deze soort horen in deze rubriek.",
    )
    account_prefixes = fields.Char(
        string="Kostenrekeningen",
        help="Begin van de kostenrekeningen van deze rubriek, gescheiden door komma's (bv. 612, 6125).",
    )
    note = fields.Text(string="Uitleg")

    @api.model
    def _match(self, allocation):
        """Rubric of a cost allocation of the owner's annual statement.

        A supplier listed on a rubric wins, then the kind of key, then the longest matching
        account prefix. Costs that match nothing stay with the landlord.
        """
        categories = self.search([])
        supplier = allocation.move_id.partner_id.commercial_partner_id
        by_partner = categories.filtered(lambda c: supplier in c.partner_ids.commercial_partner_id)
        if by_partner:
            return by_partner[:1]
        by_key = categories.filtered(lambda c: c.key_type and c.key_type == allocation.key_id.key_type)
        if by_key:
            return by_key[:1]
        # Account codes are per company in Odoo 19: read it in the company of the VME.
        code = allocation.move_line_id.account_id.with_company(allocation.company_id).code or ""
        best, best_length = self.browse(), 0
        for category in categories:
            for prefix in (category.account_prefixes or "").split(","):
                prefix = prefix.strip()
                if prefix and code.startswith(prefix) and len(prefix) > best_length:
                    best, best_length = category, len(prefix)
        return best
