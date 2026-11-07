from odoo import api, fields, models

BASE_URL_PARAM = "vme_mail_plugin.base_url"


class VmeMailPluginSetup(models.TransientModel):
    """VME > Configuratie > Outlook-invoegtoepassing: the address for Outlook and the manifest."""
    _name = "vme.mail.plugin.setup"
    _description = "Outlook-invoegtoepassing instellen"

    base_url = fields.Char(
        string="Adres van Odoo voor Outlook", default=lambda self: self._default_base_url(),
        help="Outlook laadt invoegtoepassingen alleen over https. Leeg: het gewone adres van Odoo (web.base.url).")
    effective_url = fields.Char(string="Gebruikt adres", compute="_compute_urls")
    manifest_url = fields.Char(string="Manifest", compute="_compute_urls")
    preview_url = fields.Char(string="Voorbeeld in de browser", compute="_compute_urls")
    is_https = fields.Boolean(compute="_compute_urls")

    @api.model
    def _default_base_url(self):
        return self.env["ir.config_parameter"].sudo().get_param(BASE_URL_PARAM, "")

    @api.depends("base_url")
    def _compute_urls(self):
        web_base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for setup in self:
            url = (setup.base_url or web_base_url or "").rstrip("/")
            setup.effective_url = url
            setup.manifest_url = f"{url}/vme_mail_plugin/manifest.xml"
            setup.preview_url = f"{url}/vme_mail_plugin/static/outlook/taskpane.html?demo=1"
            setup.is_https = url.startswith("https://")

    def _save(self):
        self.ensure_one()
        self.env["ir.config_parameter"].sudo().set_param(BASE_URL_PARAM, (self.base_url or "").strip().rstrip("/"))

    def action_download_manifest(self):
        self._save()
        return {"type": "ir.actions.act_url", "target": "self", "url": "/vme_mail_plugin/manifest.xml"}

    def action_open_preview(self):
        self._save()
        return {"type": "ir.actions.act_url", "target": "new",
                "url": "/vme_mail_plugin/static/outlook/taskpane.html?demo=1"}
