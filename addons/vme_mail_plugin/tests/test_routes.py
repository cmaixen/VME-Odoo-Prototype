"""The routes of the task pane over HTTP, with a real API key of scope odoo.plugin.outlook."""
import json
from datetime import date, datetime, timedelta

from lxml import etree

from odoo.tests import HttpCase, new_test_user, tagged

PASSWORD = "outlook-test-1234"


@tagged("post_install", "-at_install")
class TestRoutes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = new_test_user(cls.env, login="medewerker.outlook", password=PASSWORD,
                                  groups="base.group_user,base.group_partner_manager,account.group_account_invoice")
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Outlook"})
        cls.env.cr.precommit.run()
        cls.staff.company_ids |= cls.vme.company_id
        cls.owner = cls.env["res.partner"].create({"name": "Eigenaar Outlook O1", "email": "eigenaar.o1@example.com"})
        cls.lot = cls.env["vme.lot"].create({"association_id": cls.vme.id, "name": "O1"})
        cls.env["vme.ownership"].create({"lot_id": cls.lot.id, "partner_id": cls.owner.id, "date_start": date(2020, 1, 1)})
        cls.key = cls.env["res.users.apikeys"].with_user(cls.staff).sudo()._generate(
            "odoo.plugin.outlook", "Outlook (VME)", datetime.now() + timedelta(days=30))

    def _call(self, route, params, key=None):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        response = self.url_open(route, data=json.dumps(
            {"jsonrpc": "2.0", "method": "call", "id": 1, "params": params}).encode(), headers=headers)
        return response.json()

    def test_context_with_the_api_key(self):
        result = self._call("/mail_plugin/vme/context", {"email": "eigenaar.o1@example.com"}, self.key)["result"]
        [match] = result["matches"]
        self.assertEqual((match["vme"]["name"], match["lots"][0]["name"], match["role"]),
                         ("Residentie Outlook", "O1", "owner"))

    def test_without_or_with_a_wrong_key_nothing(self):
        for key in (None, "verkeerd"):
            answer = self._call("/mail_plugin/vme/context", {"email": "eigenaar.o1@example.com"}, key)
            self.assertNotIn("result", answer)
            self.assertIn("Access token", json.dumps(answer["error"]))

    def test_a_key_of_another_scope_is_refused(self):
        rpc_key = self.env["res.users.apikeys"].with_user(self.staff).sudo()._generate(
            "rpc", "Andere sleutel", datetime.now() + timedelta(days=1))
        answer = self._call("/mail_plugin/vme/context", {"email": "eigenaar.o1@example.com"}, rpc_key)
        self.assertIn("error", answer)

    def test_log_posts_an_internal_note(self):
        result = self._call("/mail_plugin/vme/log", {
            "model": "vme.association", "res_id": self.vme.id, "subject": "Vraag over de lift",
            "email": "eigenaar.o1@example.com", "name": "Eigenaar Outlook O1", "body": "De lift staat stil.",
        }, self.key)["result"]
        message = self.env["mail.message"].browse(result["message_id"])
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_note"))
        self.assertEqual(message.author_id, self.staff.partner_id)
        self.assertIn("De lift staat stil.", message.body)

    def test_request_from_the_mail(self):
        result = self._call("/mail_plugin/vme/request", {
            "association_id": self.vme.id, "request_type": "document", "email": "eigenaar.o1@example.com",
            "subject": "Kopie basisakte", "body": "Graag een kopie.", "message_id": "<akte-o1@example.com>",
        }, self.key)["result"]
        request = self.env["vme.request"].browse(result["id"])
        self.assertEqual((request.channel, request.source_reference, request.lot_id), ("mail", "akte-o1@example.com", self.lot))

    def test_manifest_has_the_url_of_this_instance(self):
        self.env["ir.config_parameter"].set_param("vme_mail_plugin.base_url", "https://syndicus.example.com")
        self.authenticate("medewerker.outlook", PASSWORD)
        response = self.url_open("/vme_mail_plugin/manifest.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://syndicus.example.com/vme_mail_plugin/static/outlook/taskpane.html", response.text)
        self.assertIn("<Permissions>ReadItem</Permissions>", response.text)
        self.assertIn('DisplayName DefaultValue="VME-dossier (syndicus.example.com)"', response.text)
        etree.fromstring(response.content)  # well-formed XML
        addin_id = self.env["ir.config_parameter"].get_param("vme_mail_plugin.addin_id")
        self.assertIn(f"<Id>{addin_id}</Id>", response.text)
        # The same id next time: a new manifest replaces the add-in in Outlook.
        self.assertIn(f"<Id>{addin_id}</Id>", self.url_open("/vme_mail_plugin/manifest.xml").text)

    def test_demo_inbox_for_administrators(self):
        self.authenticate("medewerker.outlook", PASSWORD)
        answer = self._call("/vme_mail_plugin/demo/inbox", {})
        self.assertIn("error", answer)
        self.authenticate("admin", "admin")
        mails = self._call("/vme_mail_plugin/demo/inbox", {})["result"]["mails"]
        self.assertEqual(len(mails), 8)
        leak = mails[0]
        self.assertEqual(leak["from"]["emailAddress"], "eigenaar.linde.a4@example.com")
        self.assertEqual(leak["internetMessageId"], "<lek-a4-20261102@example.com>")
        txt = next(m for m in mails if m["file"].endswith(".txt"))
        self.assertEqual(txt["from"]["emailAddress"], "eigenaar.beuken.b23@example.com")
        self.assertTrue(txt["body"].startswith("Beste,"))
        self.assertEqual(len(mails[-1]["attachments"]), 2)

    def test_static_task_pane_is_served(self):
        self.assertIn("taskpane.js", self.url_open("/vme_mail_plugin/static/outlook/taskpane.html").text)
