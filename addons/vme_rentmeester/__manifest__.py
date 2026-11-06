{
    "name": "VME België - Rentmeester",
    "summary": "Huurcontracten, huurfacturen, indexering, afrekening aan huurders en doorstorting aan verhuurders",
    "version": "19.0.1.1.0",
    "category": "Accounting",
    "author": "VME-prototype",
    "license": "LGPL-3",
    # The rent belongs to the landlord, not to the VME: a separate module and app, on top of
    # vme_belgie for the lots and the owners' annual statement (see docs/beslissingen.md).
    "depends": ["vme_belgie"],
    "data": [
        "security/ir.model.access.csv",
        "data/vme_rent_index_data.xml",
        "views/rent_contract_views.xml",
        "views/rent_remittance_views.xml",
        "data/rent_data.xml",
        "data/help_menu.xml",
        "report/rent_reports.xml",
    ],
    "installable": True,
    "application": True,
}
