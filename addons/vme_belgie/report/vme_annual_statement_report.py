from odoo import api, models


class ReportAnnualStatement(models.AbstractModel):
    _name = "report.vme_belgie.report_annual_statement"
    _description = "Jaarafrekening (rapport)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env["vme.annual.statement.wizard"].browse(docids)
        statements = [wizard._get_statement() for wizard in wizards]
        return {
            "doc_ids": docids,
            "doc_model": "vme.annual.statement.wizard",
            "docs": wizards,
            "statements": statements,
        }
