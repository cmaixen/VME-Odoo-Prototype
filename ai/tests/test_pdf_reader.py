"""PDF invoices and documents (step 21): demo files, mock, Claude request, scripts with a fake Odoo."""
import base64
import email
import email.policy
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import documenten
import pdf_facturen
import pdf_reader
from classifier import MODEL, RefusalError
from pdf_reader import (
    DOCUMENT_TYPES, READING_FIELDS, ClaudeDocumentClassifier, ClaudeInvoiceReader, MockDocumentClassifier,
    MockInvoiceReader,
)
from pdf_text import extract_text, write_pdf

HERE = Path(__file__).resolve().parent.parent
MODULE = HERE.parent / "addons" / "vme_belgie"
PDF_DIR = MODULE / "demo_data" / "facturen_pdf"
sys.path.insert(0, str(HERE / "tools"))
import maak_demo_pdfs  # noqa: E402

INVOICES = {inv["file"]: inv for inv in maak_demo_pdfs.INVOICES}


# --- demo files -------------------------------------------------------------

def test_pdf_text_round_trip():
    pdf = write_pdf([(50, 700, 10, False, "Prijs (incl.) 1.240,00 € – a\\b"), ("line", 0, 0, 10, 10),
                     (50, 680, 10, True, "Tweede regel")])
    assert extract_text(pdf) == ["Prijs (incl.) 1.240,00 € – a\\b", "Tweede regel"]
    assert extract_text(write_pdf([(1, 1, 9, False, "Zonder compressie")], compress=False)) == ["Zonder compressie"]


def test_demo_files_are_up_to_date():
    """The committed PDFs, mails and documents are exactly what the generator makes."""
    for index, inv in enumerate(maak_demo_pdfs.INVOICES, 1):
        pdf = write_pdf(maak_demo_pdfs.invoice_items(inv))
        assert (PDF_DIR / inv["file"]).read_bytes() == pdf
        mail_path = HERE / "facturen_pdf_inbox" / f"{index:02d}_{inv['file'].removesuffix('.pdf')}.eml"
        message = email.message_from_string(mail_path.read_text(encoding="utf-8"), policy=email.policy.default)
        assert str(message["To"]).endswith("@syndicus.example.com")
        [attachment] = list(message.iter_attachments())
        assert attachment.get_content_type() == "application/pdf"
        assert attachment.get_content() == pdf
    for doc in maak_demo_pdfs.DOCUMENTS:
        assert (HERE / "documenten_inbox" / doc["file"]).exists()


def test_same_codes_as_the_odoo_module():
    """The script and the module must agree on the field codes and document kinds."""
    odoo_fields = (MODULE / "models" / "account_move_ai.py").read_text()
    assert re.findall(r'\("(\w+)", "[^"]+"\),', odoo_fields.split("READING_LABELS")[0]) == [c for c, _l in READING_FIELDS]
    odoo_types = (MODULE / "models" / "vme_document_intake.py").read_text()
    assert set(re.findall(r'^    "(\w+)": \(', odoo_types, re.M)) == set(DOCUMENT_TYPES)


# --- mock -------------------------------------------------------------------

@pytest.mark.parametrize("name", list(INVOICES))
def test_mock_reads_every_field_of_the_demo_invoices(name):
    inv = INVOICES[name]
    reading, model = MockInvoiceReader().read((PDF_DIR / name).read_bytes(), name)
    assert model == "mock"
    assert set(reading) == {code for code, _label in READING_FIELDS}
    for code in ("supplier_name", "supplier_vat", "invoice_number", "invoice_date", "due_date", "period_start",
                 "period_end", "description", "amount_untaxed", "amount_tax", "amount_total", "iban"):
        assert reading[code]["value"] == inv[code], code
    assert reading["currency"]["value"] == "EUR"
    assert reading["customer_name"]["value"] == maak_demo_pdfs.VMES[inv["vme"]][0]
    # A field that is not on the invoice is None with low confidence, never a guess.
    if inv["period_start"] is None:
        assert reading["period_start"] == {"value": None, "confidence": "low"}


def test_mock_on_an_unreadable_pdf_reads_nothing():
    reading, _model = MockInvoiceReader().read(b"%PDF-1.4 scan zonder tekst")
    assert all(item == {"value": None, "confidence": "low"} for item in reading.values())


def test_mock_classifies_the_demo_documents(vmes):
    classifier = MockDocumentClassifier(vmes)
    for doc in maak_demo_pdfs.DOCUMENTS:
        result, _model = classifier.classify((HERE / "documenten_inbox" / doc["file"]).read_bytes(), doc["file"])
        assert result["document_type"] == doc["document_type"]
        assert next(v["name"] for v in vmes if v["id"] == result["association_id"]) == doc["vme"]


def test_document_without_known_building(vmes):
    pdf = write_pdf([(50, 700, 10, False, "Offerte voor een gebouw dat we niet kennen")])
    result, _model = MockDocumentClassifier(vmes).classify(pdf)
    assert result["association_id"] is None and result["confidence"] == "low"


# --- Claude -------------------------------------------------------------------

class FakeClient:
    def __init__(self, answer, stop_reason="end_turn"):
        self.calls = []
        self.answer = answer
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop_reason, model=MODEL,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def test_claude_reader_sends_the_pdf_with_the_schema():
    pdf = (PDF_DIR / "dakgoot_kaaihuis_2026-10.pdf").read_bytes()
    answer = {code: {"value": None, "confidence": "low"} for code, _label in READING_FIELDS}
    answer["iban"] = {"value": "BE53 9990 0090 0453", "confidence": "high"}
    answer["supplier_vat"] = {"value": "", "confidence": "high"}  # empty is "not read"
    client = FakeClient(answer)
    reading, model = ClaudeInvoiceReader(client=client).read(pdf, "x.pdf")

    assert model == MODEL
    assert reading["iban"] == {"value": "BE53 9990 0090 0453", "confidence": "high"}  # Odoo normalizes
    assert reading["supplier_vat"] == {"value": None, "confidence": "low"}
    [call] = client.calls
    assert call["model"] == MODEL
    document, instruction = call["messages"][0]["content"]
    assert document["type"] == "document" and document["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(document["source"]["data"]) == pdf
    assert instruction["type"] == "text"
    assert call["output_config"]["format"]["schema"] == pdf_reader.INVOICE_SCHEMA
    assert set(pdf_reader.INVOICE_SCHEMA["required"]) == {code for code, _label in READING_FIELDS}
    assert call["fallbacks"] == "default"


def test_claude_refusal():
    client = FakeClient({}, stop_reason="refusal")
    with pytest.raises(RefusalError):
        ClaudeInvoiceReader(client=client).read(b"%PDF", "x.pdf")


def test_claude_document_classifier_keeps_only_known_vmes(vmes):
    client = FakeClient({"association_id": 99, "document_type": "quote", "confidence": "high",
                         "summary": "Offerte", "reason": "Gok."})
    classifier = ClaudeDocumentClassifier(vmes, client=client)
    result, _model = classifier.classify(b"%PDF", "x.pdf")
    assert result["association_id"] is None and result["confidence"] == "low"
    system = client.calls[0]["system"][0]
    assert system["cache_control"] == {"type": "ephemeral"} and "Residentie Linde" in system["text"]
    assert "lots" not in system["text"]  # only id, name and address of the VME's


def test_claude_reader_with_real_sdk():
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")
    seen = {}
    answer = {code: {"value": None, "confidence": "low"} for code, _label in READING_FIELDS}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": MODEL,
            "content": [{"type": "text", "text": json.dumps(answer)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    client = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    reading, _model = ClaudeInvoiceReader(client=client).read(b"%PDF-1.4", "x.pdf")
    assert reading["iban"]["value"] is None
    assert seen["body"]["messages"][0]["content"][0]["type"] == "document"


# --- pdf_facturen.run with a fake Odoo ----------------------------------------------

class FakeOdoo:
    uid = 2

    def __init__(self, bills, pdf):
        self.bills = bills
        self.pdf = pdf
        self.applied = []

    def execute(self, model, method, *args, **kwargs):
        if model == "res.users":
            return [{"id": 2, "company_ids": [1, 2, 3, 4]}]
        if (model, method) == ("account.move", "search_read"):
            assert ("vme_ai_state", "=", "to_read") in args[0]
            assert kwargs["context"] == {"allowed_company_ids": [1, 2, 3, 4]}
            return self.bills
        if (model, method) == ("ir.attachment", "search_read"):
            return [{"id": 50, "name": "factuur.pdf", "datas": base64.b64encode(self.pdf).decode()}]
        if (model, method) == ("account.move", "vme_ai_apply_reading"):
            ids, reading, model_name = args
            self.applied.append((ids, reading, model_name))
            return {"move_id": ids[0], "partner": "Energieleverancier Voorbeeld NV", "ref": "EV-2026-110412",
                    "amount_total": 375.10, "keys": ["Algemene sleutel"], "danger": 1, "warning": 0,
                    "checks": [{"field": "IBAN", "value": reading["iban"]["value"], "confidence": "high",
                                "status": "danger", "message": "Ander IBAN dan de bevestigde rekening."}]}
        raise AssertionError((model, method))


BILL = {"id": 7, "name": "/", "company_id": [3, "Hof ter Beuken"],
        "invoice_source_email": "facturen@energieleverancier.example.com", "message_main_attachment_id": [50, "x"]}


def test_run_reads_and_hands_the_fields_to_odoo():
    pdf = (PDF_DIR / "elektriciteit_hof_ter_beuken_2026-10.pdf").read_bytes()
    odoo = FakeOdoo([BILL], pdf)
    lines = []
    results = pdf_facturen.run(odoo, MockInvoiceReader(), out=lines.append)

    [(ids, reading, model_name)] = odoo.applied
    assert ids == [7] and model_name == "mock"
    assert reading["iban"]["value"] == "BE64999000900352"
    assert results[7]["danger"] == 1
    assert any("GEVAAR IBAN" in line for line in lines)


def test_run_dry_run_writes_nothing():
    odoo = FakeOdoo([BILL], (PDF_DIR / "dakgoot_kaaihuis_2026-10.pdf").read_bytes())
    lines = []
    pdf_facturen.run(odoo, MockInvoiceReader(), dry_run=True, out=lines.append)
    assert odoo.applied == []
    assert any("DW-26-077" in line for line in lines)


def test_run_skips_a_refused_pdf():
    class Refusing:
        def read(self, pdf_bytes, name):
            raise RefusalError("Het taalmodel weigerde factuur.pdf.")

    odoo = FakeOdoo([BILL], b"%PDF")
    lines = []
    assert pdf_facturen.run(odoo, Refusing(), out=lines.append) == {7: None}
    assert odoo.applied == [] and any("manueel" in line for line in lines)


def test_main_reads_a_single_file_without_odoo(capsys, monkeypatch):
    monkeypatch.setattr(pdf_facturen, "connect", lambda: pytest.fail("Odoo mag niet aangesproken worden"))
    assert pdf_facturen.main(["--mock", "--bestand", str(PDF_DIR / "lift_onderhoud_residentie_linde_2026-q4.pdf")]) == 0
    assert "LO-2026-0412" in capsys.readouterr().out


def test_main_without_api_key_stops(capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(pdf_facturen, "load_env", lambda path: None)
    assert pdf_facturen.main([]) == 2
    assert "--mock" in capsys.readouterr().out


# --- documenten.run ---------------------------------------------------------------

class FakeDocumentOdoo:
    def __init__(self):
        self.received = []

    def execute(self, model, method, *args, **kwargs):
        assert (model, method) == ("vme.association", "vme_receive_document")
        ids, filename, datas, document_type, confidence, reason, model_name = args
        duplicate = any(r[1] == datas for r in self.received)
        self.received.append((ids, datas, document_type))
        return {"attachment_id": len(self.received), "duplicate": duplicate, "folder": False}


def test_documents_go_to_the_right_vme(vmes):
    odoo = FakeDocumentOdoo()
    docs = documenten.read_documents(HERE / "documenten_inbox")
    lines = []
    documenten.run(docs, MockDocumentClassifier(vmes), vmes, odoo=odoo, out=lines.append)
    by_type = {document_type: ids[0] for ids, _datas, document_type in odoo.received}
    assert by_type == {"inspection_report": 1, "insurance_policy": 2, "quote": 3}
    assert sum("nog geen" in line for line in lines) == 3

    documenten.run(docs, MockDocumentClassifier(vmes), vmes, odoo=odoo, out=lines.append)
    assert sum("Stond al" in line for line in lines) == 3


def test_documents_dry_run_and_unknown_vme(vmes, tmp_path):
    (tmp_path / "onbekend.pdf").write_bytes(write_pdf([(50, 700, 10, False, "Keuringsverslag ergens anders")]))
    odoo = FakeDocumentOdoo()
    lines = []
    documenten.run(documenten.read_documents(tmp_path), MockDocumentClassifier(vmes), vmes, odoo=odoo,
                   out=lines.append)
    documenten.run(documenten.read_documents(HERE / "documenten_inbox"), MockDocumentClassifier(vmes), vmes,
                   odoo=odoo, dry_run=True, out=lines.append)
    assert odoo.received == []
    assert any("klasseer dit document manueel" in line for line in lines)
