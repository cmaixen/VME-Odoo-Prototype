"""Product website: public pages, the landing after login per type of user, and the demo request
form that only creates a lead (nothing is mailed)."""
import re

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.vme_website.controllers.main import PORTAL_URL, VME_APP_URL

PASSWORD = "website-test-1234"


@tagged("post_install", "-at_install")
class TestProductWebsite(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = new_test_user(cls.env, login="medewerker.web", password=PASSWORD,
                                  groups="base.group_user,account.group_account_invoice")
        cls.owner = new_test_user(cls.env, login="eigenaar.web", password=PASSWORD, groups="base.group_portal")

    def _csrf_token(self, url="/web/login"):
        page = self.url_open(url).text
        # Login form: a hidden input. Website forms: the token in the page's session info script.
        match = re.search(r'name="csrf_token" value="([^"]+)"', page) or re.search(r'csrf_token["\']?\s*:\s*["\']([^"\']+)', page)
        return match.group(1)

    def _login(self, login, redirect=None):
        data = {"login": login, "password": PASSWORD, "csrf_token": self._csrf_token()}
        if redirect:
            data["redirect"] = redirect
        response = self.url_open("/web/login", data=data, allow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text[:500])
        return response.headers["Location"]

    def test_pages_are_public(self):
        for url, text in [("/", "Elke beslissing"), ("/functies", "Rentmeesterij"),
                          ("/voor-eigenaars", "eigenaarsportaal"), ("/prijzen", "Demo aanvragen"),
                          ("/contact", "Voorbeeldstraat 1"), ("/inloggen", "Eigenaar of huurder"),
                          ("/demo-aangevraagd", "Bedankt")]:
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn(text, response.text, url)

    def test_site_in_french(self):
        """With fr_BE installed the site has a French version, menu included (docs/dev/vertaling.md)."""
        self.env["res.lang"]._activate_lang("nl_BE")
        lang = self.env["res.lang"]._activate_lang("fr_BE")
        self.env["ir.module.module"].search([("name", "in", ["website", "vme_website"])])._update_translations(["fr_BE"])
        self.env["website"]._vme_setup_product_website()
        self.assertIn("Elke beslissing", self.url_open("/").text)
        page = self.url_open(f"/{lang.url_code}/").text
        self.assertIn("Chaque décision chez votre collaborateur", page)
        self.assertIn("Fonctionnalités", page)
        self.assertNotIn("Elke beslissing", page)

    def test_header_offers_both_routes(self):
        page = self.url_open("/").text
        self.assertIn(f"/web/login?redirect={VME_APP_URL}", page)
        self.assertIn(f"/web/login?redirect={PORTAL_URL}", page)

    def test_odoo_contact_page_redirects_to_ours(self):
        """Odoo's /contactus mails the company; ours only creates a lead."""
        response = self.url_open("/contactus", allow_redirects=False)
        self.assertIn(response.status_code, (301, 308))
        self.assertTrue(response.headers["Location"].endswith("/contact"))

    def test_staff_lands_in_vme_app(self):
        self.assertTrue(self._login("medewerker.web").endswith(VME_APP_URL))

    def test_staff_choosing_owner_route_still_lands_in_vme_app(self):
        self.assertTrue(self._login("medewerker.web", redirect=PORTAL_URL).endswith(VME_APP_URL))

    def test_owner_lands_in_portal(self):
        self.assertTrue(self._login("eigenaar.web").endswith(PORTAL_URL))

    def test_owner_choosing_staff_route_still_lands_in_portal(self):
        self.assertTrue(self._login("eigenaar.web", redirect=VME_APP_URL).endswith(PORTAL_URL))

    def test_owner_keeps_explicit_portal_link(self):
        """A link from an invitation, e.g. to a document or the online AV, is kept."""
        self.assertTrue(self._login("eigenaar.web", redirect="/my/vme").endswith("/my/vme"))

    def test_demo_form_creates_lead_without_mail(self):
        mails_before = self.env["mail.mail"].sudo().search_count([])
        response = self.url_open("/website/form/crm.lead", data={
            "csrf_token": self._csrf_token("/prijzen"),
            "name": "Demo-aanvraag via de website",
            "contact_name": "Medewerker Test",
            "partner_name": "Syndicuskantoor Test",
            "email_from": "demo.test@example.com",
            "Aantal VME's": "12",
            "description": "Graag de jaarafrekening zien.",
        })
        self.assertEqual(response.status_code, 200, response.text[:500])
        lead = self.env["crm.lead"].browse(response.json()["id"])
        self.assertEqual(lead.contact_name, "Medewerker Test")
        self.assertIn("Aantal VME's : 12", lead.description)
        self.assertFalse(lead.user_id, "nobody is assigned, so nobody gets an automatic mail")
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), mails_before)
