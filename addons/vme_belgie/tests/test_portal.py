"""Access rights of the owner portal: an owner never sees another VME, another lot, or new
documents of a lot after selling it. Also the address change that the syndic approves."""
import base64
from datetime import date

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from ..demo_data.vme_demo_data import fake_iban

PASSWORD = "portaal-test-1234"


class PortalFixture:
    """Two VMEs. In "Residentie Portaal": owner P owns A1 and G1, the seller sold A2 to the buyer
    on 1 July 2026, the neighbour owns A3. In "Residentie Ander" lives the other owner."""

    @classmethod
    def _setup_portal_fixture(cls):
        env = cls.env
        Partner = env["res.partner"]
        cls.owner, cls.seller, cls.buyer, cls.neighbour, cls.other_owner = Partner.create([
            {"name": name, "email": f"{login}@example.com"}
            for name, login in (("Eigenaar P", "eigenaar.p"), ("Verkoper P", "verkoper.p"), ("Koper P", "koper.p"),
                                ("Buur P", "buur.p"), ("Eigenaar Ander", "eigenaar.ander"))
        ])
        cls.vme, cls.other_vme = env["vme.association"].create([{"name": "Residentie Portaal"}, {"name": "Residentie Ander"}])
        env.cr.precommit.run()  # chart of accounts of the new companies
        cls.lots = env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": name, "lot_type": lot_type}
            for name, lot_type in (("A1", "apartment"), ("A2", "apartment"), ("A3", "apartment"), ("G1", "garage"))
        ])
        cls.a1, cls.a2, cls.a3, cls.g1 = cls.lots
        cls.other_lot = env["vme.lot"].create({"association_id": cls.other_vme.id, "name": "A1"})
        env["vme.ownership"].create([
            {"lot_id": cls.a1.id, "partner_id": cls.owner.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.g1.id, "partner_id": cls.owner.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.a2.id, "partner_id": cls.seller.id, "date_start": date(2015, 1, 1), "date_end": date(2026, 6, 30)},
            {"lot_id": cls.a2.id, "partner_id": cls.buyer.id, "date_start": date(2026, 7, 1)},
            {"lot_id": cls.a3.id, "partner_id": cls.neighbour.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.other_lot.id, "partner_id": cls.other_owner.id, "date_start": date(2015, 1, 1)},
        ])

        def folder(xml_id):
            return env.ref(f"vme_belgie.{xml_id}")

        def doc(name, vme, folder_id, day, lot=None, visible=None):
            vals = {
                "name": name, "association_id": vme.id, "folder_id": folder(folder_id).id,
                "lot_id": lot.id if lot else False, "date": day,
                "datas": base64.b64encode(f"Fictief document {name}".encode()), "filename": f"{name}.txt",
            }
            if visible is not None:
                vals["portal_visible"] = visible
            return env["vme.document"].create(vals)

        cls.doc_deed = doc("Basisakte", cls.vme, "folder_deed", date(1998, 1, 1))
        cls.doc_policy_after_sale = doc("Bijvoegsel polis", cls.vme, "folder_insurance", date(2026, 10, 1))
        cls.doc_internal = doc("Intern contract", cls.vme, "folder_contracts", date(2026, 1, 1), visible=False)
        cls.doc_a1 = doc("Brief A1", cls.vme, "folder_lot_letters", date(2026, 9, 1), lot=cls.a1)
        cls.doc_a3 = doc("Brief A3", cls.vme, "folder_lot_letters", date(2026, 9, 1), lot=cls.a3)
        cls.doc_a2_before = doc("Brief A2 voor verkoop", cls.vme, "folder_lot_letters", date(2026, 3, 1), lot=cls.a2)
        cls.doc_a2_after = doc("Brief A2 na verkoop", cls.vme, "folder_lot_letters", date(2026, 8, 1), lot=cls.a2)
        cls.doc_other_vme = doc("Basisakte ander", cls.other_vme, "folder_deed", date(2000, 1, 1))
        cls.doc_other_lot = doc("Brief ander A1", cls.other_vme, "folder_lot_letters", date(2026, 9, 1), lot=cls.other_lot)

        Users = env["res.users"].with_context(no_reset_password=True)
        cls.portal_users = {}
        for partner in (cls.owner, cls.seller, cls.buyer, cls.other_owner):
            cls.portal_users[partner] = Users.create({
                "login": partner.email, "password": PASSWORD, "partner_id": partner.id,
                "group_ids": [Command.set(env.ref("base.group_portal").ids)],
            })

    @classmethod
    def _setup_provisions(cls):
        env = cls.env
        Bank = env["res.partner.bank"]
        admin = env.ref("base.user_admin")
        for index, vme in enumerate((cls.vme, cls.other_vme)):
            banks = Bank.create([
                {"acc_number": fake_iban(900 + 10 * index + n), "partner_id": vme.partner_id.id} for n in (1, 2)])
            banks.with_user(admin).allow_out_payment = True
            vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
            lots = vme.lot_ids
            env["vme.key"].create({
                "name": "Algemeen", "association_id": vme.id, "key_type": "general", "total_shares": 1000,
                "line_ids": [Command.create({"lot_id": lot.id, "shares": 1000 // len(lots) + (1000 % len(lots) if i == 0 else 0)})
                             for i, lot in enumerate(lots)],
            })
            env["vme.budget"].create({
                "association_id": vme.id, "year": 2026,
                "working_capital_budget": 8000, "reserve_capital_contribution": 800, "calls_per_year": "4",
            })
        wizard = env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set((cls.vme | cls.other_vme).ids)],
            "year": 2026, "number": 1, "invoice_date": date(2026, 1, 15), "date_due": date(2026, 1, 31),
            "post_invoices": True,
        })
        wizard.action_create_calls()
        # Interest and damages of the internal collection (step 10): an invoice too, but no provision.
        collection = env["vme.collection"].create({"association_id": cls.vme.id, "partner_id": cls.owner.id})
        cls.collection_invoice = collection._create_cost_invoice({"interest": [], "penalty": 50.0}, date(2026, 3, 1))


@tagged("post_install", "-at_install")
class TestPortalAccess(PortalFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_portal_fixture()
        cls._setup_provisions()

    def _visible(self, partner):
        return self.env["vme.document"]._portal_documents_for(partner)

    def test_never_another_vme(self):
        self.assertEqual(self.owner._vme_portal_associations(), self.vme)
        self.assertFalse(self.owner._vme_portal_check_association(self.other_vme.id))
        docs = self._visible(self.owner)
        self.assertFalse(docs.filtered(lambda d: d.association_id == self.other_vme))
        self.assertFalse(self.env["vme.document"]._portal_documents_for(self.owner, self.other_vme))
        self.assertFalse(self.owner._vme_portal_provisions(self.other_vme))
        self.assertEqual(self.owner._vme_portal_statement_years(self.other_vme), [])
        self.assertIsNone(self.owner._vme_portal_statement(self.other_vme, 2026))
        self.assertFalse(self.owner._vme_portal_next_assembly(self.other_vme))
        # And the other way around.
        self.assertEqual(self._visible(self.other_owner), self.doc_other_vme | self.doc_other_lot)

    def test_never_another_lot(self):
        docs = self._visible(self.owner)
        self.assertIn(self.doc_a1, docs)
        self.assertNotIn(self.doc_a3, docs)
        self.assertNotIn(self.doc_a2_before, docs)
        self.assertNotIn(self.doc_a2_after, docs)
        self.assertNotIn(self.doc_other_lot, docs)
        self.assertNotIn(self.doc_internal, docs)
        self.assertEqual(docs, self.doc_deed | self.doc_policy_after_sale | self.doc_a1)

    def test_no_new_documents_after_sale(self):
        seller_docs = self._visible(self.seller)
        self.assertIn(self.doc_a2_before, seller_docs)
        self.assertIn(self.doc_deed, seller_docs)
        self.assertNotIn(self.doc_a2_after, seller_docs)
        self.assertNotIn(self.doc_policy_after_sale, seller_docs)
        # A document added later, dated after the sale, stays invisible to the seller.
        late = self.env["vme.document"].create({
            "name": "Nieuwe brief A2", "association_id": self.vme.id, "lot_id": self.a2.id,
            "folder_id": self.env.ref("vme_belgie.folder_lot_letters").id, "date": date(2026, 11, 1),
            "datas": base64.b64encode(b"Fictief"),
        })
        self.assertNotIn(late, self._visible(self.seller))
        # The buyer sees the new documents of the lot, not the letters to the seller.
        buyer_docs = self._visible(self.buyer)
        self.assertIn(late, buyer_docs)
        self.assertIn(self.doc_a2_after, buyer_docs)
        self.assertNotIn(self.doc_a2_before, buyer_docs)
        self.assertIn(self.doc_deed, buyer_docs)  # the deed of the building, from before the purchase

    def test_provisions_only_own_and_no_collection(self):
        provisions = self.owner._vme_portal_provisions(self.vme)
        self.assertEqual(len(provisions), 2)  # working and reserve capital of call 1
        self.assertEqual(provisions.partner_id, self.owner)
        self.assertTrue(all(provisions.mapped("vme_provision_call_id")))
        self.assertNotIn(self.collection_invoice, provisions)
        self.assertEqual(self.owner._vme_portal_statement_years(self.vme), [2026])
        statement = self.owner._vme_portal_statement(self.vme, 2026)["statement"]
        self.assertEqual(statement["partner"], self.owner)
        self.assertEqual(statement["ownerships"].lot_id, self.a1 | self.g1)

    def test_no_orm_access_for_portal_users(self):
        user = self.portal_users[self.owner]
        for model in ("vme.association", "vme.lot", "vme.ownership", "vme.document", "vme.sale.file",
                      "vme.collection", "vme.collection.reminder", "vme.address.request", "vme.cost.allocation"):
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(user).search([])

    def test_address_change_needs_approval(self):
        request = self.env["vme.address.request"]._create_from_portal(self.owner, {
            "street": "Voorbeeldlaan 1", "zip": "2000", "city": "Antwerpen",
            "country_id": str(self.env.ref("base.be").id), "email": "eigenaar.p@example.com",
        })
        self.assertFalse(self.owner.street)
        self.assertTrue(request.activity_ids)
        request.action_approve()
        self.assertEqual((self.owner.street, self.owner.zip, self.owner.city), ("Voorbeeldlaan 1", "2000", "Antwerpen"))
        self.assertFalse(request.activity_ids)
        refused = self.env["vme.address.request"]._create_from_portal(self.owner, {"street": "Elders 9", "zip": "1000", "city": "Brussel"})
        refused.action_refuse()
        self.assertEqual(self.owner.street, "Voorbeeldlaan 1")

    def test_owner_cannot_edit_own_address_directly(self):
        user = self.portal_users[self.owner]
        self.assertFalse(self.owner.with_user(user)._can_be_edited_by_current_customer())


@tagged("post_install", "-at_install")
class TestPortalRoutes(PortalFixture, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_portal_fixture()

    def test_routes(self):
        self.authenticate(self.owner.email, PASSWORD)
        self.assertEqual(self.url_open("/my/vme").status_code, 200)
        page = self.url_open(f"/my/vme/{self.vme.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Brief A1", page.text)
        self.assertNotIn("Brief A3", page.text)
        self.assertEqual(self.url_open(f"/my/vme/{self.other_vme.id}").status_code, 404)
        own = self.url_open(f"/my/vme/document/{self.doc_a1.id}")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.content, b"Fictief document Brief A1")
        for doc in (self.doc_a3, self.doc_other_vme, self.doc_other_lot, self.doc_internal, self.doc_a2_before):
            self.assertEqual(self.url_open(f"/my/vme/document/{doc.id}").status_code, 404, doc.name)
        self.assertEqual(self.url_open(f"/my/vme/{self.other_vme.id}/statement/2026").status_code, 404)
        # Odoo's own address forms send owners to the request form.
        self.assertTrue(self.url_open("/my/account").url.endswith("/my/vme/address"))

    def test_seller_after_sale(self):
        self.authenticate(self.seller.email, PASSWORD)
        self.assertEqual(self.url_open(f"/my/vme/document/{self.doc_a2_before.id}").status_code, 200)
        self.assertEqual(self.url_open(f"/my/vme/document/{self.doc_a2_after.id}").status_code, 404)
        # Today's capitals and budget are for current owners only.
        self.assertNotIn("Financiële toestand van het gebouw", self.url_open(f"/my/vme/{self.vme.id}").text)
        self.authenticate(self.buyer.email, PASSWORD)
        self.assertIn("Financiële toestand van het gebouw", self.url_open(f"/my/vme/{self.vme.id}").text)
