"""Take over a VME from another syndic package, from CSV or Excel exports.

We do not know the export format of the source packages yet, so the import reads our own,
documented format (docs/dev/migratie.md). A converter per source package can later turn its
export into this format: add a value to ``source_format`` and a ``_convert_<value>`` method.

A dry run reads and checks the files and writes nothing but its report; the import checks
them again and creates everything in one transaction.
"""
import csv
import io
import re
import zipfile
from datetime import date, datetime

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import float_compare, float_is_zero, formatLang

from odoo.addons.base_iban.models.res_partner_bank import normalize_iban, validate_iban

from .account_chart_template import VME_FUND_ACCOUNTS
from .vme_key import SHARES_PRECISION

# Columns per table; the first ones listed in REQUIRED_COLUMNS must be filled in.
TABLES = {
    "vme": ["naam", "kbo", "straat", "postcode", "gemeente", "iban_werkkapitaal", "iban_reservekapitaal", "overstapdatum"],
    "kavels": ["kavel", "type", "verdieping"],
    "eigenaars": ["code", "naam", "email", "telefoon", "straat", "postcode", "gemeente"],
    "eigendommen": ["kavel", "eigenaar", "begindatum", "einddatum"],
    "sleutels": ["sleutel", "soort", "totaal", "kavel", "quotiteit"],
    "leveranciers": ["code", "naam", "btw", "email", "iban", "sleutel"],
    "openingsbalans": ["soort", "code", "bedrag", "omschrijving"],
}
REQUIRED_COLUMNS = {
    "vme": ["naam", "kbo", "overstapdatum"],
    "kavels": ["kavel"],
    "eigenaars": ["code", "naam"],
    "eigendommen": ["kavel", "eigenaar", "begindatum"],
    "sleutels": ["sleutel", "soort", "totaal", "kavel", "quotiteit"],
    "leveranciers": ["code", "naam"],
    "openingsbalans": ["soort", "bedrag"],
}
OPTIONAL_TABLES = {"leveranciers"}

LOT_TYPES = {
    "appartement": "apartment", "garage": "garage", "berging": "storage",
    "handelsruimte": "commercial", "andere": "other",
}
KEY_TYPES = {
    "algemeen": "general", "lift": "elevator", "verwarming": "heating",
    "verbruik": "consumption", "op verbruik": "consumption", "andere": "other",
}
# Sign of an opening balance row: +1 means a positive amount is a debit.
OPENING_KINDS = {
    "bank_werkkapitaal": 1, "bank_reservekapitaal": 1, "eigenaar": 1, "rekening": 1,
    "fonds_werkkapitaal": -1, "fonds_reservekapitaal": -1, "leverancier": -1,
}
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y")


def parse_date(value):
    """Date from a cell: a date object (Excel), dd/mm/yyyy or yyyy-mm-dd. None if empty."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    value = (value or "").strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(value)


def parse_amount(value):
    """Amount from a cell: a number (Excel), 1.234,56 or 1234.56. 0.0 if empty."""
    if isinstance(value, (int, float)):
        return float(value)
    value = re.sub(r"[\s€]", "", value or "")
    if not value:
        return 0.0
    if "," in value and "." in value:
        thousands = "." if value.rfind(",") > value.rfind(".") else ","
        value = value.replace(thousands, "")
    return float(value.replace(",", "."))


def is_valid_be_number(value):
    """KBO number or Belgian VAT number: 10 digits, the last two a mod-97 check."""
    digits = re.sub(r"\D", "", value or "")
    return len(digits) == 10 and digits[0] in "01" and 97 - int(digits[:8]) % 97 == int(digits[8:])


def _cell(value):
    """Cell value: strings stripped, None empty; numbers and dates from Excel stay as they are."""
    if value is None:
        return ""
    return value.strip() if isinstance(value, str) else value


class VmeMigration(models.Model):
    _name = "vme.migration"
    _inherit = ["mail.thread"]
    _description = "Overstap van een VME uit een ander pakket"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Naam", required=True, default=lambda self: self.env._("Nieuwe overstap"))
    source_format = fields.Selection(
        [("standard", "Eigen formaat (VME-platform)")],
        string="Formaat", required=True, default="standard",
        help="Het formaat van de exportbestanden. Voor een ander pakket komt hier later een omzetter bij.",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Exportbestanden",
        help="De CSV-bestanden (of één Excel-bestand met tabbladen, of een zip), plus de PDF's "
             "van de oudere jaren.",
    )
    state = fields.Selection(
        [("draft", "Nieuw"), ("checked", "Proefrun gedaan"), ("done", "Geïmporteerd")],
        string="Status", default="draft", required=True, tracking=True,
    )
    report_html = fields.Html(string="Rapport", sanitize=False, readonly=True)
    error_count = fields.Integer(string="Fouten", readonly=True)
    warning_count = fields.Integer(string="Waarschuwingen", readonly=True)
    transition_date = fields.Date(string="Overstapdatum", readonly=True)
    association_id = fields.Many2one("vme.association", string="VME", readonly=True)
    opening_move_id = fields.Many2one("account.move", string="Openingsboeking", readonly=True)

    def write(self, vals):
        # New files invalidate the dry run.
        if {"attachment_ids", "source_format"} & set(vals) and "state" not in vals:
            vals["state"] = "draft"
            if any(m.state == "done" for m in self):
                raise UserError(self.env._("Deze overstap is al geïmporteerd."))
        return super().write(vals)

    # --- Reading the files ---

    def _read_files(self):
        """Return ({table: [row dict]}, [(file name, pdf bytes)], [message])."""
        tables, pdfs, messages = {}, [], []
        for attachment in self.attachment_ids:
            name, raw = attachment.name or "", attachment.raw or b""
            self._read_file(name, raw, tables, pdfs, messages)
        return tables, pdfs, messages

    def _read_file(self, name, raw, tables, pdfs, messages):
        lower = name.lower()
        base = lower.rsplit("/", 1)[-1]
        if lower.endswith("/") or not base:
            return
        if lower.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for member in archive.namelist():
                    if not member.endswith("/") and not member.rsplit("/", 1)[-1].startswith("."):
                        self._read_file(member, archive.read(member), tables, pdfs, messages)
        elif lower.endswith(".xlsx"):
            self._read_workbook(name, raw, tables, messages)
        elif lower.endswith(".csv") and "archief/" not in lower:
            self._add_table(base[:-4], name, self._read_csv(raw), tables, messages)
        elif lower.endswith(".pdf") or "archief/" in lower:
            if raw.startswith(b"%PDF"):
                pdfs.append((base, raw))
            else:
                messages.append(("warning", base, 0, self.env._(
                    "Is geen PDF en wordt niet in het archief bewaard.")))
        else:
            messages.append(("warning", base, 0, self.env._("Onbekend bestand; wordt overgeslagen.")))

    def _read_csv(self, raw):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")  # Excel on Windows saves CSV in this encoding
        first_line = text.split("\n", 1)[0]
        delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
        return list(csv.reader(io.StringIO(text), delimiter=delimiter))

    def _read_workbook(self, name, raw, tables, messages):
        import openpyxl  # noqa: PLC0415 - only needed for Excel files

        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        for sheet in workbook.worksheets:
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            self._add_table(sheet.title.strip().lower(), f"{name} > {sheet.title}", rows, tables, messages)

    def _add_table(self, table, source, rows, tables, messages):
        if table not in TABLES:
            messages.append(("warning", source, 0, self.env._("Onbekende tabel; wordt overgeslagen.")))
            return
        if table in tables:
            messages.append(("error", source, 0, self.env._("Tabel %s komt twee keer voor.", table)))
            return
        rows = [[_cell(value) for value in row] for row in rows]
        rows = [row for row in rows if any(value not in ("", None) for value in row)]
        if not rows:
            tables[table] = {"source": source, "columns": [], "rows": []}
            return
        columns = [str(value).strip().lower() for value in rows[0]]
        result = []
        for line, row in enumerate(rows[1:], start=2):
            record = {column: row[i] if i < len(row) else "" for i, column in enumerate(columns) if column}
            record["_line"] = line
            result.append(record)
        tables[table] = {"source": source, "columns": columns, "rows": result}

    def _convert_files(self, tables):
        """Turn the tables of the source package into our own format."""
        return getattr(self, f"_convert_{self.source_format}")(tables)

    def _convert_standard(self, tables):
        return tables

    # --- Checking ---

    def _check(self):
        """Read and check the files. Returns (messages, plan, ok); writes nothing.

        messages: [(level, file, line, text)] with level error, warning or info.
        plan: the cleaned data the import uses; only complete when ok (no errors).
        """
        self.ensure_one()
        tables, pdfs, messages = self._read_files()
        tables = self._convert_files(tables)
        checker = _Checker(self.env, tables, messages)
        plan = checker.run()
        plan["archive"] = pdfs
        ok = not any(level == "error" for level, *_rest in messages)
        return messages, plan, ok

    def action_dry_run(self):
        for migration in self:
            messages, plan, ok = migration._check()
            migration._store_report(messages, plan, ok)
            migration.state = "checked"
        return True

    def _store_report(self, messages, plan, ok):
        errors = [m for m in messages if m[0] == "error"]
        warnings = [m for m in messages if m[0] == "warning"]
        vals = {
            "error_count": len(errors),
            "warning_count": len(warnings),
            "report_html": self._report_html(messages, plan if ok else None),
        }
        if plan.get("vme") and plan["vme"]["name"]:
            vals["transition_date"] = plan["vme"]["date"]
            vals["name"] = self.env._("Overstap %s", plan["vme"]["name"])
        super(VmeMigration, self).write(vals)  # keep the state, see write()

    def _report_html(self, messages, plan):
        labels = {"error": self.env._("Fout"), "warning": self.env._("Waarschuwing"), "info": self.env._("Info")}
        classes = {"error": "text-bg-danger", "warning": "text-bg-warning", "info": "text-bg-info"}
        parts = []
        if plan:
            parts.append(Markup("<p><strong>%s</strong></p><ul>%s</ul>") % (
                self.env._("Klaar om te importeren:") if self.state != "done" else self.env._("Geïmporteerd:"),
                Markup("").join(Markup("<li>%s</li>") % line for line in self._plan_summary(plan)),
            ))
            parts.append(self._opening_html(plan))
        elif any(m[0] == "error" for m in messages):
            parts.append(Markup("<p class='text-danger'><strong>%s</strong></p>") % self.env._(
                "Verbeter eerst de fouten in de exportbestanden en doe dan een nieuwe proefrun."))
        if messages:
            order = {"error": 0, "warning": 1, "info": 2}
            rows = Markup("").join(
                Markup("<tr><td><span class='badge %s'>%s</span></td><td>%s</td><td>%s</td><td>%s</td></tr>") % (
                    classes[level], labels[level], source, line or "", text)
                for level, source, line, text in sorted(messages, key=lambda m: (order[m[0]], str(m[1]), m[2]))
            )
            parts.append(Markup(
                "<table class='table table-sm'><thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead>"
                "<tbody>%s</tbody></table>") % (
                self.env._("Soort"), self.env._("Bestand"), self.env._("Regel"), self.env._("Melding"), rows))
        else:
            parts.append(Markup("<p>%s</p>") % self.env._("Geen fouten of waarschuwingen."))
        return Markup("").join(parts)

    def _opening_html(self, plan):
        """The opening entry as a table, so it can be checked before the import."""
        if not plan["opening"]:
            return Markup("")
        currency = self.env.ref("base.EUR")
        kinds = {
            "bank_werkkapitaal": self.env._("Bank werkkapitaal"), "bank_reservekapitaal": self.env._("Bank reservekapitaal"),
            "fonds_werkkapitaal": self.env._("Werkkapitaal"), "fonds_reservekapitaal": self.env._("Reservekapitaal"),
            "eigenaar": self.env._("Eigenaar"), "leverancier": self.env._("Leverancier"), "rekening": self.env._("Rekening"),
        }
        names = {**{code: o["name"] for code, o in plan["owners"].items()},
                 **{code: s["name"] for code, s in plan["suppliers"].items()}}

        def money(amount):
            return formatLang(self.env, amount, currency_obj=currency) if amount else ""

        rows = Markup("").join(
            Markup("<tr><td>%s</td><td>%s</td><td>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td></tr>") % (
                kinds[row["kind"]], names.get(row["code"], row["code"]) if row["kind"] in ("eigenaar", "leverancier") else row["code"],
                row["label"], money(row["debit"]), money(row["credit"]))
            for row in plan["opening"]
        )
        total = Markup("<tr class='fw-bold'><td colspan='3'>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td></tr>") % (
            self.env._("Totaal"), money(sum(r["debit"] for r in plan["opening"])),
            money(sum(r["credit"] for r in plan["opening"])))
        return Markup(
            "<p><strong>%s</strong></p><table class='table table-sm'><thead><tr><th>%s</th><th>%s</th><th>%s</th>"
            "<th class='text-end'>%s</th><th class='text-end'>%s</th></tr></thead><tbody>%s%s</tbody></table>") % (
            self.env._("Openingsboeking op %s", plan["vme"]["date"].strftime("%d/%m/%Y")),
            self.env._("Soort"), self.env._("Wie"), self.env._("Omschrijving"), self.env._("Debet"), self.env._("Credit"),
            rows, total)

    def _plan_summary(self, plan):
        currency = self.env.ref("base.EUR")
        debit = sum(row["debit"] for row in plan["opening"])
        return [
            self.env._("VME %(name)s, overstapdatum %(date)s", name=plan["vme"]["name"],
                       date=plan["vme"]["date"].strftime("%d/%m/%Y")),
            self.env._("%s kavels", len(plan["lots"])),
            self.env._("%(owners)s eigenaars en %(ownerships)s eigendommen",
                       owners=len(plan["owners"]), ownerships=len(plan["ownerships"])),
            self.env._("%s verdeelsleutels", len(plan["keys"])),
            self.env._("%(count)s leveranciers (%(existing)s al gekend)", count=len(plan["suppliers"]),
                       existing=len([s for s in plan["suppliers"].values() if s["partner_id"]])),
            self.env._("Openingsboeking: %(count)s regels, totaal %(total)s", count=len(plan["opening"]),
                       total=formatLang(self.env, debit, currency_obj=currency)),
            self.env._("%s PDF's voor het archief", len(plan["archive"])),
        ]

    # --- Import ---

    def action_import(self):
        self.ensure_one()
        if self.state == "done":
            raise UserError(self.env._("Deze overstap is al geïmporteerd."))
        messages, plan, ok = self._check()
        if not ok:
            self._store_report(messages, plan, ok)
            self.state = "checked"
            # Commit the report; the user then sees why nothing was imported.
            return True
        vme, move = self._import(plan)
        self.write({"state": "done", "association_id": vme.id, "opening_move_id": move.id})
        self._store_report(messages, plan, ok)
        self.message_post(body=self.env._("VME %s geïmporteerd.", vme.name))
        return self.action_open_association()

    def _import(self, plan):
        data = plan["vme"]
        vme = self.env["vme.association"].create({
            "name": data["name"], "kbo_number": data["kbo"], "street": data["street"],
            "zip": data["zip"], "city": data["city"],
        })
        company = vme.company_id
        # The chart normally loads when the transaction commits; the opening entry needs it now.
        vme._load_vme_chart(company.id)

        Bank = self.env["res.partner.bank"]
        banks = {}
        for fund in ("working", "reserve"):
            if data[f"iban_{fund}"]:
                banks[fund] = Bank.create({"acc_number": data[f"iban_{fund}"], "partner_id": vme.partner_id.id})
        vme.write({
            "working_capital_bank_id": banks.get("working", Bank).id,
            "reserve_capital_bank_id": banks.get("reserve", Bank).id,
        })
        # Trusting needs the right permissions; otherwise the VME form asks to confirm them.
        trusted = [bank for bank in banks.values() if bank._user_can_trust()]
        for bank in trusted:
            bank.allow_out_payment = True
        journals = vme._ensure_fund_bank_journals()[vme] if len(banks) == 2 else {}

        lots = {}
        for sequence, lot in enumerate(plan["lots"]):
            lots[lot["name"]] = self.env["vme.lot"].create({
                "association_id": vme.id, "sequence": sequence, "name": lot["name"],
                "lot_type": lot["lot_type"], "floor": lot["floor"],
            })
        be = self.env.ref("base.be")
        owners = {}
        for code, owner in plan["owners"].items():
            owners[code] = self.env["res.partner"].create({
                "name": owner["name"], "ref": code, "email": owner["email"] or False,
                "phone": owner["phone"] or False, "street": owner["street"] or False,
                "zip": owner["zip"] or False, "city": owner["city"] or False, "country_id": be.id,
            })
        self.env["vme.ownership"].create([{
            "lot_id": lots[o["lot"]].id, "partner_id": owners[o["owner"]].id,
            "date_start": o["start"], "date_end": o["end"],
        } for o in plan["ownerships"]])
        keys = {}
        for sequence, (name, key) in enumerate(plan["keys"].items()):
            keys[name] = self.env["vme.key"].create({
                "name": name, "association_id": vme.id, "sequence": sequence,
                "key_type": key["key_type"], "total_shares": key["total"],
                "line_ids": [Command.create({"lot_id": lots[lot].id, "shares": shares})
                             for lot, shares in key["lines"].items()],
            })
        suppliers = {}
        for code, supplier in plan["suppliers"].items():
            partner = self.env["res.partner"].browse(supplier["partner_id"])
            if not partner:
                partner = self.env["res.partner"].create({
                    "name": supplier["name"], "is_company": True, "vat": supplier["vat"] or False,
                    "email": supplier["email"] or False, "country_id": be.id, "supplier_rank": 1,
                })
            if supplier["iban"] and not partner.bank_ids.filtered(
                    lambda b, iban=supplier["iban"]: b.sanitized_acc_number == iban):
                Bank.create({"acc_number": supplier["iban"], "partner_id": partner.id})
            if supplier["key"]:
                self.env["vme.distribution.rule"].create({
                    "association_id": vme.id, "partner_id": partner.id, "key_id": keys[supplier["key"]].id,
                })
            suppliers[code] = partner

        move = self._create_opening_move(vme, plan, journals, owners, suppliers)
        self._archive_documents(vme, plan["archive"])
        vme.message_post(body=self.env._(
            "Overgenomen uit een ander pakket via %(migration)s, overstapdatum %(date)s.",
            migration=self.name, date=data["date"].strftime("%d/%m/%Y")))
        return vme, move

    def _create_opening_move(self, vme, plan, journals, owners, suppliers):
        """One posted entry with all balances on the transition date."""
        company = vme.company_id
        Account = self.env["account.account"].with_company(company)

        def account(code):
            found = Account.search([("company_ids", "in", company.id), ("code", "=", code)], limit=1)
            if not found:
                raise UserError(self.env._("Rekening %s bestaat niet in het rekeningstelsel.", code))
            return found

        lines = []
        for row in plan["opening"]:
            kind, partner = row["kind"], self.env["res.partner"]
            if kind in ("bank_werkkapitaal", "bank_reservekapitaal"):
                acc = journals["working" if kind == "bank_werkkapitaal" else "reserve"].default_account_id
            elif kind in ("fonds_werkkapitaal", "fonds_reservekapitaal"):
                # LEGAL-CHECK: art. 3.86 §3 BW - the reserve fund belongs to the VME and goes
                # over in full; it is not settled with the owners.
                acc = account(VME_FUND_ACCOUNTS["working" if kind == "fonds_werkkapitaal" else "reserve"][0])
            elif kind == "eigenaar":
                partner = owners[row["code"]]
                acc = partner.with_company(company).property_account_receivable_id
            elif kind == "leverancier":
                partner = suppliers[row["code"]]
                acc = partner.with_company(company).property_account_payable_id
            else:
                acc = account(row["code"])
            lines.append(Command.create({
                "name": row["label"], "account_id": acc.id, "partner_id": partner.id or False,
                "debit": row["debit"], "credit": row["credit"],
            }))
        if not lines:
            return self.env["account.move"]
        journal = self.env["account.journal"].with_company(company).search(
            [("company_id", "=", company.id), ("type", "=", "general")], order="sequence, id", limit=1)
        move = self.env["account.move"].with_company(company).create({
            "move_type": "entry", "journal_id": journal.id, "date": plan["vme"]["date"],
            "ref": self.env._("Openingsbalans overstap %s", plan["vme"]["date"].strftime("%d/%m/%Y")),
            "line_ids": lines,
        })
        move.action_post()
        return move

    def _archive_documents(self, vme, pdfs):
        """Older years only come over as PDF, attached to the VME."""
        if not pdfs:
            return
        # LEGAL-CHECK: art. III.88 WER - accounting documents are kept for 7 years (check whether
        # 10 years applies); art. 3.89 §5, 13° BW - the previous syndic hands over the archive.
        attachments = self.env["ir.attachment"].create([{
            "name": name, "raw": raw, "res_model": "vme.association", "res_id": vme.id,
            "mimetype": "application/pdf",
        } for name, raw in pdfs])
        vme.message_post(
            body=self.env._("Archief uit het vorige pakket: %s", ", ".join(name for name, _raw in pdfs)),
            attachment_ids=attachments.ids,
        )

    # --- Navigation ---

    def action_open_association(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "vme.association",
            "res_id": self.association_id.id, "view_mode": "form",
        }

    def action_open_opening_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "account.move",
            "res_id": self.opening_move_id.id, "view_mode": "form",
        }


class _Checker:
    """Checks the tables and builds the import plan. Reads the database, never writes."""

    def __init__(self, env, tables, messages):
        self.env = env
        self.tables = tables
        self.messages = messages
        self._ = env._

    def add(self, level, table, line, text):
        source = self.tables.get(table, {}).get("source", f"{table}.csv")
        self.messages.append((level, source, line, text))

    def rows(self, table):
        return self.tables.get(table, {}).get("rows", [])

    def run(self):
        plan = {"vme": None, "lots": [], "owners": {}, "ownerships": [], "keys": {},
                "suppliers": {}, "opening": []}
        if not self._check_tables():
            return plan
        plan["vme"] = self._check_vme()
        plan["lots"] = self._check_lots()
        lot_names = {lot["name"] for lot in plan["lots"]}
        plan["owners"] = self._check_owners()
        plan["ownerships"] = self._check_ownerships(lot_names, plan["owners"])
        plan["keys"] = self._check_keys(lot_names)
        plan["suppliers"] = self._check_suppliers(plan["keys"])
        plan["opening"] = self._check_opening(plan)
        self._check_coverage(plan)
        return plan

    def _check_tables(self):
        ok = True
        for table, columns in REQUIRED_COLUMNS.items():
            if table not in self.tables:
                if table in OPTIONAL_TABLES:
                    self.add("warning", table, 0, self._("Bestand %s.csv ontbreekt; er worden geen leveranciers "
                                                         "overgenomen.", table))
                else:
                    self.add("error", table, 0, self._("Bestand %s.csv ontbreekt.", table))
                    ok = False
                continue
            missing = [c for c in columns if c not in self.tables[table]["columns"]]
            if missing:
                self.add("error", table, 1, self._("Kolom(men) ontbreken: %s.", ", ".join(missing)))
                ok = False
        return ok

    def _text(self, row, column):
        value = row.get(column, "")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value).strip() if value not in (None, "") else ""

    def _required(self, table, row, columns):
        missing = [c for c in columns if not self._text(row, c)]
        if missing:
            self.add("error", table, row["_line"], self._("Niet ingevuld: %s.", ", ".join(missing)))
        return not missing

    def _date(self, table, row, column):
        try:
            return parse_date(row.get(column))
        except ValueError:
            self.add("error", table, row["_line"], self._(
                "Ongeldige datum in %(column)s: %(value)s (gebruik dd/mm/jjjj).", column=column, value=row.get(column)))
            return None

    def _amount(self, table, row, column):
        try:
            return parse_amount(row.get(column))
        except ValueError:
            self.add("error", table, row["_line"], self._(
                "Ongeldig bedrag in %(column)s: %(value)s.", column=column, value=row.get(column)))
            return None

    def _iban(self, table, row, column):
        value = normalize_iban(self._text(row, column)).upper()
        if not value:
            return ""
        try:
            validate_iban(value)
        except ValidationError:
            self.add("error", table, row["_line"], self._("Ongeldige IBAN in %(column)s: %(value)s.",
                                                          column=column, value=self._text(row, column)))
            return ""
        return value

    def _check_vme(self):
        rows = self.rows("vme")
        if len(rows) != 1:
            self.add("error", "vme", 0, self._("vme.csv moet precies één VME bevatten (nu %s).", len(rows)))
            if not rows:
                return None
        row = rows[0]
        self._required("vme", row, REQUIRED_COLUMNS["vme"])
        name, kbo = self._text(row, "naam"), self._text(row, "kbo")
        Association = self.env["vme.association"].sudo().with_context(active_test=False)
        if name and Association.search_count([("name", "=ilike", name)]):
            self.add("error", "vme", row["_line"], self._("Er bestaat al een VME met de naam %s.", name))
        if kbo and not is_valid_be_number(kbo):
            self.add("error", "vme", row["_line"], self._("Ongeldig KBO-nummer: %s.", kbo))
        elif kbo:
            digits = re.sub(r"\D", "", kbo)
            for other in Association.search([("kbo_number", "!=", False)]):
                if re.sub(r"\D", "", other.kbo_number) == digits:
                    self.add("error", "vme", row["_line"], self._(
                        "KBO-nummer %(kbo)s is al in gebruik door %(vme)s.", kbo=kbo, vme=other.name))
        ibans = {}
        for fund, column in (("working", "werkkapitaal"), ("reserve", "reservekapitaal")):
            ibans[fund] = self._iban("vme", row, f"iban_{column}")
            if not self._text(row, f"iban_{column}"):
                self.add("warning", "vme", row["_line"], self._(
                    "Geen bankrekening voor het %s: vul ze na de import in, anders lukken de "
                    "provisieoproepen niet.", column))
        if ibans["working"] and ibans["working"] == ibans["reserve"]:
            # LEGAL-CHECK: art. 3.89 §5 BW - working and reserve capital on separate accounts.
            self.add("error", "vme", row["_line"], self._(
                "Werkkapitaal en reservekapitaal moeten op aparte bankrekeningen staan."))
        Bank = self.env["res.partner.bank"].sudo().with_context(active_test=False)
        for iban in filter(None, ibans.values()):
            existing = Bank.search([("sanitized_acc_number", "=", iban)], limit=1)
            if existing:
                self.add("error", "vme", row["_line"], self._(
                    "Rekening %(iban)s is al gekend bij %(partner)s.", iban=iban, partner=existing.partner_id.display_name))
        return {
            "name": name, "kbo": kbo, "street": self._text(row, "straat"), "zip": self._text(row, "postcode"),
            "city": self._text(row, "gemeente"), "iban_working": ibans["working"], "iban_reserve": ibans["reserve"],
            "date": self._date("vme", row, "overstapdatum"),
        }

    def _check_lots(self):
        lots, seen = [], set()
        for row in self.rows("kavels"):
            if not self._required("kavels", row, ["kavel"]):
                continue
            name = self._text(row, "kavel")
            if name in seen:
                self.add("error", "kavels", row["_line"], self._("Kavel %s komt twee keer voor.", name))
                continue
            seen.add(name)
            lot_type = self._text(row, "type").lower() or "appartement"
            if lot_type not in LOT_TYPES:
                self.add("error", "kavels", row["_line"], self._(
                    "Onbekend type %(type)s; kies uit %(types)s.", type=lot_type, types=", ".join(LOT_TYPES)))
                continue
            lots.append({"name": name, "lot_type": LOT_TYPES[lot_type], "floor": self._text(row, "verdieping")})
        if not lots:
            self.add("error", "kavels", 0, self._("Er zijn geen kavels."))
        return lots

    def _check_owners(self):
        owners = {}
        for row in self.rows("eigenaars"):
            if not self._required("eigenaars", row, ["code", "naam"]):
                continue
            code = self._text(row, "code")
            if code in owners:
                self.add("error", "eigenaars", row["_line"], self._("Eigenaar %s komt twee keer voor.", code))
                continue
            email = self._text(row, "email")
            if not email:
                self.add("warning", "eigenaars", row["_line"], self._(
                    "Eigenaar %s heeft geen e-mailadres.", self._text(row, "naam")))
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                self.add("error", "eigenaars", row["_line"], self._("Ongeldig e-mailadres: %s.", email))
            owners[code] = {
                "name": self._text(row, "naam"), "email": email, "phone": self._text(row, "telefoon"),
                "street": self._text(row, "straat"), "zip": self._text(row, "postcode"),
                "city": self._text(row, "gemeente"), "_line": row["_line"],
            }
        return owners

    def _check_ownerships(self, lot_names, owners):
        ownerships = []
        for row in self.rows("eigendommen"):
            if not self._required("eigendommen", row, ["kavel", "eigenaar", "begindatum"]):
                continue
            lot, owner = self._text(row, "kavel"), self._text(row, "eigenaar")
            ok = True
            if lot not in lot_names:
                self.add("error", "eigendommen", row["_line"], self._("Kavel %s bestaat niet in kavels.csv.", lot))
                ok = False
            if owner not in owners:
                self.add("error", "eigendommen", row["_line"], self._(
                    "Eigenaar %s bestaat niet in eigenaars.csv.", owner))
                ok = False
            start, end = self._date("eigendommen", row, "begindatum"), self._date("eigendommen", row, "einddatum")
            if start and end and end < start:
                self.add("error", "eigendommen", row["_line"], self._("De einddatum ligt vóór de begindatum."))
                ok = False
            if ok and start:
                ownerships.append({"lot": lot, "owner": owner, "start": start, "end": end, "_line": row["_line"]})
        # One owner per lot at a time, as in vme.ownership.
        by_lot = {}
        for ownership in ownerships:
            by_lot.setdefault(ownership["lot"], []).append(ownership)
        for lot, items in by_lot.items():
            items.sort(key=lambda o: o["start"])
            for previous, current in zip(items, items[1:]):
                if not previous["end"] or previous["end"] >= current["start"]:
                    self.add("error", "eigendommen", current["_line"], self._(
                        "Kavel %(lot)s heeft al een eigenaar in deze periode (%(owner)s).",
                        lot=lot, owner=owners[previous["owner"]]["name"]))
        return ownerships

    def _check_keys(self, lot_names):
        keys = {}
        for row in self.rows("sleutels"):
            if not self._required("sleutels", row, REQUIRED_COLUMNS["sleutels"]):
                continue
            name, lot = self._text(row, "sleutel"), self._text(row, "kavel")
            key_type = self._text(row, "soort").lower()
            total, shares = self._amount("sleutels", row, "totaal"), self._amount("sleutels", row, "quotiteit")
            if key_type not in KEY_TYPES:
                self.add("error", "sleutels", row["_line"], self._(
                    "Onbekende soort %(type)s; kies uit %(types)s.", type=key_type,
                    types="algemeen, lift, verwarming, verbruik, andere"))
                continue
            if total is None or shares is None:
                continue
            key = keys.setdefault(name, {"key_type": KEY_TYPES[key_type], "total": total, "lines": {},
                                         "_line": row["_line"]})
            if KEY_TYPES[key_type] != key["key_type"] or float_compare(total, key["total"], SHARES_PRECISION):
                self.add("error", "sleutels", row["_line"], self._(
                    "Sleutel %s heeft niet op elke regel dezelfde soort en hetzelfde totaal.", name))
            if lot not in lot_names:
                self.add("error", "sleutels", row["_line"], self._("Kavel %s bestaat niet in kavels.csv.", lot))
            elif lot in key["lines"]:
                self.add("error", "sleutels", row["_line"], self._(
                    "Kavel %(lot)s staat twee keer in sleutel %(key)s.", lot=lot, key=name))
            else:
                key["lines"][lot] = shares
        for name, key in keys.items():
            # LEGAL-CHECK: art. 3.85 §1 BW - the shares of a key must add up to its total.
            total_sum = sum(key["lines"].values())
            if float_compare(key["total"], 0.0, SHARES_PRECISION) <= 0:
                self.add("error", "sleutels", key["_line"], self._("Het totaal van sleutel %s moet groter zijn dan 0.", name))
            elif float_compare(total_sum, key["total"], SHARES_PRECISION):
                self.add("error", "sleutels", key["_line"], self._(
                    "De quotiteiten van sleutel %(key)s tellen op tot %(sum)s, maar het totaal is %(total)s "
                    "(verschil: %(diff)s).", key=name, sum=f"{total_sum:g}", total=f"{key['total']:g}",
                    diff=f"{key['total'] - total_sum:g}"))
        general = [name for name, key in keys.items() if key["key_type"] == "general"]
        if not general:
            self.add("error", "sleutels", 0, self._(
                "Er is geen sleutel met soort 'algemeen'; die is nodig voor de provisieoproepen."))
        elif len(general) > 1:
            self.add("warning", "sleutels", 0, self._(
                "Er zijn %(count)s algemene sleutels; de provisieoproepen gebruiken %(first)s.",
                count=len(general), first=general[0]))
        return keys

    def _check_suppliers(self, keys):
        suppliers = {}
        Partner = self.env["res.partner"].sudo()
        for row in self.rows("leveranciers"):
            if not self._required("leveranciers", row, ["code", "naam"]):
                continue
            code, name = self._text(row, "code"), self._text(row, "naam")
            if code in suppliers:
                self.add("error", "leveranciers", row["_line"], self._("Leverancier %s komt twee keer voor.", code))
                continue
            vat = re.sub(r"[\s.\-]", "", self._text(row, "btw")).upper()
            if vat and vat.isdigit():
                vat = f"BE{vat.zfill(10)}"
            partner = Partner.browse()
            if not vat:
                self.add("warning", "leveranciers", row["_line"], self._(
                    "Leverancier %s heeft geen btw-nummer; Peppol-facturen worden dan niet herkend.", name))
            elif vat.startswith("BE") and not is_valid_be_number(vat[2:]):
                self.add("error", "leveranciers", row["_line"], self._("Ongeldig btw-nummer: %s.", vat))
            else:
                partner = Partner.search([("vat", "=", vat), ("parent_id", "=", False)], limit=1)
                if partner:
                    self.add("info", "leveranciers", row["_line"], self._(
                        "%(name)s bestaat al als %(partner)s en wordt hergebruikt.", name=name, partner=partner.name))
            key = self._text(row, "sleutel")
            if key and key not in keys:
                self.add("error", "leveranciers", row["_line"], self._(
                    "Sleutel %s bestaat niet in sleutels.csv.", key))
            suppliers[code] = {
                "name": name, "vat": vat, "email": self._text(row, "email"),
                "iban": self._iban("leveranciers", row, "iban"), "key": key, "partner_id": partner.id,
            }
        return suppliers

    def _check_opening(self, plan):
        lines, balance = [], 0.0
        vme = plan["vme"] or {}
        for row in self.rows("openingsbalans"):
            if not self._required("openingsbalans", row, ["soort", "bedrag"]):
                continue
            kind, code = self._text(row, "soort").lower(), self._text(row, "code")
            amount = self._amount("openingsbalans", row, "bedrag")
            if kind not in OPENING_KINDS:
                self.add("error", "openingsbalans", row["_line"], self._(
                    "Onbekende soort %(kind)s; kies uit %(kinds)s.", kind=kind, kinds=", ".join(OPENING_KINDS)))
                continue
            if amount is None or float_is_zero(amount, precision_digits=2):
                continue
            label = self._text(row, "omschrijving")
            if kind == "eigenaar":
                if code not in plan["owners"]:
                    self.add("error", "openingsbalans", row["_line"], self._(
                        "Eigenaar %s bestaat niet in eigenaars.csv.", code))
                    continue
                label = label or self._("Openingssaldo %s", plan["owners"][code]["name"])
            elif kind == "leverancier":
                if code not in plan["suppliers"]:
                    self.add("error", "openingsbalans", row["_line"], self._(
                        "Leverancier %s bestaat niet in leveranciers.csv.", code))
                    continue
                label = label or self._("Openingssaldo %s", plan["suppliers"][code]["name"])
            elif kind == "rekening":
                if not re.fullmatch(r"\d{6}", code):
                    self.add("error", "openingsbalans", row["_line"], self._(
                        "Vul bij soort 'rekening' een rekeningnummer van 6 cijfers in (nu: %s).", code or "-"))
                    continue
                if code[0] in "45" and code[:3] not in ("490", "491", "492", "493", "499"):
                    self.add("error", "openingsbalans", row["_line"], self._(
                        "Rekening %s: gebruik voor bank, eigenaars en leveranciers hun eigen soort.", code))
                    continue
            elif kind.startswith("bank_") and not (vme.get("iban_working") and vme.get("iban_reserve")):
                # The bank balances go to one bank journal per fund, which needs both accounts.
                missing = [column for column, fund in (("iban_werkkapitaal", "working"), ("iban_reservekapitaal", "reserve"))
                           if not vme.get(f"iban_{fund}")]
                self.add("error", "openingsbalans", row["_line"], self._(
                    "Er is een banksaldo, maar in vme.csv ontbreekt een geldige bankrekening: %s.", ", ".join(missing)))
            signed = amount * OPENING_KINDS[kind]
            balance += signed
            lines.append({
                "kind": kind, "code": code, "label": label or self._("Openingssaldo %s", kind.replace("_", " ")),
                "debit": round(max(signed, 0.0), 2), "credit": round(max(-signed, 0.0), 2),
            })
        if not float_is_zero(balance, precision_digits=2):
            self.add("error", "openingsbalans", 0, self._(
                "De openingsbalans is niet in evenwicht: debet min credit is %s. Bank en eigenaars staan "
                "aan de debetkant, fondsen en leveranciers aan de creditkant.", f"{balance:.2f}"))
        if not lines:
            self.add("warning", "openingsbalans", 0, self._("De openingsbalans is leeg; er komt geen openingsboeking."))
        return lines

    def _check_coverage(self, plan):
        owned = {o["owner"] for o in plan["ownerships"]}
        for code, owner in plan["owners"].items():
            if code not in owned:
                self.add("warning", "eigenaars", owner["_line"], self._(
                    "Eigenaar %s heeft geen kavel.", owner["name"]))
        transition = (plan["vme"] or {}).get("date")
        in_keys = {lot for key in plan["keys"].values() for lot in key["lines"]}
        general = {lot for key in plan["keys"].values() if key["key_type"] == "general" for lot in key["lines"]}
        for lot in plan["lots"]:
            name = lot["name"]
            if transition and not any(
                o["lot"] == name and o["start"] <= transition and (not o["end"] or o["end"] >= transition)
                for o in plan["ownerships"]
            ):
                self.add("warning", "kavels", 0, self._(
                    "Kavel %(lot)s heeft geen eigenaar op de overstapdatum.", lot=name))
            if name not in in_keys:
                self.add("warning", "sleutels", 0, self._("Kavel %s staat in geen enkele sleutel.", name))
            elif general and name not in general:
                self.add("warning", "sleutels", 0, self._("Kavel %s staat niet in de algemene sleutel.", name))
