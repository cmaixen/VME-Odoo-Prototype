"""281.50 forms (Belcotax-on-web): fees, commissions and similar payments of a VME to independents.

The staff member marks a supplier as "281.50-plichtig" with a category. Per VME and year the overview
adds up what the VME paid on the posted bills of those suppliers, warns about missing data and, once a
staff member has checked it, gives a file to upload in Belcotax-on-web: XML up to income year 2025, JSON
Lines from 2026 (the new Belcotax-on-web). Nothing is filed by Odoo.
"""
import base64
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from . import belcotax_jsonl, belcotax_xml
from .belcotax_jsonl import Contact, build_belcotax_jsonl, uses_jsonl
from .belcotax_xml import (Debtor, Fiche, build_belcotax_xml, digits, kbo_is_valid, national_number_is_valid,
                           rsz_country)
from .vme_access import check_not_auditor

# LEGAL-CHECK: art. 57, 1° WIB 92 - commissions, brokerage, fees, attendance fees, benefits in kind and
# expenses borne for the beneficiary, paid to persons for whom they are professional income.
BELCOTAX_CATEGORIES = [
    ("commission", "Commissies en makelaarslonen"),
    ("fees", "Erelonen of vacatiegelden"),
    ("benefits", "Voordelen van alle aard"),
    ("expenses", "Kosten voor rekening van de verkrijger"),
]
# LEGAL-CHECK: art. 30 KB/WIB 92 as amended by the KB of April 2022 (circular 2022/C/96) - no form needed
# when the total paid to one beneficiary in the year is at most 250 euro (before: 125 euro).
BELCOTAX_THRESHOLD = 250.0


def belcotax_deadline(year):
    """Last day to upload the forms of an income year."""
    # LEGAL-CHECK: brochure Belcotax-on-web inkomsten 2025, 1 (indieningstermijnen) - the fiches 281.50 must
    # arrive "ten laatste op 29 juni" of the following year; the FOD Financiën confirms it every year.
    return date(year + 1, 6, 29)


class ResPartner(models.Model):
    _inherit = "res.partner"

    vme_belcotax_liable = fields.Boolean(
        string="281.50-plichtig",
        help="De VME moet wat ze deze leverancier betaalt jaarlijks melden op een fiche 281.50 "
             "(bv. een zelfstandige commissaris van de rekeningen, een consultant of een architect).")
    vme_belcotax_category = fields.Selection(
        BELCOTAX_CATEGORIES, string="Soort vergoeding (281.50)", default="fees")
    vme_belcotax_profession = fields.Char(string="Beroep (281.50)", help="Het beroep dat op de fiche komt.")
    vme_national_number = fields.Char(
        string="Rijksregisternummer", groups="account.group_account_invoice",
        help="Alleen voor een natuurlijke persoon die een fiche 281.50 krijgt. Een zelfstandige met een vrij "
             "beroep heeft daarnaast een ondernemingsnummer: vul het in bij btw-nummer of KBO.")


class VmeBelcotaxStatement(models.Model):
    _name = "vme.belcotax.statement"
    _description = "Fiches 281.50 van een VME"
    _inherit = ["mail.thread"]
    _order = "year desc, association_id"

    name = fields.Char(string="Naam", compute="_compute_name", store=True)
    association_id = fields.Many2one("vme.association", string="VME", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    year = fields.Integer(string="Inkomstenjaar", required=True,
                          default=lambda self: fields.Date.context_today(self).year - 1)
    state = fields.Selection(
        [("draft", "Na te kijken"), ("checked", "Nagekeken"), ("filed", "Opgeladen in Belcotax")],
        string="Status", default="draft", required=True, tracking=True, copy=False)
    line_ids = fields.One2many("vme.belcotax.line", "statement_id", string="Verkrijgers", copy=False)
    deadline = fields.Date(string="Indienen uiterlijk", compute="_compute_deadline")
    threshold = fields.Monetary(string="Drempel per verkrijger", compute="_compute_threshold",
                                currency_field="currency_id")
    fiche_count = fields.Integer(string="Fiches", compute="_compute_totals")
    total_amount = fields.Monetary(string="Totaal op fiches", compute="_compute_totals", currency_field="currency_id")
    warning_count = fields.Integer(string="Waarschuwingen", compute="_compute_totals")
    checked_by_id = fields.Many2one("res.users", string="Nagekeken door", readonly=True, copy=False)
    checked_date = fields.Date(string="Nagekeken op", readonly=True, copy=False)
    filed_date = fields.Date(string="Opgeladen op", copy=False, tracking=True)
    xml_file = fields.Binary(string="Belcotax-bestand", attachment=True, readonly=True, copy=False)
    xml_filename = fields.Char(readonly=True, copy=False)
    file_format = fields.Char(string="Formaat", compute="_compute_file_format")
    file_warning = fields.Text(string="Waarschuwing bestand", compute="_compute_file_warning")

    _unique_year = models.Constraint(
        "UNIQUE (association_id, year)", "Deze VME heeft al een overzicht 281.50 voor dat jaar.")

    @api.depends("association_id.name", "year")
    def _compute_name(self):
        for statement in self:
            statement.name = f"281.50 {statement.year} - {statement.association_id.name or ''}"

    @api.depends("year")
    def _compute_deadline(self):
        for statement in self:
            statement.deadline = statement.year and belcotax_deadline(statement.year)

    def _compute_threshold(self):
        self.threshold = BELCOTAX_THRESHOLD

    @api.depends("year")
    def _compute_file_format(self):
        for statement in self:
            statement.file_format = (
                self.env._("JSON Lines (nieuwe Belcotax-on-web)") if uses_jsonl(statement.year)
                else self.env._("XML (Belcotax-on-web tot inkomsten 2025)"))

    def _compute_file_warning(self):
        """Missing data of the VME, the sender or the contact person: a warning, the file can still be made."""
        for statement in self:
            problems = []
            debtor = statement._belcotax_debtor()
            if not kbo_is_valid(debtor.kbo):
                problems.append(self.env._("Het ondernemingsnummer van de VME ontbreekt of klopt niet."))
            if not (debtor.street and debtor.zip and debtor.city):
                problems.append(self.env._("Het adres van de VME is onvolledig."))
            if uses_jsonl(statement.year):
                if not statement._belcotax_contact().email:
                    problems.append(self.env._("Geen e-mailadres voor de contactpersoon (uw gebruiker of het kantoor)."))
            else:
                sender = statement._belcotax_sender()
                if not (sender.phone and sender.email and kbo_is_valid(sender.kbo)):
                    problems.append(self.env._(
                        "Telefoon, e-mailadres of ondernemingsnummer van de afzender (%s) ontbreekt.", sender.name))
            statement.file_warning = "\n".join(problems) or False

    @api.depends("line_ids.amount_total", "line_ids.below_threshold", "line_ids.warning")
    def _compute_totals(self):
        for statement in self:
            fiches = statement.line_ids.filtered(lambda l: not l.below_threshold)
            statement.fiche_count = len(fiches)
            statement.total_amount = sum(fiches.mapped("amount_total"))
            statement.warning_count = len(fiches.filtered("warning"))

    # Written only by the buttons (as superuser): who checked it and when it was filed is the audit trail.
    PROTECTED_FIELDS = {"state", "checked_by_id", "checked_date", "filed_date"}

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(self.PROTECTED_FIELDS & set(vals) for vals in vals_list):
            raise AccessError(self.env._("Een overzicht 281.50 begint altijd als concept."))
        statements = super().create(vals_list)
        statements._fill_lines()
        return statements

    def write(self, vals):
        if not self.env.su:
            if self.PROTECTED_FIELDS & set(vals):
                raise AccessError(self.env._("De status van een overzicht 281.50 wijzigt alleen via de knoppen."))
            if {"association_id", "year", "line_ids"} & set(vals):
                self._check_draft()
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            self._check_draft()
        return super().unlink()

    def _check_draft(self):
        if self.filtered(lambda s: s.state != "draft"):
            raise UserError(self.env._("Een nagekeken of opgeladen overzicht wijzigt niet meer. Zet het eerst "
                                       "terug naar concept."))

    # Selection and totals

    def _paid_by_partner(self):
        """Paid in the year on posted bills of 281.50-liable suppliers: {commercial partner: (amount, bills)}.

        A payment counts in the year of its reconciliation date, a credit note lowers the amount.
        """
        # LEGAL-CHECK: art. 57, 1° WIB 92 - amounts "betaald of toegekend" in the year; the prototype takes
        # what was paid (reconciled) in the year, VAT included because most VMEs cannot deduct it.
        self.ensure_one()
        start, end = date(self.year, 1, 1), date(self.year, 12, 31)
        # In the company of the VME, whatever companies the user has switched on.
        bills = self.env["account.move"].with_company(self.company_id).search([
            ("company_id", "=", self.company_id.id), ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"), ("commercial_partner_id.vme_belcotax_liable", "=", True),
        ])
        result = {}
        for bill in bills:
            payable = bill.line_ids.filtered(lambda l: l.account_id.account_type == "liability_payable")
            partials = (payable.matched_debit_ids | payable.matched_credit_ids).filtered(
                lambda p: start <= p.max_date <= end)
            if not partials:
                continue
            sign = -1 if bill.move_type == "in_refund" else 1
            amount, moves = result.get(bill.commercial_partner_id, (0.0, self.env["account.move"]))
            result[bill.commercial_partner_id] = (amount + sign * sum(partials.mapped("amount")), moves | bill)
        return result

    def _line_values(self, partner, amount, bills):
        address = ", ".join(filter(None, [partner.street, partner.street2]))
        values = {
            "statement_id": self.id,
            "partner_id": partner.id,
            "name": partner.name,
            "street": address,
            "zip": partner.zip,
            "city": partner.city,
            "country_id": partner.country_id.id,
            "is_company": partner.is_company,
            "national_number": partner.sudo().vme_national_number if not partner.is_company else False,
            "kbo": partner.company_registry or (digits(partner.vat) if (partner.vat or "")[:2] in ("BE", "")
                                                else False),
            "vat": partner.vat,
            "profession": partner.vme_belcotax_profession,
            "bill_ids": [fields.Command.set(bills.ids)],
        }
        for category, _label in BELCOTAX_CATEGORIES:
            values[f"amount_{category}"] = 0.0
        values[f"amount_{partner.vme_belcotax_category or 'fees'}"] = self.currency_id.round(amount)
        return values

    def _fill_lines(self):
        for statement in self:
            # In the company of the VME: the bills on the lines are checked against the active companies.
            statement = statement.with_company(statement.company_id)
            statement.line_ids.unlink()
            paid = statement._paid_by_partner()
            statement.env["vme.belcotax.line"].create([
                statement._line_values(partner, amount, bills)
                for partner, (amount, bills) in sorted(paid.items(), key=lambda item: item[0].name or "")
                if not statement.currency_id.is_zero(amount)
            ])

    # Buttons: a staff member checks, downloads and uploads; Odoo files nothing itself.

    def action_compute(self):
        check_not_auditor(self.env)
        if self.filtered(lambda s: s.state == "filed"):
            raise UserError(self.env._("Dit overzicht is al opgeladen. Zet het eerst terug naar concept."))
        self.sudo().write({"state": "draft", "checked_by_id": False, "checked_date": False, "xml_file": False,
                    "xml_filename": False})
        self._fill_lines()

    def action_mark_checked(self):
        check_not_auditor(self.env)
        self._check_draft()
        self.sudo().write({"state": "checked", "checked_by_id": self.env.user.id,
                    "checked_date": fields.Date.context_today(self)})

    def action_back_to_draft(self):
        check_not_auditor(self.env)
        self.sudo().write({"state": "draft", "checked_by_id": False, "checked_date": False, "xml_file": False,
                    "xml_filename": False, "filed_date": False})

    def action_mark_filed(self):
        """The staff member confirms he uploaded the file in Belcotax-on-web himself."""
        check_not_auditor(self.env)
        for statement in self:
            if statement.state != "checked":
                raise UserError(self.env._("Kijk het overzicht eerst na."))
        self.sudo().write({"state": "filed", "filed_date": fields.Date.context_today(self)})

    def _belcotax_fiches(self):
        self.ensure_one()
        fiches = []
        for sequence, line in enumerate(self.line_ids.filtered(lambda l: not l.below_threshold), start=1):
            beneficiary = f"partner-{line.partner_id.id}" if line.partner_id else f"line-{line.id}"
            fiches.append(Fiche(
                sequence=sequence, name=line.name, street=line.street or "", zip=line.zip or "",
                city=line.city or "", is_company=line.is_company, national_number=line.sudo().national_number or "",
                kbo=line.kbo or "", vat=line.vat or "", profession=line.profession or "",
                country=line.country_id.code or "BE",
                amounts={category: line[f"amount_{category}"] for category, _label in BELCOTAX_CATEGORIES},
                # Same VME, year and beneficiary give the same key, so a corrected upload replaces the fiche.
                key=f"vme-28150-{self.year}-{self.company_id.id}-{beneficiary}",
                beneficiary_key=f"vme-{beneficiary}",
            ))
        return fiches

    @api.model
    def _belcotax_party(self, company, key=""):
        return Debtor(
            name=company.name or "", street=", ".join(filter(None, [company.street, company.street2])),
            zip=company.zip or "", city=company.city or "",
            kbo=company.company_registry or digits(company.vat), country=company.country_id.code or "BE",
            contact=self.env.user.name, email=self.env.user.email or company.email or "",
            phone=company.phone or "", key=key,
        )

    def _belcotax_debtor(self):
        self.ensure_one()
        return self._belcotax_party(self.company_id, key=f"vme-debtor-{self.company_id.id}")

    def _belcotax_sender(self):
        """Who uploads the XML: the office of the syndic of the VME, or the VME itself without one."""
        self.ensure_one()
        office = self.association_id.current_agreement_id.syndic_company_id or self.env["res.company"].sudo().search(
            [("is_syndic_office", "=", True)], limit=1)
        return self._belcotax_party(office.sudo() or self.company_id)

    def _belcotax_contact(self):
        self.ensure_one()
        sender = self._belcotax_sender()
        return Contact(key=f"vme-contact-{self.env.user.id}", name=self.env.user.name,
                       email=self.env.user.email or sender.email, phone=sender.phone)

    def _belcotax_file(self):
        """The file content and name; it is checked against the official schemas first."""
        self.ensure_one()
        debtor, fiches = self._belcotax_debtor(), self._belcotax_fiches()
        number = digits(debtor.kbo) or self.id
        if uses_jsonl(self.year):
            data = build_belcotax_jsonl(self.year, debtor, self._belcotax_contact(), fiches)
            errors, filename = belcotax_jsonl.validate(data), f"belcotax_28150_{self.year}_{number}.jsonl"
        else:
            data = build_belcotax_xml(self.year, debtor, fiches, fields.Date.context_today(self),
                                      sender=self._belcotax_sender())
            errors, filename = belcotax_xml.validate(data), f"belcotax_28150_{self.year}_{number}.xml"
        if errors:
            raise UserError(self.env._("Het bestand voldoet niet aan het schema van Belcotax-on-web: %s",
                                       "; ".join(errors)))
        return data, filename

    def action_download_file(self):
        self.ensure_one()
        check_not_auditor(self.env)
        if self.state == "draft":
            raise UserError(self.env._("Kijk het overzicht eerst na: pas daarna is het bestand beschikbaar."))
        if not self.fiche_count:
            raise UserError(self.env._("Geen enkele verkrijger komt boven de drempel: er zijn geen fiches nodig."))
        data, filename = self._belcotax_file()
        self.write({"xml_file": base64.b64encode(data), "xml_filename": filename})
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/vme.belcotax.statement/{self.id}/xml_file/{filename}?download=true",
            "target": "self",
        }


class VmeBelcotaxLine(models.Model):
    _name = "vme.belcotax.line"
    _description = "Verkrijger op een fiche 281.50"
    _order = "statement_id, name"

    statement_id = fields.Many2one("vme.belcotax.statement", string="Overzicht", required=True, ondelete="cascade",
                                   index=True)
    company_id = fields.Many2one(related="statement_id.company_id", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.su:
            lines.statement_id._check_draft()
        return lines

    def write(self, vals):
        if not self.env.su:
            (self.statement_id | self.env["vme.belcotax.statement"].browse(vals.get("statement_id")))._check_draft()
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            self.statement_id._check_draft()
        return super().unlink()
    currency_id = fields.Many2one(related="statement_id.currency_id")
    partner_id = fields.Many2one("res.partner", string="Leverancier")
    name = fields.Char(string="Verkrijger", required=True)
    street = fields.Char(string="Adres")
    zip = fields.Char(string="Postcode")
    city = fields.Char(string="Gemeente")
    country_id = fields.Many2one("res.country", string="Land")
    is_company = fields.Boolean(string="Rechtspersoon")
    national_number = fields.Char(string="Rijksregisternummer", groups="account.group_account_invoice")
    kbo = fields.Char(string="Ondernemingsnummer")
    vat = fields.Char(string="Btw-nummer", help="Voor een buitenlands bedrijf zonder Belgisch ondernemingsnummer.")
    profession = fields.Char(string="Beroep")
    amount_commission = fields.Monetary(string="Commissies", currency_field="currency_id")
    amount_fees = fields.Monetary(string="Erelonen", currency_field="currency_id")
    amount_benefits = fields.Monetary(string="Voordelen van alle aard", currency_field="currency_id")
    amount_expenses = fields.Monetary(string="Kosten", currency_field="currency_id")
    amount_total = fields.Monetary(string="Totaal", compute="_compute_amount_total", store=True,
                                   currency_field="currency_id")
    below_threshold = fields.Boolean(
        string="Onder de drempel", compute="_compute_amount_total", store=True,
        help="Niet meer dan 250 euro in het jaar: geen fiche nodig.")
    bill_ids = fields.Many2many("account.move", string="Facturen")
    warning = fields.Text(string="Waarschuwing", compute="_compute_warning", store=True)

    @api.depends("amount_commission", "amount_fees", "amount_benefits", "amount_expenses")
    def _compute_amount_total(self):
        for line in self:
            line.amount_total = line.amount_commission + line.amount_fees + line.amount_benefits + line.amount_expenses
            line.below_threshold = line.amount_total <= BELCOTAX_THRESHOLD

    @api.depends("street", "zip", "city", "country_id", "is_company", "national_number", "kbo", "vat", "profession")
    def _compute_warning(self):
        """Missing or doubtful data: a warning for the staff member, never a blocking error."""
        for line in self.sudo():
            problems = []
            if not (line.street and line.zip and line.city):
                problems.append(self.env._("Adres onvolledig."))
            if not rsz_country(line.country_id.code):
                problems.append(self.env._("Geen Belcotax-landcode voor %s: vul het land zelf aan in Belcotax-on-web.",
                                           line.country_id.name))
            # LEGAL-CHECK: brochure Belcotax-on-web inkomsten 2025 (2.011, 2.110) and Pre-opening (03.11.2026),
            # 3.5 and 3.6 - the company number is required for a legal person; a natural person is identified
            # by his national number (required for all fiches from 1 January 2028, law of 12 May 2024) and,
            # with a liberal profession, his company number. A wrong number blocks the whole file.
            if line.is_company:
                if line.country_id.code in (False, "BE"):
                    if not line.kbo:
                        problems.append(self.env._("Ondernemingsnummer ontbreekt."))
                    elif not kbo_is_valid(line.kbo):
                        problems.append(self.env._("Ondernemingsnummer klopt niet (controlegetal)."))
                elif not (line.kbo or line.vat):
                    problems.append(self.env._("Ondernemingsnummer of btw-nummer ontbreekt."))
            else:
                if not line.national_number:
                    problems.append(self.env._("Rijksregisternummer ontbreekt."))
                elif not national_number_is_valid(line.national_number):
                    problems.append(self.env._("Rijksregisternummer klopt niet (controlegetal)."))
                if line.kbo and not kbo_is_valid(line.kbo):
                    problems.append(self.env._("Ondernemingsnummer klopt niet (controlegetal)."))
            if not line.profession:
                problems.append(self.env._("Beroep ontbreekt."))
            line.warning = "\n".join(problems) or False
