from odoo import models

# Belgian PCMN: maintenance and repairs, the broadest account for common costs of a VME.
VME_DEFAULT_EXPENSE_ACCOUNT_CODE = "611000"

# LEGAL-CHECK: KB 12 juli 2012 (minimum chart of accounts for VMEs) - align these codes.
# The Belgian PCMN has no accounts for the funds of a VME, so we add them.
VME_FUND_ACCOUNTS = {
    "working": ("100100", "Werkkapitaal"),
    "reserve": ("100200", "Reservekapitaal"),
}


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)
        if not self.env["vme.association"].with_context(active_test=False).search_count(
            [("company_id", "=", company.id)]
        ):
            return
        Account = self.env["account.account"].with_company(company)
        # The Belgian chart leaves the purchase journal without a default account, so
        # bill lines without a product would need an account picked by hand every time.
        journal = self.ref("purchase", raise_if_not_found=False)
        account = Account.search(
            [("company_ids", "in", company.id), ("code", "=", VME_DEFAULT_EXPENSE_ACCOUNT_CODE)], limit=1
        )
        if journal and account and not journal.default_account_id:
            journal.default_account_id = account
        for code, name in VME_FUND_ACCOUNTS.values():
            if not Account.search_count([("company_ids", "in", company.id), ("code", "=", code)]):
                Account.create({
                    "code": code, "name": name, "account_type": "equity", "company_ids": [company.id],
                })
