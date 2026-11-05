"""Step 18: maintenance contracts move from vme.installation to vme.contract.

Up to 19.0.1.9.0 an installation kept its maintenance contract in two columns
(maintenance_contract_ref, maintenance_contract_end). They become one vme.contract per
installation, linked to it, after which the old columns are dropped.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not column_exists(cr, "vme_installation", "maintenance_contract_ref"):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT id, maintenance_contract_ref, maintenance_contract_end
          FROM vme_installation
         WHERE maintenance_contract_ref IS NOT NULL OR maintenance_contract_end IS NOT NULL
    """)
    for installation_id, reference, date_end in cr.fetchall():
        installation = env["vme.installation"].browse(installation_id)
        if not installation.maintenance_partner_id:
            _logger.warning("Installation %s has a maintenance contract without a company; not migrated.",
                            installation.display_name)
            continue
        contract = env["vme.contract"].create({
            "name": f"Onderhoud {installation.name}",
            "reference": reference,
            "association_id": installation.association_id.id,
            "contract_type": "elevator" if installation.installation_type == "elevator" else "maintenance",
            "partner_id": installation.maintenance_partner_id.id,
            "installation_id": installation.id,
            "date_end": date_end,
            "responsible_user_id": installation.responsible_user_id.id,
        })
        installation.message_post(body=f"Onderhoudscontract overgezet naar Contracten: {contract.display_name}.")
    cr.execute("ALTER TABLE vme_installation DROP COLUMN maintenance_contract_ref, DROP COLUMN maintenance_contract_end")
