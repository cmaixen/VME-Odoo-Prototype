from odoo import fields, models


def _default_year(wizard):
    # In the second half of the year the syndic plans the next season.
    today = fields.Date.context_today(wizard)
    return today.year + 1 if today.month > 6 else today.year


class VmeAssemblyPlannerWizard(models.TransientModel):
    _name = "vme.assembly.planner.wizard"
    _description = "AV-planner"

    year = fields.Integer(string="Jaar", required=True, default=_default_year)
    association_ids = fields.Many2many(
        "vme.association", string="VME's",
        help="Leeg laten voor alle VME's met een AV-periode.",
    )
    replan_proposed = fields.Boolean(
        string="Voorstellen opnieuw indelen", default=True,
        help="AV's die nog niet bevestigd zijn, worden opnieuw ingedeeld. Bevestigde AV's blijven staan.",
    )

    def action_propose(self):
        self.ensure_one()
        Assembly = self.env["vme.assembly"]
        associations = self.association_ids or self.env["vme.association"].search([("assembly_period_month", "!=", False)])
        Assembly._create_missing_assemblies(self.year, associations)
        assemblies = Assembly.search([("year", "=", self.year), ("association_id", "in", associations.ids)])
        if self.replan_proposed:
            assemblies.filtered(lambda a: a.state == "proposed").write({"slot_id": False})
        to_plan = assemblies.filtered(lambda a: a.state == "draft")
        unplanned = to_plan._propose_schedule()
        planned = len(to_plan) - len(unplanned)
        message = self.env._("%(planned)s AV's ingedeeld, %(unplanned)s zonder vrij blok.",
                             planned=planned, unplanned=len(unplanned))
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_assembly_action")
        action["domain"] = [("year", "=", self.year)]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Voorstel klaar"),
                "message": message,
                "type": "warning" if unplanned else "success",
                "sticky": bool(unplanned),
                "next": action,
            },
        }
