from odoo import api, models


class ReportFinancialStatements(models.AbstractModel):
    _name = "report.vme_belgie.report_financial_statements"
    _description = "Balans en resultatenrekening (rapport)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env["vme.financial.statements.wizard"].browse(docids)
        # _get_financial_statements checks that the user may read the VME.
        values = wizards[:1]._render_values([wizard._get_statements() for wizard in wizards])
        return {
            "doc_ids": docids,
            "doc_model": "vme.financial.statements.wizard",
            "docs": wizards,
            **values,
        }
