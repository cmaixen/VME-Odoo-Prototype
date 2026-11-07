{
    "name": "VME België - Outlook",
    "summary": "Invoegtoepassing voor Outlook: een mail van een eigenaar meteen bij de juiste VME en kavel",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "VME-prototype",
    "license": "LGPL-3",
    # A separate module so that vme_belgie never needs mail_plugin (see docs/beslissingen.md).
    # mail_plugin brings the API-key login of mail add-ins (scope outlook, auth="outlook").
    "depends": ["mail_plugin", "vme_belgie"],
    "data": [
        "security/ir.model.access.csv",
        "views/vme_mail_plugin_setup_views.xml",
        "data/help_menu.xml",
    ],
    "installable": True,
    "application": False,
}
