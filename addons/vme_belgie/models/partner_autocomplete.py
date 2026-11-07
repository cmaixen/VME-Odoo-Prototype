"""No partner data to Odoo's IAP service.

partner_autocomplete installs itself (auto_install) and sends typed names, VAT numbers and the
mail domain of every new company to partner-autocomplete.odoo.com (and VAT numbers to VIES). A VME platform keeps owner and
supplier data in house, so every call stops here and the service returns no suggestions.
"""
from odoo import api, models


class IapAutocompleteApi(models.AbstractModel):
    _inherit = "iap.autocomplete.api"

    @api.model
    def _request_partner_autocomplete(self, action, params, timeout=15):
        return False, "disabled"


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def autocomplete_by_vat(self, vat, query_country_id, timeout=15):
        # Without IAP Odoo falls back to the VIES service of the EU: no outside call here either.
        return []


class ResCompany(models.Model):
    _inherit = "res.company"

    def iap_enrich_auto(self):
        # Every VME is a company: never enrich it from outside, and do not try again later.
        self.sudo().iap_enrich_auto_done = True
        return True
