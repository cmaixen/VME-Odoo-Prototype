"""Yearly cycle of the three demo VMEs (step 28), each at another point on 5 November 2026.

Runs at the end of the demo history: the cycle reads the posted provision calls and the
assembly of Residentie Linde held in March 2026.
"""
from datetime import date

from odoo import api, models

DEMO_CYCLE_DATE = date(2026, 11, 5)
# Start of the cycle per VME, and the steps of 2026 the syndic closed by hand before the demo.
# - Residentie Linde follows the whole year: 2026 is done, the assembly of 2027 is being planned.
# - Hof ter Beuken was taken over on 5 April 2026; the assembly of 2026 was never planned, so its
#   agenda, convocation and assembly are late.
# - Kaaihuis was taken over on 1 October 2026: only the last call of 2026, then 2027.
DEMO_CYCLE = {
    "Residentie Linde": (date(2026, 1, 1), ("closing", "statement", "minutes", "approved_budget")),
    "Hof ter Beuken": (date(2026, 4, 5), ()),
    "Kaaihuis": (date(2026, 10, 1), ()),
}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_cycle(self):
        Step = self.env["vme.cycle.step"].with_context(vme_today=DEMO_CYCLE_DATE)
        vmes = self.browse()
        for name, (start, done_codes) in DEMO_CYCLE.items():
            vme = self.search([("name", "=", name)], limit=1)
            vme.cycle_start_date = start
            vme._cycle_ensure_steps(DEMO_CYCLE_DATE.year)
            Step.search([("association_id", "=", vme.id), ("year", "=", DEMO_CYCLE_DATE.year),
                         ("code", "in", done_codes)])._mark_done(DEMO_CYCLE_DATE)
            vmes |= vme
        vmes._cycle_sync(DEMO_CYCLE_DATE)
