"""Documents per VME and per lot, in fixed folders, with the visibility rule of the owner portal."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class VmeDocumentFolder(models.Model):
    _name = "vme.document.folder"
    _description = "Documentmap"
    _order = "scope, sequence, id"

    name = fields.Char(string="Map", required=True, translate=True)
    sequence = fields.Integer(default=10)
    scope = fields.Selection(
        [("vme", "Per VME"), ("lot", "Per kavel")], string="Niveau", required=True, default="vme",
    )
    # LEGAL-CHECK: art. 3.89 §5, 12° BW - the syndic gives every co-owner access to the documents
    # of the co-ownership, also via a website. Which documents exactly is not yet validated;
    # minutes go to every co-owner within 30 days (art. 3.87 §10 BW).
    portal_visible = fields.Boolean(
        string="Standaard zichtbaar in het portaal", default=True,
        help="Nieuwe documenten in deze map zijn standaard zichtbaar voor de eigenaars.",
    )
    active = fields.Boolean(default=True)


class VmeDocument(models.Model):
    _name = "vme.document"
    _description = "Document"
    _order = "date desc, id desc"

    name = fields.Char(string="Titel", required=True)
    folder_id = fields.Many2one("vme.document.folder", string="Map", required=True, ondelete="restrict", index=True)
    scope = fields.Selection(related="folder_id.scope")
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True,
        compute="_compute_association_id", store=True, readonly=False, precompute=True,
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    lot_id = fields.Many2one(
        "vme.lot", string="Kavel", ondelete="cascade", index=True,
        domain="[('association_id', '=', association_id)]",
    )
    date = fields.Date(string="Datum", required=True, default=fields.Date.context_today,
                       help="Bepaalt wie het document in het portaal ziet: eigenaars op die datum.")
    datas = fields.Binary(string="Bestand", attachment=True, required=True)
    filename = fields.Char(string="Bestandsnaam")
    portal_visible = fields.Boolean(
        string="Zichtbaar in het portaal", compute="_compute_portal_visible", store=True, readonly=False,
        precompute=True,
    )
    note = fields.Char(string="Opmerking")

    @api.depends("lot_id")
    def _compute_association_id(self):
        for document in self:
            if document.lot_id:
                document.association_id = document.lot_id.association_id

    @api.depends("folder_id")
    def _compute_portal_visible(self):
        for document in self:
            document.portal_visible = document.folder_id.portal_visible

    @api.constrains("folder_id", "lot_id", "association_id")
    def _check_lot(self):
        for document in self:
            if document.folder_id.scope == "lot" and not document.lot_id:
                raise ValidationError(self.env._("Een document in de map %(folder)s hoort bij een kavel.",
                                                 folder=document.folder_id.name))
            if document.folder_id.scope == "vme" and document.lot_id:
                raise ValidationError(self.env._("De map %(folder)s is voor de hele VME, niet voor één kavel.",
                                                 folder=document.folder_id.name))
            if document.lot_id and document.lot_id.association_id != document.association_id:
                raise ValidationError(self.env._("De kavel hoort niet bij deze VME."))

    @api.model
    def _portal_domain_for(self, partner):
        """Domain of the documents an owner may see in the portal. The only place with this rule.

        - A VME document: the partner owns or owned a lot in that VME, and the document is not
          dated after the end of that ownership. A new owner also sees older documents of the
          building (deed, regulations, minutes).
        - A lot document: the partner owned that very lot on the date of the document. After a sale
          the seller sees no new documents of the lot, and the buyer not those of the seller.
        """
        ownerships = partner._vme_portal_ownerships()
        vme_terms, lot_terms = [], []
        for ownership in ownerships:
            until = Domain("date", "<=", ownership.date_end) if ownership.date_end else Domain.TRUE
            vme_terms.append(Domain("association_id", "=", ownership.association_id.id) & until)
            lot_terms.append(
                Domain("lot_id", "=", ownership.lot_id.id) & Domain("date", ">=", ownership.date_start) & until
            )
        return Domain("portal_visible", "=", True) & (
            (Domain("lot_id", "=", False) & Domain.OR(vme_terms)) | Domain.OR(lot_terms)
        )

    @api.model
    def _portal_documents_for(self, partner, association=None):
        domain = self._portal_domain_for(partner)
        if association is not None:
            domain = [("association_id", "=", association.id)] + domain
        return self.sudo().search(domain)


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    document_ids = fields.One2many("vme.document", "association_id", string="Documenten")
    document_count = fields.Integer(string="Aantal documenten", compute="_compute_document_count")

    @api.depends("document_ids")
    def _compute_document_count(self):
        for vme in self:
            vme.document_count = len(vme.document_ids)

    def action_open_documents(self):
        action = self._action_open_related("vme.document", self.env._("Documenten"))
        action["context"] = {"default_association_id": self.id, "search_default_group_folder": 1}
        return action


class VmeLot(models.Model):
    _inherit = "vme.lot"

    document_ids = fields.One2many("vme.document", "lot_id", string="Documenten")
