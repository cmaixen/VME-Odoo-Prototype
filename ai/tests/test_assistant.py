import base64
import io
import json
from datetime import date
from types import SimpleNamespace

import pytest

import odoo_api
from assistant import run
from classifier import (
    MODEL, RESULT_SCHEMA, Classification, ClaudeClassifier, MockClassifier, RefusalError, validate,
)
from conftest import INBOX
from mails import read_inbox, read_mail

TODAY = date(2026, 11, 5)

# Expected VME id, lot name and topic per test mail in ai/inbox/.
EXPECTED = {
    "01_lek_badkamer.eml": (1, "A4", "leak", "high"),
    "02_vraag_afrekening.eml": (2, "B7", "statement", "normal"),
    "03_verhuis_verkoop.eml": (3, "K4", "move", "normal"),
    "04_klacht_lift.eml": (1, "A11", "elevator", "high"),
    "05_vraag_av.txt": (2, "B23", "general_meeting", "normal"),
    "06_badge_eigenaar.eml": (1, "A4", "other", "normal"),
    "07_sleutel_huurder.eml": (1, "A6", "other", "normal"),
    "08_badge_huurder_toestemming.eml": (2, "B12", "other", "normal"),
}
# Mails that are a request with a fixed procedure in Odoo, and their type; the others are "none".
EXPECTED_REQUESTS = {
    "06_badge_eigenaar.eml": "key",
    "07_sleutel_huurder.eml": "key",
    "08_badge_huurder_toestemming.eml": "key",
}


def lot_names(vmes):
    return {lot["id"]: lot["name"] for vme in vmes for lot in vme["lots"]}


# --- Reading mails ---------------------------------------------------------------------

def test_inbox_has_eight_fictitious_mails():
    mails = read_inbox(INBOX)
    assert [m.path.name for m in mails] == list(EXPECTED)
    for mail in mails:
        assert mail.sender_email.endswith("@example.com")
        assert mail.subject and mail.body and mail.message_id


def test_read_eml():
    mail = read_mail(INBOX / "01_lek_badkamer.eml")
    assert mail.sender_name == "Eigenaar Linde A4"
    assert mail.sender_email == "eigenaar.linde.a4@example.com"
    assert mail.subject.startswith("Dringend")
    assert mail.reference == "lek-a4-20261102@example.com"
    assert "badkamer" in mail.body
    assert mail.attachments == []


def test_read_eml_with_attachments():
    mail = read_mail(INBOX / "08_badge_huurder_toestemming.eml")
    assert mail.sender_email == "huurder.beuken.b12@example.com"
    assert "toestemming van de eigenaar" in mail.body
    assert [(name, mimetype) for name, _content, mimetype in mail.attachments] == [
        ("toestemming_eigenaar_B12.pdf", "application/pdf"), ("huurcontract_B12.pdf", "application/pdf"),
    ]
    assert all(content.startswith(b"%PDF") for _name, content, _mimetype in mail.attachments)


def test_read_txt_with_dutch_headers():
    mail = read_mail(INBOX / "05_vraag_av.txt")
    assert mail.sender_email == "eigenaar.beuken.b23@example.com"
    assert mail.subject == "Wanneer is de volgende algemene vergadering?"
    assert mail.body.startswith("Beste,")


def test_read_txt_without_headers(tmp_path):
    path = tmp_path / "kort.txt"
    path.write_text("Mijn brievenbus is kapot.\nGroeten", encoding="utf-8")
    mail = read_mail(path)
    assert mail.sender_email == ""
    assert mail.body == "Mijn brievenbus is kapot.\nGroeten"
    assert mail.reference == "kort.txt"


# --- Mock classifier -------------------------------------------------------------------

@pytest.mark.parametrize("filename", list(EXPECTED))
def test_mock_links_each_mail(vmes, filename):
    result = MockClassifier(vmes).classify(read_mail(INBOX / filename))
    vme_id, lot, topic, urgency = EXPECTED[filename]
    assert result.association_id == vme_id
    assert lot_names(vmes)[result.lot_id] == lot
    assert (result.topic, result.urgency) == (topic, urgency)
    assert result.request_type == EXPECTED_REQUESTS.get(filename, "none")
    assert result.reply_body.startswith("Beste ")


def test_mock_recognises_a_tenant(vmes):
    result = MockClassifier(vmes).classify(read_mail(INBOX / "07_sleutel_huurder.eml"))
    assert "huurder van kavel A6" in result.matching_reason


@pytest.mark.parametrize("text, request_type", [
    ("Ik ben mijn badge verloren op de parking.", "badge_lost"),
    ("Mag ik een extra afstandsbediening voor de garage bestellen?", "key"),
    ("Ik meld u een nieuwe huurder vanaf 1 december.", "new_tenant"),
    ("Mag ik een buitenunit van een airco op mijn terras plaatsen? Ik vraag toestemming.", "works_permission"),
    ("Er is elke nacht lawaai bij de buren.", "nuisance"),
    ("Kunt u mij een kopie van de notulen van de laatste AV bezorgen?", "document"),
    ("Wanneer komt de afrekening?", "none"),
])
def test_mock_request_types(vmes, tmp_path, text, request_type):
    path = tmp_path / "aanvraag.txt"
    path.write_text(f"Van: eigenaar.linde.a4@example.com\nOnderwerp: Vraag\n\n{text}", encoding="utf-8")
    assert MockClassifier(vmes).classify(read_mail(path)).request_type == request_type


def test_mock_unknown_sender_found_by_building_name(vmes):
    # Mail 04 comes from a private address that is not in Odoo.
    result = MockClassifier(vmes).classify(read_mail(INBOX / "04_klacht_lift.eml"))
    assert "Afzender onbekend" in result.matching_reason
    assert result.owner_id == 103


def test_mock_without_any_match(vmes, tmp_path):
    path = tmp_path / "vreemd.txt"
    path.write_text("Van: iemand@example.com\nOnderwerp: Vraag\n\nHebt u een folder?", encoding="utf-8")
    result = MockClassifier(vmes).classify(read_mail(path))
    assert result.association_id is None and result.lot_id is None
    assert result.confidence == "low"


# --- Validation of model output ----------------------------------------------------------

def make_result(**values):
    data = {
        "association_id": 1, "lot_id": 11, "owner_id": 101, "topic": "leak", "urgency": "high",
        "confidence": "high", "summary": "s", "matching_reason": "r", "reply_subject": "Re", "reply_body": "b",
    }
    data.update(values)
    return Classification.from_dict(data)


def test_validate_drops_unknown_vme(vmes):
    result = validate(make_result(association_id=99), vmes)
    assert (result.association_id, result.lot_id, result.owner_id) == (None, None, None)
    assert result.confidence == "low"


def test_validate_drops_lot_of_other_vme(vmes):
    result = validate(make_result(association_id=1, lot_id=21), vmes)
    assert result.association_id == 1
    assert result.lot_id is None
    assert result.confidence == "low"


def test_validate_drops_unknown_request_type(vmes):
    assert validate(make_result(request_type="parking"), vmes).request_type == "none"
    assert validate(make_result(request_type="key"), vmes).request_type == "key"


def test_validate_keeps_correct_ids(vmes):
    result = validate(make_result(), vmes)
    assert (result.association_id, result.lot_id, result.owner_id, result.confidence) == (1, 11, 101, "high")


# --- Claude classifier with a fake Anthropic client ------------------------------------------

class FakeMessages:
    def __init__(self, payload, stop_reason="end_turn"):
        self.payload = payload
        self.stop_reason = stop_reason
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            model=kwargs["model"],
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=json.dumps(self.payload)),
            ],
        )


def fake_client(payload, stop_reason="end_turn"):
    messages = FakeMessages(payload, stop_reason)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_claude_request_and_result(vmes):
    payload = {
        "association_id": 1, "lot_id": 13, "owner_id": 103, "topic": "elevator", "urgency": "high",
        "confidence": "medium", "summary": "Lift staat stil.", "matching_reason": "Noemt A11.",
        "reply_subject": "Re: Lift alweer defect", "reply_body": "Beste Eigenaar Linde A11, ...",
    }
    client, messages = fake_client(payload)
    result = ClaudeClassifier(vmes, client=client).classify(read_mail(INBOX / "04_klacht_lift.eml"))

    assert result.lot_id == 13 and result.topic == "elevator" and result.model == MODEL
    request = messages.calls[0]
    assert request["model"] == MODEL
    assert request["output_config"]["format"] == {"type": "json_schema", "schema": RESULT_SCHEMA}
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]
    # The directory sits in the cached system prompt; the mail is the only user message.
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "Residentie Linde" in request["system"][0]["text"]
    assert "a11.prive@example.com" in request["messages"][0]["content"]


def test_claude_output_is_validated(vmes):
    payload = {
        "association_id": 3, "lot_id": 11, "owner_id": 101, "topic": "move", "urgency": "normal",
        "confidence": "high", "summary": "", "matching_reason": "", "reply_subject": "", "reply_body": "",
    }
    client, _messages = fake_client(payload)
    result = ClaudeClassifier(vmes, client=client).classify(read_mail(INBOX / "03_verhuis_verkoop.eml"))
    assert result.association_id == 3 and result.lot_id is None and result.confidence == "low"


def test_claude_refusal(vmes):
    client, _messages = fake_client({}, stop_reason="refusal")
    with pytest.raises(RefusalError):
        ClaudeClassifier(vmes, client=client).classify(read_mail(INBOX / "01_lek_badkamer.eml"))


# --- The whole run --------------------------------------------------------------------------

def test_run_creates_an_activity_or_a_request_per_mail(vmes, directory):
    mails = read_inbox(INBOX)
    output = io.StringIO()
    run(mails, directory, MockClassifier(vmes), vmes, today=TODAY, out=lambda line: output.write(line + "\n"))

    assert [a["association_id"] for a in directory.activities] == [1, 2, 3, 1, 2]
    leak = directory.activities[0]
    assert leak["summary"] == "AI-voorstel: Lek of waterschade (A4)"
    assert leak["deadline"] == TODAY  # urgent: today
    assert directory.activities[1]["deadline"] == date(2026, 11, 7)
    assert "nog niet verstuurd" in leak["note"]
    assert "lek-a4-20261102@example.com" in leak["note"]

    # The three requests become a vme.request in Odoo, with the attachments of the mail.
    assert [(r["association_id"], r["lot_id"], r["request_type"]) for r in directory.requests] == [
        (1, 11, "key"), (1, 14, "key"), (2, 24, "key"),
    ]
    assert len(directory.requests[2]["mail"].attachments) == 2
    assert directory.requests[0]["proposed_reply"].startswith("Beste ")
    assert "Aanvraag 100 aangemaakt op Residentie Linde." in output.getvalue()


def test_run_skips_mails_already_processed(vmes, directory):
    mails = read_inbox(INBOX)
    run(mails, directory, MockClassifier(vmes), vmes, today=TODAY, out=lambda line: None)
    lines = []
    run(mails, directory, MockClassifier(vmes), vmes, today=TODAY, out=lines.append)
    assert len(directory.activities) == 5
    assert len(directory.requests) == 3
    assert all("al verwerkt" in line for line in lines)


def test_run_dry_run_writes_nothing(vmes, directory):
    run(read_inbox(INBOX), directory, MockClassifier(vmes), vmes, dry_run=True, out=lambda line: None)
    assert directory.activities == []
    assert directory.requests == []


def test_run_without_vme_writes_nothing(vmes, directory, tmp_path):
    (tmp_path / "x.txt").write_text("Van: iemand@example.com\n\nHallo", encoding="utf-8")
    lines = []
    run(read_inbox(tmp_path), directory, MockClassifier(vmes), vmes, out=lines.append)
    assert directory.activities == []
    assert any("manueel" in line for line in lines)


def test_note_escapes_mail_content(vmes, directory, tmp_path):
    (tmp_path / "x.txt").write_text(
        "Van: Eigenaar Linde A4 <eigenaar.linde.a4@example.com>\n\n<script>alert(1)</script> lek", encoding="utf-8"
    )
    run(read_inbox(tmp_path), directory, MockClassifier(vmes), vmes, out=lambda line: None)
    note = directory.activities[0]["note"]
    assert "<script>" not in note and "&lt;script&gt;" in note


# --- Odoo JSON-RPC client with a fake server ---------------------------------------------------

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_odoo_client_login_and_execute(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        requests.append((request.full_url, payload["params"]))
        result = 2 if payload["params"]["method"] == "login" else [{"id": 1, "name": "Residentie Linde"}]
        return FakeResponse(json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result}).encode())

    monkeypatch.setattr(odoo_api.urllib.request, "urlopen", fake_urlopen)
    odoo = odoo_api.OdooClient("http://localhost:8270/", "vme_demo", "admin", "admin")
    assert odoo.uid == 2
    assert odoo.execute("vme.association", "search_read", [], fields=["name"]) == [{"id": 1, "name": "Residentie Linde"}]
    url, params = requests[1]
    assert url == "http://localhost:8270/jsonrpc"
    assert params["args"] == ["vme_demo", 2, "admin", "vme.association", "search_read", [[]], {"fields": ["name"]}]


def test_odoo_client_raises_on_error(monkeypatch):
    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        if payload["params"]["method"] == "login":
            return FakeResponse(json.dumps({"result": 2}).encode())
        return FakeResponse(json.dumps({"error": {"message": "Odoo Server Error", "data": {"message": "Geen toegang"}}}).encode())

    monkeypatch.setattr(odoo_api.urllib.request, "urlopen", fake_urlopen)
    odoo = odoo_api.OdooClient("http://x", "db", "admin", "admin")
    with pytest.raises(odoo_api.OdooError, match="Geen toegang"):
        odoo.execute("vme.association", "read", [1])


def test_odoo_client_failed_login(monkeypatch):
    monkeypatch.setattr(
        odoo_api.urllib.request, "urlopen", lambda request, timeout: FakeResponse(json.dumps({"result": False}).encode())
    )
    with pytest.raises(odoo_api.OdooError, match="Aanmelden"):
        odoo_api.OdooClient("http://x", "db", "admin", "fout")


def test_claude_with_real_sdk_and_fake_http(vmes):
    """The real Anthropic SDK builds the request; only the HTTP layer is faked (no API key needed)."""
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")  # the HTTP library of anthropic 2.x
    seen = {}
    answer = {
        "association_id": 2, "lot_id": 21, "owner_id": 201, "topic": "statement", "urgency": "normal",
        "confidence": "high", "summary": "Vraag over verwarming en openstaande provisies.",
        "matching_reason": "Afzender is eigenaar van B7.", "reply_subject": "Re: afrekening",
        "reply_body": "Beste Eigenaar Beuken B7, ...",
    }

    def handler(request):
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": MODEL,
            "content": [{"type": "text", "text": json.dumps(answer)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    client = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = ClaudeClassifier(vmes, client=client).classify(read_mail(INBOX / "02_vraag_afrekening.eml"))

    assert (result.association_id, result.lot_id, result.topic) == (2, 21, "statement")
    body = seen["body"]
    assert body["model"] == MODEL
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]


def test_main_without_api_key_stops_before_odoo(monkeypatch, capsys):
    import assistant

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(assistant, "load_env", lambda path: None)
    monkeypatch.setattr(assistant, "OdooClient", lambda *args: pytest.fail("Odoo mag niet aangesproken worden"))
    assert assistant.main([]) == 2
    assert "--mock" in capsys.readouterr().out


def test_main_odoo_unreachable(monkeypatch, capsys):
    import assistant

    monkeypatch.setattr(assistant, "load_env", lambda path: None)
    monkeypatch.setenv("ODOO_URL", "http://127.0.0.1:9")
    assert assistant.main(["--mock"]) == 1
    assert "Kan Odoo niet bereiken" in capsys.readouterr().out


# --- VmeDirectory against a fake Odoo ---------------------------------------------------------

class RecordingOdoo:
    """Answers the reads of VmeDirectory with fixed data and records every call."""

    uid = 2

    def __init__(self):
        self.calls = []

    def execute(self, model, method, *args, **kwargs):
        self.calls.append((model, method, args, kwargs))
        if method == "read":
            return [{"id": 2, "company_ids": [1, 2]}]
        if method == "create_from_intake":
            return 42
        data = {
            "vme.association": [{"id": 1, "name": "Residentie Linde", "street": "Lindedreef 12", "zip": "2000", "city": "Voorbeeldstad"}],
            "vme.lot": [{"id": 14, "name": "A6", "association_id": [1, "Residentie Linde"], "lot_type": "apartment",
                         "floor": "Verdieping 1", "current_owner_id": [104, "Eigenaar Linde A6"]}],
            "vme.lot.contact": [{"id": 1, "lot_id": [14, "A6"], "partner_id": [501, "Huurder Linde A6"]}],
            "res.partner": [{"id": 104, "name": "Eigenaar Linde A6", "email": "eigenaar.linde.a6@example.com"},
                            {"id": 501, "name": "Huurder Linde A6", "email": "huurder.linde.a6@example.com"}],
        }
        return data.get(model, [])


def test_directory_loads_tenants():
    odoo = RecordingOdoo()
    vmes = odoo_api.VmeDirectory(odoo).load(today=TODAY)
    lot = vmes[0]["lots"][0]
    assert lot["owner"]["email"] == "eigenaar.linde.a6@example.com"
    assert lot["tenants"] == [{"id": 501, "name": "Huurder Linde A6", "email": "huurder.linde.a6@example.com"}]
    domain = next(args[0] for model, method, args, _ in odoo.calls if model == "vme.lot.contact")
    assert ("role", "=", "tenant") in domain and ("date_start", "<=", "2026-11-05") in domain


def test_directory_creates_request_with_attachments():
    odoo = RecordingOdoo()
    directory = odoo_api.VmeDirectory(odoo)
    mail = read_mail(INBOX / "08_badge_huurder_toestemming.eml")
    assert directory.create_request(2, "key", mail, lot_id=24, summary="Extra badge") == 42
    model, method, args, kwargs = odoo.calls[-1]
    assert (model, method, args) == ("vme.request", "create_from_intake", ())
    assert kwargs["email"] == "huurder.beuken.b12@example.com"
    assert kwargs["reference"] == "badge-b12-20261105@example.com"
    assert kwargs["channel"] == "mail"
    assert [a["name"] for a in kwargs["attachments"]] == ["toestemming_eigenaar_B12.pdf", "huurcontract_B12.pdf"]
    assert base64.b64decode(kwargs["attachments"][0]["datas"]).startswith(b"%PDF")
    assert kwargs["context"] == {"allowed_company_ids": [1, 2]}
