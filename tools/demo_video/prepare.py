"""Steps 3 and 4 of "Vooraf" in docs/demo.md, without a browser and without an API key.

Runs inside the recorder container (python3 there is new enough for the scripts in ai/):
the AI assistant reads the eight owner mails with --mock, and the three quotes for the facade
are compared with --offline. Nothing is sent anywhere: both only write drafts in Odoo.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))

from odoo_api import OdooClient  # noqa: E402

URL = os.environ.get("ODOO_URL", "http://odoo:8069")
DB = os.environ.get("ODOO_DB", "vme_video")


def run_ai(*args):
    env = dict(os.environ, ODOO_URL=URL, ODOO_DB=DB)
    print("$", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=ROOT / "ai", env=env, check=True)


def main():
    run_ai("assistant.py", "--mock")

    odoo = OdooClient(URL, DB, "admin", "admin")
    companies = odoo.execute("res.users", "read", [odoo.uid], fields=["company_ids"])[0]["company_ids"]
    context = {"allowed_company_ids": companies}
    works = odoo.execute("vme.works", "search", [("name", "=", "Gevelrenovatie voor- en achtergevel")],
                         context=context)
    if len(works) != 1:
        sys.exit(f"Werkdossier voor de gevel niet gevonden: {works}")
    # The button "Offertes vergelijken" in the work file; the AI fills the comparison in next.
    odoo.execute("vme.works", "action_compare_quotes", works, context=context)
    run_ai("offertes.py", "--offline")


if __name__ == "__main__":
    main()
