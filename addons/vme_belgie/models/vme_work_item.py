from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, tools
from odoo.tools import format_date

from .vme_syndic import RENEWAL_URGENT_MONTHS

# Everything up to this many days after today is "this week"; later work is not shown.
HORIZON_DAYS = 7
URGENCIES = [("late", "Te laat"), ("today", "Vandaag"), ("week", "Deze week")]
ITEM_TYPES = [("task", "Taak"), ("signal", "Signaal"), ("draft", "Concept")]
KINDS = [
    ("activity", "Taak"),
    ("ai", "AI-antwoord"),
    ("cycle", "Jaarcyclus"),
    ("request", "Aanvraag"),
    ("order", "Bestelling"),
    ("reminder", "Rappel"),
    ("inspection", "Keuring"),
    ("contract", "Contract"),
    ("arrears", "Achterstallen"),
    ("sale", "Verkoop (notaris)"),
    ("mandate", "Mandaat syndicus"),
]
# Kind of a task, after the model of the record it is on.
ACTIVITY_KINDS = {
    "vme.cycle.step": "cycle",
    "vme.request": "request",
    "vme.installation": "inspection",
    "vme.contract": "contract",
    "vme.collection": "arrears",
    "vme.sale.file": "sale",
    "vme.syndic.mandate": "mandate",
}
# The AI mail assistant (ai/assistant.py) puts its proposed replies as tasks with this summary.
AI_SUMMARY_PREFIX = "AI-voorstel"
# Kinds that are a draft waiting for one click of the employee.
DRAFT_KINDS = ("ai", "order", "reminder")


class VmeWorkItem(models.TransientModel):
    """One line of "Mijn werk vandaag": a task, signal or draft of a VME, with its deadline.

    Transient: the list is built again for the user each time it is opened (see _build), from the
    records of the VMEs he may read. It shows and opens; it never sends or changes anything.
    """

    _name = "vme.work.item"
    _description = "Werk van vandaag"
    _order = "urgency_rank, association_id, date_deadline, id"
    _transient_max_hours = 12

    association_id = fields.Many2one("vme.association", string="VME", readonly=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", readonly=True, ondelete="cascade")
    name = fields.Char(string="Wat", readonly=True)
    description = fields.Char(string="Toelichting", readonly=True)
    kind = fields.Selection(KINDS, string="Onderwerp", readonly=True)
    item_type = fields.Selection(ITEM_TYPES, string="Soort", readonly=True)
    date_deadline = fields.Date(string="Termijn", readonly=True)
    urgency = fields.Selection(URGENCIES, string="Urgentie", readonly=True)
    urgency_rank = fields.Integer(readonly=True)
    user_id = fields.Many2one("res.users", string="Verantwoordelijke", readonly=True, ondelete="cascade")
    res_model = fields.Char(string="Model", readonly=True)
    res_id = fields.Integer(string="Record", readonly=True)
    activity_id = fields.Many2one("mail.activity", string="Taak", readonly=True, ondelete="cascade")

    # Building

    @api.model
    def _today(self):
        # Tests and the demo can pin "today" via the context, like the yearly cycle.
        return self.env.context.get("vme_today") or fields.Date.context_today(self)

    @api.model
    def _work_item_sources(self):
        """Methods that each return the items of one kind: a list of value dicts.

        Each gets (vmes, today, horizon, tasks), with tasks the set of (model, id) of records that have
        an open task: a signal for such a record is left out, the task is the work. Another module adds
        its own source by extending this list.
        """
        return [
            self._items_activities,
            self._items_cycle_steps,
            self._items_requests,
            self._items_reminders,
            self._items_installations,
            self._items_contracts,
            self._items_arrears,
            self._items_sale_files,
            self._items_mandates,
        ]

    @api.model
    def _build(self, today=None):
        """Replace the items of the current user by the work of today, over all VMEs he may read."""
        today = today or self._today()
        horizon = today + timedelta(days=HORIZON_DAYS)
        self.search([("create_uid", "=", self.env.uid)]).unlink()
        # Read with the record rules of the user (his companies), then with sudo within those VMEs only.
        vmes = self.env["vme.association"].search([]).sudo()
        if not vmes:
            return self
        tasks = {(a.res_model, a.res_id) for a in self.env["mail.activity"].sudo().search([
            ("res_model", "in", list(self._vme_models())), ("active", "=", True)])}
        values = []
        for source in self._work_item_sources():
            values += source(vmes, today, horizon, tasks)
        for vals in values:
            vme = vals["association_id"]
            deadline = vals["date_deadline"]
            urgency = "late" if deadline < today else "today" if deadline == today else "week"
            vals.update({
                "association_id": vme.id,
                "company_id": vme.company_id.id,
                "user_id": (vals.get("user_id") or vme.manager_user_id).id or False,
                "urgency": urgency,
                "urgency_rank": [code for code, _label in URGENCIES].index(urgency),
            })
        return self.create(values)

    @api.model
    def _vme_models(self):
        """Models whose records belong to one VME: the VME itself and every model with association_id."""
        return {
            name for name in self.env.registry
            if name == "vme.association" or (
                not self.env[name]._abstract and not self.env[name]._transient
                and isinstance(self.env[name]._fields.get("association_id"), fields.Many2one)
                and self.env[name]._fields["association_id"].comodel_name == "vme.association")
        }

    @api.model
    def _item(self, vme, record, name, deadline, item_type, kind, description=False, user=None):
        return {
            "association_id": vme, "name": name, "description": description or False,
            "date_deadline": deadline, "item_type": item_type, "kind": kind,
            "res_model": record._name, "res_id": record.id, "user_id": user or self.env["res.users"],
        }

    # Sources

    def _items_activities(self, vmes, today, horizon, tasks):
        """Tasks (mail.activity) on the VME and on every record of it, the AI proposals included."""
        activities = self.env["mail.activity"].sudo().search([
            ("res_model", "in", list(self._vme_models())), ("active", "=", True), ("date_deadline", "<=", horizon)])
        items = []
        by_model = {}
        for activity in activities:
            by_model.setdefault(activity.res_model, []).append(activity)
        for model, model_activities in by_model.items():
            records = self.env[model].sudo().browse({a.res_id for a in model_activities}).exists()
            vme_of = {r.id: (r if model == "vme.association" else r.association_id) for r in records}
            for activity in model_activities:
                vme = vme_of.get(activity.res_id)
                if not vme or vme not in vmes:
                    continue
                summary = activity.summary or activity.activity_type_id.name or ""
                record = self.env[model].browse(activity.res_id)
                kind = ACTIVITY_KINDS.get(model, "activity")
                if model == "vme.association" and summary.startswith(AI_SUMMARY_PREFIX):
                    kind = "ai"
                elif model == "vme.request" and record.sudo().order_ready:
                    kind = "order"
                deadline = activity.date_deadline
                if model == "vme.cycle.step" and record.sudo()._is_late(today):
                    # The task of a late step was made with today as deadline: the step itself is late.
                    deadline = min(deadline, record.sudo().date_deadline)
                values = self._item(
                    vme, record, summary, deadline, "draft" if kind in DRAFT_KINDS else "task", kind,
                    description=False if model == "vme.association" else record.sudo().display_name,
                    user=activity.user_id)
                values["activity_id"] = activity.id
                items.append(values)
        return items

    def _items_cycle_steps(self, vmes, today, horizon, tasks):
        """Steps of the yearly cycle that are late or due, and have no task of their own."""
        steps = self.env["vme.cycle.step"].sudo().search([
            ("association_id", "in", vmes.ids), ("state", "in", ("pending", "ready")),
            ("date_deadline", "<=", horizon), ("date_ready", "<=", today)])
        items = []
        for step in steps:
            if ("vme.cycle.step", step.id) in tasks:
                continue
            if step.date_deadline < today and not step._is_late(today):
                continue  # waits for the assembly
            items.append(self._item(
                step.association_id, step, step.name, step.date_deadline, "signal", "cycle", description=step.note,
                user=step.user_id or step.association_id._cycle_default_user()))
        return items

    def _items_requests(self, vmes, today, horizon, tasks):
        """New requests without a task, and orders for the locksmith that wait for a click."""
        Request = self.env["vme.request"].sudo()
        items = []
        for request in Request.search([("association_id", "in", vmes.ids), ("state", "=", "in_progress"),
                                       ("order_attachment_id", "!=", False), ("order_sent_date", "=", False)]):
            if request.order_ready and ("vme.request", request.id) not in tasks:
                items.append(self._item(
                    request.association_id, request,
                    self.env._("Bestelling nakijken en versturen: %s", request.display_name), today, "draft", "order",
                    description=self.env._("De bestelbon staat klaar; niets is verstuurd."), user=request.user_id))
        for request in Request.search([("association_id", "in", vmes.ids), ("state", "=", "new"),
                                       ("request_date", "<=", horizon)]):
            if ("vme.request", request.id) in tasks:
                continue
            items.append(self._item(
                request.association_id, request, self.env._("Nieuwe aanvraag behandelen: %s", request.display_name),
                request.request_date, "signal", "request", user=request.user_id))
        return items

    def _items_reminders(self, vmes, today, horizon, tasks):
        """Reminders, demands and formal notices in draft: they leave only after a click."""
        levels = dict(self.env["vme.collection.reminder"]._fields["level"]._description_selection(self.env))
        return [
            self._item(reminder.association_id, reminder,
                       self.env._("%(level)s aan %(owner)s nakijken en versturen",
                                  level=levels.get(reminder.level, ""), owner=reminder.partner_id.name),
                       min(reminder.date, today), "draft", "reminder",
                       description=self.env._("Opgemaakt op %s, nog niet verstuurd.", format_date(self.env, reminder.date)))
            for reminder in self.env["vme.collection.reminder"].sudo().search([
                ("association_id", "in", vmes.ids), ("state", "=", "draft")])
        ]

    def _items_installations(self, vmes, today, horizon, tasks):
        """Inspections and risk analyses that are expired or expire this week."""
        items = []
        Installation = self.env["vme.installation"].sudo()
        for installation in Installation.search([
                ("association_id", "in", vmes.ids), "|",
                ("next_inspection_date", "<=", horizon), ("next_risk_analysis_date", "<=", horizon)]):
            if ("vme.installation", installation.id) in tasks:
                continue
            user = installation.responsible_user_id
            if installation.next_inspection_date and installation.next_inspection_date <= horizon:
                items.append(self._item(
                    installation.association_id, installation,
                    self.env._("Keuring vervalt: %s", installation.name), installation.next_inspection_date,
                    "signal", "inspection", user=user))
            if installation.next_risk_analysis_date and installation.next_risk_analysis_date <= horizon:
                items.append(self._item(
                    installation.association_id, installation,
                    self.env._("Risicoanalyse vervalt: %s", installation.name), installation.next_risk_analysis_date,
                    "signal", "inspection", user=user))
        return items

    def _items_contracts(self, vmes, today, horizon, tasks):
        """Running contracts whose notice term ends this week or ended before the end of the period."""
        items = []
        for contract in self.env["vme.contract"].sudo().search([
                ("association_id", "in", vmes.ids), ("state", "=", "running"), ("notice_given_date", "=", False),
                ("notice_deadline", "<=", horizon), "|", ("date_end", "=", False), ("date_end", ">=", today)]):
            if ("vme.contract", contract.id) in tasks:
                continue
            items.append(self._item(
                contract.association_id, contract, self.env._("Opzeggen of verlengen: %s", contract.name),
                contract.notice_deadline, "signal", "contract",
                description=self.env._("Opzeg uiterlijk op %(date)s bij %(partner)s.",
                                       date=format_date(self.env, contract.notice_deadline),
                                       partner=contract.partner_id.name),
                user=contract.responsible_user_id))
        return items

    def _items_arrears(self, vmes, today, horizon, tasks):
        """VMEs whose arrears exceed their threshold, unless a reminder for them is already in draft."""
        arrears = {vme.id: amount for vme, amount in self.env["vme.arrears"].sudo()._read_group(
            [("association_id", "in", vmes.ids)], ["association_id"], ["amount_residual:sum"])}
        with_draft = set(self.env["vme.collection.reminder"].sudo().search(
            [("association_id", "in", vmes.ids), ("state", "=", "draft")]).association_id.ids)
        items = []
        for vme in vmes:
            currency = vme.company_id.currency_id
            amount = currency.round(arrears.get(vme.id, 0.0))
            if vme.id in with_draft or currency.compare_amounts(amount, vme.arrears_signal_threshold) <= 0:
                continue
            items.append(self._item(
                vme, vme, self.env._("Achterstallen opvolgen: %s", tools.formatLang(self.env, amount, currency_obj=currency)),
                today, "signal", "arrears",
                description=self.env._("Boven de drempel van %s. Maak de herinneringen klaar in Invordering.",
                                       tools.formatLang(self.env, vme.arrears_signal_threshold, currency_obj=currency))))
        return items

    def _items_sale_files(self, vmes, today, horizon, tasks):
        """Questions of a notary with a legal term that ends this week or has ended."""
        items = []
        for sale in self.env["vme.sale.file"].sudo().search([
                ("association_id", "in", vmes.ids), ("state", "not in", ("done", "cancelled")),
                ("answer_deadline", "<=", horizon)]):
            if ("vme.sale.file", sale.id) in tasks:
                continue
            # The legal terms themselves carry their LEGAL-CHECK in vme_sale_file.py.
            items.append(self._item(
                sale.association_id, sale, self.env._("Notaris antwoorden: %s", sale.name), sale.answer_deadline,
                "signal", "sale", description=self.env._("Wettelijke termijn tot %s.",
                                                         format_date(self.env, sale.answer_deadline)),
                user=sale.user_id))
        return items

    def _items_mandates(self, vmes, today, horizon, tasks):
        """Mandates of the syndic to renew, or whose appointment still has to be posted at the entrance."""
        items = []
        for mandate in self.env["vme.syndic.mandate"].sudo().search([("association_id", "in", vmes.ids)]):
            if ("vme.syndic.mandate", mandate.id) in tasks:
                continue
            if mandate.renewal_state in ("urgent", "decided", "expired") or (
                    mandate.renewal_state == "plan" and mandate.renewal_period_start
                    and mandate.renewal_period_start - relativedelta(months=RENEWAL_URGENT_MONTHS) <= horizon):
                deadline = mandate.date_end if mandate.renewal_state == "expired" else \
                    mandate.renewal_period_start - relativedelta(months=RENEWAL_URGENT_MONTHS)
                items.append(self._item(
                    mandate.association_id, mandate, mandate._renewal_summary(), deadline,
                    "signal", "mandate", description=mandate.renewal_text))
            if mandate.is_current and mandate.posting_state in ("todo", "late") and mandate.posting_deadline \
                    and mandate.posting_deadline <= horizon:
                items.append(self._item(
                    mandate.association_id, mandate, mandate._posting_summary(), mandate.posting_deadline,
                    "signal", "mandate"))
        return items

    # Actions

    @api.model
    def action_open_worklist(self):
        """Menu "Mijn werk vandaag": build the list for this user and show it."""
        self._build()
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_work_item_action")
        # One level of groups: Odoo opens only the first level, so the lines are sorted per VME within it.
        action["context"] = {"search_default_mine": 1, "search_default_group_urgency": 1}
        return action

    def action_refresh(self):
        return self.action_open_worklist()

    def action_open_record(self):
        """Open the record behind the line. Opening changes nothing: the employee acts there himself."""
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            return False
        if self.kind == "arrears":
            return record.action_open_collections()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {"allowed_company_ids": (self.company_id | self.env.companies).ids},
        }
