from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from ..models.vme_syndic import previous_quarter


class VmeFeeInvoiceWizard(models.TransientModel):
    _name = "vme.fee.invoice.wizard"
    _description = "Ereloonfacturen maken"

    date_from = fields.Date(string="Periode van", required=True,
                            default=lambda self: previous_quarter(fields.Date.context_today(self))[0])
    date_to = fields.Date(string="Periode tot", required=True,
                          default=lambda self: previous_quarter(fields.Date.context_today(self))[1])
    association_ids = fields.Many2many(
        "vme.association", string="VME's",
        default=lambda self: self.env.context.get("active_model") == "vme.association"
        and self.env.context.get("active_ids") or False,
        help="Leeg: alle VME's met een beheerovereenkomst.")

    def action_create(self):
        """One draft fee invoice per agreement and billing period (month or quarter) in the period."""
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(self.env._("Het einde van de periode ligt vóór het begin."))
        domain = [("date_start", "<=", self.date_to), "|", ("date_end", "=", False), ("date_end", ">=", self.date_from)]
        if self.association_ids:
            domain.append(("association_id", "in", self.association_ids.ids))
        invoices = self.env["account.move"]
        skipped = []
        for agreement in self.env["vme.management.agreement"].search(domain):
            for start, end in agreement._billing_periods(self.date_from, self.date_to):
                if agreement._fee_invoices_overlapping(start, end):
                    skipped.append(f"{agreement.association_id.name} {format_date(self.env, start)}")
                    continue
                invoices |= agreement._create_fee_invoice(start, end)
        if not invoices:
            raise UserError(self.env._(
                "Geen nieuwe ereloonfacturen voor deze periode. %s",
                self.env._("Al gefactureerd: %s.", ", ".join(skipped)) if skipped
                else self.env._("Kies een periode van volledige maanden of kwartalen.")))
        # The invoices live in the office company, which may not be selected in the company switcher:
        # a notification says where they are instead of a list that could look empty.
        offices = invoices.company_id
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Ereloonfacturen klaar"),
                "message": self.env._(
                    "%(count)s conceptfacturen in %(office)s. Kijk ze na onder VME > Syndicus > Ereloonfacturen "
                    "(vink uw kantoor aan in de bedrijvenkiezer) en bevestig ze.",
                    count=len(invoices), office=", ".join(offices.mapped("name"))),
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
