from datetime import date

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)
START = date(2026, 3, 10)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestCouncil(TransactionCase):
    """Residentie Raad has 20 apartments and 2 garages; Residentie Ander is another VME of the same syndic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Vme = cls.env["vme.association"]
        cls.vme, cls.other_vme = Vme.create([{"name": "Residentie Raad"}, {"name": "Residentie Ander"}])
        cls.env.cr.precommit.run()  # load the chart of accounts, as a real save would
        Lot = cls.env["vme.lot"]
        cls.apartments = Lot.create([{"association_id": cls.vme.id, "name": f"A{i}"} for i in range(1, 21)])
        cls.garages = Lot.create([
            {"association_id": cls.vme.id, "name": f"G{i}", "lot_type": "garage"} for i in (1, 2)])
        cls.other_lot = Lot.create({"association_id": cls.other_vme.id, "name": "B1"})
        Partner = cls.env["res.partner"]
        cls.owners = Partner.create([{"name": f"Eigenaar Raad A{i}"} for i in range(1, 21)])
        cls.other_owner = Partner.create({"name": "Eigenaar Ander B1"})
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(cls.apartments, cls.owners)
        ] + [{"lot_id": cls.other_lot.id, "partner_id": cls.other_owner.id, "date_start": date(2015, 1, 1)}])
        cls.supplier = Partner.create({"name": "Schoonmaak Test", "is_company": True})
        cls.bill = cls._bill(cls.vme, 1000)
        cls.other_bill = cls._bill(cls.other_vme, 500)

        cls.auditor_partner = Partner.create({"name": "Commissaris Test", "email": "commissaris.test@example.com"})
        cls.mandate = cls.env["vme.mandate"].create({
            "association_id": cls.vme.id, "role": "auditor", "partner_id": cls.auditor_partner.id,
            "date_start": START,
        })
        cls.mandate.action_grant_access()
        cls.auditor = cls.mandate.user_id
        cls.staff = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Test", "login": "medewerker.raad@example.com",
            "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
            "company_id": cls.vme.company_id.id,
            "company_ids": [Command.set((cls.vme | cls.other_vme).company_id.ids)],
        })

    @classmethod
    def _bill(cls, vme, price):
        bill = cls.env["account.move"].with_company(vme.company_id).create({
            "move_type": "in_invoice",
            "partner_id": cls.supplier.id,
            "invoice_date": date(2026, 4, 1),
            "invoice_line_ids": [Command.create({
                "name": "Schoonmaak gemene delen", "quantity": 1, "price_unit": price, "tax_ids": [Command.clear()],
            })],
        })
        bill.action_post()
        return bill

    # Mandates

    def test_mandate_lasts_one_year(self):
        self.assertEqual(self.mandate.date_end, date(2027, 3, 9))
        self.assertTrue(self.mandate.is_current)
        self.assertEqual(self.mandate.audit_year, 2026)
        self.assertFalse(self.mandate.is_owner)  # an outside auditor is allowed

    def test_council_only_co_owners(self):
        Mandate = self.env["vme.mandate"]
        member = Mandate.create({"association_id": self.vme.id, "role": "member", "partner_id": self.owners[0].id})
        self.assertTrue(member.is_owner)
        with self.assertRaises(ValidationError):
            Mandate.create({"association_id": self.vme.id, "role": "member", "partner_id": self.auditor_partner.id})
        with self.assertRaises(ValidationError):  # owner of another VME
            Mandate.create({"association_id": self.vme.id, "role": "member", "partner_id": self.other_owner.id})

    def test_one_chair_at_a_time(self):
        Mandate = self.env["vme.mandate"]
        Mandate.create({"association_id": self.vme.id, "role": "chair", "partner_id": self.owners[0].id,
                        "date_start": START})
        with self.assertRaises(ValidationError):
            Mandate.create({"association_id": self.vme.id, "role": "chair", "partner_id": self.owners[1].id,
                            "date_start": date(2026, 9, 1)})
        # The next year's chair may follow on the day after.
        Mandate.create({"association_id": self.vme.id, "role": "chair", "partner_id": self.owners[1].id,
                        "date_start": date(2027, 3, 10)})

    def test_council_required_from_twenty_lots_without_garages(self):
        self.assertEqual(self.vme.council_lot_count, 20)
        self.assertTrue(self.vme.council_required)
        self.assertIn("is een raad van mede-eigendom verplicht", self.vme.council_warning)
        self.apartments[-1].lot_type = "storage"  # 19 lots left
        self.assertFalse(self.vme.council_required)
        self.assertFalse(self.vme.council_warning)  # the auditor is there
        self.assertIn("geen lopend mandaat", self.other_vme.council_warning)

    # The auditor's user

    def test_auditor_user(self):
        self.assertTrue(self.auditor.has_group("vme_belgie.group_vme_auditor"))
        self.assertTrue(self.auditor.has_group("account.group_account_readonly"))
        self.assertFalse(self.auditor.has_group("account.group_account_invoice"))
        self.assertFalse(self.auditor.share)
        self.assertEqual(self.auditor.company_ids, self.vme.company_id)
        self.assertEqual(self.auditor.partner_id, self.auditor_partner)

    def test_new_vme_is_not_added_to_auditor(self):
        new_vme = self.env["vme.association"].create({"name": "Residentie Nieuw"})
        self.assertIn(new_vme.company_id, self.staff.company_ids)
        self.assertEqual(self.auditor.company_ids, self.vme.company_id)

    def test_auditor_reads_his_vme(self):
        env = self.env(user=self.auditor)
        self.assertEqual(env["vme.association"].search([]), self.vme)
        self.assertEqual(env["vme.lot"].search([]), self.apartments | self.garages)
        self.assertEqual(env["vme.ownership"].search([]).association_id, self.vme)
        self.assertEqual(env["account.move"].search([("move_type", "=", "in_invoice")]), self.bill)
        self.assertEqual(self.bill.with_user(self.auditor).amount_total, 1000)
        self.assertEqual(env["vme.mandate"].search([]), self.mandate)

    def test_auditor_sees_nothing_of_other_vme(self):
        env = self.env(user=self.auditor)
        for record in (self.other_vme, self.other_lot, self.other_bill, self.other_owner):
            with self.assertRaises(AccessError):
                record.with_user(self.auditor).read(["display_name"])
        self.assertFalse(env["res.partner"].search([("id", "=", self.other_owner.id)]))
        self.assertFalse(env["account.move"].search([("company_id", "=", self.other_vme.company_id.id)]))
        # Owners and suppliers of his own VME are visible.
        partners = env["res.partner"].search([])
        self.assertIn(self.owners[0], partners)
        self.assertIn(self.supplier, partners)
        self.assertIn(self.auditor_partner, partners)
        # Even with the other company in the context, he cannot switch to it.
        with self.assertRaises(AccessError):
            self.other_lot.with_user(self.auditor).with_context(
                allowed_company_ids=self.other_vme.company_id.ids).read(["name"])

    def test_auditor_changes_nothing(self):
        lot = self.apartments[0].with_user(self.auditor)
        with self.assertRaises(AccessError):
            lot.name = "Gewijzigd"
        with self.assertRaises(AccessError):
            lot.unlink()
        with self.assertRaises(AccessError):
            self.env["vme.lot"].with_user(self.auditor).create({"association_id": self.vme.id, "name": "A99"})
        with self.assertRaises(AccessError):
            self.vme.with_user(self.auditor).name = "Andere naam"
        with self.assertRaises(AccessError):
            self.mandate.with_user(self.auditor).date_end = date(2030, 1, 1)
        with self.assertRaises(AccessError):
            self.bill.with_user(self.auditor).ref = "Gewijzigd"
        with self.assertRaises(AccessError):
            self.bill.with_user(self.auditor).button_draft()
        with self.assertRaises(AccessError):
            self.owners[0].with_user(self.auditor).name = "Andere eigenaar"
        with self.assertRaises(AccessError):
            self.vme.with_user(self.auditor).message_post(body="Notitie")
        with self.assertRaises(AccessError):
            self.mandate.with_user(self.auditor).action_grant_access()

    def test_auditor_views_are_read_only(self):
        arch = self.env["vme.lot"].with_user(self.auditor).get_views([(False, "list"), (False, "form")])["views"]
        self.assertIn('create="0"', arch["list"]["arch"])
        self.assertIn('edit="0"', arch["form"]["arch"])
        staff_arch = self.env["vme.lot"].with_user(self.staff).get_views([(False, "list")])["views"]["list"]["arch"]
        self.assertNotIn('create="0"', staff_arch)

    def test_buttons_writing_as_superuser_are_refused(self):
        collection = self.env["vme.collection"].create({"association_id": self.vme.id, "partner_id": self.owners[0].id})
        with self.assertRaises(AccessError):
            collection.with_user(self.auditor).action_propose_reminder()
        with self.assertRaises(AccessError):
            self.env["vme.collection"].with_user(self.auditor).action_refresh()

    def test_staff_keeps_access(self):
        lot = self.other_lot.with_user(self.staff)
        lot.name = "B1 bis"
        self.assertEqual(self.env["vme.association"].with_user(self.staff).search([]), self.vme | self.other_vme)
        self.mandate.with_user(self.staff).note = "Aangesteld op de AV"
        self.assertEqual(self.env["vme.mandate"].with_user(self.staff).create({
            "association_id": self.other_vme.id, "role": "member", "partner_id": self.other_owner.id,
        }).association_id, self.other_vme)

    def test_only_user_admins_grant_access(self):
        with self.assertRaises(AccessError):
            self.mandate.with_user(self.staff).action_grant_access()

    def test_access_follows_mandates(self):
        second = self.env["vme.mandate"].create({
            "association_id": self.other_vme.id, "role": "auditor", "partner_id": self.auditor_partner.id,
            "date_start": START,
        })
        second.action_grant_access()
        self.assertEqual(second.user_id, self.auditor)
        self.assertEqual(self.auditor.company_ids, (self.vme | self.other_vme).company_id)
        self.assertEqual(self.env["vme.association"].with_user(self.auditor).search([]), self.vme | self.other_vme)

        second.action_revoke_access()
        self.assertEqual(self.auditor.company_ids, self.vme.company_id)
        with freeze_time(date(2027, 3, 10)):  # the mandate has ended
            self.env["vme.mandate"]._cron_sync_auditor_access()
        self.assertFalse(self.auditor.active)

    def test_no_access_for_council_member_or_staff_user(self):
        member = self.env["vme.mandate"].create({
            "association_id": self.vme.id, "role": "member", "partner_id": self.owners[0].id})
        with self.assertRaises(UserError):
            member.action_grant_access()
        staff_mandate = self.env["vme.mandate"].create({
            "association_id": self.vme.id, "role": "auditor", "partner_id": self.staff.partner_id.id})
        with self.assertRaises(UserError):
            staff_mandate.action_grant_access()
        self.assertFalse(self.staff.has_group("vme_belgie.group_vme_auditor"))

    # Overview for the council and the report

    def test_council_dossiers(self):
        remark = self.env["vme.inspection.remark"].create({
            "inspection_id": self.env["vme.inspection"].create({
                "installation_id": self.env["vme.installation"].create({
                    "association_id": self.vme.id, "installation_type": "elevator", "name": "Lift"}).id,
                "date": date(2026, 9, 1),
            }).id,
            "name": "Noodverlichting in de kooi", "deadline": date(2026, 10, 1),
        })
        collection = self.env["vme.collection"].create({"association_id": self.vme.id, "partner_id": self.owners[1].id})
        self.env["vme.collection"].create({"association_id": self.other_vme.id, "partner_id": self.other_owner.id})
        self.env.flush_all()

        Dossier = self.env["vme.council.dossier"]
        rows = Dossier.search([("association_id", "=", self.vme.id)])
        self.assertEqual(sorted(rows.mapped("dossier_type")), ["collection", "inspection"])
        remark_row = rows.filtered(lambda r: r.dossier_type == "inspection")
        self.assertEqual((remark_row.res_model, remark_row.res_id), ("vme.inspection.remark", remark.id))
        self.assertTrue(remark_row.is_overdue)
        self.assertEqual(remark_row.action_open_record()["res_id"], remark.id)
        self.assertEqual(self.vme.open_dossier_count, 2)

        # The auditor sees the files of his VME only.
        self.assertEqual(Dossier.with_user(self.auditor).search([]), rows)
        self.assertEqual(rows.filtered(lambda r: r.dossier_type == "collection").res_id, collection.id)

        remark.state = "resolved"
        self.env.flush_all()
        self.assertEqual(Dossier.search([("association_id", "=", self.vme.id)]).mapped("dossier_type"), ["collection"])

    def test_audit_figures(self):
        figures = self.mandate.with_user(self.auditor)._get_audit_figures()
        self.assertEqual(figures["year"], 2026)
        self.assertEqual(figures["bill_count"], 1)
        self.assertEqual(figures["bill_total"], 1000)
        self.assertEqual(figures["payable"], 1000)
        self.assertEqual(figures["call_count"], 0)
        html = self.env["ir.actions.report"].with_user(self.auditor)._render_qweb_html(
            "vme_belgie.action_report_auditor", self.mandate.ids)[0].decode()
        self.assertIn("Verslag van de commissaris van de rekeningen", html)
        self.assertIn("Commissaris Test", html)
        html = self.env["ir.actions.report"].with_user(self.auditor)._render_qweb_html(
            "vme_belgie.action_report_council_dossiers", self.vme.ids)[0].decode()
        self.assertIn("Lopende dossiers", html)
