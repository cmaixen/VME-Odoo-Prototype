"""Access review: record rules per company and the group "Toegang tot alle VME's".

Up to 19.0.1.11.0 every internal user got every new VME company. Those users keep that behaviour:
they get the new group, which now decides who receives new VMEs. The auditor stays out.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("vme_belgie.group_vme_all_companies")
    users = env["res.users"].with_context(active_test=False).search([("share", "=", False)])
    users.filtered(lambda u: not u.has_group("vme_belgie.group_vme_auditor")).write(
        {"group_ids": [(4, group.id)]})
