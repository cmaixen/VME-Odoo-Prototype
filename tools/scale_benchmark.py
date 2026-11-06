"""Measure the screens and calculations of the portfolio on the database vme_scale (docs/dev/schaal.md).

Run inside an Odoo shell after tools/scale_data.py:

    docker compose -p vme-schaal run --rm -T odoo odoo shell -d vme_scale --no-http < tools/scale_benchmark.py

Prints a Markdown table: per scenario the time (median of SCALE_RUNS runs, with an empty record
cache) and the number of SQL queries. Scenarios that create records run once, in a savepoint that
is rolled back; nothing is committed.
"""
import os
import statistics
import time
from datetime import date

from odoo.fields import Command

RUNS = int(os.environ.get("SCALE_RUNS", 3))
# SCALE_SKIP_CALLS=1 skips the provision call for all VMEs, which takes minutes.
env = env(user=env.ref("base.user_admin"))  # noqa: F821 - env is given by odoo shell
# As in the browser: the user works with all companies selected.
env = env(context={**env.context, "allowed_company_ids": env.user.company_ids.ids, "lang": "nl_BE"})
cr = env.cr
VME = env["vme.association"]
PORTFOLIO_FIELDS = [
    "currency_id", "name", "city", "lot_count", "working_capital_balance", "reserve_capital_balance",
    "budget_usage", "arrears_amount", "signal_reserve", "signal_arrears", "signal_assembly",
    "signal_inspection", "signal_count",
]
KANBAN_FIELDS = ["currency_id", "name", "city", "lot_count", "signal_count", "signal_summary",
                 "working_capital_balance", "reserve_capital_balance", "arrears_amount"]
spec = lambda names: {name: {} for name in names}  # noqa: E731

vmes = VME.search([("name", "=like", "Residentie Test %")])
# A record of its own, as the form view reads it: in the prefetch set of all VMEs, reading a
# computed field (the building card) would compute it for all 200 at once.
largest = VME.browse(max(vmes, key=lambda v: len(v.lot_ids)).id)
results = []


class Rollback(Exception):
    pass


def measure(label, func, runs=RUNS, rollback=False):
    times, queries, outcome = [], [], None
    for _ in range(runs):
        env.invalidate_all()
        count, started = cr.sql_log_count, time.perf_counter()
        try:
            with cr.savepoint():
                outcome = func()
                if rollback:
                    env.flush_all()
                    raise Rollback
        except Rollback:
            pass
        times.append(time.perf_counter() - started)
        queries.append(cr.sql_log_count - count)
        if rollback:
            env.invalidate_all()
    results.append((label, statistics.median(times), statistics.median(queries), outcome))


def portfolio(domain, fields, limit):
    records = VME.web_search_read(domain, spec(fields), limit=limit)
    return f"{records['length']} VME's"


measure("Portefeuille, lijst (80 VME's)", lambda: portfolio([], PORTFOLIO_FIELDS, 80))
measure("Portefeuille, kanban (alle VME's)", lambda: portfolio([], KANBAN_FIELDS, None))
measure("Filter 'Met signalen' + lijst", lambda: portfolio([("signal_count", ">", 0)], PORTFOLIO_FIELDS, 80))
measure("Filter 'Achterstallen boven de drempel' + lijst",
        lambda: portfolio([("signal_arrears", "=", True)], PORTFOLIO_FIELDS, 80))
measure(f"Gebouwkaart {largest.name} ({len(largest.lot_ids)} kavels)",
        lambda: len(largest.building_card_html) and "ok")
measure(f"Jaarafrekening 2026 {largest.name}",
        lambda: f"{len(largest._get_annual_statement(2026)['statements'])} eigenaars")
measure(f"Voorbeeld jaarafrekening (wizard) {largest.name}",
        lambda: env["vme.annual.statement.wizard"].create(
            {"association_id": largest.id, "year": 2026}).preview_html and "ok")


def provision_calls(background=True):
    """The wizard for all VMEs; from step 27 on that queues a run, which the cron then works off."""
    action = env["vme.provision.call.wizard"].create({
        "association_ids": [Command.set(vmes.ids)], "year": 2027, "number": 1,
        "invoice_date": date(2027, 1, 5), "date_due": date(2027, 2, 4), "post_invoices": True,
    }).action_create_calls()
    if action.get("res_model") == "vme.provision.call.run":
        if not background:
            return "in de wachtrij"
        env["vme.provision.call.run"].browse(action["res_id"])._process()
    return f"{env['account.move'].search_count([('move_type', '=', 'out_invoice'), ('invoice_date', '=', date(2027, 1, 5))])} facturen"


def distribute_bill():
    company = largest.company_id
    supplier = env["res.partner"].search([("name", "=", "Schoonmaak Test BV")], limit=1)
    bill = env["account.move"].with_company(company).create({
        "move_type": "in_invoice", "partner_id": supplier.id, "invoice_date": date(2026, 10, 31),
        "ref": "SCALE-BENCH", "invoice_line_ids": [Command.create({"name": "Schoonmaak oktober", "quantity": 1,
                                                                   "price_unit": 1234.56})],
    })
    bill.with_company(company).action_post()
    return f"{len(bill.vme_allocation_ids)} aandelen" if "vme_allocation_ids" in bill._fields else "ok"


measure(f"Verdeling van één factuur {largest.name}", distribute_bill, runs=1, rollback=True)
measure(f"Klik op 'Maak provisieoproepen' voor {len(vmes)} VME's", lambda: provision_calls(False), runs=1, rollback=True)
if not os.environ.get("SCALE_SKIP_CALLS"):  # about 15 minutes
    measure(f"Provisieoproep 2027/1 voor {len(vmes)} VME's", provision_calls, runs=1, rollback=True)

print("\n| Scenario | Tijd | Queries | Resultaat |\n| --- | ---: | ---: | --- |")
for label, seconds, queries, outcome in results:
    print(f"| {label} | {seconds:.2f} s | {queries:.0f} | {outcome} |")
cr.rollback()
