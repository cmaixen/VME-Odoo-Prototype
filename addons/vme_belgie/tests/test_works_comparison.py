import base64
from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)
PDF = base64.b64encode(b"%PDF-1.4\n% fictieve offerte\n%%EOF\n")


def _value(value, page=1):
    return {"value": value, "page": page if value else None}


def _quote(contractor, untaxed, rate, total, reservations=(), insurance="ABR en BA"):
    """One quote as ai/offerte_reader.py hands it over."""
    return {
        "contractor": _value(contractor), "reference": _value("REF-1"), "date": _value("2026-10-01"),
        "amount_untaxed": _value(untaxed, 2), "vat_rate": _value(rate, 2), "amount_total": _value(total, 2),
        "execution_period": _value("8 werkweken", 3), "validity": _value("60 dagen", 3),
        "payment_terms": _value("30 dagen", 3), "warranty": _value("10 jaar", 3), "insurance": _value(insurance, 3),
        "reservations": [{"text": text, "page": 3} for text in reservations],
    }


def _post(label, *items):
    return {"label": label, "items": [
        {"quote": number, "status": status, "amount": amount, "description": description, "page": page}
        for number, (status, amount, description, page) in enumerate(items, 1)]}


PAYLOAD = {
    "quotes": [
        _quote("Gevel Een BV", "45800.00", "6", "48548.00", ["Betonschade in regie."]),
        _quote("Gevel Twee NV", "34850.00", "6", "36941.00", ["ABEX-herziening na 31/12/2026."], insurance=None),
        _quote("Gevel Drie BV", "44000.00", "21", "53240.00"),
    ],
    "posts": [
        _post("Stelling", ("included", "9400.00", "Stelling", 1), ("excluded", None, "Stelling: door een derde", 2),
              ("included", "10250.00", "Steigerwerken", 1)),
        _post("Voegwerk", ("included", "14200.00", "Voegwerk", 1), ("included", "13600.00", "Voegen", 1),
              ("included", "15100.00", "Voegen", 2)),
        _post("Waterafstotende behandeling", ("included", "4100.00", "Hydrofuge", 2),
              ("included", "3800.00", "Hydrofuge", 1), ("absent", None, None, None)),
    ],
    "summary": "De offertes liggen tussen 36.941,00 en 53.240,00 EUR incl. btw. Gevel Twee rekent de stelling niet "
               "mee; Gevel Drie rekent 21% btw.",
}


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestWorksComparison(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({
            "name": "Residentie Vergelijking", "assembly_period_month": "3", "assembly_period_day": 10})
        cls.env.cr.precommit.run()
        lot = cls.env["vme.lot"].create({"association_id": cls.vme.id, "name": "A1"})
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 1000})]})
        cls.owner = cls.env["res.partner"].create({"name": "Eigenaar Vergelijking A1"})
        cls.env["vme.ownership"].create({"lot_id": lot.id, "partner_id": cls.owner.id, "date_start": date(2015, 1, 1)})
        cls.contractors = cls.env["res.partner"].create([
            {"name": name, "is_company": True} for name in ("Gevel Een BV", "Gevel Twee NV", "Gevel Drie BV")])
        cls.works = cls.env["vme.works"].create({
            "association_id": cls.vme.id, "name": "Gevelrenovatie", "budget": 50000,
            "user_id": cls.env.ref("base.user_admin").id})
        cls.works.action_request_quotes()
        # The third amount is entered without VAT by mistake.
        cls.works.quote_ids = [Command.create({
            "partner_id": partner.id, "reference": f"REF-{index}", "amount": amount,
            "attachment_ids": [Command.create({"name": f"offerte_{index}.pdf", "datas": PDF,
                                               "mimetype": "application/pdf"})],
        }) for index, (partner, amount) in enumerate(zip(cls.contractors, (48548, 36941, 44000)), 1)]

    def _requested(self):
        action = self.works.action_compare_quotes()
        return self.env["vme.works.comparison"].browse(action["res_id"])

    def _read(self, payload=None, model="test-model"):
        comparison = self._requested()
        comparison.vme_ai_apply_comparison(payload or PAYLOAD, model)
        return comparison

    def _line(self, comparison, name):
        return comparison.line_ids.filtered(lambda line: line.name == name)

    def test_request_needs_two_to_four_pdfs(self):
        comparison = self._requested()
        self.assertEqual(comparison.state, "to_read")
        self.assertEqual(comparison.column_ids.sorted("sequence").partner_id, self.works.quote_ids.partner_id)
        self.assertTrue(all(c.attachment_id.mimetype == "application/pdf" for c in comparison.column_ids))
        # Asking again reuses the comparison that is not approved yet.
        self.assertEqual(self._requested(), comparison)
        self.assertEqual(self.works.comparison_count, 1)
        self.works.quote_ids[1:].attachment_ids.unlink()
        with self.assertRaises(UserError):
            self.works.action_compare_quotes()

    def test_reading_builds_a_draft_table_with_pages(self):
        comparison = self._read()
        self.assertEqual(comparison.state, "draft")
        self.assertEqual(comparison.ai_model, "test-model")
        self.assertEqual(comparison.line_ids.mapped("section")[:3], ["price", "price", "price"])
        self.assertEqual(set(comparison.line_ids.mapped("section")),
                         {"price", "posts", "terms", "guarantee", "reservations"})
        columns = comparison.column_ids.sorted("sequence")
        self.assertEqual(columns.mapped("vat_rate"), [6, 6, 21])
        self.assertEqual(columns.mapped("amount_total"), [48548, 36941, 53240])
        total = self._line(comparison, "Totaal incl. btw")
        self.assertEqual((total.page_1, total.page_2, total.page_3), (2, 2, 2))
        self.assertIn("53.240,00", total.value_3)
        # Scaffolding excluded by one quote and water repellent not mentioned by another: missing.
        scaffolding = self._line(comparison, "Stelling")
        self.assertEqual((scaffolding.status_1, scaffolding.status_2, scaffolding.status_3), ("ok", "missing", "ok"))
        self.assertIn("door een derde", scaffolding.value_2)
        repellent = self._line(comparison, "Waterafstotende behandeling")
        self.assertEqual((repellent.status_3, repellent.value_3, repellent.page_3), ("missing", "Niet vermeld", 0))
        # The 21% rate is marked next to the 6% of the others.
        rate = self._line(comparison, "Btw-tarief")
        self.assertEqual((rate.status_1, rate.status_3), ("ok", "attention"))
        insurance = self._line(comparison, "Verzekering")
        self.assertEqual((insurance.status_2, insurance.value_2), ("empty", False))
        self.assertIn("(p. 3)", self._line(comparison, "Voorbehouden").value_1)
        self.assertIn("Gevel Drie BV", comparison.table_html)
        # The works get a task to review it; nothing else happens.
        self.assertIn("Offertevergelijking nakijken", self.works.activity_ids.mapped("summary"))

    def test_checks_flag_rate_amount_and_missing_posts(self):
        comparison = self._read()
        attention = comparison.attention
        self.assertIn("btw-tarief verschilt", attention)
        self.assertIn("in het werkdossier staat", attention)  # 44.000 entered, 53.240 in the quote
        self.assertIn("Stelling ontbreekt in de offerte van Gevel Twee NV", attention)
        self.assertIn("Waterafstotende behandeling ontbreekt in de offerte van Gevel Drie BV", attention)
        self.assertNotIn("aanbeveling", attention)
        self.assertNotIn("zonder bronpagina", attention)
        # Correcting the amount in the works removes that point.
        self.works.quote_ids.filtered(lambda q: q.partner_id == self.contractors[2]).amount = 53240
        comparison.invalidate_recordset(["attention"])
        self.assertNotIn("in het werkdossier staat", comparison.attention)

    def test_checks_total_page_and_recommendation(self):
        payload = {**PAYLOAD, "quotes": [dict(q) for q in PAYLOAD["quotes"]],
                   "summary": "Wij raden de offerte van Gevel Een aan: de beste keuze."}
        payload["quotes"][0]["amount_total"] = _value("49999.00", None)
        comparison = self._read(payload)
        self.assertIn("is niet het totaal", comparison.attention)
        self.assertIn("1 waarde(n) zonder bronpagina", comparison.attention)
        self.assertIn("aanbeveling", comparison.attention)
        comparison.summary = "De offertes verschillen in prijs en in wat inbegrepen is."
        self.assertNotIn("aanbeveling", comparison.attention)

    def test_reading_only_once_and_with_every_quote(self):
        comparison = self._requested()
        with self.assertRaises(UserError):
            comparison.vme_ai_apply_comparison({**PAYLOAD, "quotes": PAYLOAD["quotes"][:2]}, "test-model")
        comparison.vme_ai_apply_comparison(PAYLOAD, "test-model")
        with self.assertRaises(UserError):
            comparison.vme_ai_apply_comparison(PAYLOAD, "test-model")
        # Read again: back to waiting, the next reading rebuilds the table.
        comparison.action_read_again()
        self.assertEqual(comparison.state, "to_read")
        comparison.vme_ai_apply_comparison(PAYLOAD, "test-model")
        self.assertEqual(len(comparison.line_ids.filtered(lambda line: line.name == "Stelling")), 1)

    def test_approve_makes_the_pdf_and_locks_the_table(self):
        comparison = self._read()
        comparison.summary = False
        with self.assertRaises(UserError):
            comparison.action_approve()
        comparison.summary = PAYLOAD["summary"]
        self._line(comparison, "Uitvoeringstermijn").value_2 = "7 werkweken na de stelling"
        comparison.action_approve()
        self.assertEqual(comparison.state, "approved")
        self.assertEqual(comparison.approved_by_id, self.env.user)
        attachment = comparison.report_attachment_id
        self.assertEqual((attachment.res_model, attachment.res_id), ("vme.works", self.works.id))
        # Tests render the report as HTML (no wkhtmltopdf): check its content.
        self.assertEqual(attachment.mimetype, "application/pdf")
        self.assertIn(b"7 werkweken na de stelling", attachment.raw)
        self.assertIn(b"geen aanbeveling", attachment.raw)
        self.assertNotIn("Offertevergelijking nakijken", self.works.activity_ids.mapped("summary"))
        with self.assertRaises(UserError):
            comparison.line_ids[:1].value_1 = "Gewijzigd"
        # Nothing was sent: no mail for the contractors or the owners (only staff get notified).
        outside = self.contractors | self.owner
        self.assertFalse(self.env["mail.mail"].search([]).filtered(lambda m: m.recipient_ids & outside))
        self.assertFalse(self.env["mail.message"].search([("model", "=", "vme.works"), ("res_id", "=", self.works.id),
                                                          ("partner_ids", "in", outside.ids)]))
        comparison.action_reset_draft()
        comparison.line_ids[:1].value_1 = "Gewijzigd"
        # A new request after approval starts a new comparison.
        comparison.action_approve()
        self.assertNotEqual(self._requested(), comparison)

    def test_approved_comparison_goes_with_the_convocation(self):
        room = self.env["vme.assembly.room"].create({"name": "Zaal Vergelijking"})
        slot = self.env["vme.assembly.slot"].create({
            "date": date(2027, 3, 20), "time_start": 19.0, "room_id": room.id,
            "user_id": self.env.ref("base.user_admin").id})
        assembly = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2027, "slot_id": slot.id})
        assembly.action_confirm()
        comparison = self._read()
        comparison.assembly_id = assembly
        comparison.action_approve()
        assembly.action_create_convocations()
        convocation = assembly.convocation_ids
        self.assertEqual(len(convocation), 1)
        self.assertIn(f"{comparison.name}.pdf", convocation.attachment_ids.mapped("name"))
        self.assertEqual(convocation.state, "draft")
