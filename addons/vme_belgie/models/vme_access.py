from odoo.exceptions import AccessError

AUDITOR_GROUP = "vme_belgie.group_vme_auditor"


def check_not_auditor(env):
    """Refuse buttons that write as superuser to a user who may only read (the auditor).

    Record rules stop his own writes, but not what a method then does with sudo().
    """
    if not env.su and env.user.has_group(AUDITOR_GROUP):
        raise AccessError(env._("Als commissaris van de rekeningen kunt u alleen inkijken, niets wijzigen."))
