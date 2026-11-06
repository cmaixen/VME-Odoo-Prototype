import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from .allocation_tools import largest_remainder
from .bank_formats import make_structured
from .vme_meter import MissingReading
from .vme_access import check_not_auditor

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
    vme_provision_call_id = fields.Many2one(
        "vme.provision.call", string="Provisieoproep", index=True, ondelete="restrict", copy=False
    )
    vme_fund = fields.Selection(
        [("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")], string="Fonds", copy=False
    )
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

    @api.depends("vme_fund", "vme_association_id")
    def _compute_partner_bank_id(self):
        super()._compute_partner_bank_id()
        # LEGAL-CHECK: art. 3.89 §5 BW - a provision is paid to the bank account of its fund.
        for move in self.filtered("vme_fund"):
            # Look the VME up by company: vme_association_id may not be computed yet on create.
            vme = move.vme_association_id or self.env["vme.association"].sudo().search(
                [("company_id", "=", move.company_id.id)], limit=1
            )
            move.partner_bank_id = (
                vme.working_capital_bank_id if move.vme_fund == "working" else vme.reserve_capital_bank_id
            )

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

    def _get_invoice_reference_be_invoice(self):
        """Structured communication from the invoice number instead of the database id, for VME invoices.

        F/2026/00075 becomes +++120/2600/075xx+++ (1 = invoice, 2 = credit note, then year and number):
        the syndic can read the invoice in the communication, and the same demo always gives the
        same communications, so the fictitious bank statements match.
        """
        self.ensure_one()
        match = re.fullmatch(r"\D*(\d{4})\D+(\d{1,5})", self.name or "")
        if not self.vme_association_id or not match:
            return super()._get_invoice_reference_be_invoice()
        kind = 2 if self.move_type in ("out_refund", "in_refund") else 1
        return make_structured(f"{kind}{match[1]}{int(match[2]):05d}")

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
                if line.vme_key_id.key_type == "consumption":
                    rows = move._vme_consumption_rows(line.vme_key_id, amount, start, end, period_days)
                else:
                    rows = move._vme_share_rows(line.vme_key_id, amount, start, end, period_days)
                for key_line, (partner, seg_start, seg_end, days), owner_amount, extra in rows:
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
                        **extra,
                    })
        Allocation = self.env["vme.cost.allocation"].sudo()
        Allocation.search([("move_id", "in", self.ids)]).unlink()
        return Allocation.create(allocation_vals)

    def _vme_share_rows(self, key, amount, start, end, period_days):
        """Split an amount over the lots by shares, then over the owners by days.

        Yields (key line, ownership segment, amount, extra allocation values).
        """
        key_lines = key.line_ids.filtered("shares")
        lot_amounts = largest_remainder(amount, key_lines.mapped("shares"), AMOUNT_DIGITS)
        for key_line, lot_amount in zip(key_lines, lot_amounts):
            segments = self._vme_ownership_segments(key_line.lot_id, start, end, period_days)
            owner_amounts = largest_remainder(lot_amount, [s[3] for s in segments], AMOUNT_DIGITS)
            for segment, owner_amount in zip(segments, owner_amounts):
                yield key_line, segment, owner_amount, {}

    def _vme_consumption_rows(self, key, amount, start, end, period_days):
        """Split an amount for a key "op verbruik": a fixed part by shares, a variable part by consumption.

        The fixed part goes over the lots by their shares and over the owners by days, like any key.
        The variable part goes over the lots by the consumption of their meters in the cost period, and
        over the owners of a lot by the consumption within their own days of ownership: with a reading on
        the deed date that is the real consumption, otherwise it is interpolated per day between readings.
        """
        # LEGAL-CHECK: art. 3.94 BW - between seller and buyer, the consumption of each one's
        # ownership period; without a reading at the deed, pro rata per day between two readings.
        key_lines = key.line_ids
        fixed_total, variable_total = largest_remainder(
            amount, [key.fixed_percent, 100.0 - key.fixed_percent], AMOUNT_DIGITS
        )
        fixed_lots = largest_remainder(fixed_total, key_lines.mapped("shares"), AMOUNT_DIGITS)
        segments_by_line = {
            key_line: self._vme_ownership_segments(key_line.lot_id, start, end, period_days)
            for key_line in key_lines
        }
        consumption = {key_line: [0.0] * len(segments) for key_line, segments in segments_by_line.items()}
        if variable_total:
            consumption = self._vme_segment_consumption(key, segments_by_line)
        lot_consumption = [sum(consumption[key_line]) for key_line in key_lines]
        variable_lots = (
            largest_remainder(variable_total, lot_consumption, AMOUNT_DIGITS) if variable_total
            else [0.0] * len(key_lines)
        )
        for key_line, fixed_lot, variable_lot in zip(key_lines, fixed_lots, variable_lots):
            segments = segments_by_line[key_line]
            fixed_owners = largest_remainder(fixed_lot, [s[3] for s in segments], AMOUNT_DIGITS)
            if sum(consumption[key_line]) > 0:
                variable_owners = largest_remainder(variable_lot, consumption[key_line], AMOUNT_DIGITS)
            else:
                variable_owners = [0.0] * len(segments)
            for segment, fixed, variable, used in zip(segments, fixed_owners, variable_owners, consumption[key_line]):
                yield key_line, segment, round(fixed + variable, AMOUNT_DIGITS), {
                    "fixed_amount": fixed,
                    "variable_amount": variable,
                    "consumption": round(used, 3),
                }

    def _vme_segment_consumption(self, key, segments_by_line):
        """Consumption per ownership segment, {key line: [consumption per segment]}; raise if incomplete."""
        no_meter, missing = [], {}
        result = {}
        for key_line, segments in segments_by_line.items():
            meters = key_line.lot_id.meter_ids.filtered(lambda m: m.meter_type == key.meter_type)
            if not meters:
                no_meter.append(key_line.lot_id.name)
                continue
            values = []
            for _partner, seg_start, seg_end, _days in segments:
                used = 0.0
                for meter in meters:
                    try:
                        used += meter._consumption(seg_start, seg_end)
                    except MissingReading as error:
                        missing.setdefault(meter, error.day)
                values.append(used)
            result[key_line] = values
        if no_meter or missing:
            problems = []
            if no_meter:
                problems.append(self.env._(
                    "Geen teller \"%(type)s\" voor kavel %(lots)s.",
                    type=dict(key._fields["meter_type"].selection)[key.meter_type], lots=", ".join(no_meter),
                ))
            if missing:
                problems.append(self.env._(
                    "Ontbrekende meterstand vóór of na %(date)s voor teller %(meters)s.",
                    date=min(missing.values()).strftime("%d/%m/%Y"),
                    meters=", ".join(f"{m.name} ({m.lot_id.name})" for m in missing),
                ))
            raise UserError(self.env._(
                "Sleutel %(key)s verdeelt op verbruik, maar het verbruik in de kostperiode is niet volledig "
                "gekend. %(problems)s Lees de meterstanden in en verdeel opnieuw.",
                key=key.display_name, problems=" ".join(problems),
            ))
        if sum(sum(values) for values in result.values()) <= 0:
            raise UserError(self.env._(
                "Sleutel %s verdeelt op verbruik, maar er is geen verbruik in de kostperiode.", key.display_name
            ))
        return result

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
        empty = lines.vme_key_id.filtered(lambda key: not any(key.line_ids.mapped("shares")))
        if empty:
            raise UserError(self.env._(
                "De sleutel '%s' heeft geen kavels met een aandeel.", empty[0].display_name,
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
        check_not_auditor(self.env)  # the allocations are written as sudo
        self._vme_distribute()
        return self.action_vme_open_allocations()

    def action_vme_open_allocations(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_cost_allocation_action")
        action["domain"] = [("move_id", "in", self.ids)]
        action["context"] = {"search_default_group_partner": 1}
        return action

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        vme_bills = posted.filtered(lambda m: m.vme_association_id and m.move_type in ("in_invoice", "in_refund"))
        vme_bills._vme_auto_distribute()
        vme_bills._vme_register_inspections()
        return posted

    def _vme_register_inspections(self):
        """A posted bill of an installation's inspection body records that inspection."""
        Rule = self.env["vme.distribution.rule"].sudo()
        for move in self.filtered(lambda m: m.move_type == "in_invoice"):
            installation = Rule._find_rule(move.company_id, move.partner_id).installation_id
            body = installation.inspection_partner_id.commercial_partner_id
            if installation and body and body == move.partner_id.commercial_partner_id:
                installation._register_inspection_from_bill(move)

    def _vme_auto_distribute(self):
        """Distribute posted bills whose lines all have a key; never block the posting."""
        for move in self:
            unkeyed = move._vme_distributable_lines().filtered(lambda line: not line.vme_key_id)
            if unkeyed:
                move.message_post(body=self.env._(
                    "Niet automatisch verdeeld: geen verdeelsleutel op %s. "
                    "Kies een sleutel en klik op \"Verdeel over eigenaars\".",
                    ", ".join(unkeyed.mapped("name")),
                ))
                continue
            try:
                with self.env.cr.savepoint():
                    allocations = move._vme_distribute()
            except UserError as error:
                move.message_post(body=self.env._("Automatische verdeling mislukt: %s", error.args[0]))
                continue
            move.message_post(body=self.env._(
                "Automatisch verdeeld over %s eigenaars.", len(allocations.partner_id)
            ))

    def _extend_with_attachments(self, files_data, new=False):
        res = super()._extend_with_attachments(files_data, new)
        # Peppol/UBL invoices state the period they cover; standard Odoo ignores it.
        for file_data in files_data:
            tree = file_data.get("xml_tree")
            if tree is None:
                continue
            start = tree.findtext("./{*}InvoicePeriod/{*}StartDate")
            end = tree.findtext("./{*}InvoicePeriod/{*}EndDate")
            for move in self.filtered("vme_association_id"):
                if start and end:
                    move.write({"vme_period_start": start, "vme_period_end": end})
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    vme_key_id = fields.Many2one(
        "vme.key",
        string="Verdeelsleutel",
        compute="_compute_vme_key_id",
        store=True,
        readonly=False,
        domain="[('association_id.company_id', '=', company_id)]",
        index=True,
    )

    def _vme_rule(self):
        self.ensure_one()
        move = self.move_id
        if (self.display_type != "product" or move.move_type not in ("in_invoice", "in_refund")
                or not move.vme_association_id):
            return self.env["vme.distribution.rule"]
        return self.env["vme.distribution.rule"].sudo()._find_rule(move.company_id, move.partner_id)

    @api.depends("move_id.partner_id", "move_id.company_id", "display_type")
    def _compute_vme_key_id(self):
        # Only fill an empty key, so a key chosen by hand is never overwritten.
        for line in self:
            if not line.vme_key_id:
                line.vme_key_id = line._vme_rule().key_id

    def _compute_account_id(self):
        super()._compute_account_id()
        for line in self.filtered(lambda l: not l.product_id):
            rule = line._vme_rule()
            if rule.account_id:
                line.account_id = rule.account_id
