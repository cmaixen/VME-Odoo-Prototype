"""Comparison of contractor quotes for works, read by AI and approved by the syndic.

The script ai/offertes.py reads the two to four quote PDFs of a comparison "Wacht op AI" and
hands the result to vme_ai_apply_comparison. Odoo builds the table (one row per post and per
condition, one column per quote, every value with the page in its PDF), checks the numbers and
keeps it as a draft. The syndic edits and approves it; approving only makes the PDF for the
convocation of the general assembly. Nothing is sent to anyone.
"""
import base64
import re
from collections import Counter

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import float_compare, format_amount

MIN_QUOTES, MAX_QUOTES = 2, 4

# Same codes as QUOTE_FIELDS in ai/offerte_reader.py.
QUOTE_FIELDS = [
    ("contractor", "Aannemer"),
    ("reference", "Referentie offerte"),
    ("date", "Datum offerte"),
    ("amount_untaxed", "Totaal excl. btw"),
    ("vat_rate", "Btw-tarief"),
    ("amount_total", "Totaal incl. btw"),
    ("execution_period", "Uitvoeringstermijn"),
    ("validity", "Geldigheid"),
    ("payment_terms", "Betalingsvoorwaarden"),
    ("warranty", "Waarborg"),
    ("insurance", "Verzekering"),
]
SECTIONS = [
    ("price", "Prijs"),
    ("posts", "Posten"),
    ("terms", "Voorwaarden"),
    ("guarantee", "Waarborg en verzekering"),
    ("reservations", "Voorbehouden"),
]
# Rows per section, in the order of the table.
SECTION_FIELDS = {
    "price": ("amount_untaxed", "vat_rate", "amount_total"),
    "terms": ("execution_period", "validity", "payment_terms"),
    "guarantee": ("warranty", "insurance"),
}
CELL_STATUSES = [
    ("ok", "In orde"),
    ("missing", "Ontbreekt"),
    ("attention", "Nakijken"),
    ("empty", "Niet vermeld"),
]
# The total of a quote may differ this much from untaxed amount plus VAT (rounding per line).
TOTAL_TOLERANCE = 1.0
# Words that turn a neutral summary into advice; the assembly chooses, not the syndic or the AI.
RECOMMENDATION_WORDS = re.compile(
    r"\b(aanbevel\w*|aan te raden|raden \w* ?aan|adviser\w*|advies|beste (keuze|offerte|aannemer)|"
    r"voorkeur|kies|kiezen voor|te verkiezen)\b", re.I)

# LEGAL-CHECK: KB nr. 20 van 20 juli 1970, tabel A, rubriek XXXI - 6% VAT for renovation of a
# private dwelling that is at least ten years old (first occupation), when the contractor bills
# the owner or the VME directly; otherwise 21%. A different rate between quotes is only flagged.
REDUCED_RENOVATION_RATE = 6


class VmeWorksComparison(models.Model):
    _name = "vme.works.comparison"
    _description = "Offertevergelijking"
    _inherit = ["mail.thread"]
    _order = "works_id, id desc"

    name = fields.Char(string="Vergelijking", compute="_compute_name", store=True)
    works_id = fields.Many2one("vme.works", string="Werkdossier", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="works_id.association_id", store=True, string="VME")
    company_id = fields.Many2one(related="works_id.company_id", store=True)
    currency_id = fields.Many2one(related="works_id.currency_id")
    state = fields.Selection(
        [("to_read", "Wacht op AI"), ("draft", "Concept"), ("approved", "Goedgekeurd")],
        string="Status", required=True, default="to_read", tracking=True)
    column_ids = fields.One2many("vme.works.comparison.column", "comparison_id", string="Offertes")
    column_count = fields.Integer(compute="_compute_column_count")
    line_ids = fields.One2many("vme.works.comparison.line", "comparison_id", string="Rijen")
    summary = fields.Text(
        string="Samenvatting", tracking=True,
        help="Korte, neutrale samenvatting van de verschillen, zonder aanbeveling: de AV kiest.")
    attention = fields.Text(string="Aandachtspunten", compute="_compute_attention")
    attention_count = fields.Integer(compute="_compute_attention")
    ai_model = fields.Char(string="Gelezen door", readonly=True)
    ai_date = fields.Datetime(string="Gelezen op", readonly=True)
    assembly_id = fields.Many2one(
        "vme.assembly", string="Voor de AV",
        domain="[('association_id', '=', association_id), ('state', 'not in', ('held', 'cancelled'))]",
        help="Een goedgekeurde vergelijking gaat als bijlage mee met de oproepingen van deze algemene vergadering.")
    approved_by_id = fields.Many2one("res.users", string="Goedgekeurd door", readonly=True, copy=False)
    approved_date = fields.Datetime(string="Goedgekeurd op", readonly=True, copy=False)
    report_attachment_id = fields.Many2one("ir.attachment", string="PDF", readonly=True, copy=False)
    table_html = fields.Html(string="Vergelijkingstabel", compute="_compute_table_html", sanitize=False)

    @api.depends("works_id.name")
    def _compute_name(self):
        for comparison in self:
            comparison.name = self.env._("Offertevergelijking %s", comparison.works_id.name or "")

    @api.depends("column_ids")
    def _compute_column_count(self):
        for comparison in self:
            comparison.column_count = len(comparison.column_ids)

    @api.depends("state", "summary", "column_ids.amount_untaxed", "column_ids.vat_rate", "column_ids.amount_total",
                 "column_ids.quote_id.amount", "line_ids.status_1", "line_ids.status_2", "line_ids.status_3",
                 "line_ids.status_4", "line_ids.value_1", "line_ids.value_2", "line_ids.value_3", "line_ids.value_4",
                 "line_ids.page_1", "line_ids.page_2", "line_ids.page_3", "line_ids.page_4")
    def _compute_attention(self):
        for comparison in self:
            points = comparison._check_points() if comparison.state != "to_read" else []
            comparison.attention = "\n".join(f"• {point}" for point in points)
            comparison.attention_count = len(points)

    @api.depends("line_ids", "column_ids", "state")
    def _compute_table_html(self):
        for comparison in self:
            comparison.table_html = comparison.state != "to_read" and self.env["ir.qweb"]._render(
                "vme_belgie.works_comparison_table", {"o": comparison, "links": True})

    def _columns(self):
        return self.column_ids.sorted("sequence")

    def _table_sections(self):
        """[(section label, its lines)] in the order of the table, without empty sections."""
        self.ensure_one()
        lines = self.line_ids.sorted("sequence")
        return [(label, lines.filtered(lambda line, code=code: line.section == code))
                for code, label in SECTIONS if code in lines.mapped("section")]

    def _check_points(self):
        """Deterministic checks on what the AI read. They warn; the syndic decides."""
        self.ensure_one()
        columns = self._columns()
        points = []
        rates = Counter(c.vat_rate for c in columns if c.vat_rate)
        if len(rates) > 1:
            points.append(self.env._(
                "Het btw-tarief verschilt: %(rates)s. Kijk na of het verlaagd tarief van %(reduced)s%% voor renovatie "
                "van een woning ouder dan tien jaar van toepassing is.",
                rates=", ".join(f"{c.display_name} {c.vat_rate:g}%" for c in columns if c.vat_rate),
                reduced=REDUCED_RENOVATION_RATE))
        for column in columns:
            if not column.amount_total:
                points.append(self.env._("Geen totaal incl. btw gevonden in de offerte van %s.", column.display_name))
                continue
            if column.amount_untaxed and column.vat_rate:
                expected = column.amount_untaxed * (1 + column.vat_rate / 100)
                if abs(expected - column.amount_total) > TOTAL_TOLERANCE:
                    points.append(self.env._(
                        "%(quote)s: %(untaxed)s excl. btw plus %(rate)s%% btw is niet het totaal van %(total)s.",
                        quote=column.display_name, untaxed=self._money(column.amount_untaxed),
                        rate=f"{column.vat_rate:g}", total=self._money(column.amount_total)))
            if column.quote_id and float_compare(column.quote_id.amount, column.amount_total, 2) \
                    and abs(column.quote_id.amount - column.amount_total) > TOTAL_TOLERANCE:
                points.append(self.env._(
                    "%(quote)s: in het werkdossier staat %(entered)s, de offerte vermeldt %(read)s incl. btw.",
                    quote=column.display_name, entered=self._money(column.quote_id.amount),
                    read=self._money(column.amount_total)))
        without_page = 0
        for line in self.line_ids:
            missing = [columns[index - 1].display_name for index in range(1, len(columns) + 1)
                       if line[f"status_{index}"] == "missing"]
            if missing:
                points.append(self.env._("%(post)s ontbreekt in de offerte van %(quotes)s.",
                                         post=line.name, quotes=", ".join(missing)))
            without_page += sum(1 for index in range(1, len(columns) + 1)
                                if line[f"value_{index}"] and line[f"status_{index}"] in ("ok", "attention")
                                and not line[f"page_{index}"])
        if without_page:
            points.append(self.env._(
                "%s waarde(n) zonder bronpagina: zoek ze op in de PDF of vul de pagina in.", without_page))
        if self.summary and RECOMMENDATION_WORDS.search(self.summary):
            points.append(self.env._(
                "De samenvatting lijkt een aanbeveling te bevatten. Maak ze neutraal: de algemene vergadering kiest."))
        return points

    def _money(self, amount):
        return format_amount(self.env, amount, self.currency_id)

    # Filled by the script ai/offertes.py

    def vme_ai_apply_comparison(self, payload, model):
        """Build the draft table from the reading of ai/offertes.py; returns a short summary."""
        self.ensure_one()
        if self.state != "to_read":
            raise UserError(self.env._("Deze vergelijking wacht niet op AI: ze is al gelezen."))
        columns = self._columns()
        quotes = payload.get("quotes") or []
        if len(quotes) != len(columns):
            raise UserError(self.env._(
                "De AI las %(read)s offertes, de vergelijking heeft er %(expected)s.",
                read=len(quotes), expected=len(columns)))
        for column, quote in zip(columns, quotes):
            column.write(column._values_from_reading(quote))
        rows = []
        for code in SECTION_FIELDS["price"]:
            rows.append(("price", dict(QUOTE_FIELDS)[code],
                         [self._field_cell(code, quote, column) for quote, column in zip(quotes, columns)]))
        for post in payload.get("posts") or []:
            rows.append(("posts", post.get("label") or "?", self._post_cells(post.get("items") or [], len(columns))))
        for section in ("terms", "guarantee"):
            for code in SECTION_FIELDS[section]:
                rows.append((section, dict(QUOTE_FIELDS)[code],
                             [self._field_cell(code, quote, column) for quote, column in zip(quotes, columns)]))
        rows.append(("reservations", self.env._("Voorbehouden"),
                     [self._reservation_cell(quote.get("reservations") or []) for quote in quotes]))
        lines = [Command.clear()]
        for sequence, (section, name, cells) in enumerate(rows, 1):
            vals = {"sequence": sequence, "section": section, "name": name}
            for index, (value, page, status) in enumerate(cells, 1):
                vals.update({f"value_{index}": value, f"page_{index}": page or 0, f"status_{index}": status})
            lines.append(Command.create(vals))
        self.write({
            "line_ids": lines,
            "summary": payload.get("summary") or "",
            "ai_model": model,
            "ai_date": fields.Datetime.now(),
            "state": "draft",
        })
        works = self.works_id
        works.message_post(body=self.env._(
            "Offertevergelijking klaar als concept (%(count)s offertes, gelezen door %(model)s). "
            "Kijk ze na, pas ze aan waar nodig en keur ze goed.", count=len(columns), model=model))
        works.activity_schedule(
            "mail.mail_activity_data_todo", summary=self.env._("Offertevergelijking nakijken"),
            note=self.env._("Kijk elke waarde na tegen de PDF (paginanummer in de tabel) en keur de vergelijking goed."),
            user_id=(works.user_id or self.env.user).id)
        return {"id": self.id, "lines": len(rows), "attention": self._check_points()}

    def _field_cell(self, code, quote, column):
        item = quote.get(code) or {}
        value, page = item.get("value"), item.get("page")
        if not value:
            return False, 0, "empty"
        if code in ("amount_untaxed", "amount_total"):
            value = self._money(float(value))
        elif code == "vat_rate":
            value = f"{float(value):g}%"
            if column.vat_rate and column.vat_rate != REDUCED_RENOVATION_RATE \
                    and REDUCED_RENOVATION_RATE in self.column_ids.mapped("vat_rate"):
                return value, page, "attention"
        return value, page, "ok"

    def _post_cells(self, items, count):
        by_quote = {item.get("quote"): item for item in items}
        anyone_includes = any(item.get("status") == "included" for item in items)
        cells = []
        for number in range(1, count + 1):
            item = by_quote.get(number) or {}
            status, page = item.get("status") or "absent", item.get("page")
            if status == "included":
                value = self._money(float(item["amount"])) if item.get("amount") else self.env._("Inbegrepen")
                cells.append((value, page, "ok"))
            elif status == "excluded":
                text = self.env._("Niet inbegrepen")
                if item.get("description"):
                    text += f": {item['description']}"
                cells.append((text, page, "missing" if anyone_includes else "empty"))
            else:
                cells.append((self.env._("Niet vermeld"), 0, "missing" if anyone_includes else "empty"))
        return cells

    def _reservation_cell(self, reservations):
        if not reservations:
            return False, 0, "empty"
        text = "\n".join(
            r["text"] + (self.env._(" (p. %s)", r["page"]) if r.get("page") else "") for r in reservations)
        return text, reservations[0].get("page") or 0, "attention"

    # Steps

    def action_approve(self):
        """The syndic approves: make the PDF and keep it on the works. Nothing is sent."""
        for comparison in self:
            if comparison.state != "draft":
                raise UserError(self.env._("Alleen een concept kan goedgekeurd worden."))
            if not comparison.summary:
                raise UserError(self.env._("Vul de samenvatting in voor u goedkeurt."))
            comparison.write({"state": "approved", "approved_by_id": self.env.user.id,
                              "approved_date": fields.Datetime.now()})
            content, _ext = self.env["ir.actions.report"]._render_qweb_pdf(
                "vme_belgie.action_report_works_comparison", comparison.ids)
            attachment = self.env["ir.attachment"].create({
                "name": f"{comparison.name}.pdf",
                "datas": base64.b64encode(content),
                "res_model": "vme.works",
                "res_id": comparison.works_id.id,
                "mimetype": "application/pdf",
            })
            comparison.report_attachment_id = attachment
            works = comparison.works_id
            works.activity_ids.filtered(
                lambda a: a.summary == self.env._("Offertevergelijking nakijken")).action_feedback(
                feedback=self.env._("Goedgekeurd."))
            message = self.env._("Offertevergelijking goedgekeurd door %s.", self.env.user.name)
            if comparison.assembly_id:
                message += " " + self.env._(
                    "Ze gaat als bijlage mee met de oproepingen van %s.", comparison.assembly_id.display_name)
            works.message_post(body=message, attachment_ids=attachment.ids)
        return True

    def action_reset_draft(self):
        for comparison in self:
            if comparison.state != "approved":
                raise UserError(self.env._("Deze vergelijking is niet goedgekeurd."))
        self.write({"state": "draft", "approved_by_id": False, "approved_date": False})
        return True

    def action_read_again(self):
        """Let the AI read the quotes again; the table and the summary are rebuilt."""
        for comparison in self:
            if comparison.state != "draft":
                raise UserError(self.env._("Alleen een concept kan opnieuw gelezen worden."))
        self.write({"state": "to_read"})
        return True

    def _get_form_action(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form"}

    def action_open_pdf(self):
        self.ensure_one()
        return self.env.ref("vme_belgie.action_report_works_comparison").report_action(self)


class VmeWorksComparisonColumn(models.Model):
    _name = "vme.works.comparison.column"
    _description = "Offerte in een vergelijking"
    _order = "comparison_id, sequence, id"

    comparison_id = fields.Many2one("vme.works.comparison", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="comparison_id.company_id", store=True)
    currency_id = fields.Many2one(related="comparison_id.currency_id")
    sequence = fields.Integer(string="Kolom", required=True)
    quote_id = fields.Many2one("vme.works.quote", string="Offerte", ondelete="set null")
    partner_id = fields.Many2one(related="quote_id.partner_id", string="Aannemer")
    attachment_id = fields.Many2one("ir.attachment", string="PDF", ondelete="set null")
    contractor_name = fields.Char(string="Aannemer volgens de offerte")
    reference = fields.Char(string="Referentie")
    quote_date = fields.Date(string="Datum")
    amount_untaxed = fields.Monetary(string="Excl. btw")
    vat_rate = fields.Float(string="Btw (%)")
    amount_total = fields.Monetary(string="Incl. btw")

    @api.depends("partner_id.name", "contractor_name", "sequence")
    def _compute_display_name(self):
        for column in self:
            column.display_name = column.partner_id.name or column.contractor_name or \
                self.env._("Offerte %s", column.sequence)

    def _values_from_reading(self, quote):
        def value(code):
            return (quote.get(code) or {}).get("value")

        vals = {"contractor_name": value("contractor") or False, "reference": value("reference") or False}
        for code in ("amount_untaxed", "vat_rate", "amount_total"):
            try:
                vals[code] = float(value(code)) if value(code) else 0.0
            except ValueError:
                vals[code] = 0.0
        try:
            vals["quote_date"] = fields.Date.to_date(value("date")) if value("date") else False
        except ValueError:
            vals["quote_date"] = False
        return vals

    def _page_url(self, page):
        """Link to the page of the quote PDF, for the table in Odoo."""
        self.ensure_one()
        if not self.attachment_id:
            return False
        return f"/web/content/{self.attachment_id.id}#page={page}" if page else f"/web/content/{self.attachment_id.id}"


class VmeWorksComparisonLine(models.Model):
    _name = "vme.works.comparison.line"
    _description = "Rij van een offertevergelijking"
    _order = "comparison_id, sequence, id"

    comparison_id = fields.Many2one("vme.works.comparison", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="comparison_id.company_id", store=True)
    sequence = fields.Integer(default=100)
    section = fields.Selection(SECTIONS, string="Rubriek", required=True, default="posts")
    name = fields.Char(string="Post of voorwaarde", required=True)
    value_1 = fields.Char(string="Offerte 1")
    value_2 = fields.Char(string="Offerte 2")
    value_3 = fields.Char(string="Offerte 3")
    value_4 = fields.Char(string="Offerte 4")
    page_1 = fields.Integer(string="Blz. 1", help="Pagina in de PDF van offerte 1 (0: geen bron).")
    page_2 = fields.Integer(string="Blz. 2", help="Pagina in de PDF van offerte 2 (0: geen bron).")
    page_3 = fields.Integer(string="Blz. 3", help="Pagina in de PDF van offerte 3 (0: geen bron).")
    page_4 = fields.Integer(string="Blz. 4", help="Pagina in de PDF van offerte 4 (0: geen bron).")
    status_1 = fields.Selection(CELL_STATUSES, string="Status 1", default="ok")
    status_2 = fields.Selection(CELL_STATUSES, string="Status 2", default="ok")
    status_3 = fields.Selection(CELL_STATUSES, string="Status 3", default="ok")
    status_4 = fields.Selection(CELL_STATUSES, string="Status 4", default="ok")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_editable()
        return lines

    def write(self, vals):
        self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()

    def _check_editable(self):
        if any(line.comparison_id.state == "approved" for line in self):
            raise UserError(self.env._("Een goedgekeurde vergelijking kan niet meer gewijzigd worden. "
                                       "Zet ze eerst terug naar concept."))

    def _cells(self, columns):
        """(column, value, page, status) for each column of the comparison."""
        self.ensure_one()
        return [(column, self[f"value_{index}"], self[f"page_{index}"], self[f"status_{index}"])
                for index, column in enumerate(columns, 1)]


class VmeWorks(models.Model):
    _inherit = "vme.works"

    comparison_ids = fields.One2many("vme.works.comparison", "works_id", string="Offertevergelijkingen")
    comparison_count = fields.Integer(compute="_compute_comparison_count")

    @api.depends("comparison_ids")
    def _compute_comparison_count(self):
        for works in self:
            works.comparison_count = len(works.comparison_ids)

    def _quotes_with_pdf(self):
        """(quote, its first PDF) for every quote with a PDF, in the order they came in."""
        self.ensure_one()
        result = []
        for quote in self.quote_ids.sorted(lambda q: (q.date or fields.Date.today(), q.id)):
            pdf = quote.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if pdf:
                result.append((quote, pdf))
        return result

    def action_compare_quotes(self):
        """Ask the AI to compare the quotes: a comparison "Wacht op AI" that ai/offertes.py fills."""
        self.ensure_one()
        quotes = self._quotes_with_pdf()
        if not MIN_QUOTES <= len(quotes) <= MAX_QUOTES:
            raise UserError(self.env._(
                "Laad bij %(min)s tot %(max)s offertes de PDF op om ze te vergelijken (nu %(count)s).",
                min=MIN_QUOTES, max=MAX_QUOTES, count=len(quotes)))
        comparison = self.comparison_ids.filtered(lambda c: c.state != "approved")[:1]
        columns = [Command.clear()] + [Command.create({
            "sequence": sequence, "quote_id": quote.id, "attachment_id": pdf.id,
            "contractor_name": quote.partner_id.name,
        }) for sequence, (quote, pdf) in enumerate(quotes, 1)]
        if comparison:
            comparison.write({"state": "to_read", "line_ids": [Command.clear()], "column_ids": columns})
        else:
            comparison = self.env["vme.works.comparison"].create({"works_id": self.id, "column_ids": columns})
        self.message_post(body=self.env._(
            "Offertevergelijking gevraagd voor %s offertes. De AI leest ze en zet een concept klaar.", len(quotes)))
        return comparison._get_form_action()

    def action_open_comparisons(self):
        self.ensure_one()
        if self.comparison_count == 1:
            return self.comparison_ids._get_form_action()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Offertevergelijkingen"),
            "res_model": "vme.works.comparison",
            "view_mode": "list,form",
            "domain": [("works_id", "=", self.id)],
        }


class VmeAssemblyConvocation(models.Model):
    _inherit = "vme.assembly.convocation"

    def _generate_documents(self):
        """Also add the approved quote comparisons meant for this assembly."""
        super()._generate_documents()
        for convocation in self:
            comparisons = self.env["vme.works.comparison"].search([
                ("assembly_id", "=", convocation.assembly_id.id), ("state", "=", "approved"),
                ("report_attachment_id", "!=", False)])
            copies = self.env["ir.attachment"]
            for comparison in comparisons:
                copies |= comparison.report_attachment_id.copy({
                    "res_model": convocation._name, "res_id": convocation.id})
            if copies:
                convocation.attachment_ids = [Command.link(attachment.id) for attachment in copies]

