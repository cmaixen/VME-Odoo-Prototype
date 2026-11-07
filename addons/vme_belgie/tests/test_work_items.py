from datetime import date, timedelta

from freezegun import freeze_time

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestWorkItems(TransactionCase):
    """"Mijn werk vandaag": what comes in, in which group, for whom, and that nothing leaves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.manager = Users.create({
            "name": "Dossierbeheerder Werkbak", "login": "dossierbeheerder.werkbak@example.com",
            "group_ids": [Command.link(cls.env.ref("base.group_user").id),
                          Command.link(cls.env.ref("vme_belgie.group_vme_all_companies").id)],
        })
        cls.colleague = Users.create({
            "name": "Collega Werkbak", "login": "collega.werkbak@example.com",
            "group_ids": [Command.link(cls.env.ref("base.group_user").id),
                          Command.link(cls.env.ref("vme_belgie.group_vme_all_companies").id)],
        })
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Werkbak", "manager_user_id": cls.manager.id})
        cls.other_vme = cls.env["vme.association"].create({"name": "Residentie Elders",
                                                           "manager_user_id": cls.colleague.id})
        cls.companies = (cls.vme | cls.other_vme).company_id
        (cls.manager | cls.colleague).write({"company_ids": [Command.link(c.id) for c in cls.companies]})
        cls.owner = cls.env["res.partner"].create({"name": "Eigenaar Werkbak 1"})
        cls.supplier = cls.env["res.partner"].create({"name": "Onderhoud Werkbak", "is_company": True})
        cls.Item = cls.env["vme.work.item"]

    def _build(self, user=None):
        return self.Item.with_user(user or self.manager).with_context(vme_today=TODAY)._build()

    def _todo(self, record, deadline, summary="Taak", user=None):
        return record.activity_schedule("mail.mail_activity_data_todo", date_deadline=deadline, summary=summary,
                                        user_id=(user or self.manager).id)

    def _items_for(self, items, record):
        return items.filtered(lambda i: i.res_model == record._name and i.res_id == record.id)

    # Case manager

    def test_manager_is_the_creator_and_gets_the_automatic_tasks(self):
        defaults = self.env["vme.association"].with_user(self.manager).default_get(["manager_user_id"])
        self.assertEqual(defaults["manager_user_id"], self.manager.id)
        # Odoo itself (a cron runs as OdooBot) is never the case manager; then the administrator gets the tasks.
        unmanaged = self.env["vme.association"].sudo().create({"name": "Residentie Zonder"})
        self.assertFalse(unmanaged.manager_user_id)
        self.assertEqual(unmanaged._vme_task_user(), self.admin)
        self.assertEqual(self.env["vme.association"]._vme_task_user(), self.admin)
        # The yearly cycle: its own responsible first, then the case manager.
        self.assertEqual(self.vme._cycle_default_user(), self.manager)
        self.vme.cycle_user_id = self.colleague
        self.assertEqual(self.vme._cycle_default_user(), self.colleague)

    def test_cron_tasks_without_responsible_go_to_the_case_manager(self):
        contract = self.env["vme.contract"].create({
            "association_id": self.vme.id, "name": "Schoonmaak", "contract_type": "cleaning",
            "partner_id": self.supplier.id, "date_end": date(2027, 2, 28), "responsible_user_id": False})
        self.assertEqual(contract.notice_deadline, date(2026, 11, 30))
        self.env["vme.contract"].with_user(self.env.ref("base.user_root"))._cron_schedule_contract_activities()
        self.assertEqual(contract.activity_ids.user_id, self.manager)

    # Groups and sources

    def test_tasks_are_grouped_by_urgency_and_later_work_is_left_out(self):
        late = self._todo(self.vme, TODAY - timedelta(days=3), "Te laat")
        today = self._todo(self.vme, TODAY, "Vandaag")
        week = self._todo(self.vme, TODAY + timedelta(days=7), "Over een week")
        later = self._todo(self.vme, TODAY + timedelta(days=8), "Volgende week")
        items = self._build()
        by_activity = {item.activity_id: item for item in items}
        self.assertEqual(by_activity[late].urgency, "late")
        self.assertEqual(by_activity[today].urgency, "today")
        self.assertEqual(by_activity[week].urgency, "week")
        self.assertNotIn(later, by_activity)
        self.assertEqual(items.sorted()[0].activity_id, late)  # the late work first
        self.assertEqual(by_activity[today].item_type, "task")
        self.assertEqual(by_activity[today].association_id, self.vme)

    def test_ai_proposal_and_ready_order_are_drafts_waiting_for_a_click(self):
        ai = self._todo(self.vme, TODAY, "AI-voorstel: Lek of waterschade (A1)")
        reminder = self.env["vme.collection.reminder"].create({
            "collection_id": self.env["vme.collection"].create({
                "association_id": self.vme.id, "partner_id": self.owner.id}).id,
            "level": "1", "date": TODAY - timedelta(days=2)})
        lot = self.env["vme.lot"].create({"association_id": self.vme.id, "name": "W1", "lot_type": "apartment"})
        request = self.env["vme.request"].create({
            "association_id": self.vme.id, "request_type_id": self.env.ref("vme_belgie.request_type_key").id,
            "lot_id": lot.id, "title": "Badge", "requester_id": self.owner.id, "state": "in_progress",
            "order_attachment_id": self.env["ir.attachment"].create({"name": "Bestelbon.pdf", "raw": b"%PDF"}).id})
        self.assertTrue(request.order_ready)
        items = self._build()
        order = self._items_for(items, request)
        self.assertEqual((order.kind, order.item_type), ("order", "draft"))
        # The task "send the order" and the order are one line.
        task = self._todo(request, TODAY, "Bestelling slotenmaker nakijken en versturen")
        items = self._build()
        order = self._items_for(items, request)
        self.assertEqual((order.activity_id, order.kind, order.item_type), (task, "order", "draft"))
        ai_item = items.filtered(lambda i: i.activity_id == ai)
        self.assertEqual((ai_item.kind, ai_item.item_type), ("ai", "draft"))
        reminder_item = self._items_for(items, reminder)
        self.assertEqual((reminder_item.kind, reminder_item.item_type, reminder_item.urgency), ("reminder", "draft", "late"))
        self.assertEqual(reminder_item.user_id, self.manager)

    def test_signal_without_task_and_no_double_line_with_a_task(self):
        contract = self.env["vme.contract"].create({
            "association_id": self.vme.id, "name": "Liftonderhoud", "contract_type": "maintenance",
            "partner_id": self.supplier.id, "date_end": date(2027, 2, 10), "notice_period_months": 3,
            "responsible_user_id": False})
        self.assertEqual(contract.notice_deadline, date(2026, 11, 10))
        item = self._items_for(self._build(), contract)
        self.assertEqual((item.kind, item.item_type, item.urgency), ("contract", "signal", "week"))
        self.assertEqual(item.user_id, self.manager, "without a responsible the case manager gets the signal")
        # With a task on the contract, the task is the work: one line, not two.
        task = self._todo(contract, date(2026, 11, 9), "Opzeggen of verlengen", user=self.colleague)
        item = self._items_for(self._build(), contract)
        self.assertEqual(len(item), 1)
        self.assertEqual((item.activity_id, item.item_type, item.user_id), (task, "task", self.colleague))

    def test_expired_inspection_and_sale_file_term(self):
        installation = self.env["vme.installation"].create({
            "association_id": self.vme.id, "name": "Brandblussers", "installation_type": "fire_extinguishers",
            "responsible_user_id": self.colleague.id,
            "inspection_ids": [Command.create({"date": date(2025, 10, 20), "kind": "inspection"})]})
        self.assertEqual(installation.next_inspection_date, date(2026, 10, 20))
        lot = self.env["vme.lot"].create({"association_id": self.vme.id, "name": "W1", "lot_type": "apartment"})
        self.env["vme.ownership"].create({"lot_id": lot.id, "partner_id": self.owner.id, "date_start": date(2015, 1, 1)})
        sale = self.env["vme.sale.file"].create({
            "association_id": self.vme.id, "lot_ids": [Command.set(lot.ids)], "user_id": False,
            "first_request_date": date(2026, 10, 25)})
        sale.activity_ids.unlink()  # a sale file without a task still shows its legal term
        items = self._build()
        inspection = self._items_for(items, installation)
        self.assertEqual((inspection.kind, inspection.urgency, inspection.user_id), ("inspection", "late", self.colleague))
        sale_item = self._items_for(items, sale)
        self.assertEqual(sale_item.kind, "sale")
        self.assertEqual(sale_item.date_deadline, sale.answer_deadline)
        self.assertEqual(sale_item.user_id, self.manager)

    def test_cycle_step_without_task_goes_to_the_case_manager(self):
        step = self.env["vme.cycle.step"].create({
            "association_id": self.vme.id, "year": 2027, "code": "closing",
            "date_ready": date(2026, 11, 1), "date_deadline": date(2026, 11, 4)})
        item = self._items_for(self._build(), step)
        self.assertEqual((item.kind, item.urgency, item.user_id), ("cycle", "late", self.manager))

    # Who sees what

    def test_each_user_sees_his_own_list_of_his_own_vmes(self):
        mine = self._todo(self.vme, TODAY, "Van mij")
        theirs = self._todo(self.other_vme, TODAY, "Van de collega", user=self.colleague)
        items = self._build()
        self.assertEqual(items.activity_id, mine | theirs, "the filter on responsible is in the view, not here")
        self.assertEqual(items.filtered(lambda i: i.activity_id == theirs).user_id, self.colleague)
        # The colleague builds his list: the list of the manager stays.
        self._build(self.colleague)
        self.assertEqual(self.Item.with_user(self.manager).search([]).activity_id, mine | theirs)
        # Someone with only the company of the other VME sees nothing of Residentie Werkbak.
        restricted = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Alleen Elders", "login": "alleen.elders@example.com",
            "company_id": self.other_vme.company_id.id, "company_ids": [Command.set(self.other_vme.company_id.ids)]})
        self.assertEqual(self._build(restricted).association_id, self.other_vme)

    def test_the_list_shows_and_opens_but_sends_nothing(self):
        activity = self._todo(self.vme, TODAY, "AI-voorstel: Andere vraag (W1)")
        mails = self.env["mail.mail"].search_count([])
        messages = self.env["mail.message"].search_count([])
        action = self.Item.with_user(self.manager).with_context(vme_today=TODAY).action_open_worklist()
        self.assertEqual(action["res_model"], "vme.work.item")
        self.assertEqual(action["context"]["search_default_mine"], 1)
        item = self.Item.with_user(self.manager).search([("activity_id", "=", activity.id)])
        opened = item.action_open_record()
        self.assertEqual((opened["res_model"], opened["res_id"]), ("vme.association", self.vme.id))
        self.assertTrue(activity.exists() and activity.active, "opening does not close the task")
        self.assertEqual(self.env["mail.mail"].search_count([]), mails)
        self.assertEqual(self.env["mail.message"].search_count([]), messages)
