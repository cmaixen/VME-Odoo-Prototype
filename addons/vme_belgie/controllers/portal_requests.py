"""Requests and survey answers in the owner portal (steps 19 and 23 on the portal of step 15).

Same rules as controllers/portal.py: everything starts from the logged-in partner, the checks live
in the models (models/vme_portal_requests.py), and anything that is not the partner's answers 404.
Tenants get these pages too, but not the documents and provisions of the building.
"""
from werkzeug.exceptions import NotFound

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from .portal import VmeOwnerPortal


class VmeRequestPortal(VmeOwnerPortal):

    def _vme_feedback(self, target, message=None, error=None):
        # Feedback goes through the session, not the URL, so a link cannot put text on the page.
        request.session["vme_request_feedback"] = {"message": message, "error": error}
        return request.redirect(target)

    def _vme_pop_feedback(self):
        return request.session.pop("vme_request_feedback", None) or {}

    def _vme_require_access(self):
        if not self._vme_partner()._vme_portal_has_access():
            raise NotFound()

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "vme_count" in counters:
            partner = self._vme_partner()
            values["vme_count"] = len(
                partner._vme_portal_associations() | partner._vme_portal_current_tenant_lots().association_id)
        return values

    @http.route()
    def portal_my_vme(self, **kw):
        response = super().portal_my_vme(**kw)
        partner = self._vme_partner()
        surveys = partner._vme_portal_surveys()
        response.qcontext.update({
            "tenant_lots": partner._vme_portal_current_tenant_lots(),
            "my_requests": partner._vme_portal_requests()[:5],
            "can_request": bool(partner._vme_portal_request_lots()),
            "surveys": surveys,
        })
        return response

    @http.route()
    def portal_my_vme_detail(self, vme_id, **kw):
        response = super().portal_my_vme_detail(vme_id, **kw)
        response.qcontext["vme_surveys"] = self._vme_partner()._vme_portal_surveys().filtered(
            lambda log: log.association_id.id == vme_id and log.communication_id._portal_open_for_answers())
        return response

    @http.route("/my/vme/requests", type="http", auth="user", website=True)
    def portal_my_vme_requests(self, **kw):
        self._vme_require_access()
        partner = self._vme_partner()
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_requests",
            "requests": partner._vme_portal_requests(),
            "can_request": bool(partner._vme_portal_request_lots()),
            **self._vme_pop_feedback(),
        })
        return request.render("vme_belgie.portal_my_vme_requests", values)

    @http.route("/my/vme/requests/new", type="http", auth="user", website=True, methods=["GET", "POST"])
    def portal_my_vme_request_new(self, **post):
        partner = self._vme_partner()
        lots = partner._vme_portal_request_lots()
        if not lots:
            raise NotFound()
        error = None
        if request.httprequest.method == "POST":
            lot = lots.filtered(lambda l: str(l.id) == str(post.get("lot_id")))
            if not lot:
                # A lot that is not the partner's: same answer as any other id that is not its own.
                raise NotFound()
            try:
                new = partner._vme_portal_create_request(
                    lot, post.get("request_type"), post.get("subject"), post.get("description"),
                    request.httprequest.files.getlist("attachments"))
            except UserError as e:
                error = e.args[0]
            else:
                return self._vme_feedback(f"/my/vme/request/{new.id}", message=request.env._(
                    "Uw aanvraag %s is ontvangen. De syndicus behandelt ze en houdt u op de hoogte.", new.name))
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_request_new",
            "lots": lots,
            "owned_lots": partner._vme_portal_ownerships().filtered("is_current").lot_id,
            "request_types": partner._vme_portal_request_types(),
            "post": post,
            "error": error,
        })
        return request.render("vme_belgie.portal_my_vme_request_new", values)

    @http.route("/my/vme/request/<int:request_id>", type="http", auth="user", website=True)
    def portal_my_vme_request(self, request_id, **kw):
        vme_request = self._vme_partner()._vme_portal_request(request_id)
        if not vme_request:
            raise NotFound()
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_request",
            "vme_request": vme_request,
            "messages": vme_request._portal_messages(),
            **self._vme_pop_feedback(),
        })
        return request.render("vme_belgie.portal_my_vme_request", values)

    @http.route("/my/vme/request/<int:request_id>/proof", type="http", auth="user", website=True, methods=["POST"])
    def portal_my_vme_request_proof(self, request_id, **post):
        partner = self._vme_partner()
        vme_request = partner._vme_portal_request(request_id)
        if not vme_request:
            raise NotFound()
        target = f"/my/vme/request/{vme_request.id}"
        try:
            vme_request._portal_add_proof(partner, request.httprequest.files.getlist("attachments"), post.get("note"))
        except UserError as e:
            return self._vme_feedback(target, error=e.args[0])
        return self._vme_feedback(target, message=request.env._(
            "Bedankt, de syndicus kijkt uw documenten na."))

    @http.route("/my/vme/survey/<int:log_id>", type="http", auth="user", website=True, methods=["GET", "POST"])
    def portal_my_vme_survey(self, log_id, **post):
        partner = self._vme_partner()
        log = partner._vme_portal_survey(log_id)
        if not log:
            raise NotFound()
        if request.httprequest.method == "POST":
            try:
                log._portal_answer(partner, post.get("option_id"), post.get("note"))
            except UserError as e:
                return self._vme_feedback(f"/my/vme/survey/{log.id}", error=e.args[0])
            return self._vme_feedback(f"/my/vme/survey/{log.id}", message=request.env._(
                "Bedankt, uw antwoord is geregistreerd."))
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_survey",
            "log": log,
            "communication": log.communication_id,
            "is_open": log.communication_id._portal_open_for_answers(),
            **self._vme_pop_feedback(),
        })
        return request.render("vme_belgie.portal_my_vme_survey", values)
