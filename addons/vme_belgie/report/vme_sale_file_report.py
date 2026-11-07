from odoo import api, models
from odoo.tools import format_date


class ReportNotaryInformation(models.AbstractModel):
    _name = "report.vme_belgie.report_notary_information"
    _description = "Inlichtingen aan de notaris (rapport)"

    @api.model
    def _get_report_values(self, docids, data=None):
        sales = self.env["vme.sale.file"].browse(docids)
        answer = (data or {}).get("answer")
        return {
            "doc_ids": docids,
            "doc_model": "vme.sale.file",
            "docs": sales,
            # lang: the language of the notary (doc_lang in the template)
            "format_date": lambda d, lang=False: format_date(self.env, d, lang_code=lang) if d else "",
            "infos": {sale.id: sale._get_notary_information() for sale in sales},
            # Printed from the menu: the request that is open or was answered last.
            "answers": {sale.id: answer or ("second" if sale.second_request_date else "first") for sale in sales},
        }
