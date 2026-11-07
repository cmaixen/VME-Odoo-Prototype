"""Routes of the Outlook task pane. They reuse mail_plugin's login: an API key with scope
odoo.plugin.outlook in the Authorization header (auth="outlook"). The logic lives in vme.mail.context."""
from odoo import http
from odoo.http import request

from odoo.addons.mail_plugin.controllers.mail_plugin import MailPluginController

from ..models.vme_mail_context import LOG_MODELS


class VmeMailPluginController(MailPluginController):

    @http.route("/mail_plugin/vme/context", type="jsonrpc", auth="outlook", cors="*")
    def vme_context(self, email, name="", subject="", message_id="", association_id=False, lot_id=False, **kwargs):
        return request.env["vme.mail.context"]._vme_mail_context(
            email, name=name, subject=subject, message_id=message_id, association_id=association_id, lot_id=lot_id)

    @http.route("/mail_plugin/vme/search", type="jsonrpc", auth="outlook", cors="*")
    def vme_search(self, term, **kwargs):
        return {"results": request.env["vme.mail.context"]._vme_mail_search(term)}

    @http.route("/mail_plugin/vme/log", type="jsonrpc", auth="outlook", cors="*")
    def vme_log(self, model, res_id, subject="", email="", name="", body="", date="", attachments=None, **kwargs):
        return request.env["vme.mail.context"]._vme_mail_log(
            model, res_id, subject, email, name, body, mail_date=date, attachments=attachments)

    @http.route("/mail_plugin/vme/request", type="jsonrpc", auth="outlook", cors="*")
    def vme_request(self, association_id, request_type, email, name="", lot_id=False, subject="", body="",
                    message_id="", attachments=None, **kwargs):
        return request.env["vme.mail.context"]._vme_mail_request(
            association_id, request_type, email, name=name, lot_id=lot_id, subject=subject, body=body,
            message_id=message_id, attachments=attachments)

    def _mail_content_logging_models_whitelist(self):
        return super()._mail_content_logging_models_whitelist() + list(LOG_MODELS)

    def _translation_modules_whitelist(self):
        return super()._translation_modules_whitelist() + ["vme_mail_plugin"]
