from odoo import models

# Belgian PCMN: maintenance and repairs, the broadest account for common costs of a VME.
VME_DEFAULT_EXPENSE_ACCOUNT_CODE = "611000"


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)
        # The Belgian chart leaves the purchase journal without a default account, so
        # bill lines without a product would need an account picked by hand every time.
        if not self.env["vme.association"].with_context(active_test=False).search_count(
            [("company_id", "=", company.id)]
        ):
            return
        journal = self.ref("purchase", raise_if_not_found=False)
        account = self.env["account.account"].with_company(company).search(
            [("company_ids", "in", company.id), ("code", "=", VME_DEFAULT_EXPENSE_ACCOUNT_CODE)], limit=1
        )
        if journal and account and not journal.default_account_id:
            journal.default_account_id = account
