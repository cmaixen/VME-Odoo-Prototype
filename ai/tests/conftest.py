"""Shared fixtures: a small fictitious directory like the demo data, and fake Odoo."""
from pathlib import Path

import pytest

INBOX = Path(__file__).resolve().parent.parent / "inbox"


def _lot(lot_id, name, owner_id, short):
    return {
        "id": lot_id,
        "name": name,
        "type": "apartment",
        "floor": "",
        "owner": {"id": owner_id, "name": f"Eigenaar {short} {name}", "email": f"eigenaar.{short.lower()}.{name.lower()}@example.com"},
    }


@pytest.fixture
def vmes():
    # Same names and addresses as the demo data, with only the lots the test mails need.
    return [
        {"id": 1, "name": "Residentie Linde", "address": "Lindedreef 12 2000 Voorbeeldstad", "lots": [
            _lot(11, "A4", 101, "Linde"), _lot(12, "A7", 102, "Linde"), _lot(13, "A11", 103, "Linde"),
        ]},
        {"id": 2, "name": "Hof ter Beuken", "address": "Beukenhof 3 9000 Voorbeeldstad", "lots": [
            _lot(21, "B7", 201, "Beuken"), _lot(22, "B23", 202, "Beuken"),
            # B24 belongs to the owner of B23, as in the demo data.
            {**_lot(23, "B24", 202, "Beuken"), "owner": _lot(22, "B23", 202, "Beuken")["owner"]},
        ]},
        {"id": 3, "name": "Kaaihuis", "address": "Kaaistraat 7 8000 Voorbeeldstad", "lots": [
            _lot(31, "K4", 301, "Kaaihuis"),
        ]},
    ]


class FakeDirectory:
    """Stands in for VmeDirectory: remembers activities instead of writing to Odoo."""

    def __init__(self):
        self.activities = []
        self.claims = []

    def find_activity(self, reference):
        return next((a["id"] for a in self.activities if reference in a["note"]), None)

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

    def create_damage_claim(self, association_id, subject, body, reference, lot_id=None, owner_id=None,
                            mail_date=None):
        existing = next((c["id"] for c in self.claims if c["reference"] == reference), None)
        if existing:
            return existing
        self.claims.append({"id": len(self.claims) + 1, "association_id": association_id, "subject": subject,
                            "reference": reference, "lot_id": lot_id, "owner_id": owner_id, "mail_date": mail_date})
        return len(self.claims)


@pytest.fixture
def directory():
    return FakeDirectory()
