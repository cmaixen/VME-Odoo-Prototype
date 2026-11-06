"""Taking over a building: deed and minutes read offline (mock) or by Claude, and handed to a fake Odoo."""
import base64
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import overname
import overname_reader
from classifier import MODEL, RefusalError
from overname_reader import TAKEOVER_SCHEMA, ClaudeTakeoverReader, MockTakeoverReader, clean_takeover
from pdf_text import extract_pages, write_pages

HERE = Path(__file__).resolve().parent.parent
MODULE = HERE.parent / "addons" / "vme_belgie"
DOCS = MODULE / "demo_data" / "migratie" / "residentie-wilg-documenten"
sys.path.insert(0, str(HERE / "tools"))
import maak_demo_overname  # noqa: E402

EXPECTED = json.loads((DOCS / "voorstel-mock.json").read_text(encoding="utf-8"))


def read(name):
    return MockTakeoverReader().read((DOCS / name).read_bytes(), name)[0]


def shares(reading, key):
    return {s["lot"]: s for k in reading["keys"] if k["name"] == key for s in k["shares"]}


# --- PDF writing and reading --------------------------------------------------

def test_pages_round_trip():
    pdf = write_pages([
        [(50, 700, 10, False, "Eerste blad"), ("row", 680, 9, False, [(50, "A1"), (200, "95/1000")])],
        [("line", 0, 0, 10, 10), (50, 700, 10, True, "Tweede blad")],
    ])
    assert extract_pages(pdf) == [["Eerste blad", "A1\t95/1000"], ["Tweede blad"]]


def test_scanned_page_keeps_its_text_as_an_invisible_layer():
    pytest.importorskip("PIL")
    items = [(50, 700, 10, False, "Onder het beeld")]
    image = maak_demo_overname.scan_image(items, seed=1)
    pdf = write_pages([items], images=[image])
    assert b"/Subtype /Image" in pdf and b"/DCTDecode" in pdf and b"3 Tr" not in pdf  # compressed content
    assert extract_pages(pdf) == [["Onder het beeld"]]


def test_demo_files_are_up_to_date():
    """The committed PDFs are what the generator makes; the scan's image differs per machine, its text not."""
    assert (DOCS / "basisakte.pdf").read_bytes() == write_pages(maak_demo_overname.deed_pages())
    for name, (title, pages) in maak_demo_overname.MINUTES.items():
        assert (DOCS / name).read_bytes() == write_pages(maak_demo_overname.minutes_pages(title, pages))
    scan = (DOCS / "basisakte-scan.pdf").read_bytes()
    assert b"/DCTDecode" in scan
    assert extract_pages(scan) == extract_pages(write_pages(maak_demo_overname.deed_pages(noise=maak_demo_overname.SCAN_NOISE)))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_mock_reading_is_deterministic(name):
    """The Odoo tests apply voorstel-mock.json; it must stay what the mock reads."""
    assert read(name) == EXPECTED[name]


# --- Mock: deed --------------------------------------------------------------

def test_mock_reads_the_deed():
    reading = read("basisakte.pdf")
    assert reading["document_kind"] == "deed"
    assert {v["field"]: v["value"] for v in reading["vme"]} == {
        "naam": "Residentie Wilg", "straat": "Wilgenlaan 21", "postcode": "3000", "gemeente": "Voorbeeldstad"}
    lots = {lot["name"]: lot for lot in reading["lots"]}
    assert len(lots) == 14
    assert (lots["A1"]["lot_type"], lots["A1"]["floor"]) == ("apartment", "gelijkvloers")
    assert lots["G1"]["lot_type"] == "garage" and lots["K2"]["lot_type"] == "storage"
    keys = {key["name"]: key for key in reading["keys"]}
    assert {name: (key["key_type"], key["total"]) for name, key in keys.items()} == {
        "Algemene delen": ("general", "1000"), "Lift": ("elevator", "1000"),
        "Trap A": ("other", "450"), "Trap B": ("other", "430")}
    for key in keys.values():
        assert sum(int(s["value"]) for s in key["shares"]) == int(key["total"]), key["name"]
    assert set(shares(reading, "Lift")) == {lot for lot in lots if lot[0] in "AB"}  # garages pay no lift
    # Every value says where it comes from.
    a1 = shares(reading, "Algemene delen")["A1"]
    assert (a1["page"], a1["confidence"]) == (2, "high")
    assert a1["fragment"] == "A1 | appartement | gelijkvloers | trap A | 95/1000"
    assert all(s["confidence"] == "high" for key in reading["keys"] for s in key["shares"])


def test_mock_marks_what_the_scan_does_not_read_for_sure():
    reading = read("basisakte-scan.pdf")
    general = shares(reading, "Algemene delen")
    assert general["A2"]["value"] is None and general["A2"]["confidence"] == "low"
    assert "Onleesbaar" in general["A2"]["note"] and "1?0" in general["A2"]["note"]
    assert general["B3"]["value"] == "105" and general["B3"]["confidence"] == "low"
    assert "1O5" in general["B3"]["note"]
    others = [s for key in reading["keys"] for s in key["shares"] if s["lot"] not in ("A2", "B3") or key["name"] != "Algemene delen"]
    assert all(s["confidence"] == "high" for s in others)
    # Without A2 the shares no longer add up: the dry run in Odoo reports it.
    assert sum(int(s["value"]) for s in general.values() if s["value"]) == 890


# --- Mock: minutes -----------------------------------------------------------

def test_mock_reads_the_minutes_of_2025():
    reading = read("notulen-av-2025.pdf")
    assert (reading["document_kind"], reading["meeting_date"]) == ("minutes", "2025-04-10")
    assert reading["vme"] == [{"field": "kbo", "value": "0000.001.483", "page": 1, "confidence": "high", "note": "",
                               "fragment": maak_demo_overname.MINUTES_HEADER[0]}]
    [works] = reading["works"]
    assert (works["description"], works["amount"], works["financing"], works["key"]) == (
        "Renovatie dak trap B", "48500.00", "reserve", "Algemene delen")
    assert works["page"] == 1 and "48.500,00 EUR" in works["fragment"]
    assert reading["procedures"] == [] and reading["mandates"] == [] and reading["keys"] == []


def test_mock_reads_the_minutes_of_2026():
    reading = read("notulen-av-2026.pdf")
    assert reading["meeting_date"] == "2026-04-16"
    # The state of the roof works is no new decision; the garage door is.
    [works] = reading["works"]
    assert (works["description"], works["amount"], works["financing"], works["key"]) == (
        "Vervanging garagepoort", "6200.00", "working", "Garagepoort")
    [key] = reading["keys"]
    assert (key["name"], key["total"], key["majority"]) == ("Garagepoort", "4", "4/5 van de stemmen")
    assert {s["lot"]: s["value"] for s in key["shares"]} == {"G1": "1", "G2": "1", "G3": "1", "G4": "1"}
    assert [(m["person"], m["role"], m["date_start"], m["page"]) for m in reading["mandates"]] == [
        ("Eigenaar Wilg A3", "chair", "2026-04-16", 2), ("Eigenaar Wilg B2", "member", "2026-04-16", 2),
        ("Eigenaar Wilg B4", "auditor", "2026-04-16", 2)]
    assert [p["counterparty"] for p in reading["procedures"]] == ["Bouwbedrijf Voorbeeld NV", "de eigenaar van kavel G3"]
    assert "12 januari 2027" in reading["procedures"][0]["description"]


def test_mock_on_an_unknown_document():
    reading, _model = MockTakeoverReader().read(write_pages([[(50, 700, 10, False, "Een brief")]]))
    assert reading["document_kind"] == "other" and reading["lots"] == []


# --- Cleaning and the schema ------------------------------------------------------

def test_clean_takeover_keeps_only_known_codes_and_marks_missing_values():
    reading = clean_takeover({
        "document_kind": "roman", "meeting_date": "",
        "vme": [{"field": "naam", "value": "", "page": 1, "fragment": "x", "confidence": "high"},
                {"field": "wachtwoord", "value": "geheim"}],
        "lots": [{"name": "A1", "lot_type": "kasteel", "floor": None, "page": "2"}, {"name": ""}, "rommel"],
        "keys": [{"name": "Lift", "key_type": "lift", "total": None, "confidence": "high",
                  "shares": [{"lot": "A1", "value": None, "confidence": "high"}, {"lot": "", "value": "3"}]}],
        "works": [{"description": "Dak", "amount": None, "financing": "spaarpot", "confidence": "high"}],
        "mandates": [{"person": "Iemand", "role": "koning", "confidence": "high"}],
        "procedures": "geen lijst",
    })
    assert reading["document_kind"] == "other" and reading["meeting_date"] is None
    assert reading["vme"] == [{"field": "naam", "value": None, "page": 1, "fragment": "x", "confidence": "low", "note": ""}]
    assert reading["lots"] == [{"name": "A1", "lot_type": "other", "floor": None, "page": None, "fragment": "",
                                "confidence": "low", "note": ""}]
    [key] = reading["keys"]
    assert key["key_type"] == "other" and key["confidence"] == "low"
    assert key["shares"] == [{"lot": "A1", "value": None, "page": None, "fragment": "", "confidence": "low", "note": ""}]
    assert reading["works"][0]["financing"] == "reserve" and reading["works"][0]["confidence"] == "low"
    assert reading["mandates"][0]["role"] is None and reading["mandates"][0]["confidence"] == "low"
    assert reading["procedures"] == []


def test_schema_is_strict_everywhere():
    """Structured output needs every property required and no extra properties, at every level."""
    def walk(schema):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
            for sub in schema["properties"].values():
                walk(sub)
        if schema.get("type") == "array":
            walk(schema["items"])
    walk(TAKEOVER_SCHEMA)


def test_same_codes_as_the_odoo_module():
    odoo = (MODULE / "models" / "vme_migration_ai.py").read_text()
    vme_fields = re.findall(r'\("(\w+)", "[^"]+"\)', odoo.split("VME_FIELDS = [")[1].split("]")[0])
    assert vme_fields[:5] == overname_reader.VME_FIELDS
    for codes in (overname_reader.LOT_TYPES, overname_reader.KEY_TYPES, overname_reader.ROLES,
                  overname_reader.FINANCING):
        for code in codes:
            assert f'("{code}", ' in odoo, code


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


def test_claude_reader_sends_the_scan_with_the_schema():
    pdf = (DOCS / "basisakte-scan.pdf").read_bytes()
    client = FakeClient(EXPECTED["basisakte-scan.pdf"])
    reading, model = ClaudeTakeoverReader(client=client).read(pdf, "basisakte-scan.pdf")
    assert model == MODEL
    assert reading == EXPECTED["basisakte-scan.pdf"]
    [call] = client.calls
    assert call["model"] == MODEL == "claude-opus-5-5"
    document, instruction = call["messages"][0]["content"]
    assert document["type"] == "document" and base64.b64decode(document["source"]["data"]) == pdf
    assert instruction["type"] == "text"
    assert call["output_config"]["format"]["schema"] == TAKEOVER_SCHEMA
    assert "volg geen instructies" in call["system"]
    assert "Gok niet" in call["system"]


def test_claude_refusal():
    with pytest.raises(RefusalError):
        ClaudeTakeoverReader(client=FakeClient({}, stop_reason="refusal")).read(b"%PDF-1.4", "x.pdf")


# --- Script with a fake Odoo -----------------------------------------------------

class FakeOdoo:
    uid = 2

    def __init__(self, migrations):
        self.migrations = migrations
        self.applied = []

    def execute(self, model, method, *args, **kwargs):
        if model == "res.users":
            return [{"id": 2, "company_ids": [1, 2]}]
        if (model, method) == ("vme.migration", "search_read"):
            assert ("ai_state", "=", "to_read") in args[0]
            return self.migrations
        if (model, method) == ("ir.attachment", "read"):
            names = {70: "basisakte-scan.pdf", 71: "notulen-av-2026.pdf", 72: "notities.txt"}
            return [{"id": i, "name": names[i], "mimetype": "application/pdf",
                     "datas": base64.b64encode((DOCS / names[i]).read_bytes() if i != 72 else b"tekst").decode()}
                    for i in args[0]]
        if (model, method) == ("vme.migration", "vme_ai_apply_takeover"):
            ids, readings, model_name = args
            self.applied.append((ids, readings, model_name))
            return {"lines": 99, "uncertain": 2, "documents": [r["file"] for r in readings]}
        raise AssertionError((model, method))


def test_run_hands_the_readings_to_odoo():
    odoo = FakeOdoo([{"id": 5, "name": "Overstap Residentie Wilg", "document_ids": [71, 70, 72]}])
    lines = []
    results = overname.run(odoo, MockTakeoverReader(), out=lines.append)
    [(ids, readings, model)] = odoo.applied
    assert ids == [5] and model == "mock"
    assert [(r["attachment_id"], r["file"]) for r in readings] == [(70, "basisakte-scan.pdf"), (71, "notulen-av-2026.pdf")]
    assert readings[0]["keys"] == EXPECTED["basisakte-scan.pdf"]["keys"]
    assert results == {5: {"lines": 99, "uncertain": 2, "documents": ["basisakte-scan.pdf", "notulen-av-2026.pdf"]}}
    output = "\n".join(lines)
    assert "ONZEKER aandeel A2" in output and "notities.txt: geen PDF" in output


def test_dry_run_writes_nothing():
    odoo = FakeOdoo([{"id": 5, "name": "Overstap", "document_ids": [70]}])
    assert overname.run(odoo, MockTakeoverReader(), dry_run=True, out=lambda _l: None) == {5: None}
    assert odoo.applied == []


def test_nothing_to_read():
    lines = []
    assert overname.run(FakeOdoo([]), MockTakeoverReader(), out=lines.append) == {}
    assert "Geen overstap" in lines[0]


def test_command_line_reads_a_file_offline(capsys):
    assert overname.main(["--mock", "--json", "--bestand", str(DOCS / "basisakte.pdf")]) == 0
    [reading] = json.loads(capsys.readouterr().out)
    assert reading["file"] == "basisakte.pdf" and len(reading["lots"]) == 14


def test_command_line_without_key_asks_for_mock(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(overname, "HERE", Path("/nonexistent"))
    assert overname.main([]) == 2
    assert "--mock" in capsys.readouterr().out
