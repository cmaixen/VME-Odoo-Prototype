"""Shared fixtures: a small fictitious directory like the demo data, and fake Odoo."""
from pathlib import Path

import pytest

INBOX = Path(__file__).resolve().parent.parent / "inbox"


def _lot(lot_id, name, owner_id, short, tenant_id=None):
    return {
        "id": lot_id,
        "name": name,
        "type": "apartment",
        "floor": "",
        "owner": {"id": owner_id, "name": f"Eigenaar {short} {name}", "email": f"eigenaar.{short.lower()}.{name.lower()}@example.com"},
        "tenants": [
            {"id": tenant_id, "name": f"Huurder {short} {name}", "email": f"huurder.{short.lower()}.{name.lower()}@example.com"}
        ] if tenant_id else [],
    }


@pytest.fixture
def vmes():
    # Same names and addresses as the demo data, with only the lots the test mails need.
    return [
        {"id": 1, "name": "Residentie Linde", "address": "Lindedreef 12 2000 Voorbeeldstad", "lots": [
            _lot(11, "A4", 101, "Linde"), _lot(12, "A7", 102, "Linde"), _lot(13, "A11", 103, "Linde"),
            _lot(14, "A6", 104, "Linde", tenant_id=501),
        ]},
        {"id": 2, "name": "Hof ter Beuken", "address": "Beukenhof 3 9000 Voorbeeldstad", "lots": [
            _lot(21, "B7", 201, "Beuken"), _lot(22, "B23", 202, "Beuken"),
            _lot(24, "B12", 203, "Beuken", tenant_id=502),
            # B24 belongs to the owner of B23, as in the demo data.
            {**_lot(23, "B24", 202, "Beuken"), "owner": _lot(22, "B23", 202, "Beuken")["owner"]},
        ]},
        {"id": 3, "name": "Kaaihuis", "address": "Kaaistraat 7 8000 Voorbeeldstad", "lots": [
            _lot(31, "K4", 301, "Kaaihuis"),
        ]},
    ]


class FakeDirectory:
    """Stands in for VmeDirectory: remembers activities and requests instead of writing to Odoo."""

    def __init__(self):
        self.activities = []
        self.requests = []

    def find_activity(self, reference):
        return next((a["id"] for a in self.activities if reference in a["note"]), None)

    def find_request(self, reference):
        return next((r["id"] for r in self.requests if r["mail"].reference == reference), None)

    def create_request(self, association_id, request_type, mail, lot_id=None, summary="", proposed_reply=""):
        request = {
            "id": 100 + len(self.requests),
            "association_id": association_id,
            "request_type": request_type,
            "mail": mail,
            "lot_id": lot_id,
            "proposed_reply": proposed_reply,
        }
        self.requests.append(request)
        return request["id"]

    def create_activity(self, association_id, summary, note_html, deadline, user_id=None):
        activity = {
            "id": len(self.activities) + 1,
            "association_id": association_id,
            "summary": summary,
            "note": note_html,
            "deadline": deadline,
            "user_id": user_id,
        }
        self.activities.append(activity)
        return activity["id"]


@pytest.fixture
def directory():
    return FakeDirectory()
