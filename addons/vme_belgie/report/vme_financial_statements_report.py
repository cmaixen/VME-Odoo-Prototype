from odoo import api, models


class ReportFinancialStatements(models.AbstractModel):
    _name = "report.vme_belgie.report_financial_statements"
    _description = "Balans en resultatenrekening (rapport)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env["vme.financial.statements.wizard"].browse(docids)
        # _get_financial_statements checks that the user may read the VME.
        # In the language of the VME, like the template (headings and account names come from Python).
        values = wizards[:1]._render_values([
            wizard.with_context(lang=wizard.association_id.company_id.partner_id.lang or self.env.lang)._get_statements()
            for wizard in wizards])
        return {
            "doc_ids": docids,
            "doc_model": "vme.financial.statements.wizard",
            "docs": wizards,
            **values,
        }
