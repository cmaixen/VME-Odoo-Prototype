"""Fictitious collection history on top of the demo year 2026: reminders already sent to Beuken B7."""
from datetime import date

from odoo import api, models

BAILIFF = ("Gerechtsdeurwaarder Voorbeeld", "deurwaarder@example.com")
# Beuken B7 did not pay calls 3 (due 4 August) and 4 (due 4 November): a friendly reminder and a
# demand were already sent, so the next proposal is the formal notice. Linde A3 (call 4) gets its
# first reminder when the collection is refreshed.
SENT_REMINDERS = {
    ("Hof ter Beuken", "Eigenaar Beuken B7"): [("1", date(2026, 8, 11)), ("2", date(2026, 9, 1))],
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_collection(self):
        Collection = self.env["vme.collection"]
        bailiff = self.env["res.partner"].create({"name": BAILIFF[0], "email": BAILIFF[1], "is_company": True})
        for (vme_name, owner_name), reminders in SENT_REMINDERS.items():
            vme = self.search([("name", "=", vme_name)])
            owner = self.env["res.partner"].search([("name", "=", owner_name)], limit=1)
            collection = Collection.create({
                "association_id": vme.id, "partner_id": owner.id, "forward_partner_id": bailiff.id,
            })
            for level, sent_date in reminders:
                reminder = collection._create_reminder(level, sent_date)
                reminder.with_context(vme_today=sent_date).action_mark_sent()
        # Proposes the next level for every dossier, as drafts; nothing is sent.
        Collection._refresh()
