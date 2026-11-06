from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class VmeProvisionCallRun(models.Model):
    """Provision calls for many VMEs at once, made by a cron job VME per VME.

    Odoo needs two to three seconds per VME to create and post the invoices of a call; for the
    200 VMEs of a syndic that is longer than a web request may last (docs/dev/schaal.md). The
    wizard therefore queues large selections here, and the cron commits after every VME.
    """

    _name = "vme.provision.call.run"
    _description = "Provisieoproepen op de achtergrond"
    _order = "id desc"

    name = fields.Char(string="Omschrijving", compute="_compute_name")
    user_id = fields.Many2one("res.users", string="Gevraagd door", required=True, default=lambda self: self.env.user)
    year = fields.Integer(string="Budgetjaar", required=True)
    number = fields.Integer(string="Oproep nummer", required=True)
    invoice_date = fields.Date(string="Factuurdatum", required=True)
    date_due = fields.Date(string="Vervaldatum", required=True)
    post_invoices = fields.Boolean(string="Meteen boeken")
    association_ids = fields.Many2many(
        "vme.association", "vme_provision_call_run_association_rel", string="VME's", required=True)
    done_association_ids = fields.Many2many(
        "vme.association", "vme_provision_call_run_done_rel", string="Verwerkt")
    state = fields.Selection([("queued", "Bezig"), ("done", "Klaar")], string="Status", default="queued", required=True)
    progress = fields.Char(string="Voortgang", compute="_compute_name")
    log = fields.Text(string="Overgeslagen of mislukt", readonly=True)

    @api.depends("year", "number", "association_ids", "done_association_ids")
    def _compute_name(self):
        for run in self:
            run.name = self.env._("Oproep %(number)s van %(year)s", number=run.number, year=run.year)
            run.progress = self.env._("%(done)s van %(total)s VME's", done=len(run.done_association_ids),
                                      total=len(run.association_ids))

    def _trigger(self):
        self.env.ref("vme_belgie.ir_cron_vme_provision_call_run")._trigger()

    @api.model
    def _cron_process(self):
        runs = self.search([("state", "=", "queued")], order="id")
        Cron = self.env["ir.cron"]
        Cron._commit_progress(remaining=sum(len(run.association_ids - run.done_association_ids) for run in runs))
        runs._process(lambda: Cron._commit_progress(1))

    def _process(self, progress=None):
        """Make the calls VME per VME. progress() commits after each VME and returns the seconds left.

        A VME that fails (no general key, accounts not trusted, ...) is logged and skipped, so one
        VME does not hold up the others; the user sees the reason in the log of the run.
        """
        for run in self:
            # As the user who asked, so the invoices show who made them.
            env = self.env(user=run.user_id, context={**self.env.context,
                                                      "allowed_company_ids": run.user_id.company_ids.ids})
            wizard = env["vme.provision.call.wizard"].create({
                "association_ids": [Command.set(run.association_ids.ids)],
                "year": run.year, "number": run.number, "invoice_date": run.invoice_date,
                "date_due": run.date_due, "post_invoices": run.post_invoices,
            })
            for vme in run.association_ids - run.done_association_ids:
                message = False
                try:
                    with self.env.cr.savepoint():
                        _invoices, skipped = wizard._create_calls(vme.with_env(env))
                        if skipped:
                            message = self.env._("geen budget voor %s", run.year)
                except UserError as error:
                    message = error.args[0]
                run.write({
                    "done_association_ids": [Command.link(vme.id)],
                    "log": f"{run.log or ''}{vme.name}: {message}\n" if message else run.log,
                })
                # Thousands of invoices in one cache slow every next VME down (docs/dev/schaal.md).
                self.env.invalidate_all()
                if progress and progress() <= 0:
                    return  # out of time: the cron runs again for the rest
            run.state = "done"
            run.user_id._bus_send("simple_notification", {
                "type": "warning" if run.log else "success",
                "title": self.env._("Provisieoproepen klaar"),
                "message": self.env._("%(name)s: %(progress)s verwerkt.", name=run.name, progress=run.progress)
                + (" " + self.env._("Kijk het logboek na voor wat overgeslagen is.") if run.log else ""),
            })

    def action_open_calls(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_provision_call_action")
        action["domain"] = [("budget_id.year", "=", self.year), ("number", "=", self.number),
                            ("association_id", "in", self.association_ids.ids)]
        return action
