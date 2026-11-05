from datetime import date

from odoo import fields, models
from odoo.tools import float_is_zero

from .vme_meter import METER_UNITS


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    def _get_annual_statement(self, year, partners=None):
        """Annual statement of this VME per owner.

        Costs of the year are the cost allocations of posted vendor bills dated in that year.
        The balance settles those costs against the paid working capital provisions; reserve
        capital is reported separately because it is not refundable.
        Everything is read as sudo: a VME's records live in its own company, whatever companies
        the user has selected.
        """
        self.ensure_one()
        vme = self.sudo()
        currency = vme.company_id.currency_id
        start, end = date(year, 1, 1), date(year, 12, 31)

        bills = self.env["account.move"].sudo().search([
            ("company_id", "=", vme.company_id.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
            # Private costs of a request (e.g. a key for one owner) are charged to that owner, not distributed.
            ("vme_request_id", "=", False),
        ])
        # LEGAL-CHECK: art. 3.86 §3 BW - works paid from the reserve capital are not settled in
        # the working capital; each owner sees his share in them apart.
        reserve_bills = bills.filtered(lambda m: m.vme_reserve_move_id)
        allocations = (bills - reserve_bills).vme_allocation_ids
        reserve_allocations = reserve_bills.vme_allocation_ids
        # Provisions belong to the year of their budget, not of their invoice date: a call
        # for next year sent in December must not reduce this year's balance.
        provisions = self.env["account.move"].sudo().search([
            ("company_id", "=", vme.company_id.id),
            ("vme_provision_call_id.budget_id.year", "=", year),
            ("state", "=", "posted"),
        ])
        if partners is None:
            partners = allocations.partner_id | provisions.partner_id | reserve_allocations.partner_id
        else:
            partners = partners.sudo()

        key_totals = {}
        for allocation in allocations:
            key_totals[allocation.key_id] = key_totals.get(allocation.key_id, 0.0) + allocation.amount

        statements = []
        for partner in partners.sorted("name"):
            own = allocations.filtered(lambda a: a.partner_id == partner)
            keys = []
            for key in own.key_id.sorted("sequence"):
                key_allocations = own.filtered(lambda a, k=key: a.key_id == k)
                lot_shares = {}
                for allocation in key_allocations:
                    lot_shares[allocation.lot_id] = allocation.shares
                keys.append({
                    "key": key,
                    "total_vme": currency.round(key_totals[key]),
                    "shares": " + ".join(f"{s:g}" for s in lot_shares.values()),
                    "total_shares": key.total_shares,
                    "lots": ", ".join(lot.name for lot in lot_shares),
                    "amount": currency.round(sum(key_allocations.mapped("amount"))),
                    # Keys "op verbruik": the owner's consumption and the split into fixed and variable.
                    "consumption": key.key_type == "consumption" and {
                        "used": sum(key_allocations.mapped("consumption")),
                        "unit": METER_UNITS.get(key.meter_type, ""),
                        "fixed": currency.round(sum(key_allocations.mapped("fixed_amount"))),
                        "variable": currency.round(sum(key_allocations.mapped("variable_amount"))),
                    },
                })
            bill_lines = []
            for move in own.move_id.sorted(lambda m: (m.invoice_date, m.id)):
                move_allocations = own.filtered(lambda a, m=move: a.move_id == m)
                days = sorted(set(move_allocations.mapped("days")))
                period_days = (move.vme_period_end - move.vme_period_start).days + 1
                bill_lines.append({
                    "move": move,
                    "supplier": move.partner_id.name,
                    "description": move.ref or move.name,
                    "period": (move.vme_period_start, move.vme_period_end),
                    "keys": ", ".join(move_allocations.key_id.mapped("name")),
                    "total": move.amount_total,
                    "partial_days": days[0] if len(days) == 1 and days[0] < period_days else False,
                    "period_days": period_days,
                    "amount": currency.round(sum(move_allocations.mapped("amount"))),
                })
            funds = {}
            for fund in ("working", "reserve"):
                invoices = provisions.filtered(lambda m, f=fund: m.partner_id == partner and m.vme_fund == f)
                invoiced = sum(invoices.mapped("amount_total"))
                open_amount = sum(invoices.mapped("amount_residual"))
                funds[fund] = {
                    "invoiced": currency.round(invoiced),
                    "paid": currency.round(invoiced - open_amount),
                    "open": currency.round(open_amount),
                    "open_invoices": invoices.filtered(lambda m: not float_is_zero(m.amount_residual, precision_rounding=currency.rounding)),
                }
            reserve_works = []
            own_reserve = reserve_allocations.filtered(lambda a: a.partner_id == partner)
            for works in own_reserve.move_id.vme_works_id:
                works_allocations = own_reserve.filtered(lambda a, w=works: a.move_id.vme_works_id == w)
                reserve_works.append({
                    "works": works,
                    "total_vme": currency.round(-sum(works_allocations.move_id.mapped("amount_total_signed"))),
                    "amount": currency.round(sum(works_allocations.mapped("amount"))),
                })
            cost_total = currency.round(sum(own.mapped("amount")))
            balance = currency.round(cost_total - funds["working"]["paid"])
            ownerships = vme.lot_ids.ownership_ids.filtered(
                lambda o: o.partner_id == partner and o.date_start <= end and (not o.date_end or o.date_end >= start)
            )
            statements.append({
                "partner": partner,
                "ownerships": ownerships.sorted(lambda o: (o.lot_id.sequence, o.lot_id.name)),
                "keys": keys,
                "bills": bill_lines,
                "cost_total": cost_total,
                "working": funds["working"],
                "reserve": funds["reserve"],
                "balance": balance,
                "reserve_works": reserve_works,
                "reserve_works_total": currency.round(sum(w["amount"] for w in reserve_works)),
            })

        undistributed = bills.filtered(lambda m: not m.vme_allocation_ids)
        bills_total = currency.round(-sum(bills.mapped("amount_total_signed")))
        allocated_total = currency.round(sum((allocations | reserve_allocations).mapped("amount")))
        return {
            "vme": vme,
            "year": year,
            "currency": currency,
            "statements": statements,
            "bills_total": bills_total,
            "allocated_total": allocated_total,
            "undistributed_bills": undistributed,
            "is_complete": not undistributed and currency.is_zero(bills_total - allocated_total),
        }

    def action_open_annual_statement(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Jaarafrekening"),
            "res_model": "vme.annual.statement.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_association_id": self.id},
        }
