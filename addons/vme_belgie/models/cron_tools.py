import logging

_logger = logging.getLogger(__name__)


def run_per_record(records, process, done=None):
    """Run ``process(record)`` for each record of a daily cron, with a commit after each (K-D18).

    In a cron, each record gets a savepoint: one VME that fails is logged and skipped instead of rolling
    back the work of all the others, and ``_commit_progress`` keeps what is done. ``done(record)`` runs
    after each record, also a failed one, so it can mark it as handled for today.

    When the cron runs out of time this returns False; Odoo then calls the cron again for the rest, so
    the caller must leave out what it already handled. Outside a cron (a button, the tests) nothing is
    committed and an error is raised as usual.
    """
    env = records.env
    Cron = env["ir.cron"]
    in_cron = bool(env.context.get("ir_cron_progress_id"))
    if in_cron:
        Cron._commit_progress(remaining=len(records))
    for record in records:
        try:
            with env.cr.savepoint():
                process(record)
        except Exception:
            if not in_cron:
                raise
            _logger.exception("Dagelijkse controle: %s overgeslagen", record.display_name)
        if done:
            done(record)
        if in_cron and Cron._commit_progress(1) <= 0:
            return False
    return True
