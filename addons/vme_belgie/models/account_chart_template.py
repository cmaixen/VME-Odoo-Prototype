from odoo import models
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# Belgian PCMN: maintenance and repairs, the broadest account for common costs of a VME.
VME_DEFAULT_EXPENSE_ACCOUNT_CODE = "611000"

# LEGAL-CHECK: KB 12 juli 2012, bijlage - the minimum chart of a VME has no class 10: provisions are
# advances (700/701) and what is left is "over te dragen middelen" (489). We keep booking the
# provisions on these two accounts and present them along the KB in the balance sheet and income
# statement (models/vme_financial_statements.py, docs/dev/financiele-rapporten.md).
VME_FUND_ACCOUNTS = {
    "working": ("100100", _lt("Werkkapitaal")),
    "reserve": ("100200", _lt("Reservekapitaal")),
}


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)
        vme = self.env["vme.association"].with_context(active_test=False).search([("company_id", "=", company.id)])
        if not vme:
            return
        Account = self.env["account.account"].with_company(company)
        # The Belgian chart sets no or an unsuitable default account on the purchase journal
        # (600000 raw materials), so bill lines without a product would land on the wrong account.
        journal = self.ref("purchase", raise_if_not_found=False)
        account = Account.search(
            [("company_ids", "in", company.id), ("code", "=", VME_DEFAULT_EXPENSE_ACCOUNT_CODE)], limit=1
        )
        if journal and account:
            journal.default_account_id = account
        langs = self.env["res.lang"].search([("code", "!=", "en_US")]).mapped("code")
        for code, name in VME_FUND_ACCOUNTS.values():
            if not Account.search_count([("company_ids", "in", company.id), ("code", "=", code)]):
                # The source (Dutch) as value, with the name in every installed language (balance sheet).
                account = Account.create({
                    "code": code, "name": self.with_context(lang="en_US").env._(name), "account_type": "equity",
                    "company_ids": [company.id],
                })
                account.update_field_translations("name", {
                    lang: self.with_context(lang=lang).env._(name) for lang in langs})
        self._vme_make_purchase_vat_non_deductible(company)
        # Mail address for vendor bills, on the purchase journal that now exists.
        vme._ensure_bill_alias()

    def _vme_make_purchase_vat_non_deductible(self, company):
        """Book the VAT of vendor bills on the cost account instead of "terug te vorderen btw".

        A repartition line without account puts the tax on the account of the bill line, so
        the costs in the books are the amounts VAT included, as the distribution counts them.
        Reverse-charge taxes (with a negative repartition line) are left alone.
        """
        # LEGAL-CHECK: art. 45 §1 WBTW - a VME that is not liable for VAT cannot deduct it, so the
        # VAT on its purchases is a cost.
        taxes = self.env["account.tax"].with_context(active_test=False).search([
            ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"), ("amount_type", "!=", "group")])
        for tax in taxes:
            lines = tax.repartition_line_ids.filtered(lambda line: line.repartition_type == "tax")
            if lines and all(line.factor_percent > 0 for line in lines):
                lines.write({"account_id": False, "use_in_tax_closing": False})
