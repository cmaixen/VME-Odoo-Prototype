"""A fictitious hybrid extraordinary assembly of Residentie Linde (step 24), ready for the demo:
confirmed, convocation sent, attendance list made, one proxy. The online reception is still closed:
in the demo the syndic opens it, the owners sign in through the portal and vote."""
from datetime import date

from odoo import api, models

DEMO_HYBRID_ASSEMBLY = {
    "vme": "Residentie Linde",
    "block": (date(2026, 11, 19), 19.0, 0),  # date, hour, room index in ASSEMBLY_ROOMS
    "subject": "Laadpalen in de garage",
    "video_url": "https://meet.example.com/residentie-linde-bav-2026",
    "convocation_sent": date(2026, 11, 3),
    # apartment of the owner giving a proxy -> apartment of the proxy holder (portal login A1)
    "represented": {"A7": "A1"},
    "chair": "A2",
    "secretary": "A6",
    # (title, majority, written vote beforehand allowed, explanation)
    "items": [
        ("Plaatsing van laadpalen in de ondergrondse garage, raming 24.000 euro uit het reservekapitaal",
         "two_thirds", False,
         "Acht laadpunten met een gedeelde aansluiting; elke eigenaar van een garage betaalt zijn eigen verbruik."),
        ("Schilderwerken van de traphal blok A, raming 6.500 euro", "absolute", True,
         "Over dit punt kunt u vooraf schriftelijk stemmen in het eigenaarsportaal."),
    ],
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_hybrid_assembly(self):
        # Imported here: vme_demo_data imports the demo mixins of the other steps.
        from .vme_demo_data import ASSEMBLY_ROOMS

        spec = DEMO_HYBRID_ASSEMBLY
        vme = self.search([("name", "=", spec["vme"])])
        day, hour, room_index = spec["block"]
        room = self.env["vme.assembly.room"].search([("name", "=", ASSEMBLY_ROOMS[room_index][0])], limit=1)
        slot = self.env["vme.assembly.slot"].create({
            "date": day, "time_start": hour, "room_id": room.id, "user_id": self.env.ref("base.user_admin").id,
        })
        assembly = self.env["vme.assembly"].create({
            "association_id": vme.id, "year": day.year, "assembly_type": "extraordinary", "subject": spec["subject"],
            "slot_id": slot.id, "meeting_mode": "hybrid", "video_url": spec["video_url"],
        })
        assembly.action_confirm()
        assembly.convocation_sent_date = spec["convocation_sent"]
        next_sequence = max(assembly.item_ids.mapped("sequence")) + 1
        self.env["vme.assembly.item"].create([{
            "assembly_id": assembly.id, "sequence": next_sequence + offset, "name": title, "majority": majority,
            "allow_advance_vote": advance, "description": description,
        } for offset, (title, majority, advance, description) in enumerate(spec["items"])])
        assembly.action_create_attendance_list()
        by_apartment = {a.lot_names.split(", ")[0]: a for a in assembly.attendee_ids}
        for apartment, holder in spec["represented"].items():
            by_apartment[apartment].write({
                "attendance": "represented", "proxy_holder_id": by_apartment[holder].partner_id.id})
        assembly.write({
            "chair_id": by_apartment[spec["chair"]].partner_id.id,
            "secretary_id": by_apartment[spec["secretary"]].partner_id.id,
        })
        return assembly
