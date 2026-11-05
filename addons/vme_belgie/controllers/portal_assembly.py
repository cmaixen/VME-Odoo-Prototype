"""Digital and hybrid general assembly in the owner portal (step 24).

Same rules as the rest of the portal (controllers/portal.py): everything starts from the logged-in
partner, the checks live in the models (models/vme_assembly_online.py), and anything that is not
the owner's answers 404. Every form is a POST with Odoo's CSRF token.
"""
from werkzeug.exceptions import NotFound
from werkzeug.urls import url_encode

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from .portal import VmeOwnerPortal


class VmeAssemblyPortal(VmeOwnerPortal):

    def _vme_assembly(self, assembly_id):
        assembly = self._vme_partner()._vme_portal_assembly(assembly_id)
        if not assembly:
            raise NotFound()
        return assembly

    def _vme_back(self, assembly, anchor="", message=None, error=None):
        # Feedback goes through the session, not the URL, so a link cannot put text on the page.
        request.session["vme_assembly_feedback"] = {"message": message, "error": error}
        return request.redirect(f"/my/vme/assembly/{assembly.id}{anchor}")

    @staticmethod
    def _vme_ip():
        return request.httprequest.remote_addr

    @http.route()
    def portal_my_vme_detail(self, vme_id, **kw):
        response = super().portal_my_vme_detail(vme_id, **kw)
        association = self._vme_get_association(vme_id)
        response.qcontext["assemblies_to_sign"] = self._vme_partner()._vme_portal_assemblies_to_sign(association)
        return response

    @http.route("/av/<string:token>", type="http", auth="public", website=True)
    def portal_assembly_link(self, token, **kw):
        """The link per assembly from the convocation: log in, then go to the meeting page."""
        assembly = request.env["vme.assembly"].sudo().search(
            [("online_token", "=", token), ("meeting_mode", "!=", "in_person")], limit=1) if token else None
        if not assembly:
            raise NotFound()
        target = f"/my/vme/assembly/{assembly.id}"
        if request.env.user._is_public():
            return request.redirect(f"/web/login?{url_encode({'redirect': target})}")
        return request.redirect(target)

    @http.route("/my/vme/assembly/<int:assembly_id>", type="http", auth="user", website=True)
    def portal_my_vme_assembly(self, assembly_id, **kw):
        partner = self._vme_partner()
        assembly = self._vme_assembly(assembly_id)
        attendee = assembly._portal_attendee(partner)
        owner = partner._vme_owner()
        represented = assembly.attendee_ids.filtered(
            lambda a: a.attendance == "represented" and a.proxy_holder_id == owner)
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_assembly",
            "vme": assembly.association_id,
            "assembly": assembly,
            "attendee": attendee,
            "represented": represented,
            # Lines whose votes this owner may see: its own and those of the owners it represents.
            "mine": attendee | represented,
            "item_rights": {item.id: item._portal_vote_rights(partner) for item in assembly.item_ids},
            "votes": {(vote.item_id.id, vote.attendee_id.id): vote for vote in assembly.item_ids.vote_ids},
            "signature": assembly._portal_signature(partner) if assembly.state == "held" else None,
            **(request.session.pop("vme_assembly_feedback", None) or {}),
        })
        return request.render("vme_belgie.portal_my_vme_assembly", values)

    @http.route("/my/vme/assembly/<int:assembly_id>/checkin", type="http", auth="user", website=True, methods=["POST"])
    def portal_my_vme_assembly_checkin(self, assembly_id, **post):
        assembly = self._vme_assembly(assembly_id)
        try:
            assembly._portal_check_in(self._vme_partner(), self._vme_ip())
        except UserError as e:
            return self._vme_back(assembly, error=e.args[0])
        return self._vme_back(assembly, message=request.env._("U bent online aanwezig."))

    @http.route("/my/vme/assembly/<int:assembly_id>/vote", type="http", auth="user", website=True, methods=["POST"])
    def portal_my_vme_assembly_vote(self, assembly_id, item_id=None, **post):
        assembly = self._vme_assembly(assembly_id)
        item = assembly.item_ids.filtered(lambda i: str(i.id) == str(item_id))
        if not item:
            raise NotFound()
        attendees = {str(a.id): a for a in assembly.attendee_ids}
        choices = {}
        for key, value in post.items():
            if key.startswith("vote_"):
                attendee = attendees.get(key[len("vote_"):])
                if not attendee:
                    raise NotFound()
                choices[attendee] = value
        anchor = f"#punt-{item.id}"
        try:
            item._portal_cast_votes(self._vme_partner(), choices, self._vme_ip())
        except UserError as e:
            return self._vme_back(assembly, anchor, error=e.args[0])
        return self._vme_back(assembly, anchor, message=request.env._(
            "Uw stem over punt %s is geregistreerd.", item.sequence))

    @http.route("/my/vme/assembly/<int:assembly_id>/sign", type="http", auth="user", website=True, methods=["POST"])
    def portal_my_vme_assembly_sign(self, assembly_id, signature_id=None, signed_name=None, agree=None, **post):
        partner = self._vme_partner()
        assembly = self._vme_assembly(assembly_id)
        signature = assembly._portal_signature(partner)
        if not signature or str(signature.id) != str(signature_id):
            raise NotFound()
        if not agree:
            return self._vme_back(assembly, "#ondertekenen", error=request.env._("Bevestig dat u de notulen gelezen hebt."))
        try:
            signature._portal_sign(partner, signed_name, self._vme_ip(), request.httprequest.user_agent.string)
        except UserError as e:
            return self._vme_back(assembly, "#ondertekenen", error=e.args[0])
        return self._vme_back(assembly, "#ondertekenen", message=request.env._("U hebt de notulen ondertekend."))

    @http.route("/my/vme/assembly/<int:assembly_id>/minutes", type="http", auth="user", website=True)
    def portal_my_vme_assembly_minutes(self, assembly_id, **kw):
        partner = self._vme_partner()
        assembly = self._vme_assembly(assembly_id)
        if not assembly._portal_signature(partner) or not assembly.minutes_attachment_id:
            raise NotFound()
        stream = request.env["ir.binary"]._get_stream_from(assembly.minutes_attachment_id.sudo(), "raw")
        return stream.get_response(as_attachment=False)
