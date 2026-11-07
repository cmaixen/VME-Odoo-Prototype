"""Taking over a building: the deed and the minutes read by a language model, as a proposal.

A staff member adds the deed (text PDF or scan) and the minutes of the last general assemblies
to a takeover (vme.migration). Odoo marks it "to read"; the script ai/overname.py reads the PDFs
outside Odoo and sends the readings to vme_ai_apply_takeover. Each value becomes a proposal line
with the page and fragment it comes from and a confidence. The staff member accepts, corrects or
rejects every line next to its fragment.

The accepted lines become tables in the documented import format (vme, kavels, sleutels, werken,
procedures, mandaten), so the dry run and the import check them like exported files: the shares
of a key must add up to its total, every lot needs an owner, and so on. Lines that are still
proposed block the import. Nothing is created before the import.
"""
import re
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .vme_migration import FINANCING, KEY_TYPES, LOT_TYPES, MANDATE_ROLES, TABLES, parse_amount

CONFIDENCES = [("high", "Hoog"), ("medium", "Gemiddeld"), ("low", "Laag")]
PROPOSAL_KINDS = [
    ("vme", "VME"), ("lot", "Kavel"), ("share", "Aandeel"),
    ("works", "Werken"), ("procedure", "Procedure"), ("mandate", "Mandaat"),
]
# The codes of the reading (ai/overname_reader.py) are our selection codes; the import format is Dutch.
LOT_TYPE_NAMES = {code: name for name, code in LOT_TYPES.items()}
KEY_TYPE_NAMES = {"general": "algemeen", "elevator": "lift", "heating": "verwarming",
                  "consumption": "verbruik", "other": "andere"}
FINANCING_NAMES = {code: name for name, code in FINANCING.items()}
ROLE_NAMES = {code: name for name, code in MANDATE_ROLES.items()}
# Fields of the VME a line can fill; the first five come from the documents, the others the staff member adds.
VME_FIELDS = [
    ("naam", "Naam"), ("kbo", "KBO-nummer"), ("straat", "Straat"), ("postcode", "Postcode"),
    ("gemeente", "Gemeente"), ("overstapdatum", "Overstapdatum"),
    ("iban_werkkapitaal", "IBAN werkkapitaal"), ("iban_reservekapitaal", "IBAN reservekapitaal"),
]
# Fields that hold what was read; changing one marks the line as corrected by a person.
VALUE_FIELDS = {"vme_field", "value", "lot_name", "lot_type", "floor", "key_name", "key_type", "key_total",
                "majority", "description", "amount", "financing", "counterparty", "status_text", "role",
                "person", "date", "date_end"}
SOURCE = "Voorstel uit de documenten"


def _iso_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


class VmeMigrationProposal(models.Model):
    _name = "vme.migration.proposal"
    _description = "Voorstel uit de basisakte of de notulen bij een overstap"
    _order = "migration_id, sequence, id"

    migration_id = fields.Many2one("vme.migration", string="Overstap", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(string="Nr.", default=0)
    kind = fields.Selection(PROPOSAL_KINDS, string="Soort", required=True, default="vme")
    origin = fields.Selection([("ai", "Gelezen door AI"), ("manual", "Toegevoegd door medewerker")],
                              string="Herkomst", required=True, default="manual", readonly=True)
    state = fields.Selection(
        [("proposed", "Na te kijken"), ("accepted", "Aanvaard"), ("rejected", "Geweigerd")],
        string="Status", required=True, default="accepted",
        help="Een regel die de AI las, start als 'Na te kijken'. Een regel die je zelf toevoegt, geldt als aanvaard.")
    edited = fields.Boolean(string="Verbeterd", readonly=True,
                            help="Een medewerker heeft de gelezen waarde aangepast.")

    # What was read
    vme_field = fields.Selection(VME_FIELDS, string="Gegeven")
    value = fields.Char(string="Waarde", help="Bij een aandeel: het aantal aandelen van de kavel in de sleutel.")
    lot_name = fields.Char(string="Kavel")
    lot_type = fields.Selection([(code, label) for code, label in [
        ("apartment", "Appartement"), ("garage", "Garage"), ("storage", "Berging"),
        ("commercial", "Handelsruimte"), ("other", "Andere")]], string="Type")
    floor = fields.Char(string="Verdieping")
    key_name = fields.Char(string="Sleutel")
    key_type = fields.Selection([
        ("general", "Algemeen"), ("elevator", "Lift"), ("heating", "Verwarming"),
        ("consumption", "Op verbruik"), ("other", "Andere")], string="Soort sleutel")
    key_total = fields.Char(string="Totaal sleutel")
    majority = fields.Char(string="Meerderheid", help="De meerderheid waarmee de AV een afwijkende sleutel aannam.")
    description = fields.Char(string="Omschrijving")
    amount = fields.Char(string="Geraamd bedrag")
    financing = fields.Selection([("working", "Werkkapitaal"), ("reserve", "Reservekapitaal")], string="Financiering")
    counterparty = fields.Char(string="Tegenpartij")
    status_text = fields.Char(string="Stand")
    role = fields.Selection([("chair", "Voorzitter raad"), ("member", "Lid raad"),
                             ("auditor", "Commissaris van de rekeningen")], string="Rol")
    person = fields.Char(string="Persoon")
    date = fields.Date(string="Datum", help="Datum van de AV, of begin van het mandaat.")
    date_end = fields.Date(string="Einde mandaat")

    # Where it was read
    attachment_id = fields.Many2one("ir.attachment", string="Document", readonly=True, ondelete="set null")
    source_name = fields.Char(related="attachment_id.name", string="Bron")
    page = fields.Integer(string="Blz.", readonly=True)
    fragment = fields.Text(string="Fragment", readonly=True, help="De zin of tabelrij waar de waarde gelezen werd.")
    confidence = fields.Selection(CONFIDENCES, string="Zekerheid", readonly=True)
    note = fields.Char(string="Opmerking AI", readonly=True)
    uncertain = fields.Boolean(
        string="Onzeker", compute="_compute_uncertain", store=True,
        help="Lage zekerheid of geen waarde gelezen: lees na in het document voor je aanvaardt.")
    summary = fields.Char(string="Voorstel", compute="_compute_summary")

    @api.depends("origin", "confidence", "kind", "value", "amount", "role", "edited")
    def _compute_uncertain(self):
        for line in self:
            missing = (line.kind in ("vme", "share") and not line.value) or (
                line.kind == "works" and not line.amount) or (line.kind == "mandate" and not line.role)
            line.uncertain = line.origin == "ai" and not line.edited and (line.confidence == "low" or missing)

    def _compute_summary(self):
        for line in self:
            line.summary = line._summary()

    def _summary(self):
        if self.kind == "vme":
            return f"{dict(VME_FIELDS).get(self.vme_field, '')}: {self.value or '?'}"
        if self.kind == "lot":
            return f"{self.lot_name} ({LOT_TYPE_NAMES.get(self.lot_type, '')}, {self.floor or '-'})"
        if self.kind == "share":
            return f"{self.key_name} / {self.lot_name}: {self.value or '?'}/{self.key_total or '?'}"
        if self.kind == "mandate":
            return f"{self.person}: {ROLE_NAMES.get(self.role, '?')}"
        return self.description or ""

    def write(self, vals):
        self._check_editable()
        if VALUE_FIELDS & set(vals) and "edited" not in vals:
            ai_lines = self.filtered(lambda line: line.origin == "ai")
            if ai_lines:
                super(VmeMigrationProposal, ai_lines).write({"edited": True})
        return super().write(vals)

    def action_accept(self):
        self.write({"state": "accepted"})
        return True

    def action_reject(self):
        self.write({"state": "rejected"})
        return True

    def action_reset(self):
        self.write({"state": "proposed"})
        return True

    def _check_editable(self):
        if any(line.migration_id.state == "done" for line in self):
            raise UserError(self.env._("Deze overstap is al geïmporteerd."))

    def action_open_source(self):
        """The document in a new tab, at the page of the fragment."""
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(self.env._("Deze regel heeft geen brondocument."))
        return {
            "type": "ir.actions.act_url", "target": "new",
            "url": f"/web/content/{self.attachment_id.id}#page={self.page or 1}",
        }


class VmeMigration(models.Model):
    _inherit = "vme.migration"

    document_ids = fields.Many2many(
        "ir.attachment", "vme_migration_document_rel", "migration_id", "attachment_id",
        string="Basisakte en notulen",
        help="De basisakte (ook een scan) en de notulen van de laatste AV's van de vorige syndicus. "
             "Een taalmodel leest ze en maakt een voorstel dat je regel per regel nakijkt.",
    )
    ai_state = fields.Selection(
        [("none", "Geen documenten"), ("to_read", "Te lezen door AI"), ("read", "Gelezen")],
        string="AI-lezing", default="none", required=True, readonly=True, tracking=True)
    ai_model = fields.Char(string="Gelezen door", readonly=True)
    proposal_ids = fields.One2many("vme.migration.proposal", "migration_id", string="Voorstel")
    proposal_vme_ids = fields.One2many(
        "vme.migration.proposal", "migration_id", string="Gegevens van de VME", domain=[("kind", "=", "vme")])
    proposal_lot_ids = fields.One2many(
        "vme.migration.proposal", "migration_id", string="Kavels", domain=[("kind", "=", "lot")])
    proposal_share_ids = fields.One2many(
        "vme.migration.proposal", "migration_id", string="Aandelen", domain=[("kind", "=", "share")])
    proposal_works_ids = fields.One2many(
        "vme.migration.proposal", "migration_id", string="Werken", domain=[("kind", "=", "works")])
    proposal_procedure_ids = fields.One2many(
        "vme.migration.proposal", "migration_id", string="Procedures", domain=[("kind", "=", "procedure")])
    proposal_mandate_ids = fields.One2many(
        "vme.migration.proposal", "migration_id", string="Mandaten", domain=[("kind", "=", "mandate")])
    proposal_pending_count = fields.Integer(string="Na te kijken", compute="_compute_proposal_counts")
    proposal_uncertain_count = fields.Integer(string="Onzeker", compute="_compute_proposal_counts")

    @api.depends("proposal_ids.state", "proposal_ids.uncertain")
    def _compute_proposal_counts(self):
        for migration in self:
            pending = migration.proposal_ids.filtered(lambda line: line.state == "proposed")
            migration.proposal_pending_count = len(pending)
            migration.proposal_uncertain_count = len(pending.filtered("uncertain"))

    def write(self, vals):
        result = super().write(vals)
        if "document_ids" in vals:
            for migration in self:
                # New documents need a new reading; it replaces the proposal of the AI.
                migration.ai_state = "to_read" if migration.document_ids else "none"
                if migration.state != "draft":
                    super(VmeMigration, migration).write({"state": "draft"})
        if "proposal_ids" in vals or any(k.startswith("proposal_") and k.endswith("_ids") for k in vals):
            # Changed proposal lines invalidate the dry run.
            self.filtered(lambda m: m.state == "checked").write({"state": "draft"})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        migrations = super().create(vals_list)
        migrations.filtered("document_ids").ai_state = "to_read"
        return migrations

    # --- Reading (called by ai/overname.py over JSON-RPC) ---

    def vme_ai_apply_takeover(self, readings, model):
        """Replace the AI proposal with the readings of the documents; returns counts for the script.

        readings: [{"attachment_id", "file", "document_kind", "meeting_date", "summary", "vme", "lots",
        "keys", "works", "procedures", "mandates"}] as made by ai/overname_reader.py. Only creates
        proposal lines: nothing else is made before the import.
        """
        self.ensure_one()
        if self.state == "done":
            raise UserError(self.env._("Deze overstap is al geïmporteerd."))
        self.proposal_ids.filtered(lambda line: line.origin == "ai").unlink()
        documents = {attachment.id: attachment for attachment in self.document_ids}
        manual = self.proposal_ids
        vals_list = []
        for reading in readings or []:
            if not isinstance(reading, dict):
                continue
            attachment = documents.get(reading.get("attachment_id"))
            meeting = _iso_date(reading.get("meeting_date"))
            for item in self._reading_items(reading, meeting):
                item.update({
                    "migration_id": self.id, "origin": "ai", "state": "proposed",
                    "attachment_id": attachment.id if attachment else False,
                })
                vals_list.append(item)
        for sequence, vals in enumerate(vals_list, start=len(manual) + 1):
            vals["sequence"] = sequence
        lines = self.env["vme.migration.proposal"].create(vals_list)
        kinds = dict(PROPOSAL_KINDS)
        uncertain = lines.filtered("uncertain")
        counts = ", ".join(f"{len(lines.filtered(lambda line, k=k: line.kind == k))} × {label.lower()}"
                           for k, label in kinds.items() if lines.filtered(lambda line, k=k: line.kind == k))
        super(VmeMigration, self).write({"ai_state": "read", "ai_model": model, "state": "draft"})
        self.message_post(body=self.env._(
            "Basisakte en notulen gelezen door %(model)s: %(count)s regels (%(counts)s), waarvan %(uncertain)s "
            "onzeker. Kijk elke regel na naast het fragment en aanvaard of weiger ze.",
            model=model, count=len(lines), counts=counts or "-", uncertain=len(uncertain)))
        return {"lines": len(lines), "uncertain": len(uncertain),
                "documents": [reading.get("file") for reading in readings or [] if isinstance(reading, dict)]}

    def _reading_items(self, reading, meeting):
        """Proposal line values for one document, in the order of the document."""

        def source(item):
            page = item.get("page")
            return {
                "page": page if isinstance(page, int) and page > 0 else 0,
                "fragment": str(item.get("fragment") or "")[:1000],
                "confidence": item.get("confidence") if item.get("confidence") in dict(CONFIDENCES) else "low",
                "note": str(item.get("note") or "")[:250],
            }

        def text(value):
            return str(value).strip() if value not in (None, "") else False

        def choice(value, codes, default=False):
            return value if value in codes else default

        items = []
        for item in reading.get("vme") or []:
            if isinstance(item, dict) and item.get("field") in dict(VME_FIELDS):
                items.append({"kind": "vme", "vme_field": item["field"], "value": text(item.get("value")),
                              **source(item)})
        for item in reading.get("lots") or []:
            if isinstance(item, dict) and text(item.get("name")):
                items.append({"kind": "lot", "lot_name": text(item["name"]),
                              "lot_type": choice(item.get("lot_type"), LOT_TYPE_NAMES, "other"),
                              "floor": text(item.get("floor")), **source(item)})
        for key in reading.get("keys") or []:
            if not isinstance(key, dict) or not text(key.get("name")):
                continue
            key_source = source(key)
            for share in key.get("shares") or []:
                if not isinstance(share, dict) or not text(share.get("lot")):
                    continue
                line = source(share)
                if key_source["confidence"] == "low":
                    # An unsure total makes every share of the key unsure.
                    line["confidence"] = "low"
                    line["note"] = line["note"] or key_source["note"]
                items.append({
                    "kind": "share", "key_name": text(key["name"]),
                    "key_type": choice(key.get("key_type"), KEY_TYPE_NAMES, "other"),
                    "key_total": text(key.get("total")), "majority": text(key.get("majority")),
                    "lot_name": text(share["lot"]), "value": text(share.get("value")), **line,
                })
        for item in reading.get("works") or []:
            if isinstance(item, dict) and text(item.get("description")):
                items.append({"kind": "works", "description": text(item["description"]),
                              "amount": text(item.get("amount")),
                              "financing": choice(item.get("financing"), FINANCING_NAMES, "reserve"),
                              "key_name": text(item.get("key")), "date": meeting, **source(item)})
        for item in reading.get("procedures") or []:
            if isinstance(item, dict) and text(item.get("description")):
                items.append({"kind": "procedure", "description": text(item["description"])[:250],
                              "counterparty": text(item.get("counterparty")), "status_text": text(item.get("status")),
                              "date": meeting, **source(item)})
        for item in reading.get("mandates") or []:
            if isinstance(item, dict) and text(item.get("person")):
                items.append({"kind": "mandate", "person": text(item["person"]),
                              "role": choice(item.get("role"), ROLE_NAMES),
                              "date": _iso_date(item.get("date_start")) or meeting,
                              "date_end": _iso_date(item.get("date_end")), **source(item)})
        return items

    def action_accept_certain(self):
        """Accept the proposed lines that were read with certainty; unsure lines stay to be checked one by one."""
        self.ensure_one()
        lines = self.proposal_ids.filtered(lambda line: line.state == "proposed" and not line.uncertain)
        lines.action_accept()
        if lines:
            self.message_post(body=self.env._(
                "%(count)s zeker gelezen regels aanvaard door %(user)s. Nog na te kijken: %(left)s.",
                count=len(lines), user=self.env.user.name, left=self.proposal_pending_count))
        return True

    # --- From proposal to tables (called by _check) ---

    def _check(self):
        messages, plan, ok = super()._check()
        if self.document_ids:
            plan["archive"] = plan["archive"] + [
                (attachment.name, attachment.raw) for attachment in self.document_ids if attachment.raw]
        return messages, plan, ok

    def _apply_proposal(self, tables, messages):
        tables = super()._apply_proposal(tables, messages)
        if self.document_ids and self.ai_state == "to_read":
            messages.append(("error", SOURCE, 0, self.env._(
                "De basisakte en de notulen zijn nog niet gelezen. Start de AI-lezing (ai/overname.py) en kijk "
                "het voorstel na.")))
        lines = self.proposal_ids
        if not lines:
            return tables
        pending = lines.filtered(lambda line: line.state == "proposed")
        if pending:
            messages.append(("error", SOURCE, 0, self.env._(
                "%(count)s regels uit het voorstel zijn nog niet nagekeken (waarvan %(uncertain)s onzeker). "
                "Aanvaard of weiger elke regel.", count=len(pending), uncertain=len(pending.filtered("uncertain")))))
        accepted = lines.filtered(lambda line: line.state == "accepted")
        for line in accepted.filtered(lambda line: line.origin == "ai" and line.confidence == "low" and not line.edited):
            messages.append(("warning", SOURCE, line.sequence, self.env._(
                "Onzeker gelezen en aanvaard zonder verbetering: %(what)s. Kijk het na in %(doc)s, blz. %(page)s.",
                what=line._summary(), doc=line.source_name or "het document", page=line.page or "?")))

        def row(line, **values):
            return {**{column: value or "" for column, value in values.items()}, "_line": line.sequence}

        vme_lines = accepted.filtered(lambda line: line.kind == "vme" and line.value)
        if vme_lines:
            self._merge_vme(tables, messages, vme_lines)
        lots = [row(line, kavel=line.lot_name, type=LOT_TYPE_NAMES.get(line.lot_type, "andere"), verdieping=line.floor)
                for line in accepted.filtered(lambda line: line.kind == "lot")]
        if lots:
            self._replace_table(tables, messages, "kavels", lots, lambda r: str(r.get("kavel") or ""),
                                lambda r: str(r.get("type") or "appartement").lower(), self.env._("type"))
        shares = [row(line, sleutel=line.key_name, soort=KEY_TYPE_NAMES.get(line.key_type, "andere"),
                      totaal=line.key_total, kavel=line.lot_name, quotiteit=line.value, meerderheid=line.majority)
                  for line in accepted.filtered(lambda line: line.kind == "share")]
        if shares:
            self._replace_table(tables, messages, "sleutels", shares,
                                lambda r: (str(r.get("sleutel") or ""), str(r.get("kavel") or "")),
                                self._share_value, self.env._("quotiteit"))
        extra = {
            "werken": [row(line, omschrijving=line.description, bedrag=line.amount,
                           financiering=FINANCING_NAMES.get(line.financing), sleutel=line.key_name,
                           datum_av=line.date and line.date.isoformat())
                       for line in accepted.filtered(lambda line: line.kind == "works")],
            "procedures": [row(line, omschrijving=line.description, tegenpartij=line.counterparty,
                               stand=line.status_text)
                           for line in accepted.filtered(lambda line: line.kind == "procedure")],
            "mandaten": [row(line, rol=ROLE_NAMES.get(line.role), naam=line.person,
                             begindatum=line.date and line.date.isoformat(),
                             einddatum=line.date_end and line.date_end.isoformat())
                         for line in accepted.filtered(lambda line: line.kind == "mandate")],
        }
        for table, rows in extra.items():
            if rows:
                existing = tables.get(table)
                if existing:
                    existing["rows"] = existing["rows"] + rows
                    existing["columns"] = list(dict.fromkeys(existing["columns"] + TABLES[table]))
                else:
                    tables[table] = {"source": SOURCE, "columns": TABLES[table], "rows": rows}
        return tables

    @staticmethod
    def _share_value(row):
        try:
            return parse_amount(row.get("quotiteit"))
        except ValueError:
            return row.get("quotiteit")

    def _merge_vme(self, tables, messages, lines):
        """The VME data of the documents, completed with vme.csv (dates and accounts are not in a deed)."""
        values = {}
        for line in lines:
            if line.vme_field in values and values[line.vme_field] != line.value:
                messages.append(("error", SOURCE, line.sequence, self.env._(
                    "Twee verschillende waarden aanvaard voor %(field)s: %(a)s en %(b)s.",
                    field=dict(VME_FIELDS)[line.vme_field], a=values[line.vme_field], b=line.value)))
            values[line.vme_field] = line.value
        existing = tables.get("vme")
        if not existing or len(existing["rows"]) != 1:
            if existing:
                return  # the checker reports a vme.csv with more than one row
            tables["vme"] = {"source": SOURCE, "columns": TABLES["vme"], "rows": [{**values, "_line": 0}]}
            return
        csv_row = existing["rows"][0]
        for field, value in values.items():
            old = csv_row.get(field)
            if old not in (None, "") and self._normalize(old) != self._normalize(value):
                messages.append(("warning", existing["source"], csv_row["_line"], self.env._(
                    "%(field)s: het bestand zegt %(old)s, het voorstel %(new)s. Het voorstel wordt gebruikt.",
                    field=dict(VME_FIELDS)[field], old=old, new=value)))
            csv_row[field] = value
        existing["columns"] = list(dict.fromkeys(existing["columns"] + list(values)))

    @staticmethod
    def _differs(old, new):
        if isinstance(old, float) and isinstance(new, float):
            return bool(float_compare(old, new, precision_digits=2))
        return old != new

    @staticmethod
    def _show(value):
        return f"{value:g}" if isinstance(value, float) else value

    @staticmethod
    def _normalize(value):
        return re.sub(r"[\s.\-]", "", str(value)).lower()

    def _replace_table(self, tables, messages, table, rows, key, value, label):
        """The deed is the legal source of lots and shares: its table replaces an exported one, with a
        warning for every difference so that the staff member sees what the old package had wrong."""
        existing = tables.get(table)
        if existing:
            old = {key(r): r for r in existing["rows"]
                   if (all(key(r)) if isinstance(key(r), tuple) else key(r))}
            new = {key(r): r for r in rows}
            for name in sorted(set(old) | set(new), key=str):
                what = " / ".join(name) if isinstance(name, tuple) else name
                if name not in new:
                    text = self.env._("%(what)s staat in %(file)s maar niet in het voorstel.",
                                      what=what, file=existing["source"])
                elif name not in old:
                    text = self.env._("%(what)s staat in het voorstel maar niet in %(file)s.",
                                      what=what, file=existing["source"])
                elif self._differs(value(old[name]), value(new[name])):
                    text = self.env._("%(what)s: %(label)s %(old)s in %(file)s, %(new)s in het voorstel.",
                                      what=what, label=label, old=self._show(value(old[name])),
                                      new=self._show(value(new[name])), file=existing["source"])
                else:
                    continue
                messages.append(("warning", SOURCE, new[name]["_line"] if name in new else 0, text))
            messages.append(("info", SOURCE, 0, self.env._(
                "%(table)s komt uit het voorstel (de basisakte); %(file)s wordt niet gebruikt.",
                table=table, file=existing["source"])))
        tables[table] = {"source": SOURCE, "columns": TABLES[table], "rows": rows}
