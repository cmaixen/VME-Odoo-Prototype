import base64

from odoo import api, models
from odoo.tools.misc import file_open

PRODUCT_NAME = "Quotis"

# (name, url) of the main menu; the pages themselves are website.page records in data/page_data.xml.
MAIN_MENU = [
    ("Home", "/"),
    ("Functies", "/functies"),
    ("Voor eigenaars", "/voor-eigenaars"),
    ("Prijzen", "/prijzen"),
    ("Contact", "/contact"),
]


class Website(models.Model):
    _inherit = "website"

    @api.model
    def _vme_setup_product_website(self):
        """Turn the default website into the product website: name, logo, language and menu.

        Called from data on every install and upgrade. The menu is only rebuilt while it is
        still Odoo's default one, so changes made later in the website editor stay.
        """
        website = self.env.ref("website.default_website")
        values = {
            "name": PRODUCT_NAME,
            # No onboarding wizard ("configurator") when a user opens the website.
            "configurator_done": True,
            # Leads from the demo form get no salesperson: nobody is notified automatically.
            "crm_default_user_id": False,
        }
        if website.name != PRODUCT_NAME:
            with file_open("vme_website/static/src/img/logo.svg", "rb") as logo:
                values["logo"] = base64.b64encode(logo.read())
        lang = self.env["res.lang"]._lang_get("nl_BE")
        if lang:
            values.update({"language_ids": [(4, lang.id)], "default_lang_id": lang.id})
        website.write(values)
        # Odoo's contact page mails the company (mail.mail). Unpublished, the redirect in
        # data/page_data.xml sends visitors to our form, which only creates a lead.
        self.env.ref("website.contactus_page").is_published = False

        menu = website.menu_id
        if menu and not menu.child_id.filtered(lambda m: m.url == "/functies"):
            menu.child_id.unlink()
            pages = self.env["website.page"].search([("url", "in", [url for _name, url in MAIN_MENU])])
            self.env["website.menu"].create([{
                "name": name,
                "url": url,
                "page_id": pages.filtered(lambda p, url=url: p.url == url)[:1].id,
                "parent_id": menu.id,
                "website_id": website.id,
                "sequence": (index + 1) * 10,
            } for index, (name, url) in enumerate(MAIN_MENU)])
