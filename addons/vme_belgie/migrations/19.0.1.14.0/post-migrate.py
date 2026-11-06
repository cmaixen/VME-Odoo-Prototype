"""Step 29: every VME gets a case manager (dossierbeheerder).

Existing VMEs get the internal user who created them, or the administrator when that was the
superuser (the demo data and the migration from another package run as OdooBot or admin).
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE vme_association vme
           SET manager_user_id = COALESCE(
                   (SELECT u.id FROM res_users u
                     WHERE u.id = vme.create_uid AND u.id != 1 AND u.share IS NOT TRUE AND u.active),
                   (SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'user_admin'))
         WHERE vme.manager_user_id IS NULL
    """)
