from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..demo_data.vme_demo_data import distribute_shares, fake_iban


@tagged("post_install", "-at_install")
class TestDemoData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["vme.association"]._load_demo_data()
        cls.vmes = cls.env["vme.association"].search([])
        cls.linde = cls.vmes.filtered(lambda v: v.name == "Residentie Linde")

    def test_helpers(self):
        self.assertEqual(sum(distribute_shares([1, 1, 1])), 1000)
        self.assertEqual(distribute_shares([1, 1, 1]), [334, 333, 333])
        iban = fake_iban(1)
        self.assertTrue(iban.startswith("BE") and iban[4:7] == "999")
        # ISO 13616 check: rearranged IBAN modulo 97 equals 1.
        rearranged = iban[4:] + "1114" + iban[2:4]
        self.assertEqual(int(rearranged) % 97, 1)

    def test_buildings_and_lots(self):
        lots_per_vme = {vme.name: vme.lot_count for vme in self.vmes}
        self.assertEqual(lots_per_vme, {"Residentie Linde": 20, "Hof ter Beuken": 24, "Kaaihuis": 6})
        for vme in self.vmes:
            self.assertTrue(vme.company_id)
            self.assertTrue(vme._is_valid_kbo(vme.kbo_number))

    def test_keys_are_balanced(self):
        keys = self.env["vme.key"].search([("association_id", "in", self.vmes.ids)])
        self.assertEqual(len(keys), 5)
        for key in keys:
            self.assertTrue(key.is_balanced, key.display_name)
            self.assertEqual(key.shares_sum, 1000)
        lift = keys.filtered(lambda k: k.key_type == "elevator")
        self.assertEqual(lift.association_id, self.linde)
        self.assertEqual(set(lift.line_ids.lot_id.mapped("lot_type")), {"apartment"})
        self.assertFalse(self.vmes.filtered(lambda v: v.name == "Kaaihuis").key_ids.filtered(
            lambda k: k.key_type == "elevator"))
        # The fixed part of the heating (by consumption) must really differ from the general key.
        beuken_keys = keys.filtered(lambda k: k.association_id.name == "Hof ter Beuken")
        shares = {k.key_type: k.line_ids.sorted("lot_id").mapped("shares") for k in beuken_keys}
        self.assertNotEqual(shares["general"], shares["consumption"])
        heating = beuken_keys.filtered(lambda k: k.key_type == "consumption")
        self.assertEqual((heating.meter_type, heating.fixed_percent), ("heating", 30.0))

    def test_sale_mid_year(self):
        lot_a5 = self.linde.lot_ids.filtered(lambda l: l.name == "A5")
        seller = lot_a5._get_owner_on(date(2026, 6, 30))
        buyer = lot_a5._get_owner_on(date(2026, 7, 1))
        self.assertTrue(seller and buyer)
        self.assertNotEqual(seller, buyer)
        lot_g5 = self.linde.lot_ids.filtered(lambda l: l.name == "G5")
        self.assertEqual(lot_g5._get_owner_on(date(2026, 7, 1)), buyer)

    def test_owner_with_multiple_lots(self):
        beuken = self.vmes.filtered(lambda v: v.name == "Hof ter Beuken")
        b23, b24 = (beuken.lot_ids.filtered(lambda l, n=n: l.name == n) for n in ("B23", "B24"))
        self.assertEqual(b23.current_owner_id, b24.current_owner_id)
        self.assertEqual(beuken.owner_count, 23)

    def test_separate_bank_accounts(self):
        for vme in self.vmes:
            self.assertTrue(vme.working_capital_bank_id and vme.reserve_capital_bank_id)
            self.assertNotEqual(vme.working_capital_bank_id, vme.reserve_capital_bank_id)

    def test_fictitious_contact_data(self):
        owners = self.env["vme.ownership"].search([("association_id", "in", self.vmes.ids)]).partner_id
        self.assertTrue(all(email.endswith("@example.com") for email in owners.mapped("email")))

    def test_loading_twice_is_refused(self):
        with self.assertRaises(UserError):
            self.env["vme.association"]._load_demo_data()

    def test_assembly_planner_solves_conflict(self):
        """Linde and Kaaihuis both fit on 17 March; Linde's period ends first, so it gets that evening."""
        wizard = self.env["vme.assembly.planner.wizard"].with_context(vme_today=date(2026, 11, 5)).create({"year": 2027})
        wizard.action_propose()
        assemblies = self.env["vme.assembly"].search([("year", "=", 2027)])
        self.assertEqual(len(assemblies), 3)
        self.assertEqual(set(assemblies.mapped("state")), {"proposed"})
        day_by_vme = {a.association_id.name: a.date for a in assemblies}
        self.assertEqual(day_by_vme, {
            "Residentie Linde": date(2027, 3, 17),
            "Kaaihuis": date(2027, 3, 23),
            "Hof ter Beuken": date(2027, 4, 20),
        })
        for assembly in assemblies:
            self.assertTrue(assembly.period_start <= assembly.date <= assembly.period_end)
        self.assertTrue(self.env["res.users"].search([("login", "=", "medewerker.voorbeeld@example.com")]))

    def test_demo_assembly_linde_2026(self):
        assembly = self.env["vme.assembly"].search([
            ("association_id", "=", self.linde.id), ("year", "=", 2026), ("assembly_type", "=", "ordinary")])
        self.assertEqual(assembly.state, "held")
        self.assertEqual((assembly.owners_total, assembly.owners_present), (12, 10))
        self.assertTrue(assembly.quorum_reached)
        outcome = {item.name.split(":")[0]: item.outcome for item in assembly.item_ids}
        self.assertEqual(outcome["Dakwerken"], "adopted")
        self.assertEqual(outcome["Statutenwijziging"], "rejected")
        roof = assembly.item_ids.filtered(lambda i: i.name.startswith("Dakwerken"))
        # The follow-up task "Drie offertes vragen voor de dakwerken" is done: the works are awarded (step 14).
        self.assertFalse(roof.activity_ids)
        self.assertEqual(roof.works_ids.state, "awarded")
        self.assertEqual(len(assembly.item_ids.filtered("decision_number")), 7)

    def test_demo_hybrid_assembly_linde(self):
        assembly = self.env["vme.assembly"].search([
            ("association_id", "=", self.linde.id), ("assembly_type", "=", "extraordinary")])
        self.assertEqual((assembly.state, assembly.meeting_mode, assembly.date), ("confirmed", "hybrid", date(2026, 11, 19)))
        self.assertTrue(assembly.online_url)
        self.assertFalse(assembly.online_open)
        a1 = self.env["res.partner"].search([("name", "=", "Eigenaar Linde A1")])
        rights = assembly.attendee_ids.filtered(lambda a: a.proxy_holder_id == a1)
        self.assertEqual(rights.partner_id.name, "Eigenaar Linde A7")
        self.assertEqual(len(assembly.item_ids), 3)
        self.assertEqual(len(assembly.item_ids.filtered("allow_advance_vote")), 1)
        for login in ("eigenaar.linde.a1@example.com", "eigenaar.linde.a6@example.com"):
            self.assertTrue(self.env["res.users"].search([("login", "=", login), ("share", "=", True)]))

    def test_demo_sale_linde_a3(self):
        sale = self.env["vme.sale.file"].search([("association_id", "=", self.linde.id)])
        self.assertEqual(sale.lot_ids.mapped("name"), ["A3", "G3"])
        self.assertEqual(sale.seller_id.name, "Eigenaar Linde A3")
        self.assertEqual(sale.first_deadline, date(2026, 11, 12))
        self.assertEqual(sale.activity_ids.date_deadline, date(2026, 11, 12))
        info = sale._get_notary_information()
        self.assertEqual(len(info["works"]), 1)
        self.assertTrue(info["works"][0]["share"] > 0)
        self.assertIn("gevelwerken", info["legal_proceedings"])

    def test_demo_works_and_damage_linde(self):
        works = self.env["vme.works"].search([("association_id", "=", self.linde.id)])
        self.assertEqual(works.name, "Renovatie plat dak blok A")
        self.assertEqual((works.budget, works.financing, works.state), (38000, "reserve", "awarded"))
        self.assertEqual(len(works.quote_ids), 3)
        self.assertEqual(works.contractor_id.name, "Dakrenovatie Fictief NV")
        self.assertEqual(works.contract_amount, 36450)
        self.assertEqual(works.activity_ids.summary, "Start van de werken opvolgen")
        self.assertFalse(works.decision_id.works_done)
        claim = self.env["vme.damage.claim"].search([("association_id", "=", self.linde.id)])
        self.assertEqual(claim.lot_ids.mapped("name"), ["A4", "A7"])
        self.assertEqual(claim.state, "expertise")
        self.assertEqual(claim.policy_id.insurer_id.name, "Verzekeringen Voorbeeld NV")
        self.assertEqual(claim.mail_reference, "lek-a4-20261102@example.com")
        self.assertEqual(len(self.env["vme.insurance.policy"].search([])), 3)
    def test_council_and_auditors(self):
        beuken = self.vmes.filtered(lambda v: v.name == "Hof ter Beuken")
        self.assertTrue(beuken.council_required)
        self.assertEqual(sorted(beuken.council_member_ids.mapped("role")), ["chair", "member", "member"])
        self.assertTrue(all(beuken.council_member_ids.mapped("is_owner")))
        self.assertFalse(beuken.auditor_mandate_ids.is_owner)  # an outside auditor
        self.assertFalse(beuken.auditor_mandate_ids.user_id)
        # The auditor of Residentie Linde is the owner of A2, with a read-only login on Linde only.
        mandate = self.linde.auditor_mandate_ids
        self.assertEqual(mandate.assembly_item_id.name, "Benoeming van de commissaris van de rekeningen")
        self.assertEqual(mandate.user_id.login, "eigenaar.linde.a2@example.com")
        self.assertEqual(mandate.user_id.company_ids, self.linde.company_id)
        self.assertEqual(self.env["vme.association"].with_user(mandate.user_id).search([]), self.linde)
    def test_demo_contracts(self):
        contracts = self.env["vme.contract"].search([("association_id", "in", self.vmes.ids)])
        self.assertEqual(set(contracts.mapped("association_id.name")), set(self.vmes.mapped("name")))
        # At least one notice deadline within 60 days after the demo date of 5 November 2026.
        soon = contracts.filtered(lambda c: c.notice_deadline and date(2026, 11, 5) <= c.notice_deadline <= date(2027, 1, 4))
        self.assertGreaterEqual(len(soon), 2)
        lift = self.linde.installation_ids.filtered(lambda i: i.name == "Lift blok A")
        self.assertEqual(lift.maintenance_contract_id.reference, "LO-2023-117")
        concierge = contracts.filtered(lambda c: c.contract_type == "staff")
        self.assertEqual(concierge.association_id.name, "Hof ter Beuken")
        self.assertFalse(concierge.notice_deadline)
        self.assertEqual(concierge.partner_id.vat, "BE0000018014")
        linde_evaluation = contracts.filtered(lambda c: c.association_id == self.linde).evaluation_ids[:1]
        self.assertEqual(linde_evaluation.assembly_id.slot_id.date, date(2026, 3, 10))

    def test_demo_portfolio_signals(self):
        # On the demo date: Hof ter Beuken builds too little reserve and, like Kaaihuis, held no
        # assembly in its period; the fire extinguishers of Linde are overdue since 1 October 2026.
        signals = {vme.name: {s["code"] for s in vme._get_signals(date(2026, 11, 5))} for vme in self.vmes}
        self.assertIn("reserve", signals["Hof ter Beuken"])
        self.assertIn("assembly", signals["Hof ter Beuken"])
        self.assertIn("assembly", signals["Kaaihuis"])
        self.assertNotIn("assembly", signals["Residentie Linde"])
        self.assertIn("inspection", signals["Residentie Linde"])
        self.assertEqual(self.linde.arrears_signal_threshold, 250)

    def test_demo_case_managers(self):
        # Step 29: the demo login manages Linde and Hof ter Beuken, his colleague Kaaihuis; open tasks follow.
        admin = self.env.ref("base.user_admin")
        staff = self.env["res.users"].search([("login", "=", "medewerker.voorbeeld@example.com")])
        managers = {vme.name: vme.manager_user_id for vme in self.vmes}
        self.assertEqual(managers, {"Residentie Linde": admin, "Hof ter Beuken": admin, "Kaaihuis": staff})
        kaai = self.vmes.filtered(lambda v: v.name == "Kaaihuis")
        tasks = self.env["mail.activity"].search([("res_model", "=", "vme.contract"), ("res_id", "in", self.env[
            "vme.contract"].search([("association_id", "=", kaai.id)]).ids)])
        self.assertEqual(tasks.user_id, staff if tasks else self.env["res.users"])

    def test_demo_portal_request_and_survey(self):
        # Step 27: A1 filed a request in the portal and answered the survey on charging points there.
        request = self.env["vme.request"].search([("association_id", "=", self.linde.id), ("channel", "=", "portal")])
        self.assertEqual(request.requester_id.name, "Eigenaar Linde A1")
        self.assertEqual(request.state, "in_progress")
        survey = self.env["vme.communication"].search([("association_id", "=", self.linde.id), ("kind", "=", "survey")])
        self.assertEqual(survey.state, "sent")
        self.assertFalse(survey.log_ids.mail_id, "the demo survey queues no mails")
        answered = survey.log_ids.filtered("answer_option_id")
        self.assertEqual(len(answered), 3)
        self.assertEqual(answered.filtered(lambda log: log.answer_channel == "portal").partner_id.name, "Eigenaar Linde A1")
        tenant = self.env["res.partner"].search([("name", "=", "Huurder Linde A6")])
        self.assertTrue(tenant.user_ids.share)
        self.assertEqual(tenant._vme_portal_request_lots().name, "A6")

    @freeze_time(date(2026, 11, 5))
    def test_demo_syndic(self):
        office = self.env["res.company"].search([("is_syndic_office", "=", True)])
        self.assertEqual(office.name, "Syndicus Voorbeeld BV")
        agreements = self.env["vme.management.agreement"].search([])
        self.assertEqual(sorted(agreements.mapped("association_id.name")), sorted(self.vmes.mapped("name")))
        mandates = {m.association_id.name: m for m in self.env["vme.syndic.mandate"].search([])}
        self.assertEqual(mandates["Residentie Linde"].renewal_assembly_year, 2027)
        self.assertEqual(mandates["Residentie Linde"].renewal_state, "plan")
        self.assertEqual(mandates["Hof ter Beuken"].renewal_state, "ok")
        self.assertEqual(mandates["Kaaihuis"].posting_state, "late")
        services = {(s.association_id.name, s.service_type) for s in self.env["vme.service.line"].search([])}
        self.assertEqual(services, {("Residentie Linde", "damage_claim"), ("Hof ter Beuken", "extra_meeting"),
                                    ("Kaaihuis", "registered_mail")})

