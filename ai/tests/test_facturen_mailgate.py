import email
import email.policy
from pathlib import Path

import facturen_mailgate
from odoo_api import OdooError

HERE = Path(__file__).resolve().parent.parent
INBOX = HERE / "facturen_inbox"
UBL_DIR = HERE.parent / "addons" / "vme_belgie" / "demo_data" / "facturen"

EXPECTED = {
    "01_elektriciteit_residentie_linde.eml": ("facturen-residentie-linde@syndicus.example.com", "elektriciteit_residentie_linde_2026.xml"),
    "02_elektriciteit_hof_ter_beuken.eml": ("facturen-hof-ter-beuken@syndicus.example.com", "elektriciteit_hof_ter_beuken_2026.xml"),
    "03_elektriciteit_kaaihuis.eml": ("facturen-kaaihuis@syndicus.example.com", "elektriciteit_kaaihuis_2026.xml"),
}


def test_three_fictitious_bill_mails():
    mails = facturen_mailgate.read_mails(INBOX)
    assert [path.name for path, _raw in mails] == list(EXPECTED)
    for path, raw in mails:
        message = email.message_from_string(raw, policy=email.policy.default)
        to, attachment_name = EXPECTED[path.name]
        assert str(message["To"]) == to
        assert str(message["From"]).endswith("@energieleverancier.example.com>")
        assert message["Message-ID"]
        [attachment] = list(message.iter_attachments())
        assert attachment.get_filename() == attachment_name
        # The attachment is exactly the demo UBL invoice of the module, so they cannot drift apart.
        assert attachment.get_content() == (UBL_DIR / attachment_name).read_bytes()


class FakeOdoo:
    """Records gateway calls; answers reads for the summary line."""

    uid = 2

    def __init__(self, fail_on=None):
        self.processed = []
        self.fail_on = fail_on

    def execute(self, model, method, *args, **kwargs):
        if model == "res.users":
            return [{"id": 2, "company_ids": [1, 2, 3, 4]}]
        if method == "message_process":
            raw = args[1]
            if self.fail_on and self.fail_on in raw:
                raise OdooError("No possible route found for incoming message")
            self.processed.append(raw)
            return len(self.processed)
        if model == "account.move":
            return [{
                "company_id": [4, "Kaaihuis"], "partner_id": [9, "Energieleverancier Voorbeeld NV"],
                "ref": "EV-2026-110303", "amount_total": 1500.4, "state": "draft",
                "vme_period_start": "2025-11-01", "vme_period_end": "2026-10-31", "invoice_line_ids": [7],
            }]
        if model == "account.move.line":
            return [{"id": 7, "vme_key_id": [5, "Algemene sleutel"]}]
        raise AssertionError((model, method))


def test_run_hands_each_raw_mail_to_the_gateway():
    odoo = FakeOdoo()
    mails = facturen_mailgate.read_mails(INBOX)
    lines = []
    results = facturen_mailgate.run(odoo, mails, out=lines.append)
    assert odoo.processed == [raw for _path, raw in mails]
    assert results == {name: index for index, name in enumerate(EXPECTED, 1)}
    assert any("conceptfactuur EV-2026-110303" in line and "Algemene sleutel" in line for line in lines)


def test_dry_run_delivers_nothing():
    lines = []
    facturen_mailgate.run(None, facturen_mailgate.read_mails(INBOX), dry_run=True, out=lines.append)
    assert len(lines) == 3 and all("bijlagen: elektriciteit_" in line for line in lines)


def test_unroutable_mail_is_reported_and_skipped():
    odoo = FakeOdoo(fail_on="facturen-kaaihuis@")
    lines = []
    results = facturen_mailgate.run(odoo, facturen_mailgate.read_mails(INBOX), out=lines.append)
    assert results["03_elektriciteit_kaaihuis.eml"] is None
    assert len(odoo.processed) == 2
    assert any("Niet verwerkt" in line for line in lines)


def test_already_processed_mail():
    class AlreadySeen(FakeOdoo):
        def execute(self, model, method, *args, **kwargs):
            if method == "message_process":
                return False  # Odoo ignores a Message-ID it already processed
            return super().execute(model, method, *args, **kwargs)

    lines = []
    results = facturen_mailgate.run(AlreadySeen(), facturen_mailgate.read_mails(INBOX), out=lines.append)
    assert set(results.values()) == {None}
    assert sum("Al eerder verwerkt" in line for line in lines) == 3
