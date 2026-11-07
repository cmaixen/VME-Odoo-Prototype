from odoo import api, models
from odoo.tools import format_date


class VmeRentReportMixin(models.AbstractModel):
    _name = "vme.rent.report.mixin"
    _description = "Hulpfuncties voor de rapporten van de rentmeester"

    _report_model = None

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            "doc_ids": docids,
            "doc_model": self._report_model,
            "docs": self.env[self._report_model].browse(docids),
            # lang: the language of the recipient (doc_lang in the template)
            "format_date": lambda value, date_format=False, lang=False: format_date(
                self.env, value, lang_code=lang, date_format=date_format),
        }


class ReportIndexationLetter(models.AbstractModel):
    _name = "report.vme_rentmeester.report_indexation_letter"
    _inherit = "vme.rent.report.mixin"
    _description = "Indexatiebrief"
    _report_model = "vme.rent.indexation"


class ReportRentSettlement(models.AbstractModel):
    _name = "report.vme_rentmeester.report_rent_settlement"
    _inherit = "vme.rent.report.mixin"
    _description = "Afrekening lasten huurder"
    _report_model = "vme.rent.settlement"


class ReportRentRemittance(models.AbstractModel):
    _name = "report.vme_rentmeester.report_rent_remittance"
    _inherit = "vme.rent.report.mixin"
    _description = "Afrekening verhuurder"
    _report_model = "vme.rent.remittance"
