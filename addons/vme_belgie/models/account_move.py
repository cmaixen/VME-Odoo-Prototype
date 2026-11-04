from odoo import api, fields, models
from odoo.exceptions import UserError

from .allocation_tools import largest_remainder

AMOUNT_DIGITS = 2


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_association_id = fields.Many2one(
        "vme.association",
        string="VME",
        compute="_compute_vme_association_id",
        store=True,
        index=True,
    )
    vme_period_start = fields.Date(
        string="Kostperiode van",
        compute="_compute_vme_period",
        store=True,
        readonly=False,
        help="Periode waarop de kost slaat. Bij een verkoop wordt de kost pro rata "
             "over de dagen eigendom in deze periode verdeeld.",
    )
    vme_period_end = fields.Date(
        string="Kostperiode tot", compute="_compute_vme_period", store=True, readonly=False
    )
    vme_allocation_ids = fields.One2many("vme.cost.allocation", "move_id", string="Kostenverdeling")
    vme_allocation_owner_count = fields.Integer(compute="_compute_vme_allocation_owner_count")

    @api.depends("company_id")
    def _compute_vme_association_id(self):
        # Each VME is its own company, so the company tells which VME a bill belongs to.
        associations = self.env["vme.association"].sudo().with_context(active_test=False).search(
            [("company_id", "in", self.company_id.ids)]
        )
        by_company = {vme.company_id: vme for vme in associations}
        for move in self:
            move.vme_association_id = by_company.get(move.company_id, False)

    @api.depends("invoice_date")
    def _compute_vme_period(self):
        for move in self:
            if not move.vme_period_start:
                move.vme_period_start = move.invoice_date
            if not move.vme_period_end:
                move.vme_period_end = move.invoice_date

    @api.depends("vme_allocation_ids.partner_id")
    def _compute_vme_allocation_owner_count(self):
        for move in self:
            move.vme_allocation_owner_count = len(move.vme_allocation_ids.partner_id)

    def _vme_distributable_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(lambda line: line.display_type == "product")

    def _vme_distribute(self):
        """(Re)build the cost allocation of these vendor bills per owner."""
        allocation_vals = []
        for move in self:
            move._vme_check_distributable()
            vme = move.vme_association_id
            start, end = move.vme_period_start, move.vme_period_end
            period_days = (end - start).days + 1
            sign = -1 if move.move_type == "in_refund" else 1
            for line in move._vme_distributable_lines():
                amount = sign * move.currency_id._convert(
                    line.price_total, move.company_currency_id, move.company_id,
                    move.invoice_date or fields.Date.context_today(move),
                )
                key_lines = line.vme_key_id.line_ids.filtered("shares")
                lot_amounts = largest_remainder(amount, key_lines.mapped("shares"), AMOUNT_DIGITS)
                for key_line, lot_amount in zip(key_lines, lot_amounts):
                    segments = move._vme_ownership_segments(key_line.lot_id, start, end, period_days)
                    owner_amounts = largest_remainder(lot_amount, [s[3] for s in segments], AMOUNT_DIGITS)
                    for (partner, seg_start, seg_end, days), owner_amount in zip(segments, owner_amounts):
                        allocation_vals.append({
                            "move_id": move.id,
                            "move_line_id": line.id,
                            "association_id": vme.id,
                            "key_id": line.vme_key_id.id,
                            "lot_id": key_line.lot_id.id,
                            "partner_id": partner.id,
                            "shares": key_line.shares,
                            "date_from": seg_start,
                            "date_to": seg_end,
                            "days": days,
                            "amount": owner_amount,
                        })
        Allocation = self.env["vme.cost.allocation"].sudo()
        Allocation.search([("move_id", "in", self.ids)]).unlink()
        return Allocation.create(allocation_vals)

    def _vme_check_distributable(self):
        self.ensure_one()
        if self.move_type not in ("in_invoice", "in_refund"):
            raise UserError(self.env._("Alleen leveranciersfacturen en -creditnota's kunnen verdeeld worden."))
        if not self.vme_association_id:
            raise UserError(self.env._("Deze factuur hoort niet bij een VME."))
        if not self.vme_period_start or not self.vme_period_end:
            raise UserError(self.env._("Vul de kostperiode in."))
        if self.vme_period_end < self.vme_period_start:
            raise UserError(self.env._("Het einde van de kostperiode ligt voor het begin."))
        lines = self._vme_distributable_lines()
        if not lines:
            raise UserError(self.env._("Deze factuur heeft geen lijnen om te verdelen."))
        missing = lines.filtered(lambda line: not line.vme_key_id)
        if missing:
            raise UserError(self.env._(
                "Kies een verdeelsleutel voor elke factuurlijn. Zonder sleutel: %s",
                ", ".join(missing.mapped("name")),
            ))
        foreign = lines.filtered(lambda line: line.vme_key_id.association_id != self.vme_association_id)
        if foreign:
            raise UserError(self.env._(
                "De sleutel van lijn '%s' hoort niet bij %s.",
                foreign[0].name, self.vme_association_id.name,
            ))

    def _vme_ownership_segments(self, lot, start, end, period_days):
        """Owners of a lot within [start, end] as (partner, from, to, days); must cover every day."""
        # LEGAL-CHECK: art. 3.94 BW - costs are split between seller and buyer by the
        # number of days each one owned the lot within the cost period.
        segments = []
        for ownership in lot.ownership_ids.sorted("date_start"):
            seg_start = max(start, ownership.date_start)
            seg_end = min(end, ownership.date_end) if ownership.date_end else end
            if seg_start <= seg_end:
                segments.append((ownership.partner_id, seg_start, seg_end, (seg_end - seg_start).days + 1))
        if sum(s[3] for s in segments) != period_days:
            raise UserError(self.env._(
                "Kavel %(lot)s heeft niet voor de hele kostperiode een eigenaar "
                "(%(start)s tot %(end)s). Vul de eigendommen aan.",
                lot=lot.display_name,
                start=fields.Date.to_string(start),
                end=fields.Date.to_string(end),
            ))
        return segments

    def action_vme_distribute(self):
        self._vme_distribute()
        return self.action_vme_open_allocations()

    def action_vme_open_allocations(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_cost_allocation_action")
        action["domain"] = [("move_id", "in", self.ids)]
        action["context"] = {"search_default_group_partner": 1}
        return action


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    vme_key_id = fields.Many2one(
        "vme.key",
        string="Verdeelsleutel",
        domain="[('association_id.company_id', '=', company_id)]",
        index=True,
    )
