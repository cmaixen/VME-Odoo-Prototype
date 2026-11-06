"""Load the fictitious portfolio of 200 VMEs into the database vme_scale, in batches with a commit each.

Run inside an Odoo shell (see docs/dev/schaal.md):

    docker compose -p vme-schaal run --rm -T odoo odoo shell -d vme_scale --no-http < tools/scale_data.py

Set SCALE_COUNT / SCALE_BATCH in the environment to change the size. Rerunning continues where a
previous run stopped: existing VMEs and VMEs with provision calls are skipped.
"""
import logging
import os
import time

_logger = logging.getLogger("vme_scale")
count = int(os.environ.get("SCALE_COUNT", 200))
batch = int(os.environ.get("SCALE_BATCH", 10))

# As admin: only a person may trust the bank accounts of the VMEs (see docs/dev/valkuilen.md).
env = env(user=env.ref("base.user_admin"))  # noqa: F821 - env is given by odoo shell
VME = env["vme.association"]
for start in range(1, count + 1, batch):
    size = min(batch, count + 1 - start)
    started = time.perf_counter()
    VME._load_scale_data(start, size)
    env.cr.commit()  # loads the charts of accounts of the new companies
    structure = time.perf_counter() - started
    vmes = VME.search([("name", "in", [f"Residentie Test {i:03d}" for i in range(start, start + size)])])
    vmes._load_scale_history()
    env.cr.commit()
    _logger.info("VME %s-%s: structure %.0f s, history %.0f s", start, start + size - 1,
                 structure, time.perf_counter() - started - structure)
# Fresh statistics after the bulk load, as a database in use would have.
env.cr.execute("ANALYZE")
env.cr.commit()
