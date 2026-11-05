"""Step 24: extraordinary assemblies.

Up to 19.0.1.10.0 a VME had at most one assembly per year (SQL constraint). That rule now only
holds for ordinary assemblies, through a partial unique index, so the old constraint goes.
"""


def migrate(cr, version):
    cr.execute("ALTER TABLE vme_assembly DROP CONSTRAINT IF EXISTS vme_assembly_unique_year_per_association")
