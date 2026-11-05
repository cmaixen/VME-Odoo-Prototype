import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VmeAssociation(models.Model):
    _name = "vme.association"
    _description = "Vereniging van mede-eigenaars"
    _order = "name"

    # LEGAL-CHECK: art. 3.89 §5 BW - every VME keeps its own accounts,
    # so each association gets its own res.company.
    # Not required=True: the web client would then demand it before create() can make it.
    company_id = fields.Many2one(
        "res.company", string="Company", ondelete="restrict", index=True
    )
    name = fields.Char(related="company_id.name", string="Naam", readonly=False, store=True)
    active = fields.Boolean(string="Actief", default=True)
    kbo_number = fields.Char(
        related="company_id.company_registry", string="KBO-nummer", readonly=False
    )
    street = fields.Char(related="company_id.street", string="Straat", readonly=False)
    zip = fields.Char(related="company_id.zip", string="Postcode", readonly=False)
    city = fields.Char(related="company_id.city", string="Gemeente", readonly=False)
    country_id = fields.Many2one(
        related="company_id.country_id", string="Land", readonly=False
    )
    partner_id = fields.Many2one(related="company_id.partner_id", string="Partner")

    # LEGAL-CHECK: art. 3.89 §5 BW - working and reserve capital on separate accounts.
    working_capital_bank_id = fields.Many2one(
        "res.partner.bank",
        string="Rekening werkkapitaal",
        domain="[('partner_id', '=', partner_id)]",
    )
    reserve_capital_bank_id = fields.Many2one(
        "res.partner.bank",
        string="Rekening reservekapitaal",
        domain="[('partner_id', '=', partner_id)]",
    )

    untrusted_fund_bank_ids = fields.Many2many(
        "res.partner.bank", string="Niet-bevestigde rekeningen", compute="_compute_untrusted_fund_bank_ids"
    )

    lot_ids = fields.One2many("vme.lot", "association_id", string="Kavels")
    key_ids = fields.One2many("vme.key", "association_id", string="Verdeelsleutels")
    distribution_rule_ids = fields.One2many("vme.distribution.rule", "association_id", string="Verdeelregels")
    budget_ids = fields.One2many("vme.budget", "association_id", string="Budgetten")
    lot_count = fields.Integer(string="Aantal kavels", compute="_compute_counts")
    key_count = fields.Integer(string="Aantal sleutels", compute="_compute_counts")
    owner_count = fields.Integer(string="Aantal eigenaars", compute="_compute_counts")
    notes = fields.Html(string="Notities")

    _company_required = models.Constraint(
        "CHECK (company_id IS NOT NULL)",
        "Elke VME moet een eigen bedrijf hebben.",
    )
    _company_unique = models.Constraint(
        "UNIQUE (company_id)",
        "Een bedrijf kan maar bij één VME horen.",
    )

    @api.depends("lot_ids", "key_ids", "lot_ids.current_owner_id")
    def _compute_counts(self):
        for vme in self:
            vme.lot_count = len(vme.lot_ids)
            vme.key_count = len(vme.key_ids)
            vme.owner_count = len(vme.lot_ids.current_owner_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("company_id"):
                company = self.env["res.company"].sudo().create({
                    "name": vals.get("name") or self.env._("Nieuwe VME"),
                    "country_id": vals.get("country_id") or self.env.ref("base.be").id,
                    "currency_id": self.env.ref("base.EUR").id,
                    # LEGAL-CHECK: KB 12 juli 2012 (minimum chart of accounts for VMEs).
                    # The full Belgian PCMN is the closest standard Odoo chart for now.
                    "chart_template": "be_comp",
                })
                # Syndic staff work on every VME, so every internal user gets access to it,
                # not only the user who created it (which may be the system user in a script).
                internal_users = self.env["res.users"].sudo().search([("share", "=", False)]) | self.env.user
                internal_users.sudo().write({"company_ids": [fields.Command.link(company.id)]})
                vals["company_id"] = company.id
        return super().create(vals_list)

    @api.constrains("kbo_number")
    def _check_kbo_number(self):
        for vme in self:
            if vme.kbo_number and not self._is_valid_kbo(vme.kbo_number):
                raise ValidationError(self.env._(
                    "Het KBO-nummer %(kbo)s is ongeldig. Gebruik 10 cijfers, "
                    "bijvoorbeeld 0123.456.749.", kbo=vme.kbo_number,
                ))

    @api.model
    def _is_valid_kbo(self, value):
        digits = re.sub(r"\D", "", value or "")
        if len(digits) != 10 or digits[0] not in "01":
            return False
        return 97 - int(digits[:8]) % 97 == int(digits[8:])

    @api.constrains("working_capital_bank_id", "reserve_capital_bank_id")
    def _check_separate_bank_accounts(self):
        # LEGAL-CHECK: art. 3.89 §5 BW - working and reserve capital must not share an account.
        for vme in self:
            working = vme.working_capital_bank_id
            reserve = vme.reserve_capital_bank_id
            if working and reserve and working.sanitized_acc_number == reserve.sanitized_acc_number:
                raise ValidationError(self.env._(
                    "Werkkapitaal en reservekapitaal moeten op aparte bankrekeningen staan."
                ))

    @api.depends("working_capital_bank_id.allow_out_payment", "reserve_capital_bank_id.allow_out_payment")
    def _compute_untrusted_fund_bank_ids(self):
        # Odoo only puts a company bank account on customer invoices once a person with the
        # right permissions has trusted it ("Send Money"); scripts may not do that on purpose.
        for vme in self:
            vme.untrusted_fund_bank_ids = (vme.working_capital_bank_id | vme.reserve_capital_bank_id).filtered(
                lambda bank: not bank.allow_out_payment
            )

    def _ensure_fund_bank_journals(self):
        """One bank journal per fund, linked to its bank account, so payments land on the right fund.

        Returns {vme: {"working": journal, "reserve": journal}}.
        """
        # LEGAL-CHECK: art. 3.89 §5 BW - working and reserve capital on separate bank accounts.
        result = {}
        for vme in self.sudo():
            Journal = self.env["account.journal"].sudo().with_company(vme.company_id)
            bank_journals = Journal.search([("company_id", "=", vme.company_id.id), ("type", "=", "bank")])
            journals = {}
            for fund, bank, code, name in (
                ("working", vme.working_capital_bank_id, "WK", self.env._("Werkkapitaal")),
                ("reserve", vme.reserve_capital_bank_id, "RK", self.env._("Reservekapitaal")),
            ):
                journal = bank_journals.filtered(lambda j, b=bank: j.bank_account_id == b)[:1]
                if not journal:
                    # Reuse the default bank journal of the chart for the working capital.
                    free = bank_journals.filtered(lambda j: not j.bank_account_id and j not in journals.values())
                    journal = free[:1] if fund == "working" else Journal.browse()
                    if journal:
                        journal.write({"bank_account_id": bank.id, "name": name, "code": code})
                    else:
                        journal = Journal.create({
                            "name": name, "code": code, "type": "bank",
                            "bank_account_id": bank.id, "company_id": vme.company_id.id,
                        })
                journals[fund] = journal
            result[vme] = journals
        return result

    def _action_open_related(self, model, name):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": [("association_id", "=", self.id)],
            "context": {"default_association_id": self.id},
        }

    def action_open_lots(self):
        return self._action_open_related("vme.lot", self.env._("Kavels"))

    def action_open_keys(self):
        return self._action_open_related("vme.key", self.env._("Verdeelsleutels"))

    def action_open_ownerships(self):
        action = self._action_open_related("vme.ownership", self.env._("Eigendommen"))
        action["domain"] = [("lot_id.association_id", "=", self.id)]
        action["context"] = {}
        return action
