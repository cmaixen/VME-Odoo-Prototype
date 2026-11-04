{
    "name": "VME België",
    "summary": "Beheer van verenigingen van mede-eigenaars (VME) voor syndici",
    "version": "19.0.1.3.0",
    "category": "Accounting",
    "author": "VME-prototype",
    "license": "LGPL-3",
    # l10n_be and account_peppol must be installed up front: otherwise Odoo installs them
    # in the middle of creating the first Belgian company, which breaks that request.
    "depends": ["account", "l10n_be", "account_peppol"],
    "data": [
        "security/ir.model.access.csv",
        "views/vme_association_views.xml",
        "views/vme_lot_views.xml",
        "views/vme_key_views.xml",
        "views/vme_ownership_views.xml",
        "views/menus.xml",
        "views/vme_cost_allocation_views.xml",
        "views/account_move_views.xml",
        "data/demo_actions.xml",
    ],
    "installable": True,
    "application": True,
}
