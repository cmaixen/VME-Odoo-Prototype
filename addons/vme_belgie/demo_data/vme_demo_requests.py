"""Fictitious data for requests of residents: a locksmith, key certificates, tenants and a key register.

The requests themselves come in as mails through the AI assistant (ai/inbox/06-08).
"""
from datetime import date

from odoo import api, models

# VAT number with valid check digits that starts with 0000, so it cannot be real.
LOCKSMITH = {
    "name": "Slotenmaker Voorbeeld BV",
    "vat": "BE0000001186",
    "email": "bestellingen@slotenmaker.example.com",
    "street": "Sleutelstraat 8",
    "zip": "2000",
    "city": "Voorbeeldstad",
}
KEY_CERTIFICATES = {
    "Residentie Linde": "CERT-VB-LINDE-0417",
    "Hof ter Beuken": "CERT-VB-BEUKEN-0932",
    "Kaaihuis": "CERT-VB-KAAI-0158",
}
# Tenants per lot: (VME, lot, name, e-mail, start of the lease).
TENANTS = [
    ("Residentie Linde", "A6", "Huurder Linde A6", "huurder.linde.a6@example.com", date(2025, 9, 1)),
    ("Hof ter Beuken", "B12", "Huurder Beuken B12", "huurder.beuken.b12@example.com", date(2024, 3, 1)),
    ("Kaaihuis", "K2", "Huurder Kaaihuis K2", "huurder.kaaihuis.k2@example.com", date(2026, 2, 1)),
]
# Keys handed out per lot type and VME: (kind, number prefix).
KEY_SETS = {
    "Residentie Linde": {"apartment": [("entrance_key", "VS-L"), ("badge", "BA-L")], "garage": [("remote", "AB-L")]},
    "Hof ter Beuken": {"apartment": [("badge", "BA-B")]},
    "Kaaihuis": {"apartment": [("entrance_key", "VS-K")]},
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_requests(self):
        Partner = self.env["res.partner"]
        locksmith = Partner.create({**LOCKSMITH, "is_company": True, "country_id": self.env.ref("base.be").id})
        for name, certificate in KEY_CERTIFICATES.items():
            self.search([("name", "=", name)]).write({
                "locksmith_partner_id": locksmith.id, "key_certificate_ref": certificate,
            })

        tenants = {}
        for vme_name, lot_name, name, email, start in TENANTS:
            lot = self.env["vme.lot"].search([("association_id.name", "=", vme_name), ("name", "=", lot_name)])
            tenant = Partner.create({"name": name, "email": email})
            self.env["vme.lot.contact"].create({
                "lot_id": lot.id, "partner_id": tenant.id, "role": "tenant", "date_start": start,
            })
            tenants[lot] = (tenant, start)

        key_vals = []
        for vme_name, sets in KEY_SETS.items():
            vme = self.search([("name", "=", vme_name)])
            counters = {}
            for lot in vme.lot_ids.sorted(lambda l: (l.sequence, l.name)):
                today_owner = lot.ownership_ids.filtered(lambda o: not o.date_end)[:1]
                for kind, prefix in sets.get(lot.lot_type, []):
                    counters[prefix] = counters.get(prefix, 0) + 1
                    holder, issued = today_owner.partner_id, today_owner.date_start
                    # The tenant got the badge or key of the apartment.
                    if lot in tenants and kind in ("badge", "entrance_key"):
                        holder, issued = tenants[lot]
                    key_vals.append({
                        "lot_id": lot.id, "kind": kind, "number": f"{prefix}-{counters[prefix]:03d}",
                        "issue_date": max(issued, date(2015, 1, 1)), "partner_id": holder.id,
                    })
        self.env["vme.lot.key"].create(key_vals)
