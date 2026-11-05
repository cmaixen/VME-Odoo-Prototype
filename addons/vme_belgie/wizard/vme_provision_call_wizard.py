from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import formatLang

from ..models.account_chart_template import VME_FUND_ACCOUNTS
from ..models.allocation_tools import largest_remainder

FUND_LABELS = {"working": "Werkkapitaal", "reserve": "Reservekapitaal"}


class VmeProvisionCallWizard(models.TransientModel):
    _name = "vme.provision.call.wizard"
    _description = "Provisieoproep maken"

    association_ids = fields.Many2many(
        "vme.association", string="VME's", required=True,
        default=lambda self: self.env.context.get("active_model") == "vme.association"
        and self.env["vme.association"].browse(self.env.context.get("active_ids")),
    )
    year = fields.Integer(string="Budgetjaar", required=True, default=lambda self: fields.Date.today().year + 1)
    number = fields.Integer(string="Oproep nummer", required=True, default=1)
    invoice_date = fields.Date(string="Factuurdatum", required=True, default=fields.Date.context_today)
    date_due = fields.Date(
        string="Vervaldatum", required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=30),
    )
    post_invoices = fields.Boolean(string="Meteen boeken", default=True)
    preview_html = fields.Html(string="Voorbeeld", compute="_compute_preview_html", sanitize=False)

    @api.depends("association_ids", "year", "number")
    def _compute_preview_html(self):
        for wizard in self:
            rows = []
            for vme in wizard.association_ids:
                budget = wizard._get_budget(vme)
                if not budget:
                    rows.append(Markup("<tr><td>%s</td><td colspan='3' class='text-danger'>%s</td></tr>") % (
                        vme.name, self.env._("Geen budget voor %s: wordt overgeslagen.", wizard.year)))
                    continue
                calls = int(budget.calls_per_year)
                amounts = [formatLang(self.env, amount / calls, currency_obj=budget.currency_id)
                           for amount in (budget.working_capital_budget, budget.reserve_capital_contribution)]
                warning = Markup("<div class='text-warning'>%s</div>") % budget.reserve_warning if budget.reserve_warning else ""
                rows.append(Markup("<tr><td>%s%s</td><td>%s/%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td></tr>") % (
                    vme.name, warning, wizard.number, calls, amounts[0], amounts[1]))
            header = Markup("<tr><th>%s</th><th>%s</th><th class='text-end'>%s</th><th class='text-end'>%s</th></tr>") % (
                self.env._("VME"), self.env._("Oproep"), self.env._("Werkkapitaal"), self.env._("Reservekapitaal"))
            wizard.preview_html = Markup("<table class='table table-sm'>%s%s</table>") % (header, Markup("").join(rows)) if rows else False

    def _get_budget(self, vme):
        # In the open wizard form the VMEs are temporary copies; search on the real record.
        return self.env["vme.budget"].search(
            [("association_id", "=", vme._origin.id), ("year", "=", self.year)], limit=1
        )

    def action_create_calls(self):
        self.ensure_one()
        invoices = self.env["account.move"]
        skipped = []
        for vme in self.association_ids:
            budget = self._get_budget(vme)
            if not budget:
                skipped.append(vme.name)
                continue
            vme_invoices = self._create_call(vme, budget)
            if self.post_invoices:
                # Post within the VME's own company: the user may have another company selected.
                vme_invoices.with_company(vme.company_id).action_post()
            invoices |= vme_invoices
        if not invoices:
            raise UserError(self.env._("Er zijn geen provisieoproepen gemaakt: geen budget voor %s.", ", ".join(skipped)))
        # The provision call overview spans all VMEs; an invoice list would only show the
        # companies currently selected in the company switcher.
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_provision_call_action")
        action["domain"] = [("id", "in", invoices.vme_provision_call_id.ids)]
        if skipped:
            self.env.user._bus_send("simple_notification", {
                "type": "warning",
                "title": self.env._("Overgeslagen"),
                "message": self.env._("Geen budget voor %(year)s: %(vmes)s", year=self.year, vmes=", ".join(skipped)),
            })
        return action

    def _create_call(self, vme, budget):
        calls = int(budget.calls_per_year)
        if not 1 <= self.number <= calls:
            raise UserError(self.env._(
                "Oproep %(number)s bestaat niet voor %(vme)s: het budget voorziet %(calls)s oproepen per jaar.",
                number=self.number, vme=vme.name, calls=calls,
            ))
        if budget.provision_call_ids.filtered(lambda c: c.number == self.number):
            raise UserError(self.env._(
                "Oproep %(number)s van %(year)s is voor %(vme)s al gemaakt.",
                number=self.number, year=self.year, vme=vme.name,
            ))
        key = vme.key_ids.filtered(lambda k: k.key_type == "general")[:1]
        if not key or not key.line_ids:
            raise UserError(self.env._("%s heeft geen algemene verdeelsleutel.", vme.name))

        company = vme.company_id
        Move = self.env["account.move"].with_company(company)
        journal = self.env["account.journal"].with_company(company).search(
            [("company_id", "=", company.id), ("type", "=", "sale")], limit=1
        )
        accounts = {
            fund: self.env["account.account"].with_company(company).search(
                [("company_ids", "in", company.id), ("code", "=", code)], limit=1)
            for fund, (code, _name) in VME_FUND_ACCOUNTS.items()
        }
        # LEGAL-CHECK: art. 3.89 §5 BW - working and reserve capital on separate bank accounts,
        # so each fund gets its own invoice paid to its own account.
        banks = {"working": vme.working_capital_bank_id, "reserve": vme.reserve_capital_bank_id}
        if not journal or not all(accounts.values()):
            raise UserError(self.env._("Het rekeningstelsel van %s is nog niet volledig geladen.", vme.name))
        if not all(banks.values()):
            raise UserError(self.env._("Vul de rekeningen voor werk- en reservekapitaal van %s in.", vme.name))
        if vme.untrusted_fund_bank_ids:
            raise UserError(self.env._(
                "De rekening(en) %(banks)s van %(vme)s zijn nog niet bevestigd. Open ze en zet "
                "\"Geld verzenden\" aan; anders laat Odoo ze weg van de provisieoproepen.",
                banks=", ".join(vme.untrusted_fund_bank_ids.mapped("acc_number")), vme=vme.name,
            ))

        call = self.env["vme.provision.call"].create({
            "budget_id": budget.id, "number": self.number,
            "date": self.invoice_date, "date_due": self.date_due,
        })
        key_lines = key.line_ids.filtered("shares")
        owners = {}
        for key_line in key_lines:
            owner = key_line.lot_id._get_owner_on(self.invoice_date)
            if not owner:
                raise UserError(self.env._(
                    "Kavel %(lot)s heeft geen eigenaar op %(date)s.",
                    lot=key_line.lot_id.display_name, date=fields.Date.to_string(self.invoice_date),
                ))
            owners[key_line] = owner

        invoices = self.env["account.move"]
        for fund, yearly in (("working", budget.working_capital_budget), ("reserve", budget.reserve_capital_contribution)):
            if not yearly:
                continue
            lot_amounts = largest_remainder(yearly / calls, key_lines.mapped("shares"), 2)
            lines_by_owner = {}
            for key_line, amount in zip(key_lines, lot_amounts):
                if not amount:
                    continue
                lines_by_owner.setdefault(owners[key_line], []).append(Command.create({
                    "name": self.env._(
                        "%(fund)s oproep %(number)s/%(calls)s %(year)s - kavel %(lot)s (%(shares)s/%(total)s)",
                        fund=FUND_LABELS[fund], number=self.number, calls=calls, year=self.year,
                        lot=key_line.lot_id.name, shares=f"{key_line.shares:g}", total=f"{key.total_shares:g}",
                    ),
                    "quantity": 1,
                    "price_unit": amount,
                    "account_id": accounts[fund].id,
                    "tax_ids": [Command.clear()],
                }))
            invoices |= Move.create([{
                "move_type": "out_invoice",
                "journal_id": journal.id,
                "partner_id": owner.id,
                "invoice_date": self.invoice_date,
                "invoice_date_due": self.date_due,
                "partner_bank_id": banks[fund].id,
                "vme_provision_call_id": call.id,
                "vme_fund": fund,
                "invoice_line_ids": lines,
            } for owner, lines in lines_by_owner.items()])
        return invoices
