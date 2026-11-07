"""What the Outlook task pane shows for a mail: matches, open items, the AI proposal and access."""
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase, new_test_user, tagged

DUE = date(2026, 2, 4)
REFERENCE = "lek-m2-20261102@example.com"


def assistant_note(reference):
    """An activity note in the format of ai/assistant.py (activity_note)."""
    return (
        "<p><b>Voorgesteld antwoord, nog niet verstuurd.</b> Kijk het na.</p>"
        "<ul>"
        "<li><b>Van:</b> Eigenaar Mail M2 &lt;eigenaar.m2@example.com&gt;</li>"
        "<li><b>Kavel:</b> M2</li>"
        "<li><b>Onderwerp:</b> Lek of waterschade</li>"
        "<li><b>Dringendheid:</b> dringend</li>"
        "<li><b>Zekerheid koppeling:</b> hoog &#8212; afzender is eigenaar van M2</li>"
        "<li><b>Samenvatting:</b> Water in de badkamer.</li>"
        "</ul>"
        "<h4>Conceptantwoord: Re: waterlek</h4>"
        "<blockquote><p>Beste eigenaar,</p><p>We sturen vandaag een loodgieter.</p></blockquote>"
        "<h4>Oorspronkelijke mail: waterlek</h4>"
        f"<p class=\"text-muted\">Mon, 02 Nov 2026 &#183; {reference}</p>"
        "<blockquote><p>Er loopt water.</p></blockquote>"
    )


@tagged("post_install", "-at_install")
class TestMailContext(TransactionCase):
    """Residentie Mail: M1 and M2 belong to the multi-owner, M3 to the other owner and is rented out.
    Residentie Ander: the multi-owner also owns X1 there."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme, cls.other_vme = cls.env["vme.association"].create([
            {"name": "Residentie Mail"}, {"name": "Residentie Ander"}])
        cls.env.cr.precommit.run()  # load the chart of accounts and the fund accounts
        cls.owner, cls.other, cls.tenant, cls.former = cls.env["res.partner"].create([
            {"name": "Eigenaar Mail M1", "email": "eigenaar.m1@example.com"},
            {"name": "Eigenaar Mail M3", "email": "eigenaar.m3@example.com"},
            {"name": "Huurder Mail M3", "email": "huurder.m3@example.com"},
            {"name": "Vorige eigenaar M1", "email": "vorige.m1@example.com"},
        ])
        cls.m1, cls.m2, cls.m3 = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": name, "sequence": seq} for seq, name in enumerate(["M1", "M2", "M3"])])
        cls.x1 = cls.env["vme.lot"].create({"association_id": cls.other_vme.id, "name": "X1"})
        cls.env["vme.ownership"].create([
            {"lot_id": cls.m1.id, "partner_id": cls.former.id, "date_start": date(2010, 1, 1), "date_end": date(2019, 12, 31)},
            {"lot_id": cls.m1.id, "partner_id": cls.owner.id, "date_start": date(2020, 1, 1)},
            {"lot_id": cls.m2.id, "partner_id": cls.owner.id, "date_start": date(2020, 1, 1)},
            {"lot_id": cls.m3.id, "partner_id": cls.other.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.x1.id, "partner_id": cls.owner.id, "date_start": date(2018, 1, 1)},
        ])
        cls.env["vme.lot.contact"].create({
            "lot_id": cls.m3.id, "partner_id": cls.tenant.id, "role": "tenant", "date_start": date(2024, 9, 1)})
        cls.Context = cls.env["vme.mail.context"]

    @classmethod
    def _overdue_provision(cls, vme, partner, amount):
        company = vme.company_id
        account = cls.env["account.account"].with_company(company).search(
            [("company_ids", "in", company.id), ("code", "=", "100100")], limit=1)
        move = cls.env["account.move"].with_company(company).create({
            "move_type": "out_invoice", "partner_id": partner.id, "vme_fund": "working",
            "invoice_date": date(2026, 1, 5), "invoice_date_due": DUE,
            "invoice_line_ids": [Command.create({
                "name": "Provisie werkkapitaal", "quantity": 1, "price_unit": amount,
                "account_id": account.id, "tax_ids": [Command.clear()]})],
        })
        move.action_post()
        return move

    def _match(self, email, vme=None):
        matches = self.Context._vme_mail_context(email)["matches"]
        return [m for m in matches if m["vme"]["id"] == (vme or self.vme).id]

    # Who sent the mail?

    def test_owner_of_two_lots_is_one_match_with_both_lots(self):
        [match] = self._match("Eigenaar.M1@example.com")
        self.assertEqual(match["role"], "owner")
        self.assertEqual(match["partner"]["id"], self.owner.id)
        self.assertEqual([lot["name"] for lot in match["lots"]], ["M1", "M2"])
        self.assertIn(f"/odoo/vme.association/{self.vme.id}", match["vme"]["url"])

    def test_owner_in_two_vmes_gets_a_match_per_vme(self):
        matches = self.Context._vme_mail_context("eigenaar.m1@example.com")["matches"]
        self.assertEqual({m["vme"]["name"] for m in matches}, {"Residentie Mail", "Residentie Ander"})

    def test_owner_of_one_lot(self):
        [match] = self._match("eigenaar.m3@example.com")
        self.assertEqual(([lot["name"] for lot in match["lots"]], match["role"]), (["M3"], "owner"))

    def test_tenant(self):
        [match] = self._match("Huurder M3 <huurder.m3@example.com>")
        self.assertEqual(match["role"], "tenant")
        self.assertEqual(match["partner"]["id"], self.tenant.id)
        self.assertEqual([lot["name"] for lot in match["lots"]], ["M3"])

    def test_unknown_and_former_owner_have_no_match(self):
        self.assertEqual(self.Context._vme_mail_context("onbekend@example.com")["matches"], [])
        self.assertEqual(self.Context._vme_mail_context("vorige.m1@example.com")["matches"], [])
        self.assertEqual(self.Context._vme_mail_context("")["matches"], [])

    def test_manual_choice_after_search(self):
        results = self.Context._vme_mail_search("Mail M3")
        self.assertIn(self.m3.id, [r["lot_id"] for r in results])
        context = self.Context._vme_mail_context("onbekend@example.com", association_id=self.vme.id, lot_id=self.m3.id)
        [match] = context["matches"]
        self.assertEqual((match["role"], match["partner"]["id"]), ("manual", self.other.id))
        self.assertEqual(self.Context._vme_mail_search("a"), [])

    # What is open?

    def test_open_items_are_those_of_this_partner_and_vme(self):
        self._overdue_provision(self.vme, self.owner, 250)
        self._overdue_provision(self.vme, self.other, 999)
        self._overdue_provision(self.other_vme, self.owner, 111)
        Request = self.env["vme.request"]
        own = Request.browse(Request.create_from_intake(
            self.vme.id, "document", "eigenaar.m1@example.com", subject="Kopie notulen", reference="req-m1"))
        Request.create_from_intake(self.vme.id, "document", "eigenaar.m3@example.com", subject="Kopie notulen M3")
        claim = self.env["vme.damage.claim"].create({
            "name": "Lek M2", "association_id": self.vme.id, "lot_ids": [Command.set(self.m2.ids)]})
        self.env["vme.damage.claim"].create({
            "name": "Lek M3", "association_id": self.vme.id, "lot_ids": [Command.set(self.m3.ids)]})
        [match] = self._match("eigenaar.m1@example.com")
        items = match["open_items"]
        self.assertEqual([line["amount"] for line in items["arrears"]], [250])
        self.assertEqual(items["arrears"][0]["date_due"], fields.Date.to_string(DUE))
        self.assertEqual([r["id"] for r in items["requests"]], [own.id])
        self.assertEqual([c["id"] for c in items["claims"]], [claim.id])
        [other_match] = self._match("eigenaar.m1@example.com", self.other_vme)
        self.assertEqual([line["amount"] for line in other_match["open_items"]["arrears"]], [111])

    # The AI proposal

    def test_proposal_from_an_activity_note(self):
        self.vme.activity_schedule(
            "mail.mail_activity_data_todo", summary="AI-voorstel: Lek of waterschade (M2)",
            note=assistant_note(REFERENCE), user_id=self.env.uid)
        proposal = self.Context._vme_mail_context("eigenaar.m1@example.com", message_id=f"<{REFERENCE}>")["proposal"]
        self.assertEqual(proposal["source"], "activity")
        self.assertEqual(proposal["vme"]["id"], self.vme.id)
        self.assertEqual((proposal["lot"], proposal["lot_id"], proposal["topic"]), ("M2", self.m2.id, "Lek of waterschade"))
        self.assertEqual((proposal["confidence"], proposal["reason"]), ("hoog", "afzender is eigenaar van M2"))
        self.assertEqual(proposal["reply_subject"], "Re: waterlek")
        self.assertIn("We sturen vandaag een loodgieter.", proposal["reply_html"])
        self.assertNotIn("Er loopt water", proposal["reply_html"])
        self.assertFalse(self.Context._vme_mail_context("x@example.com", message_id="<ander@example.com>")["proposal"])
        # A request made afterwards from the pane has no AI reply: the proposal stays the activity's.
        self.Context._vme_mail_request(self.vme.id, "document", "eigenaar.m1@example.com", subject="waterlek",
                                       message_id=f"<{REFERENCE}>")
        self.assertEqual(self.Context._vme_mail_proposal(f"<{REFERENCE}>")["source"], "activity")

    def test_proposal_from_a_request(self):
        Request = self.env["vme.request"]
        request = Request.browse(Request.create_from_intake(
            self.vme.id, "document", "eigenaar.m1@example.com", subject="Kopie notulen", reference="doc-m1@example.com",
            proposed_reply="Beste eigenaar,\nU krijgt de notulen deze week."))
        proposal = self.Context._vme_mail_proposal("<doc-m1@example.com>")
        self.assertEqual(proposal["source"], "request")
        self.assertEqual(proposal["record"]["name"], request.display_name)
        self.assertIn("U krijgt de notulen deze week.", proposal["reply_html"])
        self.assertNotIn("Voorgesteld antwoord", proposal["reply_html"])

    # Filing the mail and making a request; nothing is sent

    def test_log_is_an_internal_note(self):
        self.vme.message_subscribe(partner_ids=self.other.ids)
        result = self.Context._vme_mail_log(
            "vme.association", self.vme.id, "Vraag", "eigenaar.m1@example.com", "Eigenaar Mail M1", "Regel 1\nRegel 2",
            attachments=[{"name": "foto.txt", "datas": "aGFsbG8=", "mimetype": "text/plain"}])
        message = self.env["mail.message"].browse(result["message_id"])
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(message.notified_partner_ids)
        self.assertIn("Regel 1<br>Regel 2", message.body)
        self.assertEqual(message.attachment_ids.mapped("name"), ["foto.txt"])
        with self.assertRaises(Exception):
            self.Context._vme_mail_log("res.partner", self.owner.id, "x", "a@example.com", "", "")

    def test_request_from_the_pane(self):
        result = self.Context._vme_mail_request(
            self.vme.id, "document", "eigenaar.m3@example.com", subject="Kopie basisakte", body="Graag een kopie.",
            message_id="<basisakte-m3@example.com>")
        request = self.env["vme.request"].browse(result["id"])
        self.assertEqual((request.channel, request.source_reference), ("mail", "basisakte-m3@example.com"))
        self.assertEqual((request.requester_id, request.lot_id), (self.other, self.m3))
        again = self.Context._vme_mail_request(self.vme.id, "document", "eigenaar.m3@example.com",
                                               message_id="<basisakte-m3@example.com>")
        self.assertEqual(again["id"], request.id)

    # Access

    def test_user_sees_only_the_vmes_of_his_companies(self):
        staff = new_test_user(self.env, login="medewerker.mail", groups="base.group_user,account.group_account_invoice",
                              company_id=self.vme.company_id.id, company_ids=self.vme.company_id.ids)
        matches = self.Context.with_user(staff)._vme_mail_context("eigenaar.m1@example.com")["matches"]
        self.assertEqual([m["vme"]["name"] for m in matches], ["Residentie Mail"])

    def test_auditor_reads_but_cannot_log_or_create(self):
        mandate = self.env["vme.mandate"].create({
            "association_id": self.vme.id, "role": "auditor", "date_start": fields.Date.today() - timedelta(days=30),
            "partner_id": self.env["res.partner"].create({"name": "Commissaris Mail", "email": "commissaris.mail@example.com"}).id,
        })
        mandate.action_grant_access()
        Context = self.Context.with_user(mandate.user_id)
        context = Context._vme_mail_context("eigenaar.m3@example.com")
        self.assertFalse(context["can_write"])
        self.assertEqual([m["lots"][0]["name"] for m in context["matches"]], ["M3"])
        # A tenant is recognised, but the auditor may not read the contact itself.
        [tenant_match] = Context._vme_mail_context("huurder.m3@example.com")["matches"]
        self.assertEqual((tenant_match["role"], tenant_match["partner"]["name"]), ("tenant", ""))
        # The other VME is not his.
        self.assertEqual([m["vme"]["name"] for m in Context._vme_mail_context("eigenaar.m1@example.com")["matches"]],
                         ["Residentie Mail"])
        with self.assertRaises(AccessError):
            Context._vme_mail_log("vme.association", self.vme.id, "Vraag", "eigenaar.m3@example.com", "", "tekst")
        with self.assertRaises(AccessError):
            Context._vme_mail_request(self.vme.id, "document", "eigenaar.m3@example.com", subject="x")
