from datetime import date

from psycopg2 import IntegrityError

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open, mute_logger


def _account(company, code):
    return company.env["account.account"].with_company(company).search(
        [("company_ids", "in", company.id), ("code", "=", code)], limit=1
    )


@tagged("post_install", "-at_install")
class TestDistributionRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Regels"})
        cls.env.cr.precommit.run()  # load the chart of accounts
        cls.company = cls.vme.company_id
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": name} for name in ("A1", "A2")
        ])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(cls.lots, (600, 400))],
        })
        cls.other_key = cls.env["vme.key"].create({
            "name": "Alleen A1", "association_id": cls.vme.id, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": cls.lots[0].id, "shares": 1000})],
        })
        Partner = cls.env["res.partner"]
        cls.owner, cls.seller, cls.buyer = Partner.create([{"name": n} for n in ("Eigenaar R1", "Verkoper R2", "Koper R2")])
        cls.env["vme.ownership"].create([
            {"lot_id": cls.lots[0].id, "partner_id": cls.owner.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.lots[1].id, "partner_id": cls.seller.id,
             "date_start": date(2015, 1, 1), "date_end": date(2026, 6, 30)},
            {"lot_id": cls.lots[1].id, "partner_id": cls.buyer.id, "date_start": date(2026, 7, 1)},
        ])
        cls.energy, cls.unknown = Partner.create([
            {"name": "Energie Regeltest", "is_company": True},
            {"name": "Leverancier zonder regel", "is_company": True},
        ])
        cls.electricity_account = _account(cls.company, "612500")
        cls.rule = cls.env["vme.distribution.rule"].create({
            "association_id": cls.vme.id,
            "partner_id": cls.energy.id,
            "key_id": cls.key.id,
            "account_id": cls.electricity_account.id,
        })

    def _bill(self, partner, price=1000, **line_vals):
        return self.env["account.move"].with_company(self.company).create({
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "invoice_date": date(2026, 12, 31),
            "vme_period_start": date(2026, 1, 1),
            "vme_period_end": date(2026, 12, 31),
            "invoice_line_ids": [Command.create({
                "name": "Elektriciteit", "quantity": 1, "price_unit": price,
                "tax_ids": [Command.clear()], **line_vals,
            })],
        })

    def test_rule_fills_key_and_account(self):
        line = self._bill(self.energy).invoice_line_ids
        self.assertEqual(line.vme_key_id, self.key)
        self.assertEqual(line.account_id, self.electricity_account)

    def test_manual_key_is_kept(self):
        line = self._bill(self.energy, vme_key_id=self.other_key.id).invoice_line_ids
        self.assertEqual(line.vme_key_id, self.other_key)

    def test_no_rule_no_key(self):
        line = self._bill(self.unknown).invoice_line_ids
        self.assertFalse(line.vme_key_id)
        self.assertNotEqual(line.account_id, self.electricity_account)

    def test_posting_distributes_automatically(self):
        bill = self._bill(self.energy)
        bill.action_post()
        allocations = bill.vme_allocation_ids
        self.assertEqual(round(sum(allocations.mapped("amount")), 2), 1000.0)
        # Lot A2 (400) sold on 30 June: 181 days seller, 184 days buyer.
        seller = allocations.filtered(lambda a: a.partner_id == self.seller)
        self.assertEqual(seller.amount, round(400 * 181 / 365, 2))
        self.assertIn("Automatisch verdeeld over 3 eigenaars", bill.message_ids[0].body)

    def test_posting_without_rule_does_not_distribute(self):
        bill = self._bill(self.unknown)
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.vme_allocation_ids)
        self.assertIn("Niet automatisch verdeeld", bill.message_ids[0].body)

    def test_failed_distribution_does_not_block_posting(self):
        lot = self.env["vme.lot"].create({"association_id": self.vme.id, "name": "A3"})
        key = self.env["vme.key"].create({
            "name": "Met lege kavel", "association_id": self.vme.id, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": self.lots[0].id, "shares": 900}),
                         Command.create({"lot_id": lot.id, "shares": 100})],
        })
        bill = self._bill(self.unknown, vme_key_id=key.id)
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.vme_allocation_ids)
        self.assertIn("Automatische verdeling mislukt", bill.message_ids[0].body)

    def test_key_without_lots_does_not_block_posting(self):
        key = self.env["vme.key"].create({"name": "Nog leeg", "association_id": self.vme.id, "total_shares": 1000})
        bill = self._bill(self.unknown, vme_key_id=key.id)
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.vme_allocation_ids)
        self.assertIn("geen kavels met een aandeel", bill.message_ids[0].body)

    def test_one_rule_per_supplier_and_vme(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["vme.distribution.rule"].create({
                "association_id": self.vme.id, "partner_id": self.energy.id, "key_id": self.other_key.id,
            })


@tagged("post_install", "-at_install")
class TestUblImport(TransactionCase):

    def test_import_peppol_invoice_residentie_linde(self):
        self.env["vme.association"]._load_demo_data()
        self.env.cr.precommit.run()
        linde = self.env["vme.association"].search([("name", "=", "Residentie Linde")])
        company = linde.company_id
        rule = linde.distribution_rule_ids.filtered(lambda r: r.partner_id.vat == "BE0000000394")
        self.assertEqual(rule.account_id, _account(company, "612500"))

        with file_open("vme_belgie/demo_data/facturen/elektriciteit_residentie_linde_2026.xml", "rb") as f:
            attachment = self.env["ir.attachment"].create({
                "name": "elektriciteit_residentie_linde_2026.xml", "raw": f.read(), "mimetype": "application/xml",
            })
        journal = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "purchase")], limit=1
        )
        bill = journal.with_company(company)._create_document_from_attachment(attachment.ids)

        self.assertEqual(len(bill), 1)
        self.assertEqual(bill.partner_id, rule.partner_id)
        self.assertEqual(bill.vme_association_id, linde)
        self.assertEqual((bill.vme_period_start, bill.vme_period_end), (date(2025, 11, 1), date(2026, 10, 31)))
        self.assertEqual(len(bill.invoice_line_ids), 2)
        self.assertEqual(bill.invoice_line_ids.vme_key_id, rule.key_id)
        self.assertEqual(bill.invoice_line_ids.account_id, rule.account_id)
        self.assertAlmostEqual(bill.amount_total, 5324.00, places=2)

        bill.action_post()
        allocations = bill.vme_allocation_ids
        self.assertAlmostEqual(sum(allocations.mapped("amount")), 5324.00, places=2)
        a5 = allocations.filtered(lambda a: a.lot_id.name == "A5")
        # Seller 01-11-2025..30-06-2026 = 242 days, buyer 01-07..31-10-2026 = 123 days (per line).
        self.assertEqual(sorted(set(a5.mapped("days"))), [123, 242])
