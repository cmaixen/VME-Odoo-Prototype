from datetime import date
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestSyndic(TransactionCase):
    """Office "Syndicus Test BV" manages Residentie Ereloon: four lots, owners A1-A4, general key 250 each."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.office = Company.create({
            "name": "Syndicus Test BV", "is_syndic_office": True, "country_id": cls.env.ref("base.be").id,
            "currency_id": cls.env.ref("base.EUR").id, "street": "Kantoorlaan 1", "zip": "2000",
            "city": "Voorbeeldstad", "company_registry": "0000.000.592",
        })
        cls.env["vme.association"]._load_vme_chart(cls.office.id)
        cls.vme = cls.env["vme.association"].create(
            {"name": "Residentie Ereloon", "assembly_period_month": "3", "assembly_period_day": 4})
        cls.env.cr.precommit.run()
        cls.env.user.company_ids |= cls.office
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": f"A{i}", "sequence": i} for i in range(1, 5)])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 250}) for lot in cls.lots],
        })
        cls.owners = cls.env["res.partner"].create([{"name": f"Eigenaar {lot.name}"} for lot in cls.lots])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(cls.lots, cls.owners)])
        cls.env["vme.consumer.price.index"].create([
            {"month": date(2023, 12, 1), "value": 100.0},
            {"month": date(2024, 12, 1), "value": 103.0},
            {"month": date(2025, 12, 1), "value": 105.06},
        ])
        cls.agreement = cls.env["vme.management.agreement"].create({
            "association_id": cls.vme.id, "date_start": date(2024, 1, 1), "fee_basis": "lot",
            "fee_amount": 12.0, "billing_period": "quarter", "indexation": "cpi",
        })

    # --- Indexation -------------------------------------------------------------------------

    def test_defaults_rule_and_price_list(self):
        self.assertEqual(self.agreement.syndic_company_id, self.office)
        self.assertEqual(self.agreement.index_base_month, date(2023, 12, 1))
        self.assertEqual(self.agreement.index_base_value, 100.0)
        self.assertEqual(len(self.agreement.rate_ids), 5)
        rule = self.env["vme.distribution.rule"]._find_rule(self.vme.company_id, self.office.partner_id)
        self.assertEqual(rule.key_id, self.key)
        self.assertEqual(rule.account_id.with_company(self.vme.company_id).code, "613290")

    def test_cpi_indexation_on_each_anniversary(self):
        self.assertEqual(self.agreement._unit_fee(date(2024, 12, 1)), 12.0)
        self.assertEqual(self.agreement._unit_fee(date(2025, 1, 1)), 12.36)  # 12 x 103 / 100
        self.assertEqual(self.agreement._unit_fee(date(2026, 1, 1)), 12.61)  # 12 x 105.06 / 100
        self.assertEqual(self.agreement.current_monthly_fee, 4 * 12.61)

    def test_fixed_percentage(self):
        self.agreement.write({"indexation": "percent", "index_percent": 2.0})
        self.assertEqual(self.agreement._unit_fee(date(2025, 6, 1)), 12.24)
        self.assertEqual(self.agreement._unit_fee(date(2026, 6, 1)), 12.48)  # 12 x 1.02^2 = 12.4848

    def test_missing_index_figure_is_explained(self):
        with self.assertRaisesRegex(UserError, "consumptieprijsindex van .* staat nog niet in de tabel"):
            self.agreement._unit_fee(date(2027, 1, 1))

    def test_anniversary_in_the_middle_of_a_quarter(self):
        self.agreement.date_start = date(2024, 2, 1)
        self.agreement.index_base_value = 100.0
        self.env["vme.consumer.price.index"].create([
            {"month": date(2025, 1, 1), "value": 103.0}, {"month": date(2026, 1, 1), "value": 106.0}])
        lines = self.agreement._fixed_fee_lines(date(2026, 1, 1), date(2026, 3, 31))
        # January still on the index of the first anniversary (January 2025 = 103), February on January 2026.
        self.assertEqual([(l["quantity"], l["price_unit"]) for l in lines], [(4, 12.36), (8, 12.72)])

    # --- Services where they arise ------------------------------------------------------------

    def test_service_from_registered_mail_only_once(self):
        mail = self.env["vme.registered.mail"].create({
            "association_id": self.vme.id, "partner_id": self.owners[0].id, "subject": "Ingebrekestelling"})
        mail.action_deposit()
        mail.action_deposit()
        line = self.env["vme.service.line"].search([("res_model", "=", "vme.registered.mail"), ("res_id", "=", mail.id)])
        self.assertEqual(len(line), 1)
        self.assertEqual((line.service_type, line.date, line.price_unit), ("registered_mail", TODAY, 18.91))
        self.assertEqual(line.state, "to_invoice")

    def test_service_from_damage_claim(self):
        insurer = self.env["res.partner"].create({"name": "Verzekeraar Test", "is_company": True})
        policy = self.env["vme.insurance.policy"].create({
            "association_id": self.vme.id, "name": "Brandpolis", "insurer_id": insurer.id, "policy_number": "POL-1",
            "declaration_days": 8})
        claim = self.env["vme.damage.claim"].create({
            "association_id": self.vme.id, "name": "Waterschade A2", "event_date": date(2026, 11, 1),
            "report_date": date(2026, 11, 2), "policy_id": policy.id})
        claim.action_declare()
        line = self.vme.service_line_ids
        self.assertEqual(line.service_type, "damage_claim")
        self.assertEqual(line.price_unit, 126.07)  # 120 x 1.0506: the price list is indexed too

    def test_service_from_sale_file_recharges_the_seller(self):
        sale = self.env["vme.sale.file"].create({
            "association_id": self.vme.id, "lot_ids": [Command.set(self.lots[:1].ids)],
            "first_request_date": date(2026, 11, 2)})
        with patch.object(type(sale), "_render_answer", return_value=b"%PDF-1.4"):
            sale.action_answer_first()
        line = self.vme.service_line_ids
        self.assertEqual(line.service_type, "sale_file")
        self.assertEqual(line.recharge_partner_id, self.owners[0])

    def test_service_from_extraordinary_assembly_and_second_meeting(self):
        extraordinary, second = self.env["vme.assembly"].create([
            {"association_id": self.vme.id, "year": 2026, "assembly_type": "extraordinary", "subject": "Laadpalen"},
            {"association_id": self.vme.id, "year": 2026, "assembly_type": "extraordinary", "subject": "Gevel",
             "second_session": True},
        ])
        (extraordinary | second).item_ids.majority = "none"
        (extraordinary | second).action_mark_held()
        types = {line.res_id: line.service_type for line in self.vme.service_line_ids}
        self.assertEqual(types, {extraordinary.id: "extraordinary_assembly", second.id: "extra_meeting"})

    def test_no_service_without_agreement(self):
        other = self.env["vme.association"].create({"name": "Residentie Zonder"})
        mail = self.env["vme.registered.mail"].create({
            "association_id": other.id, "partner_id": self.owners[0].id, "subject": "Brief"})
        mail.action_deposit()
        self.assertFalse(other.service_line_ids)

    # --- Fee invoice ------------------------------------------------------------------------

    def _service(self, day, service_type="registered_mail", **vals):
        return self.env["vme.service.line"].create({
            "association_id": self.vme.id, "service_type": service_type, "date": day,
            "name": "Aangetekende zending", **vals})

    def test_invoice_is_fixed_fee_plus_services(self):
        done = self._service(date(2026, 8, 3))
        later = self._service(date(2026, 10, 2))
        free = self._service(date(2026, 8, 4), no_charge=True)
        invoice = self.agreement._create_fee_invoice(date(2026, 7, 1), date(2026, 9, 30))
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.company_id, self.office)
        self.assertEqual(invoice.partner_id, self.vme.partner_id)
        fixed = 4 * 3 * 12.61
        self.assertAlmostEqual(invoice.amount_untaxed, fixed + done.price_unit)
        self.assertAlmostEqual(invoice.amount_tax, round((fixed + done.price_unit) * 0.21, 2))
        self.assertEqual((done.state, later.state, free.state), ("invoiced", "to_invoice", "no_charge"))
        self.assertIn("(4 kavels × 3 maand(en))", invoice.invoice_line_ids[0].name)
        with self.assertRaisesRegex(UserError, "bestaat al een ereloonfactuur"):
            self.agreement._create_fee_invoice(date(2026, 9, 1), date(2026, 9, 30))
        invoice.button_cancel()
        self.assertEqual(done.state, "to_invoice")

    def test_deleting_a_draft_invoice_frees_the_services(self):
        service = self._service(date(2026, 8, 3))
        invoice = self.agreement._create_fee_invoice(date(2026, 7, 1), date(2026, 9, 30))
        invoice.unlink()
        self.assertEqual(service.state, "to_invoice")

    def test_wizard_by_billing_period(self):
        self.agreement.billing_period = "month"
        wizard = self.env["vme.fee.invoice.wizard"].create({})
        self.assertEqual((wizard.date_from, wizard.date_to), (date(2026, 7, 1), date(2026, 9, 30)))
        wizard.action_create()
        invoices = self.agreement.fee_invoice_ids
        self.assertEqual(sorted(invoices.mapped("vme_period_start")),
                         [date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)])
        with self.assertRaisesRegex(UserError, "Al gefactureerd"):
            self.env["vme.fee.invoice.wizard"].create({}).action_create()

    def test_confirming_prepares_a_draft_bill_in_the_vme(self):
        self._service(date(2026, 8, 3))
        invoice = self.agreement._create_fee_invoice(date(2026, 7, 1), date(2026, 9, 30))
        invoice.action_post()
        bill = invoice.vme_fee_bill_id
        self.assertEqual((bill.move_type, bill.state, bill.company_id), ("in_invoice", "draft", self.vme.company_id))
        self.assertEqual(bill.partner_id, self.office.partner_id)
        self.assertEqual((bill.ref, bill.vme_period_start, bill.vme_period_end),
                         (invoice.name, date(2026, 7, 1), date(2026, 9, 30)))
        self.assertEqual(bill.invoice_line_ids.vme_key_id, self.key)
        self.assertEqual(bill.invoice_line_ids.account_id.with_company(self.vme.company_id).code, "613290")
        self.assertAlmostEqual(bill.amount_total, invoice.amount_total)
        self.assertFalse(bill.vme_allocation_ids)
        # A person confirms the bill in the VME; then it is split over the owners.
        bill.action_post()
        self.assertEqual(len(bill.vme_allocation_ids.partner_id), 4)
        self.assertAlmostEqual(sum(bill.vme_allocation_ids.mapped("amount")), bill.amount_total)

    # --- Mandate ----------------------------------------------------------------------------

    def _mandate(self, start, **vals):
        return self.env["vme.syndic.mandate"].create({"association_id": self.vme.id, "date_start": start, **vals})

    def test_mandate_at_most_three_years(self):
        mandate = self._mandate(date(2024, 3, 12))
        self.assertEqual(mandate.date_end, date(2027, 3, 11))
        self.assertEqual(mandate.partner_id, self.office.partner_id)
        with self.assertRaisesRegex(ValidationError, "hoogstens drie jaar"):
            mandate.date_end = date(2027, 3, 12)

    def test_renewal_assembly_and_signal(self):
        mandate = self._mandate(date(2024, 3, 12))
        # Period 4-18 March 2027 starts before the end on 11 March 2027: that assembly decides.
        self.assertEqual((mandate.renewal_assembly_year, mandate.renewal_period_start), (2027, date(2027, 3, 4)))
        self.assertEqual(mandate.renewal_state, "plan")
        self.assertIn("Nog geen agendapunt", mandate.renewal_text)
        with freeze_time(date(2027, 1, 10)):
            mandate.invalidate_recordset(["renewal_state"])
            self.assertEqual(mandate.renewal_state, "urgent")
        with freeze_time(date(2026, 8, 1)):
            mandate.invalidate_recordset(["renewal_state"])
            self.assertEqual(mandate.renewal_state, "ok")
        self.assertEqual(self.vme.current_syndic_mandate_id, mandate)
        self.assertEqual(self.vme._get_syndic_mandate_on(date(2027, 3, 12)), self.env["vme.syndic.mandate"])
        mandate.invalidate_recordset(["renewal_state"])
        self.assertIn(mandate, self.env["vme.syndic.mandate"].search([("renewal_state", "=", "plan")]))

    def test_renewal_point_on_new_assembly_and_renewal(self):
        mandate = self._mandate(date(2024, 3, 12))
        assembly = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2027})
        item = assembly.item_ids.filtered(lambda i: i.name.startswith("Herbenoeming van de syndicus"))
        self.assertEqual(len(item), 1)
        self.assertEqual(mandate.renewal_item_id, item)
        mandate.action_add_renewal_item()
        self.assertEqual(len(assembly.item_ids.filtered(lambda i: i.name == item.name)), 1)
        with self.assertRaisesRegex(UserError, "niet aangenomen"):
            mandate.action_renew()
        with patch.object(type(item), "_compute_outcome", lambda items: items.update({"outcome": "adopted"})):
            item._compute_outcome()
            mandate.invalidate_recordset(["renewal_state"])
            self.assertEqual(mandate.renewal_state, "decided")
            action = mandate.action_renew()
        new = self.env["vme.syndic.mandate"].browse(action["res_id"])
        self.assertEqual((new.date_start, new.date_end), (date(2027, 3, 12), date(2030, 3, 11)))
        self.assertEqual((new.previous_mandate_id, new.appointment_item_id), (mandate, item))
        mandate.invalidate_recordset(["renewal_state", "next_mandate_id"])
        self.assertEqual(mandate.renewal_state, "renewed")

    def test_cron_schedules_renewal_and_posting_tasks(self):
        mandate = self._mandate(date(2024, 3, 12))
        self.env["vme.syndic.mandate"]._cron_schedule_mandate_activities()
        self.env["vme.syndic.mandate"]._cron_schedule_mandate_activities()
        self.assertEqual(sorted(mandate.activity_ids.mapped("summary")), [
            "Aanstelling syndicus aanplakken aan de ingang", "Herbenoeming syndicus voorbereiden (AV 2027)"])

    def test_posting_within_eight_days(self):
        mandate = self._mandate(date(2026, 10, 20))
        self.assertEqual(mandate.posting_deadline, date(2026, 10, 28))
        self.assertEqual(mandate.posting_state, "late")
        with patch.object(type(self.env["ir.actions.report"]), "_render_qweb_pdf",
                          return_value=(b"%PDF-1.4", "pdf")):
            mandate.action_make_posting()
        document = mandate.posting_document_id
        self.assertEqual(document.folder_id, self.env.ref("vme_belgie.folder_syndic"))
        self.assertEqual(document.association_id, self.vme)
        mandate.action_mark_posted()
        self.assertEqual((mandate.posted_date, mandate.posting_state), (TODAY, "posted"))

    def test_posting_report_renders(self):
        mandate = self._mandate(date(2026, 10, 20))
        html = self.env["ir.actions.report"]._render_qweb_html("vme_belgie.report_syndic_posting", mandate.ids)[0]
        self.assertIn(b"Syndicus Test BV", html)
        self.assertIn(b"0000.000.592", html)
