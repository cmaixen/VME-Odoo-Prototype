from datetime import date

from odoo import models

from .account_chart_template import VME_FUND_ACCOUNTS

# LEGAL-CHECK: KB 12 juli 2012, bijlage - minimum chart of accounts for VMEs: the headings of the
# balance sheet (inventory) and the income statement. A VME has no equity (no class 10): what is
# left at year end is a debt to the owners on 489 "over te dragen middelen" (CBN advice 2012/14).
BALANCE_ASSETS = [
    ("2", "Vaste activa en borgtochten"),
    ("4100", "Opgevraagd voorschot reservekapitaal"),
    ("4101", "Opgevraagd voorschot werkkapitaal"),
    ("416", "Diverse vorderingen"),
    ("53", "Geldbeleggingen op termijn"),
    ("550", "Kredietinstelling: reservekapitaal"),
    ("551", "Kredietinstelling: werkkapitaal"),
    ("552", "Kredietinstelling: andere rekeningen"),
    ("57", "Kas"),
    ("58", "Interne overboekingen"),
    ("49A", "Overlopende rekeningen en wachtrekeningen"),
    ("unclassified", "Niet ingedeeld"),
]
BALANCE_LIABILITIES = [
    ("17", "Schulden op meer dan één jaar"),
    ("42", "Schulden op meer dan één jaar die binnen het jaar vervallen"),
    ("43", "Financiële schulden"),
    ("440", "Leveranciers"),
    ("444", "Te ontvangen facturen"),
    ("45", "Schulden met betrekking tot belastingen, bezoldigingen en sociale lasten"),
    ("48", "Diverse schulden"),
    ("48901", "Over te dragen middelen reservekapitaal"),
    ("48902", "Over te dragen middelen werkkapitaal"),
    ("49P", "Overlopende rekeningen"),
]
# Rows that always show, also when they are zero.
BALANCE_FIXED_ROWS = {"550", "551", "48901", "48902"}

# LEGAL-CHECK: KB 12 juli 2012, bijlage - costs (61 to 66) and income (70, 75, 76) of a VME.
INCOME_STATEMENT_COSTS = [
    ("610", "Onderhoud gebouw, tuin en terreinen"),
    ("611", "Renovatie en andere uitzonderlijke werken"),
    ("612", "Leveringen aan de vereniging"),
    ("613", "Erelonen, kosten raad van mede-eigendom en commissaris"),
    ("614", "Verzekeringen"),
    ("615", "Conciërgewoning"),
    ("616", "Administratie- en beheerskosten"),
    ("62", "Bezoldigingen, sociale lasten en pensioenen"),
    ("63", "Afschrijvingen en waardeverminderingen"),
    ("64", "Andere kosten"),
    ("65", "Financiële kosten"),
    ("66", "Uitzonderlijke kosten"),
]
INCOME_STATEMENT_INCOME = [
    ("700", "Voorschotten reservekapitaal"),
    ("701", "Voorschotten werkkapitaal"),
    ("75", "Financiële opbrengsten"),
    ("76", "Uitzonderlijke en andere opbrengsten"),
]

# LEGAL-CHECK: KB 12 juli 2012, bijlage - mapping of the Belgian PCMN accounts that Odoo's chart
# uses onto the cost headings of the VME chart; the longest prefix wins. Bills of a works file go
# to 611 (renovation and exceptional works), whatever their account.
COST_PREFIXES = {
    "60": "612",
    "61": "616",
    "610": "616",
    "611": "610",
    "612": "612",
    "613": "613",
    "61331": "616",
    "614": "614",
    "616": "616",
    "617": "616",
    "618": "616",
    "62": "62",
    "63": "63",
    "64": "64",
    "65": "65",
    "66": "66",
    "67": "64",
    "68": "64",
    "69": "64",
}
INCOME_PREFIXES = {
    "7": "76",
    "75": "75",
}

PROFIT_LOSS_TYPES = ("income", "income_other", "expense", "expense_depreciation", "expense_direct_cost")


def _prefix_lookup(code, mapping, default):
    for length in range(len(code), 0, -1):
        if code[:length] in mapping:
            return mapping[code[:length]]
    return default


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    def _get_financial_statements(self, year):
        """Balance sheet at 31/12 and income statement of `year`, with the previous year to compare.

        Presented along the minimum chart of accounts for VMEs (KB 12 juli 2012) from our own
        bookings: the provisions on 100100/100200 become the advances 700/701, and the funds plus
        the accumulated result become the 489 "over te dragen middelen" (the 693 entry of the KB
        is shown, not booked).
        """
        self.ensure_one()
        # Read as superuser, but only a VME the user may read (the auditor: only his own).
        self.check_access("read")
        vme = self.sudo()
        company = vme.company_id
        currency = company.currency_id
        context = vme._financial_context()
        columns = {}
        for column_year in (year, year - 1):
            balance = vme._financial_balance_sheet(date(column_year, 12, 31), context)
            columns[column_year] = {
                "balance": balance,
                "income": vme._financial_income_statement(column_year, context),
                "opening": vme._financial_balance_sheet(date(column_year - 1, 12, 31), context),
            }
        for column in columns.values():
            column["carry"] = vme._financial_carry_forward(column)

        def rows(section, headings, fixed=()):
            result = []
            for code, name in headings:
                current = columns[year][section].get(code, {"amount": 0.0, "details": {}})
                previous = columns[year - 1][section].get(code, {"amount": 0.0, "details": {}})
                if not (currency.round(current["amount"]) or currency.round(previous["amount"])) and code not in fixed:
                    continue
                labels = sorted(set(current["details"]) | set(previous["details"]))
                result.append({
                    "code": code.rstrip("AP") if code != "unclassified" else "",
                    "name": name,
                    "amount": currency.round(current["amount"]),
                    "previous": currency.round(previous["amount"]),
                    "details": [{
                        "label": label,
                        "amount": currency.round(current["details"].get(label, 0.0)),
                        "previous": currency.round(previous["details"].get(label, 0.0)),
                    } for label in labels],
                })
            return result

        def total(section, headings, column_year):
            return currency.round(sum(columns[column_year][section].get(code, {"amount": 0.0})["amount"]
                                      for code, _name in headings))

        def totals(section, headings):
            return {"amount": total(section, headings, year), "previous": total(section, headings, year - 1)}

        assets = totals("balance", BALANCE_ASSETS)
        liabilities = totals("balance", BALANCE_LIABILITIES)
        costs = totals("income", INCOME_STATEMENT_COSTS)
        income = totals("income", INCOME_STATEMENT_INCOME)
        carry = {
            fund: {key: {"amount": columns[year]["carry"][fund][key], "previous": columns[year - 1]["carry"][fund][key]}
                   for key in columns[year]["carry"][fund]}
            for fund in ("reserve", "working", "total")
        }
        balance_ok = all(currency.is_zero(assets[key] - liabilities[key]) for key in ("amount", "previous"))
        carry_ok = all(
            currency.is_zero(columns[column_year]["carry"][fund]["closing"]
                             - columns[column_year]["balance"].get(code, {"amount": 0.0})["amount"])
            for column_year in (year, year - 1)
            for fund, code in (("reserve", "48901"), ("working", "48902")))
        unclassified = [row for row in rows("balance", BALANCE_ASSETS) if row["name"] == "Niet ingedeeld"]
        return {
            "vme": vme,
            "company": company,
            "currency": currency,
            "year": year,
            "previous_year": year - 1,
            "date": date(year, 12, 31),
            "previous_date": date(year - 1, 12, 31),
            "assets": rows("balance", BALANCE_ASSETS, BALANCE_FIXED_ROWS),
            "liabilities": rows("balance", BALANCE_LIABILITIES, BALANCE_FIXED_ROWS),
            "costs": rows("income", INCOME_STATEMENT_COSTS),
            "income": rows("income", INCOME_STATEMENT_INCOME, {"700", "701"}),
            "assets_total": assets,
            "liabilities_total": liabilities,
            "costs_total": costs,
            "income_total": income,
            "result": {key: currency.round(income[key] - costs[key]) for key in ("amount", "previous")},
            "carry": carry,
            "balance_ok": balance_ok,
            "carry_ok": carry_ok,
            "unclassified": unclassified,
            "has_bookings": bool(context["has_bookings"](date(year, 12, 31))),
        }

    def _financial_context(self):
        """Accounts, journals and moves that the classification needs, read once per report."""
        self.ensure_one()
        company = self.company_id
        Account = self.env["account.account"].sudo().with_company(company)
        accounts = self._fund_accounts()
        journals = self.env["account.journal"].sudo().search([("company_id", "=", company.id)])
        fund_journals = {}
        for fund, bank_account in (("working", self.working_capital_bank_id), ("reserve", self.reserve_capital_bank_id)):
            for journal in journals.filtered(lambda j, b=bank_account: b and j.type == "bank" and j.bank_account_id == b):
                fund_journals[journal.id] = fund
        Move = self.env["account.move"].sudo()
        # Entries that bring works bills to the charge of the reserve capital, and their reversals.
        reserve_moves = Move.search([("company_id", "=", company.id), ("vme_reserve_move_id", "!=", False)]
                                    ).vme_reserve_move_id
        reserve_moves |= Move.search([("company_id", "=", company.id), ("reversed_entry_id", "in", reserve_moves.ids)])
        MoveLine = self.env["account.move.line"].sudo()
        return {
            "company": company,
            "accounts": Account,
            "working_account": accounts["working"],
            "reserve_account": accounts["reserve"],
            "journal_fund": fund_journals,
            "journal_type": {journal.id: journal.type for journal in journals},
            "reserve_move_ids": set(reserve_moves.ids),
            "has_bookings": lambda date_to: MoveLine.search_count([
                ("company_id", "=", company.id), ("parent_state", "=", "posted"), ("date", "<=", date_to)], limit=1),
        }

    def _financial_groups(self, context, domain):
        """Posted move lines of the VME, summed per account, journal and move."""
        groups = self.env["account.move.line"].sudo()._read_group(
            [("company_id", "=", context["company"].id), ("parent_state", "=", "posted"), *domain],
            groupby=["account_id", "journal_id", "move_id"], aggregates=["balance:sum"])
        moves = self.env["account.move"].sudo().browse({move.id for _a, _j, move, _b in groups})
        moves.fetch(["vme_works_id", "vme_fund", "origin_payment_id"])
        return [(account.with_company(context["company"]), journal, move, amount)
                for account, journal, move, amount in groups if amount]

    @staticmethod
    def _financial_add(section, code, label, amount):
        entry = section.setdefault(code, {"amount": 0.0, "details": {}})
        entry["amount"] += amount
        entry["details"][label] = entry["details"].get(label, 0.0) + amount

    def _financial_balance_sheet(self, date_to, context):
        """Balance sheet headings at date_to: assets with their debit balance, liabilities with their credit balance."""
        result = {}
        result_label = self.env._("Resultaat van de boekjaren (kosten en opbrengsten)")
        for account, journal, move, amount in self._financial_groups(context, [("date", "<=", date_to)]):
            code, account_type = account.code or "", account.account_type
            label = f"{code} {account.name}"
            journal_fund = context["journal_fund"].get(journal.id)
            if account == context["reserve_account"]:
                self._financial_add(result, "48901", label, -amount)
            elif account == context["working_account"]:
                self._financial_add(result, "48902", label, -amount)
            elif account_type in PROFIT_LOSS_TYPES or account_type == "equity_unaffected":
                # No closing entries in Odoo: the result of every year so far belongs to the working capital.
                self._financial_add(result, "48902", result_label, -amount)
            elif account_type == "asset_receivable":
                fund = move.vme_fund or journal_fund
                self._financial_add(result, {"reserve": "4100", "working": "4101"}.get(fund, "416"), label, amount)
            elif account_type == "asset_cash" or (move.origin_payment_id and account_type == "asset_current"):
                # Bank accounts, and registered payments that no bank statement matched yet.
                # LEGAL-CHECK: art. 3.89 §5 BW - working and reserve capital on separate bank accounts.
                if journal_fund:
                    self._financial_add(result, {"reserve": "550", "working": "551"}[journal_fund], label, amount)
                elif context["journal_type"].get(journal.id) == "cash":
                    self._financial_add(result, "57", label, amount)
                else:
                    self._financial_add(result, "552", label, amount)
            elif account_type in ("asset_non_current", "asset_fixed"):
                self._financial_add(result, "2", label, amount)
            elif account_type in ("asset_current", "asset_prepayments"):
                heading = "58" if code.startswith("58") else "53" if code.startswith("53") else \
                    "49A" if code.startswith("49") or account_type == "asset_prepayments" else "416"
                self._financial_add(result, heading, label, amount)
            elif account_type == "liability_payable":
                self._financial_add(result, "444" if code.startswith("444") else "440", label, -amount)
            elif account_type == "liability_non_current":
                self._financial_add(result, "17", label, -amount)
            elif account_type in ("liability_current", "liability_credit_card"):
                heading = next((prefix for prefix in ("42", "43", "45") if code.startswith(prefix)), None)
                if account_type == "liability_credit_card":
                    heading = "43"
                elif not heading:
                    heading = "49P" if code.startswith("49") else "48"
                self._financial_add(result, heading, label, -amount)
            elif account_type == "off_balance":
                continue
            else:
                # Other equity accounts have no place in the chart of a VME: shown so it can be corrected.
                self._financial_add(result, "unclassified", label, amount)
        return result

    def _financial_income_statement(self, year, context):
        """Income statement headings of one year, costs and income both as positive amounts.

        Costs are gross: the entries that bring works bills to the charge of the reserve capital
        are left out here and shown in the carry-forward of the reserve capital instead.
        """
        result = {}
        reserve_use = 0.0
        domain = [("date", ">=", date(year, 1, 1)), ("date", "<=", date(year, 12, 31))]
        for account, _journal, move, amount in self._financial_groups(context, domain):
            code, account_type = account.code or "", account.account_type
            label = f"{code} {account.name}"
            if move.id in context["reserve_move_ids"]:
                if account == context["reserve_account"]:
                    reserve_use += amount
                continue
            if account == context["reserve_account"]:
                # LEGAL-CHECK: KB 12 juli 2012, bijlage - provisions are income: 700 reserve capital, 701 working capital.
                self._financial_add(result, "700", label, -amount)
            elif account == context["working_account"]:
                self._financial_add(result, "701", label, -amount)
            elif account_type in ("expense", "expense_depreciation", "expense_direct_cost"):
                heading = "611" if move.vme_works_id else _prefix_lookup(code, COST_PREFIXES, "64")
                self._financial_add(result, heading, label, amount)
            elif account_type in ("income", "income_other"):
                self._financial_add(result, _prefix_lookup(code, INCOME_PREFIXES, "76"), label, -amount)
        result["_reserve_use"] = reserve_use
        return result

    def _financial_carry_forward(self, column):
        """Carried-forward funds per fund: opening + advances + other income - costs = closing.

        This is the 693 entry of the KB, worked out instead of booked; the closing amounts equal
        the 489 headings of the balance sheet (checked in `carry_ok`).
        """
        income, opening, balance = column["income"], column["opening"], column["balance"]

        def amount(section, code):
            return section.get(code, {"amount": 0.0})["amount"]

        costs = sum(amount(income, code) for code, _name in INCOME_STATEMENT_COSTS)
        reserve_use = income["_reserve_use"]
        reserve = {
            "opening": amount(opening, "48901"),
            "advances": amount(income, "700"),
            "other_income": 0.0,
            "costs": reserve_use,
        }
        working = {
            "opening": amount(opening, "48902"),
            "advances": amount(income, "701"),
            "other_income": amount(income, "75") + amount(income, "76"),
            "costs": costs - reserve_use,
        }
        currency = self.company_id.currency_id
        result = {}
        for fund, values in (("reserve", reserve), ("working", working)):
            values["closing"] = values["opening"] + values["advances"] + values["other_income"] - values["costs"]
            result[fund] = {key: currency.round(value) for key, value in values.items()}
        result["total"] = {key: currency.round(result["reserve"][key] + result["working"][key]) for key in reserve}
        return result

    def action_open_financial_statements(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_financial_statements_wizard_action")
        action["context"] = {"default_association_id": self.id, "dialog_size": "extra-large"}
        return action
