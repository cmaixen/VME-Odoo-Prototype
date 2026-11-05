"""Incoming documents (inspection reports, policies, quotes) classified by the AI assistant.

The script ai/documenten.py decides with a language model which VME a PDF belongs to and what
kind of document it is, and hands it to vme_receive_document. Odoo stores it on the VME and
asks _vme_document_folder where it belongs. Filing it in a folder is the job of document
management (step 15): that step overrides _vme_document_folder. See docs/dev/pdf-ai-lezen.md.
"""
import base64

from markupsafe import Markup

from odoo import models

# Kind of document -> code of the VME folder of step 15 it belongs in (False: no VME folder).
DOCUMENT_TYPES = {
    "inspection_report": ("Keuringsverslag", "inspection_reports"),
    "insurance_policy": ("Verzekeringspolis", "insurance_policies"),
    "quote": ("Offerte", False),  # belongs to a work order (step 14), not to a folder
    "minutes": ("Notulen", "minutes"),
    "contract": ("Contract", "contracts"),
    "deed": ("Basisakte of reglement van mede-eigendom", "deed"),
    "annual_statement": ("Jaarafrekening", "annual_statements"),
    "other": ("Ander document", False),
}
CONFIDENCE_LABELS = {"high": "hoog", "medium": "gemiddeld", "low": "laag"}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    def vme_receive_document(self, filename, datas, document_type, confidence="low", reason="", model_name=""):
        """Store a document the AI assistant classified for this VME; a file already here is skipped.

        datas is the file in base64. Returns {"attachment_id", "duplicate", "folder"}.
        """
        self.ensure_one()
        if document_type not in DOCUMENT_TYPES:
            document_type = "other"
        raw = base64.b64decode(datas)
        Attachment = self.env["ir.attachment"]
        existing = Attachment.search([
            ("res_model", "=", self._name), ("res_id", "=", self.id),
            ("checksum", "=", Attachment._compute_checksum(raw)),
        ], limit=1)
        if existing:
            return {"attachment_id": existing.id, "duplicate": True, "folder": False}

        label = DOCUMENT_TYPES[document_type][0]
        attachment = Attachment.create({
            "name": filename,
            "raw": raw,
            "res_model": self._name,
            "res_id": self.id,
            "description": self.env._("Soort: %(type)s (AI, zekerheid %(confidence)s)",
                                      type=label, confidence=CONFIDENCE_LABELS.get(confidence, confidence)),
        })
        folder = self._vme_document_folder(attachment, document_type)
        place = folder or self.env._("nog geen map: het document staat bij de bijlagen van de VME")
        self.message_post(
            body=Markup("<p>%s</p><ul><li>%s</li><li>%s</li><li>%s</li></ul><p>%s</p>") % (
                self.env._("Document ontvangen en geklasseerd door %s. Kijk na of het klopt.", model_name or "AI"),
                self.env._("Soort: %s", label),
                self.env._("Zekerheid: %s", CONFIDENCE_LABELS.get(confidence, confidence)),
                self.env._("Plaats: %s", place),
                reason,
            ),
            attachment_ids=attachment.ids,
        )
        return {"attachment_id": attachment.id, "duplicate": False, "folder": folder or False}

    def _vme_document_folder(self, attachment, document_type):
        """Put a classified document in the folder of this VME and return the folder's name.

        Extension point for document management (step 15): override this, look up the VME
        folder with code DOCUMENT_TYPES[document_type][1] and file the attachment there.
        Without document management there are no folders, so it returns False.
        """
        return False
