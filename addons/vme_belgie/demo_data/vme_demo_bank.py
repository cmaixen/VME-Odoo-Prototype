"""Fictitious bank statements of early November 2026, after the demo history (stap 12).

Three CODA files (one per VME, with a statement for each fund account) and one CAMT.053 file.
They contain on purpose a few exceptions: a late payment, an underpayment, a wrong and a
missing communication, a payment on the account of the other fund, a double payment and an
unknown payer. The communications follow from the invoice numbers of the demo history, so they
only match a demo database built with the standard steps (demo data, then demo history).
"""
from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import file_open

BANK_FILES = [
    "residentie_linde_2026-11-05.cod",
    "hof_ter_beuken_2026-11-05.cod",
    "kaaihuis_2026-11-05.cod",
    "kaaihuis_reservekapitaal_2026-11-05.xml",
]


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    @api.model
    def _load_demo_bank_statements(self):
        if not self.env["vme.provision.call"].search_count([("budget_id.year", "=", 2026)]):
            raise UserError(self.env._("Laad eerst de demodata en de demohistoriek 2026."))
        Wizard = self.env["vme.bank.import.wizard"]
        lines = self.env["account.bank.statement.line"]
        for filename in BANK_FILES:
            with file_open(f"vme_belgie/demo_data/bankafschriften/{filename}", "rb") as f:
                lines |= Wizard._import_file(f.read(), filename)
        return Wizard._action_open_lines(lines)
