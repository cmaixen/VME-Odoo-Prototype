from unittest.mock import patch

from odoo.addons.iap.tools import iap_tools
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPartnerAutocomplete(TransactionCase):
    """partner_autocomplete never contacts Odoo's IAP service."""

    def test_no_call_to_the_iap_service(self):
        def fail(*args, **kwargs):
            raise AssertionError("partner_autocomplete contacted the IAP service")

        belgium = self.env.ref("base.be")
        with patch.object(iap_tools, "iap_jsonrpc", fail):
            self.assertFalse(self.env["res.partner"].autocomplete_by_name("Residentie Linde", belgium.id))
            self.assertFalse(self.env["res.partner"].autocomplete_by_vat("BE0000000097", belgium.id))
            self.assertFalse(self.env["res.partner"].enrich_by_domain("example.com").get("name"))
            company = self.env["res.company"].create({"name": "Residentie Autocomplete"})
            company.iap_enrich_auto_done = False
            company.iap_enrich_auto()
            self.assertTrue(company.iap_enrich_auto_done)
