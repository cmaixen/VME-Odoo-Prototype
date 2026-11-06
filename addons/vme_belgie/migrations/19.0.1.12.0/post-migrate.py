"""Step 26: the VAT on vendor bills of a VME becomes a cost (non-deductible).

New VME companies get this when their chart is loaded; existing ones get it here. Bills
that are already posted keep their VAT on 411000.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ChartTemplate = env["account.chart.template"]
    for vme in env["vme.association"].with_context(active_test=False).search([]):
        ChartTemplate._vme_make_purchase_vat_non_deductible(vme.company_id)
