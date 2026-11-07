from collections import defaultdict
from datetime import date

from odoo import api, fields, models

from .vme_building_card import INSPECTION_CARD_STATES

# Bills on the supplier card: the most recent ones, the open ones always.
SUPPLIER_CARD_BILLS = 15


class ResPartner(models.Model):
    _inherit = "res.partner"

    vme_supplier_contract_count = fields.Integer(string="Contracten", compute="_compute_vme_supplier_card")
    vme_supplier_currency_id = fields.Many2one("res.currency", compute="_compute_vme_supplier_card")
    vme_supplier_open_amount = fields.Monetary(
        string="Te betalen", compute="_compute_vme_supplier_card", currency_field="vme_supplier_currency_id")
    vme_is_supplier = fields.Boolean(
        string="Leverancier van een VME", compute="_compute_vme_supplier_card", search="_search_vme_is_supplier",
        help="Heeft facturen, een contract, een installatie in onderhoud of keuring, of werken in een VME.")
    vme_supplier_vme_names = fields.Char(string="VME's", compute="_compute_vme_supplier_card")
    vme_supplier_card_html = fields.Html(
        string="Leverancierskaart", compute="_compute_vme_supplier_card_html", sanitize=False)

    def _vme_supplier_card_scope(self):
        """The VMEs the current user may see: record rules limit an auditor to his own."""
        return self.env["vme.association"].search([])

    def _get_vme_supplier_card_data(self, today=None):
        """Contracts, installations and inspections, works and bills of this supplier in all VMEs."""
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        partner = self.commercial_partner_id
        vmes = self._vme_supplier_card_scope().sudo()
        companies = vmes.company_id
        partners = self.sudo().search([("id", "child_of", partner.id)])

        contracts = self.env["vme.contract"].sudo().search([
            ("association_id", "in", vmes.ids), ("partner_id", "in", partners.ids)], order="association_id, date_end")
        Installation = self.env["vme.installation"].sudo()
        installations = Installation.search([
            ("association_id", "in", vmes.ids), "|",
            ("maintenance_partner_id", "in", partners.ids), ("inspection_partner_id", "in", partners.ids)])
        inspections = self.env["vme.inspection"].sudo().search([
            ("association_id", "in", vmes.ids), ("partner_id", "in", partners.ids)], order="date desc", limit=10)
        works = self.env["vme.works"].sudo().search([
            ("association_id", "in", vmes.ids), ("contractor_id", "in", partners.ids),
            ("state", "not in", ("closed", "cancelled"))])
        rules = self.env["vme.distribution.rule"].sudo().search([
            ("association_id", "in", vmes.ids), ("partner_id", "in", partners.ids)])

        Move = self.env["account.move"].sudo()
        bill_domain = [
            ("company_id", "in", companies.ids), ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"), ("commercial_partner_id", "=", partner.id),
        ]
        open_bills = Move.search(bill_domain + [("amount_residual", ">", 0)], order="invoice_date_due, id")
        recent_bills = Move.search(bill_domain, order="invoice_date desc, id desc", limit=SUPPLIER_CARD_BILLS)
        year_bills = Move.search(bill_domain + [("invoice_date", ">=", date(today.year, 1, 1))])
        vme_by_company = {vme.company_id: vme for vme in vmes}

        payment_terms = [{
            "vme": vme,
            "term": partner.with_company(vme.company_id).sudo().property_supplier_payment_term_id,
        } for vme in vmes.filtered(lambda v: v in contracts.association_id or v.company_id in recent_bills.company_id
                                   or v in rules.association_id)]
        rule_lines = [{
            "vme": rule.association_id,
            "key": rule.key_id,
            "account": rule.account_id.with_company(rule.company_id),
        } for rule in rules]

        totals = {}
        for bill in year_bills:
            currency = bill.company_currency_id
            totals.setdefault(currency, 0.0)
            totals[currency] += -bill.amount_total_signed
        return {
            "partner": partner,
            "today": today,
            "vmes": vmes,
            "contracts": contracts,
            "installations": installations,
            "inspection_card_states": INSPECTION_CARD_STATES,
            "inspections": inspections,
            "works": works,
            "rules": rule_lines,
            "open_bills": open_bills,
            "recent_bills": recent_bills,
            "year_totals": list(totals.items()),
            "payment_terms": payment_terms,
            "vme_by_company": vme_by_company,
            "selection_label": self.env["vme.association"]._selection_label,
        }

    @api.depends_context("uid")
    def _compute_vme_supplier_card(self):
        vmes = self._vme_supplier_card_scope().sudo()
        role_partners = self._vme_supplier_partners()
        # One query per model for the whole list, grouped on the commercial partner.
        commercials = self.filtered("id").commercial_partner_id
        contract_count, vme_ids = defaultdict(int), defaultdict(set)
        open_amount, bill_companies = defaultdict(float), defaultdict(set)
        if commercials:
            for contract in self.env["vme.contract"].sudo().search([
                    ("association_id", "in", vmes.ids), ("partner_id", "child_of", commercials.ids),
                    ("state", "=", "running")]):
                contract_count[contract.partner_id.commercial_partner_id] += 1
                vme_ids[contract.partner_id.commercial_partner_id].add(contract.association_id.id)
            for installation in self.env["vme.installation"].sudo().search([
                    ("association_id", "in", vmes.ids), "|", ("maintenance_partner_id", "child_of", commercials.ids),
                    ("inspection_partner_id", "child_of", commercials.ids)]):
                for supplier in (installation.maintenance_partner_id | installation.inspection_partner_id).commercial_partner_id:
                    vme_ids[supplier].add(installation.association_id.id)
            for works in self.env["vme.works"].sudo().search([
                    ("association_id", "in", vmes.ids), ("contractor_id", "child_of", commercials.ids)]):
                vme_ids[works.contractor_id.commercial_partner_id].add(works.association_id.id)
            for supplier, company, amount in self.env["account.move"].sudo()._read_group([
                    ("company_id", "in", vmes.company_id.ids), ("move_type", "in", ("in_invoice", "in_refund")),
                    ("state", "=", "posted"), ("commercial_partner_id", "in", commercials.ids)],
                    ["commercial_partner_id", "company_id"], ["amount_residual_signed:sum"]):
                open_amount[supplier] -= amount
                bill_companies[supplier].add(company.id)
        for partner in self:
            commercial = partner.commercial_partner_id
            if not partner.id:
                partner.update({"vme_supplier_contract_count": 0, "vme_supplier_open_amount": 0.0,
                                "vme_supplier_vme_names": False, "vme_supplier_currency_id": False,
                                "vme_is_supplier": False})
                continue
            companies = bill_companies[commercial]
            names = (vmes.browse(vme_ids[commercial])
                     | vmes.filtered(lambda v, c=companies: v.company_id.id in c)).mapped("name")
            currency = vmes.company_id.filtered(lambda c, ids=companies: c.id in ids).currency_id
            partner.update({
                "vme_supplier_currency_id": (currency or vmes.company_id.currency_id)[:1],
                "vme_is_supplier": bool(commercial.supplier_rank) or commercial in role_partners,
                "vme_supplier_contract_count": contract_count[commercial],
                "vme_supplier_open_amount": open_amount[commercial],
                "vme_supplier_vme_names": ", ".join(sorted(set(names))) or False,
            })

    @api.model
    def _vme_supplier_partners(self):
        """Commercial partners with a contract, an installation or works in a VME, without bills too."""
        vmes = self._vme_supplier_card_scope().sudo()
        installations = self.env["vme.installation"].sudo().search([("association_id", "in", vmes.ids)])
        partners = (
            self.env["vme.contract"].sudo().search([("association_id", "in", vmes.ids)]).partner_id
            | installations.maintenance_partner_id | installations.inspection_partner_id
            | self.env["vme.works"].sudo().search([("association_id", "in", vmes.ids)]).contractor_id
        )
        return partners.commercial_partner_id

    def _search_vme_is_supplier(self, operator, value):
        if operator not in ("=", "!="):
            return NotImplemented
        domain = ["|", ("supplier_rank", ">", 0), ("id", "in", self._vme_supplier_partners().ids)]
        return domain if (operator == "=") == bool(value) else ["!", *domain]

    @api.depends_context("uid")
    def _compute_vme_supplier_card_html(self):
        QWeb = self.env["ir.qweb"]
        for partner in self:
            partner.vme_supplier_card_html = partner.id and QWeb._render(
                "vme_belgie.supplier_card_content", partner._get_vme_supplier_card_data())

    def action_open_vme_supplier_card(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Leverancierskaart"),
            "res_model": "res.partner",
            "res_id": self.commercial_partner_id.id,
            "view_mode": "form",
            "views": [(self.env.ref("vme_belgie.res_partner_view_form_supplier_card").id, "form")],
            "target": "current",
        }
