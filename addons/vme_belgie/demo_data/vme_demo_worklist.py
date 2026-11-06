"""Case managers and a filled "Mijn werk vandaag" on 5 November 2026 (step 29).

The administrator (the login of the demo) manages Residentie Linde and Hof ter Beuken; his colleague
"Medewerker Voorbeeld" manages Kaaihuis. Nothing is sent: the AI proposals are tasks with a draft
reply, the order for the locksmith waits for a click.
"""
from datetime import date

from markupsafe import Markup

from odoo import api, models

from .vme_demo_data import STAFF_USER

DEMO_WORKLIST_DATE = date(2026, 11, 5)
DEMO_MANAGERS = {"Residentie Linde": "admin", "Hof ter Beuken": "admin", "Kaaihuis": "staff"}
# Records of a VME with their own responsible: these follow the case manager in the demo.
RESPONSIBLE_FIELDS = [
    ("vme.request", "user_id"), ("vme.sale.file", "user_id"), ("vme.works", "user_id"),
    ("vme.damage.claim", "user_id"), ("vme.contract", "responsible_user_id"),
    ("vme.installation", "responsible_user_id"),
]
# Proposed replies of the AI mail assistant, as ai/assistant.py makes them: (VME, lot, topic, mail, reply).
DEMO_AI_PROPOSALS = [
    ("Residentie Linde", "A8", "Vraag over afrekening of provisies",
     "Ik zie op de provisieoproep van oktober een hoger bedrag dan vorig jaar. Klopt dat?",
     "Het budget 2026 is op de AV van maart verhoogd voor de dakwerken. De oproep volgt dat budget; "
     "de verdeling per sleutel staat op de achterkant van de oproep."),
    ("Kaaihuis", "K3", "Lift of technisch defect",
     "De buitenverlichting aan de inkom brandt al drie avonden niet meer.",
     "Bedankt voor de melding. We vragen de elektricien om de verlichting deze week na te kijken."),
]


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_managers(self):
        """Who manages which demo VME. Runs before the history, so the tasks of the cycle follow."""
        users = {"admin": self.env.ref("base.user_admin"),
                 "staff": self.env["res.users"].search([("login", "=", STAFF_USER["login"])], limit=1)}
        for name, user in DEMO_MANAGERS.items():
            vme = self.search([("name", "=", name)], limit=1)
            manager = users[user]
            vme.manager_user_id = manager
            for model, field in RESPONSIBLE_FIELDS:
                self.env[model].search([("association_id", "=", vme.id)]).write({field: manager.id})
            for model in self.env["vme.work.item"]._vme_models():
                records = vme if model == "vme.association" else self.env[model].search([("association_id", "=", vme.id)])
                records_activities = self.env["mail.activity"].search([
                    ("res_model", "=", model), ("res_id", "in", records.ids)])
                records_activities.write({"user_id": manager.id})

    @api.model
    def _load_demo_worklist(self):
        """A few drafts that wait for a click on the demo date: AI replies and an order for the locksmith."""
        for name, lot, topic, question, reply in DEMO_AI_PROPOSALS:
            vme = self.search([("name", "=", name)], limit=1)
            vme.activity_schedule(
                "mail.mail_activity_data_todo", date_deadline=DEMO_WORKLIST_DATE,
                summary=f"AI-voorstel: {topic} ({lot})",
                note=Markup(
                    "<p><b>Voorgesteld antwoord, nog niet verstuurd.</b> Kijk het na, pas aan waar nodig en "
                    "verstuur het zelf. Markeer de activiteit daarna als gedaan.</p>"
                    "<ul><li><b>Kavel:</b> %s</li><li><b>Onderwerp:</b> %s</li></ul>"
                    "<h4>Conceptantwoord</h4><blockquote><p>%s</p></blockquote>"
                    "<h4>Oorspronkelijke mail</h4><blockquote><p>%s</p></blockquote>"
                    "<p class=\"text-muted\">Fictieve mail voor de demo.</p>") % (lot, topic, reply, question),
                user_id=vme._vme_task_user().id)

        # An owner asked a key by mail: verified at once, the order is prepared and waits for a click.
        # Not in Residentie Linde: there the demo shows the badge request of A4 through the AI assistant.
        beuken = self.search([("name", "=", "Hof ter Beuken")], limit=1)
        Request = self.env["vme.request"]
        request = Request.browse(Request.create_from_intake(
            beuken.id, "key", "eigenaar.beuken.b3@example.com", subject="Extra sleutel voordeur",
            body="Graag een extra sleutel van de voordeur voor mijn dochter."))
        request.request_date = date(2026, 11, 4)
        request.activity_ids.write({"date_deadline": DEMO_WORKLIST_DATE})
