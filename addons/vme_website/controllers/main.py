"""Login landing for the product website.

The "Inloggen" button offers two routes (staff and owners), but where someone lands after
logging in depends only on who they are: staff always reach the VME app, portal users always
their owner portal, even when they picked the other route.
"""
from odoo.http import request

from odoo.addons.website.controllers.main import Website

VME_APP_URL = "/odoo/action-vme_belgie.vme_association_action"
PORTAL_URL = "/my"


def _is_backend_url(url):
    return url == "/odoo" or url.startswith(("/odoo/", "/odoo?", "/web#", "/web?")) or url == "/web"


class VmeWebsite(Website):

    def _login_redirect(self, uid, redirect=None):
        is_internal = request.env["res.users"].browse(uid)._is_internal()
        if is_internal and (not redirect or redirect == PORTAL_URL or redirect == "/odoo"):
            redirect = VME_APP_URL
        elif not is_internal and (not redirect or _is_backend_url(redirect)):
            redirect = PORTAL_URL
        return super()._login_redirect(uid, redirect=redirect)
