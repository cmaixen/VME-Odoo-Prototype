import base64

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from ..models.vme_migration import parse_amount, parse_date

# Column names of the meter reading file (lower case, first row). See docs/dev/verbruik.md.
REQUIRED_COLUMNS = ("kavel", "teller", "soort", "datum", "stand")
OPTIONAL_COLUMNS = ("coefficient", "plaats")
COLUMN_ALIASES = {"coëfficiënt": "coefficient", "coefficiënt": "coefficient", "tellernummer": "teller"}
METER_TYPE_WORDS = {
    "water": "water",
    "verwarming": "heating", "kostenverdeler": "heating", "warmte": "heating",
    "elektriciteit": "electricity", "electriciteit": "electricity",
}


class VmeMeterImportWizard(models.TransientModel):
    _name = "vme.meter.import.wizard"
    _description = "Meterstanden inlezen"

    association_id = fields.Many2one("vme.association", string="VME", required=True)
    data_file = fields.Binary(string="Bestand", required=True)
    filename = fields.Char(string="Bestandsnaam")
    state = fields.Selection([("draft", "Nieuw"), ("checked", "Gecontroleerd")], default="draft")
    report_html = fields.Html(string="Rapport", sanitize=False, readonly=True)
    error_count = fields.Integer(string="Fouten", readonly=True)
    warning_count = fields.Integer(string="Waarschuwingen", readonly=True)

    @api.onchange("data_file", "association_id")
    def _onchange_file(self):
        self.state = "draft"

    def action_check(self):
        """Dry run: check the file and show the report, write nothing."""
        self.ensure_one()
        plan, messages = self._check_file(self.association_id, base64.b64decode(self.data_file))
        self.write({
            "state": "checked",
            "report_html": self._report_html(plan, messages),
            "error_count": sum(1 for m in messages if m[0] == "error"),
            "warning_count": sum(1 for m in messages if m[0] == "warning"),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": self.env._("Meterstanden inlezen"),
        }

    def action_import(self):
        self.ensure_one()
        readings = self._import_file(self.association_id, base64.b64decode(self.data_file), self.filename or "")
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_meter_reading_action")
        action["domain"] = [("id", "in", readings.ids)]
        action["name"] = self.env._("Ingelezen meterstanden")
        return action

    @api.model
    def _import_file(self, vme, raw, filename):
        """Check the file again and create its meters and readings in one go; refuse on any error."""
        plan, messages = self._check_file(vme, raw)
        errors = [m for m in messages if m[0] == "error"]
        if errors:
            raise UserError(self.env._(
                "Het bestand heeft %(count)s fout(en); er is niets ingelezen. Eerste fout, regel %(line)s: %(text)s",
                count=len(errors), line=errors[0][1], text=errors[0][2],
            ))
        Meter = self.env["vme.meter"]
        meters = {}
        for name, (lot, meter_type, factor, location) in plan["new_meters"].items():
            meters[name] = Meter.create({
                "name": name, "lot_id": lot.id, "meter_type": meter_type, "factor": factor, "location": location,
            })
        return self.env["vme.meter.reading"].create([{
            "meter_id": (row["meter"] or meters[row["meter_name"]]).id,
            "date": row["date"],
            "value": row["value"],
            "source": "import",
            "import_ref": filename,
        } for row in plan["rows"]])

    @api.model
    def _check_file(self, vme, raw):
        """Read a meter reading file for one VME.

        Returns (plan, messages): the plan has the readings to create ("rows") and the meters that do
        not exist yet ("new_meters"); a message is (level, line number, text) with level error or warning.
        """
        messages = []
        plan = {"rows": [], "new_meters": {}, "skipped": 0}
        _ = self.env._
        rows = self.env["vme.migration"]._read_csv(raw)
        if not rows:
            return plan, [("error", 1, _("Het bestand is leeg."))]
        header = [COLUMN_ALIASES.get(c.strip().lower(), c.strip().lower()) for c in rows[0]]
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            return plan, [("error", 1, _("Kolommen ontbreken: %s.", ", ".join(missing)))]

        lots = {lot.name.upper(): lot for lot in vme.lot_ids}
        existing = {m.name: m for m in self.env["vme.meter"].with_context(active_test=False).search(
            [("association_id", "=", vme.id)])}
        # Index values per meter name: existing readings plus the file, to check that they only go up.
        series = {name: {r.date: (r.value, None) for r in meter.reading_ids} for name, meter in existing.items()}

        for number, values in enumerate(rows[1:], start=2):
            if not any((v or "").strip() for v in values):
                continue
            row = dict(zip(header, (v.strip() for v in values)))

            def error(text, number=number):
                messages.append(("error", number, text))

            lot = lots.get(row.get("kavel", "").upper())
            if not lot:
                error(_("Kavel %(lot)s bestaat niet in %(vme)s.", lot=row.get("kavel") or "?", vme=vme.name))
                continue
            meter_name = row.get("teller", "")
            if not meter_name:
                error(_("Het tellernummer ontbreekt."))
                continue
            meter_type = METER_TYPE_WORDS.get(row.get("soort", "").lower())
            if not meter_type:
                error(_("Onbekende soort %(type)s; kies uit water, verwarming of elektriciteit.", type=row.get("soort")))
                continue
            try:
                day = parse_date(row.get("datum"))
            except ValueError:
                day = None
            if not day:
                error(_("Ongeldige datum %s; gebruik DD/MM/JJJJ.", row.get("datum") or "(leeg)"))
                continue
            try:
                value = parse_amount(row.get("stand"))
            except ValueError:
                value = None
            if value is None or not row.get("stand") or value < 0:
                error(_("Ongeldige stand %s.", row.get("stand") or "(leeg)"))
                continue
            factor = 1.0
            if row.get("coefficient"):
                try:
                    factor = parse_amount(row["coefficient"])
                except ValueError:
                    factor = 0.0
                if factor <= 0:
                    error(_("Ongeldige coëfficiënt %s.", row["coefficient"]))
                    continue

            meter = existing.get(meter_name)
            if meter:
                if meter.lot_id != lot or meter.meter_type != meter_type:
                    error(_("Teller %(meter)s hoort bij kavel %(lot)s (%(type)s), niet bij %(file_lot)s.",
                            meter=meter_name, lot=meter.lot_id.name,
                            type=dict(meter._fields["meter_type"].selection)[meter.meter_type], file_lot=lot.name))
                    continue
                if row.get("coefficient") and float_compare(factor, meter.factor, precision_digits=4):
                    messages.append(("warning", number, _(
                        "Teller %(meter)s heeft coëfficiënt %(old)s, het bestand zegt %(new)s; de coëfficiënt "
                        "wordt niet gewijzigd.", meter=meter_name, old=meter.factor, new=factor)))
            else:
                new = plan["new_meters"].get(meter_name)
                if new and (new[0] != lot or new[1] != meter_type):
                    error(_("Teller %s staat in het bestand bij twee kavels of soorten.", meter_name))
                    continue
                if not new:
                    plan["new_meters"][meter_name] = (lot, meter_type, factor, row.get("plaats") or False)
                    messages.append(("warning", number, _(
                        "Teller %(meter)s van kavel %(lot)s is nieuw en wordt aangemaakt.", meter=meter_name, lot=lot.name)))

            known = series.setdefault(meter_name, {})
            if day in known:
                old_value, old_line = known[day]
                if float_compare(old_value, value, precision_digits=3):
                    where = _("regel %s", old_line) if old_line else _("al ingelezen")
                    error(_("Teller %(meter)s heeft op %(date)s al stand %(old)s (%(where)s), het bestand zegt %(new)s.",
                            meter=meter_name, date=day.strftime("%d/%m/%Y"), old=old_value, where=where, new=value))
                else:
                    plan["skipped"] += 1
                continue
            known[day] = (value, number)
            plan["rows"].append({"meter": meter, "meter_name": meter_name, "lot": lot, "date": day,
                                 "value": value, "line": number})

        # Readings of a meter must not go down (a replaced meter is a new meter).
        for meter_name, known in series.items():
            previous = None
            for day in sorted(known):
                value, line = known[day]
                if previous and float_compare(value, previous[1], precision_digits=3) < 0 and (line or previous[2]):
                    messages.append(("error", line or previous[2], _(
                        "De stand van teller %(meter)s daalt van %(old)s op %(old_date)s naar %(new)s op %(date)s.",
                        meter=meter_name, old=previous[1], old_date=previous[0].strftime("%d/%m/%Y"),
                        new=value, date=day.strftime("%d/%m/%Y"))))
                previous = (day, value, line)
        if plan["skipped"]:
            messages.append(("warning", 0, _("%s meterstanden waren al ingelezen en worden overgeslagen.", plan["skipped"])))
        if not plan["rows"] and not any(m[0] == "error" for m in messages):
            messages.append(("warning", 0, _("Het bestand bevat geen nieuwe meterstanden.")))
        messages.sort(key=lambda m: (m[0] != "error", m[1]))
        return plan, messages

    @api.model
    def _report_html(self, plan, messages):
        _ = self.env._
        rows = plan["rows"]
        days = sorted({r["date"] for r in rows})
        summary = _("%(readings)s nieuwe meterstanden voor %(meters)s tellers (waarvan %(new)s nieuw).",
                    readings=len(rows), meters=len({r["meter_name"] for r in rows}), new=len(plan["new_meters"]))
        if days:
            summary += " " + _("Opnamedatums: %s.", ", ".join(d.strftime("%d/%m/%Y") for d in days))
        html = Markup("<p>%s</p>") % summary
        errors = [m for m in messages if m[0] == "error"]
        html += Markup('<p class="fw-bold %s">%s</p>') % (
            "text-danger" if errors else "text-success",
            _("%s fout(en): verbeter het bestand en controleer opnieuw.", len(errors)) if errors
            else _("Geen fouten: je kan importeren."),
        )
        if messages:
            html += Markup('<table class="table table-sm"><thead><tr><th>Regel</th><th>Soort</th>'
                           '<th>Melding</th></tr></thead><tbody>')
            for level, line, text in messages[:200]:
                html += Markup('<tr class="%s"><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                    "table-danger" if level == "error" else "table-warning",
                    line or "", _("Fout") if level == "error" else _("Waarschuwing"), escape(text),
                )
            html += Markup("</tbody></table>")
        return html
