import base64

from odoo import api, models
from odoo.tools.misc import file_open
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

PRODUCT_NAME = "Quotis"
# Languages of the site, the first is the default; a language that is not installed is skipped.
LANGUAGES = ["nl_BE", "fr_BE"]

# (name, url) of the main menu; the pages themselves are website.page records in data/page_data.xml.
MAIN_MENU = [
    (_lt("Home"), "/"),
    (_lt("Functies"), "/functies"),
    (_lt("Voor eigenaars"), "/voor-eigenaars"),
    (_lt("Prijzen"), "/prijzen"),
    (_lt("Contact"), "/contact"),
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
        langs = self.env["res.lang"].search([("code", "in", LANGUAGES)])
        if langs:
            default = langs.filtered(lambda l: l.code == LANGUAGES[0]) or langs[:1]
            values.update({"language_ids": [(4, lang.id) for lang in langs], "default_lang_id": default.id})
        website.write(values)
        # Odoo's contact page mails the company (mail.mail). Unpublished, the redirect in
        # data/page_data.xml sends visitors to our form, which only creates a lead.
        self.env.ref("website.contactus_page").is_published = False

        menu = website.menu_id
        if menu and not menu.child_id.filtered(lambda m: m.url == "/functies"):
            menu.child_id.unlink()
            pages = self.env["website.page"].search([("url", "in", [url for _name, url in MAIN_MENU])])
            # The source text (Dutch) is the value in en_US, which is always installed.
            nl_env = self.with_context(lang="en_US").env
            self.env["website.menu"].create([{
                "name": nl_env._(name),
                "url": url,
                "page_id": pages.filtered(lambda p, url=url: p.url == url)[:1].id,
                "parent_id": menu.id,
                "website_id": website.id,
                "sequence": (index + 1) * 10,
            } for index, (name, url) in enumerate(MAIN_MENU)])

        # Menu names in the other languages (also for a menu made before a language was installed).
        for menu_item in menu.child_id if menu else []:
            name = next((name for name, url in MAIN_MENU if url == menu_item.url), None)
            if name is None:
                continue
            menu_item.update_field_translations("name", {
                lang.code: self.with_context(lang=lang.code).env._(name) for lang in langs if lang.code != "nl_BE"})
