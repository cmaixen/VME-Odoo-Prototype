from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _vme_portal_tenant_lots(self):
        """The tenant lots of the portal (vme_belgie), plus the lots of the partner's leases."""
        lots = super()._vme_portal_tenant_lots()
        today = fields.Date.context_today(self)
        contracts = self.env["vme.rent.contract"].sudo().search([
            ("tenant_ids", "in", self._vme_owner().ids), ("date_start", "<=", today),
            ("state", "in", ("active", "notice", "ended")),
        ])
        # Whether the lease still runs today is decided by vme.lot._get_tenants_on.
        return lots | contracts.lot_ids
