from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VmeDistributionRule(models.Model):
    _name = "vme.distribution.rule"
    _description = "Verdeelregel"
    _order = "association_id, partner_id"
    _check_company_auto = True

    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Leverancier", required=True, index=True)
    key_id = fields.Many2one(
        "vme.key",
        string="Verdeelsleutel",
        required=True,
        ondelete="restrict",
        domain="[('association_id', '=', association_id)]",
    )
    account_id = fields.Many2one(
        "account.account",
        string="Boeken op rekening",
        check_company=True,
        domain="[('company_ids', 'in', company_id), ('account_type', 'in', ('expense', 'expense_direct_cost'))]",
        help="Optioneel: factuurlijnen zonder product van deze leverancier worden op deze rekening geboekt.",
    )
    installation_id = fields.Many2one(
        "vme.installation",
        string="Installatie",
        domain="[('association_id', '=', association_id)]",
        help="Optioneel: een geboekte factuur van het keuringsorganisme van deze installatie "
             "registreert automatisch een keuring en verschuift de volgende vervaldatum.",
    )
    active = fields.Boolean(string="Actief", default=True)
    note = fields.Char(string="Notitie")

    _unique_supplier_per_association = models.Constraint(
        "UNIQUE (association_id, partner_id)",
        "Er bestaat al een verdeelregel voor deze leverancier in deze VME.",
    )

    @api.constrains("key_id", "association_id")
    def _check_key_association(self):
        for rule in self:
            if rule.key_id.association_id != rule.association_id:
                raise ValidationError(self.env._(
                    "Sleutel %(key)s hoort niet bij %(vme)s.",
                    key=rule.key_id.display_name, vme=rule.association_id.display_name,
                ))

    @api.model
    def _find_rule(self, company, partner):
        """Active rule of the VME behind this company for this supplier (or its commercial parent)."""
        if not company or not partner:
            return self.browse()
        return self.search([
            ("company_id", "=", company.id),
            ("partner_id", "in", (partner | partner.commercial_partner_id).ids),
        ], limit=1)
