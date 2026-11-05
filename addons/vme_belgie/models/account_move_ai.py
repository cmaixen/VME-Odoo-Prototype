"""Vendor bills that arrive as a PDF without UBL, read by a language model outside Odoo.

Odoo marks such a draft bill "to read". The script ai/pdf_facturen.py fetches the PDF over
JSON-RPC, lets Claude (or a mock) read it, and sends back each field with a confidence through
vme_ai_apply_reading. Odoo then checks every field and fills the draft. The API key never
enters Odoo, and all checks that need Odoo's data (known suppliers, their confirmed bank
accounts, duplicates) run here.

Never automatic: no supplier and no bank account is ever created, an IBAN is only used when
it is a confirmed account of the supplier, and a bill with a danger cannot be posted before a
person marks the warnings as reviewed.
"""
import re
from datetime import date

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

# Fields the language model reads, in the order they are shown. The script in ai/ uses the same codes.
READING_FIELDS = [
    ("supplier_name", "Leverancier"),
    ("supplier_vat", "Btw-nummer leverancier"),
    ("customer_name", "Klant op de factuur"),
    ("invoice_number", "Factuurnummer"),
    ("invoice_date", "Factuurdatum"),
    ("due_date", "Vervaldatum"),
    ("period_start", "Kostperiode van"),
    ("period_end", "Kostperiode tot"),
    ("description", "Omschrijving"),
    ("amount_untaxed", "Bedrag excl. btw"),
    ("amount_tax", "Btw"),
    ("amount_total", "Totaal"),
    ("currency", "Munt"),
    ("iban", "IBAN"),
]
READING_LABELS = dict(READING_FIELDS)
# A missing optional field is fine: the bill falls back on Odoo's defaults.
OPTIONAL_FIELDS = {"customer_name", "due_date", "period_start", "period_end", "description"}
CONFIDENCES = ("high", "medium", "low")
STATUS_RANK = {"ok": 0, "warning": 1, "danger": 2}


def normalize_vat(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def is_valid_be_vat(vat):
    """Belgian VAT/KBO number: BE + 10 digits starting with 0 or 1, last two = 97 - (first eight mod 97)."""
    match = re.fullmatch(r"BE([01]\d{9})", vat)
    return bool(match) and 97 - int(match[1][:8]) % 97 == int(match[1][8:])


def normalize_iban(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def is_valid_iban(iban):
    """ISO 13616 check: country code and check digits moved to the end, letters as numbers, mod 97 = 1."""
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{8,30}", iban):
        return False
    if iban.startswith("BE") and len(iban) != 16:
        return False
    digits = "".join(str(int(char, 36)) for char in iban[4:] + iban[:4])
    return int(digits) % 97 == 1


def parse_date(value):
    """ISO date, or the Belgian dd/mm/yyyy and dd-mm-yyyy; None if it is not a date."""
    value = (value or "").strip()
    for pattern, order in ((r"(\d{4})-(\d{1,2})-(\d{1,2})", (0, 1, 2)), (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", (2, 1, 0))):
        match = re.fullmatch(pattern, value)
        if match:
            parts = [int(match[i + 1]) for i in order]
            try:
                return date(*parts)
            except ValueError:
                return None
    return None


def parse_amount(value):
    """1234.56, "1.234,56", "1 234,56 EUR" -> 1234.56; None if it is not an amount."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = re.sub(r"[^\d,.\-]", "", str(value or ""))
    if not re.search(r"\d", text):
        return None
    if "," in text:  # Belgian notation: dot for thousands, comma for decimals
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


class VmeBillAiCheck(models.Model):
    _name = "vme.bill.ai.check"
    _description = "Controle van een door AI gelezen factuurveld"
    _order = "move_id, sequence, id"

    move_id = fields.Many2one("account.move", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer()
    field_code = fields.Char(string="Code")
    name = fields.Char(string="Veld")
    value = fields.Char(string="Gelezen waarde")
    confidence = fields.Selection(
        [("high", "Hoog"), ("medium", "Gemiddeld"), ("low", "Laag")], string="Zekerheid"
    )
    status = fields.Selection(
        [("ok", "In orde"), ("warning", "Nakijken"), ("danger", "Gevaar")], string="Controle", default="ok"
    )
    message = fields.Char(string="Uitleg")


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_ai_state = fields.Selection(
        [("to_read", "Te lezen door AI"), ("read", "Gelezen door AI")],
        string="AI-lezing", copy=False, index=True,
    )
    vme_ai_reading = fields.Json(string="Gelezen velden", copy=False)
    vme_ai_model = fields.Char(string="Gelezen door", copy=False)
    vme_ai_iban = fields.Char(
        string="IBAN op de factuur", copy=False,
        help="Zoals gelezen uit de PDF. Wordt nooit automatisch als rekening van de leverancier opgeslagen.",
    )
    vme_ai_check_ids = fields.One2many("vme.bill.ai.check", "move_id", string="Controle AI-lezing", copy=False)
    vme_ai_danger_count = fields.Integer(compute="_compute_vme_ai_counts")
    vme_ai_warning_count = fields.Integer(compute="_compute_vme_ai_counts")
    vme_ai_reviewed_by_id = fields.Many2one("res.users", string="Waarschuwingen nagekeken door", copy=False)
    vme_ai_reviewed_date = fields.Datetime(string="Nagekeken op", copy=False)

    @api.depends("vme_ai_check_ids.status")
    def _compute_vme_ai_counts(self):
        for move in self:
            statuses = move.vme_ai_check_ids.mapped("status")
            move.vme_ai_danger_count = statuses.count("danger")
            move.vme_ai_warning_count = statuses.count("warning")

    # ------------------------------------------------------------------
    # Arrival: a PDF without UBL waits for the AI assistant
    # ------------------------------------------------------------------

    def _extend_with_attachments(self, files_data, new=False):
        res = super()._extend_with_attachments(files_data, new)
        if any(file_data.get("import_file_type") == "pdf" for file_data in files_data):
            # No decoder filled any line: the PDF had no UBL or Factur-X inside.
            for move in self.filtered(lambda m: (
                m.vme_association_id and m.move_type in ("in_invoice", "in_refund") and m.state == "draft"
                and not m.invoice_line_ids and not m.vme_ai_state
            )):
                move.vme_ai_state = "to_read"
                move.message_post(body=self.env._(
                    "PDF zonder UBL ontvangen: de AI-assistent leest de factuur en vult ze in als concept."
                ))
        return res

    # ------------------------------------------------------------------
    # Entry point for the script in ai/
    # ------------------------------------------------------------------

    def vme_ai_apply_reading(self, reading, model_name=""):
        """Check what a language model read from this bill's PDF and fill the draft with it.

        reading: {field code: {"value": text or number or None, "confidence": "high"|"medium"|"low"}}
        for the codes in READING_FIELDS. Returns a summary with the result of every check.
        """
        self.ensure_one()
        if self.state != "draft" or self.move_type not in ("in_invoice", "in_refund") or not self.vme_association_id:
            raise UserError(self.env._("Alleen een conceptfactuur van een VME kan door de AI ingevuld worden."))
        if self.vme_ai_state != "to_read" or self.invoice_line_ids:
            raise UserError(self.env._(
                "Factuur %s wacht niet op een AI-lezing: ze is al gelezen of al ingevuld.", self.display_name
            ))
        self.write({
            "vme_ai_reading": self._vme_ai_clean(reading),
            "vme_ai_model": model_name or "",
            "vme_ai_state": "read",
        })
        self._vme_ai_fill()
        self._vme_ai_check()
        self.message_post(body=self._vme_ai_message())
        return self._vme_ai_summary()

    @api.model
    def _vme_ai_clean(self, reading):
        """Keep only known fields, as text or None, with a valid confidence."""
        cleaned = {}
        for code, _label in READING_FIELDS:
            item = (reading or {}).get(code) or {}
            if not isinstance(item, dict):
                item = {"value": item}
            value = item.get("value")
            value = None if value in (None, "") else str(value).strip()[:500]
            confidence = item.get("confidence") if item.get("confidence") in CONFIDENCES else "low"
            cleaned[code] = {"value": value, "confidence": confidence}
        return cleaned

    def _vme_ai_value(self, code):
        return ((self.vme_ai_reading or {}).get(code) or {}).get("value")

    def _vme_ai_supplier(self):
        """Known supplier with the VAT number on the bill, or an empty recordset. Never creates one."""
        vat = normalize_vat(self._vme_ai_value("supplier_vat"))
        if not vat:
            return self.env["res.partner"]
        if normalize_vat(self.partner_id.commercial_partner_id.vat) == vat:
            return self.partner_id
        candidates = self.env["res.partner"].search([
            *self.env["res.partner"]._check_company_domain(self.company_id),
            ("vat", "!=", False), ("is_company", "=", True),
        ])
        return candidates.filtered(lambda p: normalize_vat(p.vat) == vat)[:1]

    def _vme_ai_purchase_tax(self, untaxed, tax):
        """Purchase tax of the company with the rate tax/untaxed (21%, 6%...), or an empty recordset."""
        Tax = self.env["account.tax"]
        if not untaxed or tax is None or abs(tax) < 0.005:
            return Tax
        rate = round(tax / untaxed * 100, 1)
        default = self.company_id.account_purchase_tax_id
        if default.amount_type == "percent" and abs(default.amount - rate) < 0.05:
            return default
        return Tax.search([
            *Tax._check_company_domain(self.company_id),
            ("type_tax_use", "=", "purchase"), ("amount_type", "=", "percent"), ("amount", "=", rate),
        ], limit=1)

    def _vme_ai_fill(self):
        self.ensure_one()
        value = self._vme_ai_value
        vals = {}
        supplier = self._vme_ai_supplier()
        if supplier:
            vals["partner_id"] = supplier.id
        elif value("supplier_vat"):
            # The VAT number on the bill is not a known supplier: do not trust the sender's address.
            vals["partner_id"] = False
        if value("invoice_number"):
            vals["ref"] = value("invoice_number")
        invoice_date = parse_date(value("invoice_date"))
        if invoice_date:
            vals["invoice_date"] = invoice_date
        due_date = parse_date(value("due_date"))
        if due_date and (not invoice_date or due_date >= invoice_date):
            vals.update(invoice_payment_term_id=False, invoice_date_due=due_date)
        start, end = parse_date(value("period_start")), parse_date(value("period_end"))
        if start and end and start <= end:
            vals.update(vme_period_start=start, vme_period_end=end)
        iban = normalize_iban(value("iban"))
        vals["vme_ai_iban"] = iban or False
        self.write(vals)

        untaxed, tax, total = (parse_amount(value(code)) for code in ("amount_untaxed", "amount_tax", "amount_total"))
        purchase_tax = self._vme_ai_purchase_tax(untaxed, tax)
        if purchase_tax or (untaxed is not None and tax is not None and abs(tax) < 0.005):
            price = untaxed
        else:
            # No matching rate: one line with the total, so the amount to pay is right; flagged in the checks.
            price = total if total is not None else untaxed
        if price is not None:
            self.write({"invoice_line_ids": [Command.create({
                "name": value("description") or self.env._("Factuur %s", value("invoice_number") or ""),
                "quantity": 1,
                "price_unit": price,
                "tax_ids": [Command.set(purchase_tax.ids)],
            })]})

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _vme_ai_check(self):
        """(Re)compute the check of every read field against the bill and Odoo's data."""
        self.ensure_one()
        reading = self.vme_ai_reading or {}
        results = {code: ["ok", ""] for code, _label in READING_FIELDS}

        def flag(code, status, message):
            if STATUS_RANK[status] >= STATUS_RANK[results[code][0]]:
                results[code][0] = status
            results[code][1] = " ".join(filter(None, [results[code][1], message]))

        for code, _label in READING_FIELDS:
            item = reading.get(code) or {}
            if item.get("value") is None:
                if code in OPTIONAL_FIELDS:
                    results[code][1] = self.env._("Niet op de factuur.")
                else:
                    flag(code, "warning", self.env._("Niet gelezen: vul zelf in vanuit de PDF."))
            elif item.get("confidence") == "low":
                flag(code, "warning", self.env._("Lage zekerheid: vergelijk met de PDF."))

        self._vme_ai_check_supplier(flag)
        self._vme_ai_check_dates(flag)
        self._vme_ai_check_amounts(flag)
        self._vme_ai_check_iban(flag)

        self.vme_ai_check_ids = [Command.clear()] + [
            Command.create({
                "sequence": sequence,
                "field_code": code,
                "name": label,
                "value": (reading.get(code) or {}).get("value") or "",
                "confidence": (reading.get(code) or {}).get("confidence") or "low",
                "status": results[code][0],
                "message": results[code][1],
            })
            for sequence, (code, label) in enumerate(READING_FIELDS)
        ]

    def _vme_ai_check_supplier(self, flag):
        value = self._vme_ai_value
        vat = normalize_vat(value("supplier_vat"))
        if vat:
            if vat.startswith("BE") and not is_valid_be_vat(vat):
                flag("supplier_vat", "danger", self.env._("Ongeldig Belgisch btw-nummer (controlegetal klopt niet)."))
            supplier = self._vme_ai_supplier()
            if supplier:
                flag("supplier_vat", "ok", self.env._("Gekende leverancier: %s.", supplier.display_name))
                name = (value("supplier_name") or "").lower()
                known = supplier.commercial_partner_id.name.lower()
                if name and name not in known and known not in name:
                    flag("supplier_name", "warning", self.env._("Naam verschilt van de gekende leverancier %s.", supplier.display_name))
            else:
                flag("supplier_vat", "danger", self.env._(
                    "Nieuwe leverancier: niet automatisch aangemaakt. Controleer de onderneming (KBO) "
                    "en maak de leverancier zelf aan."
                ))
        elif self.partner_id:
            flag("supplier_vat", "warning", self.env._(
                "Geen btw-nummer gelezen: leverancier %s gekozen op het afzenderadres.", self.partner_id.display_name
            ))
        elif value("supplier_name"):
            flag("supplier_name", "danger", self.env._("Leverancier niet gevonden: kies of maak hem zelf aan."))

        customer = (value("customer_name") or "").lower()
        vme_name = self.vme_association_id.name.lower()
        if customer and vme_name not in customer:
            flag("customer_name", "warning", self.env._(
                "De factuur is niet gericht aan %s. Hoort ze bij een andere VME?", self.vme_association_id.name
            ))

        number = value("invoice_number")
        if number and self.partner_id:
            duplicate = self.search([
                ("id", "!=", self.id), ("move_type", "=", self.move_type), ("ref", "=", number),
                ("commercial_partner_id", "=", self.partner_id.commercial_partner_id.id),
                ("state", "!=", "cancel"),
            ], limit=1)
            if duplicate:
                flag("invoice_number", "warning", self.env._(
                    "Mogelijk dubbel: zelfde nummer als %s.", duplicate.display_name
                ))

    def _vme_ai_check_dates(self, flag):
        value = self._vme_ai_value
        today = fields.Date.context_today(self)
        dates = {code: parse_date(value(code)) for code in ("invoice_date", "due_date", "period_start", "period_end")}
        for code, parsed in dates.items():
            if value(code) and not parsed:
                flag(code, "warning", self.env._("Geen geldige datum."))
        if dates["invoice_date"] and dates["invoice_date"] > today:
            flag("invoice_date", "warning", self.env._("Factuurdatum ligt in de toekomst."))
        if dates["invoice_date"] and dates["due_date"] and dates["due_date"] < dates["invoice_date"]:
            flag("due_date", "warning", self.env._("Vervaldatum ligt voor de factuurdatum: niet overgenomen."))
        start, end = dates["period_start"], dates["period_end"]
        if bool(start) != bool(end):
            flag("period_start" if not start else "period_end", "warning",
                 self.env._("Maar één kant van de kostperiode gelezen: factuurdatum gebruikt."))
        elif start and end and end < start:
            flag("period_end", "warning", self.env._("Einde voor begin: factuurdatum gebruikt als kostperiode."))

    def _vme_ai_check_amounts(self, flag):
        value = self._vme_ai_value
        for code in ("amount_untaxed", "amount_tax", "amount_total"):
            if value(code) and parse_amount(value(code)) is None:
                flag(code, "warning", self.env._("Geen geldig bedrag."))
        untaxed, tax, total = (parse_amount(value(code)) for code in ("amount_untaxed", "amount_tax", "amount_total"))
        if None not in (untaxed, tax, total) and abs(untaxed + tax - total) > 0.01:
            flag("amount_total", "warning", self.env._(
                "Excl. btw plus btw (%(sum).2f) is niet gelijk aan het totaal.", sum=untaxed + tax
            ))
        if total is not None and total <= 0:
            flag("amount_total", "warning", self.env._("Totaal is nul of negatief: is dit een creditnota?"))
        if tax and abs(tax) >= 0.005 and untaxed and not self._vme_ai_purchase_tax(untaxed, tax):
            flag("amount_tax", "warning", self.env._(
                "Geen btw-tarief van %(rate).1f%% gevonden: één lijn met het totaalbedrag zonder btw.",
                rate=tax / untaxed * 100,
            ))
        if total is not None and self.invoice_line_ids and abs(self.amount_total - total) > 0.01:
            flag("amount_total", "warning", self.env._(
                "Totaal van de factuur in Odoo (%(odoo).2f) verschilt van het gelezen totaal.", odoo=self.amount_total
            ))
        currency = (value("currency") or "").upper()
        if currency and currency not in ("EUR", "€"):
            flag("currency", "warning", self.env._("Geen factuur in euro: munt en bedragen nakijken."))

    def _vme_ai_check_iban(self, flag):
        """Compare the IBAN on the bill with the confirmed accounts of the supplier.

        Fraudsters send bills with their own IBAN under a known supplier's name. So only an
        account that is already known and confirmed is used for payment; anything else is a
        danger, the bill gets no bank account, and the IBAN is never stored on the supplier.
        """
        iban = normalize_iban(self._vme_ai_value("iban"))
        supplier = self.partner_id.commercial_partner_id
        if not iban:
            flag("iban", "warning", self.env._("Geen IBAN gelezen: kies zelf de rekening van de leverancier."))
            return
        if not is_valid_iban(iban):
            flag("iban", "danger", self.env._("Ongeldig IBAN (controlegetal klopt niet). Niet gebruiken."))
            self.partner_bank_id = False
            return
        if not supplier:
            flag("iban", "danger", self.env._("IBAN van een onbekende leverancier: niet gebruiken voor betaling."))
            self.partner_bank_id = False
            return
        banks = self.env["res.partner.bank"].search([("partner_id", "child_of", supplier.id)])
        bank = banks.filtered(lambda b: b.sanitized_acc_number == iban)[:1]
        confirmed = banks.filtered("allow_out_payment")
        if bank and bank.allow_out_payment:
            flag("iban", "ok", self.env._("Bevestigde rekening van %s.", supplier.name))
            self.partner_bank_id = bank
            return
        if bank:
            message = self.env._(
                "Rekening staat bij %s maar is niet bevestigd. Bevestig ze pas na controle bij de leverancier.",
                supplier.name,
            )
        elif confirmed:
            message = self.env._(
                "Ander IBAN dan de bevestigde rekening %(known)s van %(supplier)s. Mogelijk fraude: bel de "
                "leverancier op een gekend nummer. Het IBAN van de factuur wordt niet opgeslagen.",
                known=", ".join(confirmed.mapped("acc_number")), supplier=supplier.name,
            )
        else:
            message = self.env._(
                "Geen bevestigde rekening van %s. Controleer het IBAN bij de leverancier voor je het toevoegt.",
                supplier.name,
            )
        flag("iban", "danger", message)
        self.partner_bank_id = False

    # ------------------------------------------------------------------
    # Messages and buttons
    # ------------------------------------------------------------------

    def _vme_ai_summary(self):
        return {
            "move_id": self.id,
            "partner": self.partner_id.display_name or False,
            "ref": self.ref or False,
            "amount_total": self.amount_total,
            "keys": sorted(set(self.invoice_line_ids.vme_key_id.mapped("name"))),
            "danger": self.vme_ai_danger_count,
            "warning": self.vme_ai_warning_count,
            "checks": [
                {"field": check.name, "value": check.value, "confidence": check.confidence,
                 "status": check.status, "message": check.message}
                for check in self.vme_ai_check_ids
            ],
        }

    def _vme_ai_message(self):
        problems = self.vme_ai_check_ids.filtered(lambda c: c.status != "ok")
        items = Markup("").join(
            Markup("<li><b>%s</b>: %s</li>") % (check.name, check.message) for check in problems
        )
        intro = self.env._(
            "Factuur gelezen door %(model)s: %(danger)s gevaar, %(warning)s om na te kijken. "
            "Niets is geboekt of betaald.",
            model=self.vme_ai_model or "AI", danger=self.vme_ai_danger_count, warning=self.vme_ai_warning_count,
        )
        return Markup("<p>%s</p>") % intro + (Markup("<ul>%s</ul>") % items if items else Markup(""))

    def action_vme_ai_recheck(self):
        """Run the checks again, e.g. after creating the supplier or confirming its bank account."""
        for move in self.filtered(lambda m: m.vme_ai_state == "read"):
            move._vme_ai_check()
            move.write({"vme_ai_reviewed_by_id": False, "vme_ai_reviewed_date": False})
            move.message_post(body=move._vme_ai_message())

    def action_vme_ai_mark_reviewed(self):
        for move in self.filtered("vme_ai_danger_count"):
            move.write({"vme_ai_reviewed_by_id": self.env.user.id, "vme_ai_reviewed_date": fields.Datetime.now()})
            dangers = move.vme_ai_check_ids.filtered(lambda c: c.status == "danger")
            move.message_post(body=Markup("<p>%s</p><ul>%s</ul>") % (
                self.env._("%s heeft de waarschuwingen van de AI-lezing nagekeken:", self.env.user.name),
                Markup("").join(Markup("<li><b>%s</b>: %s</li>") % (c.name, c.message) for c in dangers),
            ))

    def _post(self, soft=True):
        blocked = self.filtered(lambda m: m.vme_ai_state == "read" and m.vme_ai_danger_count and not m.vme_ai_reviewed_by_id)
        if blocked:
            raise UserError(self.env._(
                "%s heeft waarschuwingen van de AI-lezing (nieuwe leverancier of IBAN). "
                "Kijk ze na en klik op \"Waarschuwingen nagekeken\" voor je boekt.",
                blocked[0].display_name,
            ))
        return super()._post(soft=soft)
