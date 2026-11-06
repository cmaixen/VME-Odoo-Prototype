{
    "name": "VME België - Website",
    "summary": "Productwebsite van het syndicusplatform, met inloggen voor medewerkers en eigenaars",
    "version": "19.0.1.0.0",
    "category": "Website",
    "author": "VME-prototype",
    "license": "LGPL-3",
    # The website is a separate module so that vme_belgie never needs the website app
    # (see docs/beslissingen.md). website_crm turns the demo request form into a lead.
    "depends": ["website", "website_crm", "vme_belgie"],
    "data": [
        "views/layout_templates.xml",
        "views/page_templates.xml",
        "data/page_data.xml",
        "data/website_data.xml",
        "data/help_menu.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            "vme_website/static/src/scss/primary_variables.scss",
        ],
        "web.assets_frontend": [
            "vme_website/static/src/scss/website.scss",
        ],
    },
    "installable": True,
    "application": False,
}
