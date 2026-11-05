from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

from .account_chart_template import VME_FUND_ACCOUNTS
from .vme_access import AUDITOR_GROUP

ROLES = [
    ("chair", "Voorzitter raad van mede-eigendom"),
    ("member", "Lid raad van mede-eigendom"),
    ("auditor", "Commissaris van de rekeningen"),
]
COUNCIL_ROLES = ("chair", "member")

# LEGAL-CHECK: art. 3.90 §1 BW - a council is mandatory in a building with at least twenty lots,
# not counting cellars, garages and parking spaces. Storage rooms (bergingen) count as cellars here.
COUNCIL_REQUIRED_MIN_LOTS = 20
COUNCIL_EXCLUDED_LOT_TYPES = ("garage", "storage")


class VmeMandate(models.Model):
    _name = "vme.mandate"
    _description = "Mandaat in de raad van mede-eigendom of als commissaris van de rekeningen"
    _inherit = ["mail.thread"]
    _order = "association_id, date_start desc, role, id"

    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    role = fields.Selection(ROLES, string="Rol", required=True, default="member", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Persoon", required=True, index=True, tracking=True)
    email = fields.Char(related="partner_id.email", readonly=False)
    date_start = fields.Date(string="Begin mandaat", required=True, default=fields.Date.context_today, tracking=True)
    # LEGAL-CHECK: art. 3.90 §1 en art. 3.91 BW - council members and the auditor are appointed by the
    # general assembly for one year, renewable; the default end date follows that rule.
    date_end = fields.Date(
        string="Einde mandaat", compute="_compute_date_end", store=True, readonly=False, tracking=True,
        help="Standaard één jaar na het begin. De AV kan het mandaat hernieuwen met een nieuw mandaat.")
    assembly_item_id = fields.Many2one(
        "vme.assembly.item", string="Beslissing AV",
        domain="[('association_id', '=', association_id), ('outcome', '=', 'adopted')]",
        help="Het agendapunt waarop de AV deze persoon aanstelde.")
    is_current = fields.Boolean(string="Lopend", compute="_compute_is_current", search="_search_is_current")
    is_owner = fields.Boolean(
        string="Mede-eigenaar", compute="_compute_is_owner",
        help="Eigenaar van een kavel in deze VME bij het begin van het mandaat.")
    audit_year = fields.Integer(
        string="Te controleren boekjaar", compute="_compute_audit_year", store=True, readonly=False,
        help="Het boekjaar waarover de commissaris verslag uitbrengt op de volgende AV.")
    user_id = fields.Many2one("res.users", string="Gebruiker", readonly=True, copy=False)
    note = fields.Text(string="Notities")

    @api.depends("date_start")
    def _compute_date_end(self):
        for mandate in self:
            if mandate.date_start and not mandate.date_end:
                mandate.date_end = mandate.date_start + relativedelta(years=1, days=-1)

    @api.depends("date_start")
    def _compute_audit_year(self):
        for mandate in self:
            if not mandate.audit_year:
                mandate.audit_year = mandate.date_start.year if mandate.date_start else False

    @api.depends("date_start", "date_end")
    def _compute_is_current(self):
        today = fields.Date.context_today(self)
        for mandate in self:
            mandate.is_current = mandate.date_start <= today and (not mandate.date_end or mandate.date_end >= today)

    def _search_is_current(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(self.env._("Zoeken op 'Lopend' kan alleen met waar of onwaar."))
        today = fields.Date.context_today(self)
        domain = [("date_start", "<=", today), "|", ("date_end", "=", False), ("date_end", ">=", today)]
        return domain if (operator == "=") == value else ["!"] + domain

    @api.depends("partner_id", "association_id", "date_start")
    def _compute_is_owner(self):
        for mandate in self:
            mandate.is_owner = bool(mandate.partner_id and mandate.association_id and mandate._owned_lots())

    def _owned_lots(self):
        self.ensure_one()
        date = self.date_start or fields.Date.context_today(self)
        ownerships = self.env["vme.ownership"].sudo().search([
            ("association_id", "=", self.association_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("date_start", "<=", date),
            "|", ("date_end", "=", False), ("date_end", ">=", date),
        ])
        return ownerships.lot_id

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for mandate in self:
            if mandate.date_end and mandate.date_end < mandate.date_start:
                raise ValidationError(self.env._("Het einde van een mandaat kan niet voor het begin liggen."))

    @api.constrains("role", "partner_id", "association_id", "date_start")
    def _check_council_owner(self):
        for mandate in self.filtered(lambda m: m.role in COUNCIL_ROLES):
            # LEGAL-CHECK: art. 3.90 §1 BW - the council consists only of co-owners. The auditor
            # may be a co-owner or someone from outside (art. 3.91 BW), so no check there.
            if not mandate._owned_lots():
                raise ValidationError(self.env._(
                    "%(person)s is geen mede-eigenaar van %(vme)s op %(date)s. Alleen mede-eigenaars kunnen "
                    "in de raad van mede-eigendom zetelen.",
                    person=mandate.partner_id.display_name, vme=mandate.association_id.name,
                    date=mandate.date_start))

    @api.constrains("role", "association_id", "date_start", "date_end")
    def _check_one_chair(self):
        for mandate in self.filtered(lambda m: m.role == "chair"):
            overlapping = self.search_count([
                ("id", "!=", mandate.id), ("association_id", "=", mandate.association_id.id),
                ("role", "=", "chair"),
                "|", ("date_end", "=", False), ("date_end", ">=", mandate.date_start),
                *([("date_start", "<=", mandate.date_end)] if mandate.date_end else []),
            ])
            if overlapping:
                raise ValidationError(self.env._(
                    "%s heeft in die periode al een voorzitter van de raad.", mandate.association_id.name))

    @api.depends("role", "partner_id")
    def _compute_display_name(self):
        roles = dict(ROLES)
        for mandate in self:
            mandate.display_name = f"{mandate.partner_id.name or ''} ({roles.get(mandate.role, '')})"

    # Read access for the auditor

    def action_grant_access(self):
        """Give the auditor an internal user that can only read the books of his VME's.

        No invitation is sent: the staff member sends the password e-mail from the user form when
        the auditor should get in.
        """
        self._check_user_admin()
        for mandate in self:
            if mandate.role != "auditor":
                raise UserError(self.env._("Alleen de commissaris van de rekeningen krijgt leestoegang."))
            if not mandate.is_current:
                raise UserError(self.env._("Het mandaat van %s loopt niet.", mandate.partner_id.name))
            user = mandate.partner_id.with_context(active_test=False).user_ids[:1]
            if user and not user.has_group(AUDITOR_GROUP):
                raise UserError(self.env._(
                    "%s heeft al een gebruiker met andere rechten. Geef de commissaris een eigen gebruiker "
                    "met een ander e-mailadres.", mandate.partner_id.name))
            if not user:
                if not mandate.partner_id.email:
                    raise UserError(self.env._("Vul eerst het e-mailadres van %s in.", mandate.partner_id.name))
                user = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
                    "name": mandate.partner_id.name,
                    "login": mandate.partner_id.email,
                    "partner_id": mandate.partner_id.id,
                    "group_ids": [fields.Command.set([self.env.ref(AUDITOR_GROUP).id])],
                    "company_id": mandate.company_id.id,
                    "company_ids": [fields.Command.set(mandate.company_id.ids)],
                })
            mandate.user_id = user
            mandate.message_post(body=self.env._(
                "Leestoegang gegeven aan %(user)s (login %(login)s). Er is geen uitnodiging verstuurd.",
                user=user.name, login=user.login))
        self.user_id._vme_sync_auditor_access()

    def action_revoke_access(self):
        self._check_user_admin()
        users = self.user_id
        self.user_id = False
        users._vme_sync_auditor_access()

    def _check_user_admin(self):
        # Creating users is for whoever manages access rights, not for every staff member.
        if not self.env.su and not self.env.user.has_group("base.group_erp_manager"):
            raise AccessError(self.env._("Alleen wie gebruikers beheert, kan leestoegang geven of intrekken."))

    @api.model
    def _cron_sync_auditor_access(self):
        """Daily: an auditor only sees the VME's of his running mandates, and loses access after the last."""
        self.env["res.users"].with_context(active_test=False).search(
            [("group_ids", "in", self.env.ref(AUDITOR_GROUP).id)])._vme_sync_auditor_access()

    # Report to the general assembly

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref("vme_belgie.action_report_auditor").report_action(self)

    def _get_audit_figures(self):
        """Key figures of the audited year, from the books of the VME's company.

        Read as superuser once the user may read the mandate: an auditor of two VME's may have
        only one company selected, and the figures belong to this mandate's VME only.
        """
        self.ensure_one()
        self.check_access("read")
        company = self.company_id
        year = self.audit_year or fields.Date.context_today(self).year
        start, end = fields.Date.to_date(f"{year}-01-01"), fields.Date.to_date(f"{year}-12-31")
        Move = self.env["account.move"].sudo()
        moves = Move.search([
            ("company_id", "=", company.id), ("state", "=", "posted"),
            ("date", ">=", start), ("date", "<=", end),
            ("move_type", "in", ("in_invoice", "in_refund", "out_invoice", "out_refund")),
        ])
        bills = moves.filtered(lambda m: m.move_type in ("in_invoice", "in_refund"))
        calls = moves.filtered(lambda m: m.move_type in ("out_invoice", "out_refund"))
        Line = self.env["account.move.line"].sudo()

        def balance(domain):
            groups = Line._read_group(
                [("company_id", "=", company.id), ("parent_state", "=", "posted"), ("date", "<=", end), *domain],
                aggregates=["balance:sum"])
            return groups[0][0] if groups else 0.0

        journals = self.env["account.journal"].sudo().search([("company_id", "=", company.id), ("type", "=", "bank")])
        reserve_code = VME_FUND_ACCOUNTS["reserve"][0]
        return {
            "year": year,
            "start": start,
            "end": end,
            "currency": company.currency_id,
            "bill_count": len(bills),
            "bill_total": sum(bills.mapped("amount_total_signed")) * -1,
            "call_count": len(calls),
            "call_total": sum(calls.mapped("amount_total_signed")),
            "banks": [{
                "name": journal.name,
                "account": journal.bank_account_id.acc_number or "",
                "statement_lines": self.env["account.bank.statement.line"].sudo().search_count([
                    ("journal_id", "=", journal.id), ("date", ">=", start), ("date", "<=", end)]),
                "balance": balance([("account_id", "=", journal.default_account_id.id)]),
            } for journal in journals],
            "receivable": balance([("account_id.account_type", "=", "asset_receivable")]),
            "payable": -balance([("account_id.account_type", "=", "liability_payable")]),
            # Equity accounts: credit balance, shown as a positive amount.
            "reserve_fund": -balance([("account_id.code", "=", reserve_code)]),
        }


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    mandate_ids = fields.One2many("vme.mandate", "association_id", string="Mandaten")
    council_member_ids = fields.One2many(
        "vme.mandate", "association_id", string="Raad van mede-eigendom",
        domain=[("role", "in", COUNCIL_ROLES)])
    auditor_mandate_ids = fields.One2many(
        "vme.mandate", "association_id", string="Commissaris van de rekeningen", domain=[("role", "=", "auditor")])
    council_lot_count = fields.Integer(
        string="Kavels voor de raad", compute="_compute_council_required",
        help="Kavels zonder garages en bergingen: die tellen niet mee voor de verplichte raad.")
    council_required = fields.Boolean(string="Raad verplicht", compute="_compute_council_required")
    council_warning = fields.Char(string="Waarschuwing raad", compute="_compute_council_required")
    open_dossier_count = fields.Integer(string="Lopende dossiers", compute="_compute_open_dossier_count")

    @api.depends("lot_ids.lot_type", "mandate_ids.role", "mandate_ids.date_start", "mandate_ids.date_end")
    def _compute_council_required(self):
        for vme in self:
            vme.council_lot_count = len(vme.lot_ids.filtered(lambda l: l.lot_type not in COUNCIL_EXCLUDED_LOT_TYPES))
            vme.council_required = vme.council_lot_count >= COUNCIL_REQUIRED_MIN_LOTS
            current = vme.mandate_ids.filtered("is_current")
            warnings = []
            if vme.council_required and not current.filtered(lambda m: m.role in COUNCIL_ROLES):
                warnings.append(self.env._(
                    "Met %s kavels (zonder garages en bergingen) is een raad van mede-eigendom verplicht.",
                    vme.council_lot_count))
            # LEGAL-CHECK: art. 3.91 BW - every year the general assembly appoints an auditor.
            if vme.lot_ids and not current.filtered(lambda m: m.role == "auditor"):
                warnings.append(self.env._("Er is geen lopend mandaat van een commissaris van de rekeningen."))
            vme.council_warning = " ".join(warnings) or False

    def _compute_open_dossier_count(self):
        counts = dict(self.env["vme.council.dossier"]._read_group(
            [("association_id", "in", self.ids)], ["association_id"], ["__count"]))
        for vme in self:
            vme.open_dossier_count = counts.get(vme, 0)

    def action_open_council_dossiers(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_council_dossier_action")
        action["domain"] = [("association_id", "in", self.ids)]
        action["context"] = {"group_by": ["dossier_type"]}
        return action

    def action_print_council_dossiers(self):
        return self.env.ref("vme_belgie.action_report_council_dossiers").report_action(self)

    @api.model_create_multi
    def create(self, vals_list):
        # An auditor keeps only the companies of his own VME's (see res.users below).
        vmes = super().create(vals_list)
        auditors = vmes.company_id.user_ids.filtered(lambda u: u.has_group(AUDITOR_GROUP))
        auditors._vme_sync_auditor_access()
        return vmes


class ResUsers(models.Model):
    _inherit = "res.users"

    def _vme_sync_auditor_access(self):
        """Auditors see exactly the companies of their running auditor mandates; none left: archived."""
        Mandate = self.env["vme.mandate"].sudo()
        for user in self.sudo().with_context(active_test=False):
            if not user.has_group(AUDITOR_GROUP):
                continue
            mandates = Mandate.search([("user_id", "=", user.id), ("role", "=", "auditor"), ("is_current", "=", True)])
            companies = mandates.company_id
            if not companies:
                if user.active:
                    user.active = False
                continue
            vals = {}
            if set(user.company_ids.ids) != set(companies.ids):
                vals["company_ids"] = [fields.Command.set(companies.ids)]
            if user.company_id not in companies:
                vals["company_id"] = companies[:1].id
            if not user.active:
                vals["active"] = True
            if vals:
                user.write(vals)


class Base(models.AbstractModel):
    _inherit = "base"

    # The auditor can only read: hide New, Edit and Delete in his views, so he does not run into
    # access errors. The record rules remain the real protection.
    def _vme_is_auditor_view(self, view_type):
        return (view_type in ("list", "form", "kanban") and not self._transient and self._name != "res.users"
                and self.env.user.has_group(AUDITOR_GROUP))

    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        return super()._get_view_cache_key(view_id, view_type, **options) + (self._vme_is_auditor_view(view_type),)

    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if self._vme_is_auditor_view(view_type):
            for attribute in ("create", "edit", "delete"):
                arch.set(attribute, "0")
        return arch, view


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Used by the record rule of the auditor: he sees the owners of his VME's, no one else's.
    vme_ownership_ids = fields.One2many("vme.ownership", "partner_id", string="Eigendommen")
    vme_mandate_ids = fields.One2many("vme.mandate", "partner_id", string="Mandaten in een VME")


DOSSIER_TYPES = [
    ("sale", "Verkoop"),
    ("collection", "Invordering"),
    ("inspection", "Keuring"),
    ("assembly", "Opvolging AV"),
    # Works and damage files (step 14) add their rows by extending _dossier_queries().
    ("works", "Werken"),
    ("damage", "Schade"),
]


class VmeCouncilDossier(models.Model):
    """Running files of a VME in one list, for the council meeting. Read-only SQL view."""

    _name = "vme.council.dossier"
    _description = "Lopend dossier voor de raad van mede-eigendom"
    _auto = False
    _order = "association_id, dossier_type, date_deadline, id"

    association_id = fields.Many2one("vme.association", string="VME", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    dossier_type = fields.Selection(DOSSIER_TYPES, string="Soort", readonly=True)
    name = fields.Char(string="Dossier", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Betrokkene", readonly=True)
    status = fields.Char(string="Stand van zaken", readonly=True)
    date_deadline = fields.Date(string="Termijn", readonly=True)
    is_overdue = fields.Boolean(string="Over termijn", readonly=True)
    user_id = fields.Many2one("res.users", string="Opvolging door", readonly=True)
    res_model = fields.Char(string="Model", readonly=True)
    res_id = fields.Integer(string="Record", readonly=True)

    @api.model
    def _dossier_queries(self):
        """One SELECT per kind of file, with the columns of this view.

        Ids are unique per kind: the record id times 10 plus a digit per kind (1 to 4 here,
        5 and up for works and damage).
        """
        return [
            """
            SELECT s.id * 10 + 1 AS id, s.association_id, s.company_id, 'sale' AS dossier_type,
                   s.name, s.seller_id AS partner_id,
                   CASE s.state WHEN 'new' THEN 'Eerste vraag notaris ontvangen'
                                WHEN 'first_answered' THEN 'Eerste vraag beantwoord'
                                WHEN 'second_received' THEN 'Tweede vraag notaris ontvangen'
                                ELSE 'Tweede vraag beantwoord, wacht op de akte' END AS status,
                   COALESCE(s.answer_deadline, s.deed_date) AS date_deadline,
                   s.user_id, 'vme.sale.file' AS res_model, s.id AS res_id
              FROM vme_sale_file s
             WHERE s.state NOT IN ('done', 'cancelled')
            """,
            """
            SELECT c.id * 10 + 2, c.association_id, c.company_id, 'collection',
                   'Achterstallen ' || p.name, c.partner_id,
                   CASE WHEN c.state = 'forwarded' THEN 'Doorgestuurd naar advocaat of deurwaarder'
                        WHEN c.level = '3' THEN 'Ingebrekestelling verstuurd'
                        WHEN c.level = '2' THEN 'Aanmaning verstuurd'
                        WHEN c.level = '1' THEN 'Herinnering verstuurd'
                        ELSE 'Nog geen herinnering verstuurd' END,
                   NULL::date, NULL::integer, 'vme.collection', c.id
              FROM vme_collection c
              JOIN res_partner p ON p.id = c.partner_id
             WHERE c.state IN ('open', 'forwarded')
            """,
            """
            SELECT r.id * 10 + 3, r.association_id, r.company_id, 'inspection',
                   i.name || ': ' || r.name, NULL::integer,
                   CASE r.severity WHEN 'blocking' THEN 'Stilstand' WHEN 'major' THEN 'Ernstig' ELSE 'Licht' END
                   || ', ' || CASE r.state WHEN 'planned' THEN 'herstelling gepland' ELSE 'open' END,
                   r.deadline, NULL::integer, 'vme.inspection.remark', r.id
              FROM vme_inspection_remark r
              JOIN vme_installation i ON i.id = r.installation_id
             WHERE r.state IN ('open', 'planned')
            """,
            """
            SELECT a.id * 10 + 4, item.association_id, item.company_id, 'assembly',
                   COALESCE(a.summary, item.name), NULL::integer,
                   'Beslissing ' || COALESCE(item.decision_number, '') || ': ' || item.name,
                   a.date_deadline, a.user_id, 'vme.assembly.item', item.id
              FROM mail_activity a
              JOIN vme_assembly_item item ON item.id = a.res_id
             WHERE a.res_model = 'vme.assembly.item' AND a.active
            """,
        ]

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        union = " UNION ALL ".join(f"({query})" for query in self._dossier_queries())
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT d.*, (d.date_deadline < CURRENT_DATE) AS is_overdue
              FROM ({union}) AS d (id, association_id, company_id, dossier_type, name, partner_id, status,
                                   date_deadline, user_id, res_model, res_id)
        """)

    def action_open_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }
