"""Owner portal on Odoo Community's portal module (/my/vme).

Every route starts from the logged-in partner and goes through the helpers on res.partner and
vme.document (models/vme_portal.py, models/vme_document.py). Anything that does not belong to the
owner answers 404, so the portal does not even reveal that it exists.
"""
from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class VmeOwnerPortal(CustomerPortal):

    def _vme_partner(self):
        return request.env.user.partner_id

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if not counters:
            # Only for rendering /my: /my/counters returns every key, and Odoo's script stops at a
            # key without a counter on the page, so no tile ever appeared.
            values["vme_owner"] = self._vme_partner()._vme_is_owner()
        if "vme_count" in counters:
            values["vme_count"] = len(self._vme_partner()._vme_portal_associations())
        return values

    def _vme_get_association(self, vme_id):
        association = self._vme_partner()._vme_portal_check_association(vme_id)
        if not association:
            raise NotFound()
        return association

    # Owners change their address through a request that the syndic approves (see
    # res.partner._can_be_edited_by_current_customer), so Odoo's own forms send them there.
    @http.route()
    def account(self, **kwargs):
        if self._vme_partner()._vme_is_owner():
            return request.redirect("/my/vme/address")
        return super().account(**kwargs)

    @http.route()
    def my_addresses(self, **query_params):
        if self._vme_partner()._vme_is_owner():
            return request.redirect("/my/vme/address")
        return super().my_addresses(**query_params)

    @http.route("/my/vme", type="http", auth="user", website=True)
    def portal_my_vme(self, **kw):
        partner = self._vme_partner()
        ownerships = partner._vme_portal_ownerships()
        today = request.env.cr.now().date()
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme",
            "associations": ownerships.association_id.sorted("name"),
            "ownerships": ownerships.sorted(lambda o: (o.lot_id.association_id.name, o.lot_id.sequence, o.lot_id.name)),
            "today": today,
            "pending_request": partner._vme_owner().vme_address_request_ids.sudo().filtered(
                lambda r: r.state == "to_approve")[:1],
        })
        return request.render("vme_belgie.portal_my_vme", values)

    @http.route("/my/vme/<int:vme_id>", type="http", auth="user", website=True)
    def portal_my_vme_detail(self, vme_id, **kw):
        partner = self._vme_partner()
        association = self._vme_get_association(vme_id)
        documents = request.env["vme.document"]._portal_documents_for(partner, association)
        # Folders of the building first, then those of the owner's lots.
        folders = documents.folder_id.sorted(lambda f: (f.scope != "vme", f.sequence, f.id))
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_detail",
            "vme": association.sudo(),
            "ownerships": partner._vme_portal_ownerships().filtered(lambda o: o.association_id == association),
            "folders": [(folder, documents.filtered(lambda d, f=folder: d.folder_id == f)) for folder in folders],
            "provisions": partner._vme_portal_provisions(association),
            "statement_years": partner._vme_portal_statement_years(association),
            "assembly": partner._vme_portal_next_assembly(association),
            "today": request.env.cr.now().date(),
        })
        return request.render("vme_belgie.portal_my_vme_detail", values)

    @http.route("/my/vme/<int:vme_id>/statement/<int:year>", type="http", auth="user", website=True)
    def portal_my_vme_statement(self, vme_id, year, **kw):
        partner = self._vme_partner()
        association = self._vme_get_association(vme_id)
        result = partner._vme_portal_statement(association, year)
        if not result:
            raise NotFound()
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_statement",
            "vme": association.sudo(),
            "year": year,
            "currency": result["data"]["currency"],
            "st": result["statement"],
            "final": result["final"],
        })
        return request.render("vme_belgie.portal_my_vme_statement", values)

    @http.route("/my/vme/<int:vme_id>/statement/<int:year>/pdf", type="http", auth="user", website=True)
    def portal_my_vme_statement_pdf(self, vme_id, year, **kw):
        partner = self._vme_partner()
        association = self._vme_get_association(vme_id)
        if not partner._vme_portal_statement(association, year):
            raise NotFound()
        wizard = request.env["vme.annual.statement.wizard"].sudo().create({
            "association_id": association.id, "year": year,
            "partner_ids": [(6, 0, partner._vme_owner().ids)],
        })
        pdf, _type = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "vme_belgie.action_report_annual_statement", wizard.ids)
        filename = f"Jaarafrekening {association.name} {year}.pdf"
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf)),
            ("Content-Disposition", http.content_disposition(filename)),
        ])

    @http.route("/my/vme/document/<int:document_id>", type="http", auth="user", website=True)
    def portal_my_vme_document(self, document_id, download=False, **kw):
        partner = self._vme_partner()
        document = request.env["vme.document"]._portal_documents_for(partner).filtered(
            lambda d: d.id == document_id)
        if not document:
            raise NotFound()
        stream = request.env["ir.binary"]._get_stream_from(
            document, "datas", filename=document.filename or document.name)
        return stream.get_response(as_attachment=bool(download))

    @http.route("/my/vme/address", type="http", auth="user", website=True, methods=["GET", "POST"])
    def portal_my_vme_address(self, **post):
        partner = self._vme_partner()
        owner = partner._vme_owner()
        if not partner._vme_is_owner():
            raise NotFound()
        Request = request.env["vme.address.request"].sudo()
        pending = Request.search([("partner_id", "=", owner.id), ("state", "=", "to_approve")], limit=1)
        error = None
        if request.httprequest.method == "POST" and not pending:
            if not (post.get("street") and post.get("zip") and post.get("city")):
                error = request.env._("Vul minstens straat, postcode en gemeente in.")
            else:
                pending = Request._create_from_portal(owner, post)
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "vme_address",
            "owner": owner.sudo(),
            "pending": pending,
            "error": error,
            "post": post,
            "countries": request.env["res.country"].sudo().search([]),
        })
        return request.render("vme_belgie.portal_my_vme_address", values)
