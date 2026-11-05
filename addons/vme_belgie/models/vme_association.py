import functools
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VmeAssociation(models.Model):
    _name = "vme.association"
    # Chatter and activities: the AI mail assistant (ai/) puts its proposed replies here as to-dos.
    _inherit = ["mail.thread", "mail.activity.mixin"]
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

    bill_alias_email = fields.Char(
        string="E-mailadres voor facturen",
        compute="_compute_bill_alias_email",
        help="Leveranciers sturen hun facturen naar dit adres; elke mail met een factuur als bijlage "
        "wordt een conceptfactuur in deze VME.",
    )

    untrusted_fund_bank_ids = fields.Many2many(
        "res.partner.bank", string="Niet-bevestigde rekeningen", compute="_compute_untrusted_fund_bank_ids"
    )

    lot_ids = fields.One2many("vme.lot", "association_id", string="Kavels")
    key_ids = fields.One2many("vme.key", "association_id", string="Verdeelsleutels")
    distribution_rule_ids = fields.One2many("vme.distribution.rule", "association_id", string="Verdeelregels")
    budget_ids = fields.One2many("vme.budget", "association_id", string="Budgetten")
    installation_ids = fields.One2many("vme.installation", "association_id", string="Installaties")
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

    @api.model
    def _load_vme_chart(self, company_id):
        company = self.env["res.company"].sudo().browse(company_id)
        if company.exists() and not company.chart_template:
            # LEGAL-CHECK: KB 12 juli 2012 (minimum chart of accounts for VMEs).
            # The full Belgian PCMN is the closest standard Odoo chart for now.
            self.env["account.chart.template"].sudo().try_loading("be_comp", company, install_demo=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # An empty country from the form would overwrite Belgium on the company afterwards.
            vals["country_id"] = vals.get("country_id") or self.env.ref("base.be").id
            if not vals.get("company_id"):
                company = self.env["res.company"].sudo().create({
                    "name": vals.get("name") or self.env._("Nieuwe VME"),
                    "country_id": vals["country_id"],
                    "currency_id": self.env.ref("base.EUR").id,
                })
                # Load the chart explicitly once the company exists: setting chart_template on
                # create loads the accounts but leaves partners without a default payable and
                # receivable account in this company, so entering a bill by hand fails.
                self.env.cr.precommit.add(functools.partial(self._load_vme_chart, company.id))
                # Syndic staff work on every VME, so every internal user gets access to it,
                # not only the user who created it (which may be the system user in a script).
                internal_users = self.env["res.users"].sudo().search([("share", "=", False)]) | self.env.user
                internal_users.sudo().write({"company_ids": [fields.Command.link(company.id)]})
                vals["company_id"] = company.id
        return super().create(vals_list)

    def _purchase_journal(self):
        self.ensure_one()
        return self.env["account.journal"].sudo().search(
            [("company_id", "=", self.company_id.id), ("type", "=", "purchase")], order="sequence, id", limit=1
        )

    @api.depends("company_id")
    def _compute_bill_alias_email(self):
        for vme in self:
            vme.bill_alias_email = vme.company_id and vme._purchase_journal().alias_email or False

    @api.model
    def _ensure_all_bill_aliases(self):
        self.with_context(active_test=False).search([])._ensure_bill_alias()

    def _ensure_bill_alias(self):
        """Give the purchase journal of each VME the alias facturen-<name>@<mail domain>.

        Odoo's own mail gateway then turns every mail to that address into a draft vendor bill
        in the company of the VME, and reads UBL attachments like an upload would.
        """
        Alias = self.env["mail.alias"].sudo()
        default_domain = self.env.ref("vme_belgie.mail_alias_domain_vme", raise_if_not_found=False)
        for vme in self.sudo():
            company = vme.company_id
            journal = vme._purchase_journal()
            if not journal:  # chart of accounts not loaded yet
                continue
            if not company.alias_domain_id and default_domain:
                company.alias_domain_id = default_domain
            name = Alias._sanitize_alias_name(f"facturen-{company.name}")
            if Alias.search_count([
                ("alias_name", "=", name), ("alias_domain_id", "=", company.alias_domain_id.id),
                ("id", "!=", journal.alias_id.id),
            ]):
                name = f"{name}-{company.id}"
            if journal.alias_name != name or journal.alias_domain_id != company.alias_domain_id:
                journal.write({"alias_name": name, "alias_domain_id": company.alias_domain_id.id})

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
