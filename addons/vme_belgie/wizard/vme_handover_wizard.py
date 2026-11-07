"""Handover of one VME to a new syndic: one ZIP with everything the successor needs.

- the CSV files in the format of our own migration import (docs/dev/migratie.md), so the package can
  be read back in with VME > Configuratie > Overstap uit ander pakket;
- PDFs: the handover form, the latest annual statement, balance sheet and income statement, the open
  balances per owner and the reserve fund;
- the documents of the VME (deed, minutes, policies, certificates) under archief/.

The staff member downloads the package and hands it over. Nothing is sent.
"""
import base64
import csv
import io
import mimetypes
import re
import zipfile
from datetime import timedelta

import lxml.html
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date, formatLang

from odoo.addons.base_iban.models.res_partner_bank import normalize_iban, validate_iban

from ..models.account_chart_template import VME_FUND_ACCOUNTS
from ..models.vme_access import check_not_auditor
from ..models.vme_damage import CLOSED_STATES as CLOSED_CLAIM_STATES
from ..models.vme_migration import FINANCING, KEY_TYPES, LOT_TYPES, MANDATE_ROLES, TABLES

# LEGAL-CHECK: art. 3.89 §5, 6° BW - at the end of his mandate the syndic hands over the complete
# management file, with the accounts and the assets he managed, every damage claim and the history of
# the account on which the claims were settled, to his successor (without a successor: to the chair of
# the last general assembly) within thirty days.
HANDOVER_DAYS = 30
# Classes 4 and 5 that the migration import accepts as a plain account (see _Checker._check_opening).
ALLOWED_CLASS_45 = ("490", "491", "492", "493", "499")
# Where the import puts a balance it has no kind for: the suspense account.
SUSPENSE_ACCOUNT = "499000"
CLOSED_WORKS_STATES = ("closed", "cancelled")


def _reverse(mapping):
    """{value: first key} of an import mapping, e.g. "apartment" -> "appartement"."""
    result = {}
    for key, value in mapping.items():
        result.setdefault(value, key)
    return result


LOT_TYPE_NAMES = _reverse(LOT_TYPES)
KEY_TYPE_NAMES = _reverse(KEY_TYPES)
FINANCING_NAMES = _reverse(FINANCING)
MANDATE_ROLE_NAMES = _reverse(MANDATE_ROLES)


def _date(value):
    return value.strftime("%d/%m/%Y") if value else ""


def _amount(value):
    """Amount as the import reads it: no thousands separator, comma as decimal sign (Excel in Belgium)."""
    return f"{value:.2f}".replace(".", ",")


def _shares(value):
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") if value % 1 else str(int(value))


def _valid_iban(value):
    iban = normalize_iban(value or "").upper()
    try:
        validate_iban(iban)
    except ValidationError:
        return ""
    return iban


def _safe_name(name):
    """A file or folder name without characters that zip tools or Windows refuse."""
    return re.sub(r'[\\/:*?"<>|]+', "-", name or "").strip(" .") or "document"


class VmeHandoverWizard(models.TransientModel):
    _name = "vme.handover.wizard"
    _description = "Overdracht aan nieuwe syndicus"

    association_id = fields.Many2one("vme.association", string="VME", required=True)
    handover_date = fields.Date(
        string="Overdrachtsdatum", required=True, default=fields.Date.context_today,
        help="Laatste dag van het mandaat. Saldi en openingsbalans staan op deze datum; de nieuwe syndicus "
             "neemt de boekhouding de dag erna over.",
    )
    deadline = fields.Date(string="Overdragen uiterlijk", compute="_compute_deadline")
    recipient_id = fields.Many2one(
        "res.partner", string="Nieuwe syndicus",
        help="Wie het pakket ontvangt. Is er geen opvolger, dan de voorzitter van de laatste algemene vergadering.",
    )
    statement_year = fields.Integer(
        string="Jaar jaarafrekening en balans", compute="_compute_statement_year", store=True, readonly=False,
        help="Standaard het laatste jaar met boekingen tot de overdrachtsdatum.",
    )
    note = fields.Text(string="Opmerkingen op het overdrachtsdocument")
    summary_html = fields.Html(string="Inhoud", compute="_compute_summary_html", sanitize=False)

    @api.depends("handover_date")
    def _compute_deadline(self):
        for wizard in self:
            wizard.deadline = wizard.handover_date and wizard.handover_date + timedelta(days=HANDOVER_DAYS)

    @api.depends("association_id", "handover_date")
    def _compute_statement_year(self):
        for wizard in self:
            if not wizard.association_id or not wizard.handover_date:
                wizard.statement_year = wizard.handover_date.year if wizard.handover_date else False
                continue
            last = self.env["account.move.line"].sudo().search([
                ("company_id", "=", wizard.association_id.sudo().company_id.id), ("parent_state", "=", "posted"),
                ("date", "<=", wizard.handover_date)], order="date desc", limit=1)
            wizard.statement_year = (last.date or wizard.handover_date).year

    @api.depends("association_id", "handover_date", "statement_year")
    def _compute_summary_html(self):
        for wizard in self:
            if not wizard.association_id or not wizard.handover_date:
                wizard.summary_html = False
                continue
            data = wizard._handover_data()
            tables = data["tables"]
            lines = [
                self.env._("%(lots)s kavels, %(owners)s eigenaars, %(keys)s verdeelsleutels, %(suppliers)s leveranciers",
                           lots=len(tables["kavels"]), owners=len(tables["eigenaars"]),
                           keys=len(data["keys"]), suppliers=len(tables["leveranciers"])),
                self.env._("Openingsbalans op %(date)s: %(count)s regels",
                           date=format_date(self.env, wizard.handover_date), count=len(tables["openingsbalans"])),
                self.env._("%(works)s lopende werken, %(claims)s open schadedossiers, %(procedures)s procedures",
                           works=len(data["works"]), claims=len(data["claims"]), procedures=len(data["procedures"])),
                self.env._("%(contracts)s lopende contracten en %(policies)s polissen, %(mandates)s mandaten",
                           contracts=len(data["contracts"]), policies=len(data["policies"]),
                           mandates=len(data["mandates"])),
                self.env._("%s documenten in het archief", len(data["documents"])),
            ]
            warnings = [Markup("<div class='alert alert-warning mb-1'>%s</div>") % text for text in data["warnings"]]
            wizard.summary_html = Markup("<ul>%s</ul>%s") % (
                Markup("").join(Markup("<li>%s</li>") % line for line in lines), Markup("").join(warnings))

    # --- Collecting ---

    def _handover_data(self):
        """Everything in the package, read as superuser for a VME the user may read."""
        self.ensure_one()
        self.association_id.check_access("read")
        vme = self.association_id.sudo()
        company = vme.company_id
        currency = company.currency_id
        day = self.handover_date
        warnings = []

        lots = vme.lot_ids.sorted(lambda lot: (lot.sequence, lot.name, lot.id))
        ownerships = self.env["vme.ownership"].sudo().search(
            [("lot_id", "in", lots.ids)], order="date_start, id")
        balances = self.env["account.move.line"].sudo()._read_group(
            [("company_id", "=", company.id), ("parent_state", "=", "posted"), ("date", "<=", day)],
            ["account_id", "partner_id"], ["balance:sum"])
        receivable_partners = self.env["res.partner"].browse(
            {p.id for account, p, balance in balances
             if p and account.account_type == "asset_receivable" and not currency.is_zero(balance)})

        # Suppliers: a balance, a bill, a distribution rule or a contract in this VME.
        rules = vme.distribution_rule_ids.filtered("active")
        billed = self.env["account.move"].sudo().search([
            ("company_id", "=", company.id), ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted")]).partner_id.commercial_partner_id
        contracts = vme.contract_ids.filtered(lambda c: c.state != "ended")
        owners = (ownerships.partner_id | receivable_partners.filtered(
            lambda p: p not in billed and p not in rules.partner_id)).sorted(lambda p: (p.name or "", p.id))
        payable_partners = self.env["res.partner"].browse(
            {p.id for account, p, balance in balances
             if p and account.account_type == "liability_payable" and not currency.is_zero(balance)})
        suppliers = (billed | rules.partner_id | contracts.partner_id | payable_partners) - owners
        suppliers = suppliers.sorted(lambda p: (p.name or "", p.id))
        owner_codes = self._partner_codes(owners, "E")
        supplier_codes = self._partner_codes(suppliers, "L")

        key_names, keys = {}, vme.key_ids.sorted(lambda k: (k.sequence, k.id))
        for key in keys:
            name, number = key.name, 2
            while name in key_names.values():
                name, number = f"{key.name} ({number})", number + 1
            key_names[key] = name

        working_bank, reserve_bank = vme.working_capital_bank_id, vme.reserve_capital_bank_id
        bank_journals = self.env["account.journal"].sudo().search(
            [("company_id", "=", company.id), ("type", "=", "bank")])
        bank_accounts = {
            fund: bank_journals.filtered(lambda j, b=bank: b and j.bank_account_id == b)[:1].default_account_id
            for fund, bank in (("working", working_bank), ("reserve", reserve_bank))
        }

        tables = {
            "vme": [{
                "naam": vme.name, "kbo": vme.kbo_number or "", "straat": vme.street or "",
                "postcode": vme.zip or "", "gemeente": vme.city or "",
                "iban_werkkapitaal": _valid_iban(working_bank.acc_number),
                "iban_reservekapitaal": _valid_iban(reserve_bank.acc_number),
                "overstapdatum": _date(day),
            }],
            "kavels": [{"kavel": lot.name, "type": LOT_TYPE_NAMES.get(lot.lot_type, "andere"),
                        "verdieping": lot.floor or ""} for lot in lots],
            "eigenaars": [{
                "code": owner_codes[p], "naam": p.name, "email": p.email or "", "telefoon": p.phone or "",
                "straat": p.street or "", "postcode": p.zip or "", "gemeente": p.city or "",
            } for p in owners],
            "eigendommen": [{
                "kavel": o.lot_id.name, "eigenaar": owner_codes[o.partner_id],
                "begindatum": _date(o.date_start), "einddatum": _date(o.date_end),
            } for o in ownerships],
            "sleutels": [{
                "sleutel": key_names[key], "soort": KEY_TYPE_NAMES.get(key.key_type, "andere"),
                "totaal": _shares(key.total_shares), "kavel": line.lot_id.name, "quotiteit": _shares(line.shares),
                "meerderheid": "",
            } for key in keys for line in key.line_ids.sorted(lambda l: (l.lot_id.sequence, l.lot_id.name))],
            "leveranciers": [],
            "openingsbalans": self._opening_rows(balances, bank_accounts, owner_codes, supplier_codes, warnings),
        }
        for partner in suppliers:
            iban = next(filter(None, (_valid_iban(b.acc_number) for b in partner.bank_ids)), "")
            rule = rules.filtered(lambda r, p=partner: r.partner_id == p and r.key_id)[:1]
            tables["leveranciers"].append({
                "code": supplier_codes[partner], "naam": partner.name,
                "btw": partner.vat or "", "email": partner.email or "", "iban": iban,
                "sleutel": key_names.get(rule.key_id, ""),
            })

        works = self.env["vme.works"].sudo().search(
            [("association_id", "=", vme.id), ("state", "not in", CLOSED_WORKS_STATES)], order="id")
        tables["werken"] = []
        for item in works:
            remaining = currency.round(max((item.contract_amount or item.budget) - item.invoiced_amount, 0.0))
            if currency.is_zero(remaining):
                continue  # nothing left to finance; still on the handover form
            tables["werken"].append({
                "omschrijving": item.name, "bedrag": _amount(remaining),
                "financiering": FINANCING_NAMES.get(item.financing, "reservekapitaal"),
                "sleutel": key_names.get(item.key_id, ""), "datum_av": _date(item.decision_date),
            })
        procedures = self._procedures(vme)
        tables["procedures"] = procedures
        mandates = self.env["vme.mandate"].sudo().search([
            ("association_id", "=", vme.id), ("date_start", "<=", day),
            "|", ("date_end", "=", False), ("date_end", ">=", day)], order="role, date_start")
        tables["mandaten"] = [{
            "rol": MANDATE_ROLE_NAMES[m.role], "naam": m.partner_id.name,
            "begindatum": _date(m.date_start), "einddatum": _date(m.date_end),
        } for m in mandates if m.role in MANDATE_ROLE_NAMES]

        if not (tables["vme"][0]["iban_werkkapitaal"] and tables["vme"][0]["iban_reservekapitaal"]):
            warnings.append(self.env._(
                "De VME heeft geen geldige bankrekening voor beide fondsen: de nieuwe syndicus moet ze na de "
                "overstap zelf invullen, en de banksaldi staan op de wachtrekening."))

        return {
            "vme": vme, "company": company, "currency": currency, "date": day, "keys": keys,
            "tables": tables, "warnings": warnings, "owner_codes": owner_codes,
            "banks": self._bank_rows(vme, bank_accounts),
            "works": works, "claims": vme.damage_claim_ids.filtered(lambda c: c.state not in CLOSED_CLAIM_STATES),
            "procedures": procedures, "contracts": contracts,
            "policies": vme.insurance_policy_ids.filtered(lambda p: not p.date_end or p.date_end >= day),
            "mandates": mandates,
            "syndic_mandates": self.env["vme.syndic.mandate"].sudo().search(
                [("association_id", "=", vme.id), ("date_start", "<=", day)], order="date_start desc", limit=1),
            "documents": self._documents(vme),
        }

    def _partner_codes(self, partners, prefix):
        """{partner: code}: the reference from the old package when it is unique, else prefix + number."""
        refs = [(p.ref or "").strip() for p in partners]
        codes, used = {}, set()
        for partner, ref in zip(partners, refs):
            if ref and refs.count(ref) == 1:
                codes[partner] = ref
                used.add(ref)
        number = 0
        for partner in partners:
            while partner not in codes:
                number += 1
                code = f"{prefix}{number:03d}"
                if code not in used:
                    codes[partner] = code
                    used.add(code)
        return codes

    def _opening_rows(self, balances, bank_accounts, owner_codes, supplier_codes, warnings):
        """The balance of every account on the handover date, in the kinds of openingsbalans.csv."""
        company = self.association_id.sudo().company_id
        currency = company.currency_id
        day = _date(self.handover_date)
        fund_codes = {VME_FUND_ACCOUNTS["working"][0]: "fonds_werkkapitaal",
                      VME_FUND_ACCOUNTS["reserve"][0]: "fonds_reservekapitaal"}
        totals, suspense = {}, {}
        for account, partner, balance in balances:
            if currency.is_zero(balance):
                continue
            account = account.with_company(company)  # codes depend on the company in Odoo 19
            code = account.code or ""
            if account == bank_accounts["working"]:
                row = ("bank_werkkapitaal", "", self.env._("Saldo rekening werkkapitaal op %s", day), 1)
            elif account == bank_accounts["reserve"]:
                row = ("bank_reservekapitaal", "", self.env._("Saldo rekening reservekapitaal op %s", day), 1)
            elif code in fund_codes:
                row = (fund_codes[code], "", self.env._("%(account)s op %(date)s", account=account.name, date=day), -1)
            elif account.account_type in ("asset_receivable", "liability_payable") and partner in owner_codes:
                row = ("eigenaar", owner_codes[partner], self.env._("Saldo op %s", day), 1)
            elif account.account_type in ("asset_receivable", "liability_payable") and partner in supplier_codes:
                row = ("leverancier", supplier_codes[partner], self.env._("Saldo op %s", day), -1)
            elif re.fullmatch(r"\d{6}", code) and (code[0] not in "45" or code[:3] in ALLOWED_CLASS_45) \
                    and account.account_type not in ("asset_receivable", "liability_payable", "asset_cash"):
                row = ("rekening", code, account.name, 1)
            else:
                # The import has no kind for it (another bank account, payments not yet on a statement, VAT, a
                # receivable without owner): one row per account on the suspense account, named in the description.
                named = partner if account.account_type in ("asset_receivable", "liability_payable") else False
                label = f"{code} {account.name}" + (f" - {named.name}" if named else "")
                row = ("rekening", SUSPENSE_ACCOUNT, self.env._("Saldo %s", label), 1)
                suspense[row[2]] = label
            kind, code, label, sign = row
            totals[(kind, code, label)] = totals.get((kind, code, label), 0.0) + balance * sign
        for (_kind, _code, label), amount in totals.items():
            if label in suspense and not currency.is_zero(amount):
                warnings.append(self.env._(
                    "Het saldo van %(label)s (%(amount)s) komt op de wachtrekening %(suspense)s: boek het na de "
                    "overstap op de juiste rekening.", label=suspense[label],
                    amount=formatLang(self.env, amount, currency_obj=currency), suspense=SUSPENSE_ACCOUNT))
        order = ["bank_werkkapitaal", "bank_reservekapitaal", "eigenaar", "leverancier", "rekening",
                 "fonds_werkkapitaal", "fonds_reservekapitaal"]
        return [
            {"soort": kind, "code": code, "bedrag": _amount(currency.round(amount)), "omschrijving": label}
            for (kind, code, label), amount in sorted(totals.items(), key=lambda item: (order.index(item[0][0]), item[0][1]))
            if not currency.is_zero(amount)
        ]

    def _procedures(self, vme):
        """Running proceedings: the items of "Lopende gerechtelijke procedures" and the forwarded collections."""
        root = lxml.html.fromstring(f"<div>{vme.legal_proceedings or ''}</div>")
        items = root.xpath("//li") or root.xpath("//p") or [root]
        rows = [{"omschrijving": " ".join(item.text_content().split()), "tegenpartij": "", "stand": ""}
                for item in items if item.text_content().strip()]
        collections = self.env["vme.collection"].sudo().search(
            [("association_id", "=", vme.id), ("state", "=", "forwarded")], order="id")
        for collection in collections:
            rows.append({
                "omschrijving": self.env._("Invordering achterstallen %s", collection.display_name),
                "tegenpartij": collection.partner_id.name,
                "stand": self.env._("Doorgestuurd naar %(lawyer)s op %(date)s",
                                    lawyer=collection.forward_partner_id.name or "-", date=_date(collection.forward_date)),
            })
        return rows

    def _bank_rows(self, vme, bank_accounts):
        day = self.handover_date
        rows = []
        for fund, bank, label in (("working", vme.working_capital_bank_id, self.env._("Werkkapitaal")),
                                  ("reserve", vme.reserve_capital_bank_id, self.env._("Reservekapitaal"))):
            account = bank_accounts[fund]
            lines = self.env["account.move.line"].sudo().search([
                ("account_id", "=", account.id), ("parent_state", "=", "posted"), ("date", "<=", day)]) if account else []
            rows.append({
                "fund": fund, "label": label, "iban": bank.acc_number or "", "bank": bank.bank_id.name or "",
                "bank_balance": sum(line.balance for line in lines),
                "fund_balance": vme._get_fund_balance(fund, day),
            })
        return rows

    def _documents(self, vme):
        """[(path in the zip, bytes)] of the documents and the files attached to the VME."""
        # The web client reads with bin_size: binary fields would then give "12.3 Kb" instead of the file.
        self, vme = self.with_context(bin_size=False), vme.with_context(bin_size=False)
        files = []
        for document in vme.document_ids.sorted(lambda d: (d.folder_id.sequence, d.date, d.id)):
            if not document.datas:
                continue
            name = document.filename or document.name
            if "." not in name:
                attachment = self.env["ir.attachment"].sudo().search([
                    ("res_model", "=", "vme.document"), ("res_id", "=", document.id), ("res_field", "=", "datas")],
                    limit=1)
                name += mimetypes.guess_extension(attachment.mimetype or "") or ""
            folder = [_safe_name(document.folder_id.name)] + ([_safe_name(document.lot_id.name)] if document.lot_id else [])
            files.append(("/".join(["archief", *folder, _safe_name(name)]), base64.b64decode(document.datas)))
        attachments = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", "vme.association"), ("res_id", "=", vme.id), ("res_field", "=", False),
            ("mimetype", "!=", "application/zip")], order="id")
        for attachment in attachments:
            files.append((f"archief/{_safe_name(self.env._('Bijlagen VME'))}/{_safe_name(attachment.name)}", attachment.raw))
        # The same name twice in one folder: number the later ones.
        seen, result = set(), []
        for path, raw in files:
            stem, dot, extension = path.rpartition(".")
            unique, number = path, 2
            while unique.lower() in seen:
                unique = f"{stem} ({number}).{extension}" if dot else f"{path} ({number})"
                number += 1
            seen.add(unique.lower())
            result.append((unique, raw))
        return result

    # --- Reports ---

    def _arrears_data(self):
        """Open balances per owner on the handover date, with the invoices that are still open today."""
        self.ensure_one()
        data = self._handover_data()
        vme, company, day = data["vme"], data["company"], data["date"]
        lines = self.env["account.move.line"].sudo().search([
            ("company_id", "=", company.id), ("parent_state", "=", "posted"), ("date", "<=", day),
            ("account_id.account_type", "=", "asset_receivable"), ("partner_id", "in", [p.id for p in data["owner_codes"]])])
        collections = self.env["vme.collection"].sudo().search(
            [("association_id", "=", vme.id), ("state", "!=", "closed")])
        result = []
        for partner, code in data["owner_codes"].items():
            own = lines.filtered(lambda l, p=partner: l.partner_id == p)
            balance = data["currency"].round(sum(own.mapped("balance")))
            if data["currency"].is_zero(balance):
                continue
            current = self.env["vme.ownership"].sudo().search([
                ("partner_id", "=", partner.id), ("lot_id.association_id", "=", vme.id),
                ("date_start", "<=", day), "|", ("date_end", "=", False), ("date_end", ">=", day)])
            result.append({
                "code": code, "partner": partner, "lots": ", ".join(current.lot_id.mapped("name")),
                "balance": balance,
                "open_lines": own.filtered(lambda l: not data["currency"].is_zero(l.amount_residual))
                    .sorted(lambda l: (l.date_maturity or l.date, l.id)),
                "collection": collections.filtered(lambda c, p=partner: c.partner_id == p)[:1],
            })
        return {**data, "owners": result,
                "total": data["currency"].round(sum(row["balance"] for row in result)),
                "is_past": day < fields.Date.context_today(self)}

    def _reserve_data(self):
        """Reserve capital on the handover date, its movements in that year and what open works still need."""
        self.ensure_one()
        data = self._handover_data()
        vme, company, day, currency = data["vme"], data["company"], data["date"], data["currency"]
        account = self.env["account.account"].sudo().with_company(company).search([
            ("company_ids", "in", company.id), ("code", "=", VME_FUND_ACCOUNTS["reserve"][0])], limit=1)
        movements = self.env["account.move.line"].sudo().search([
            ("account_id", "=", account.id), ("company_id", "=", company.id), ("parent_state", "=", "posted"),
            ("date", ">=", day.replace(month=1, day=1)), ("date", "<=", day)], order="date, id") if account else []
        # One row per document: a provision call has a line per lot.
        per_move = {}
        for line in movements:
            per_move.setdefault(line.move_id, 0.0)
            per_move[line.move_id] -= line.balance
        movements = [{"date": move.date, "name": move.name, "ref": move.partner_id.name or move.ref or "",
                      "amount": currency.round(amount)} for move, amount in per_move.items()]
        reserve_works = data["works"].filtered(lambda w: w.financing == "reserve")
        committed = currency.round(sum(
            max((w.contract_amount or w.budget) - w.invoiced_amount, 0.0) for w in reserve_works))
        balance = vme._get_fund_balance("reserve", day)
        bank = next(row for row in data["banks"] if row["fund"] == "reserve")
        return {**data, "balance": balance, "opening": vme._get_fund_balance("reserve", day.replace(month=1, day=1)
                                                                             - timedelta(days=1)),
                "movements": movements, "reserve_works": reserve_works, "committed": committed,
                "available": currency.round(balance - committed), "bank": bank}

    def _render_pdf(self, report_ref, records):
        content, _ext = self.env["ir.actions.report"]._render_qweb_pdf(report_ref, records.ids)
        return content

    def _report_files(self, data):
        """[(path, bytes)] of the PDFs, without the handover form (it lists these files)."""
        vme, year = data["vme"], self.statement_year
        files = []
        statement = self.env["vme.annual.statement.wizard"].create({"association_id": vme.id, "year": year})
        if statement._get_statement()["statements"]:
            files.append((f"rapporten/{_safe_name(self.env._('Jaarafrekening %s', year))}.pdf",
                          self._render_pdf("vme_belgie.action_report_annual_statement", statement)))
        else:
            data["warnings"].append(self.env._("Geen jaarafrekening voor %s: er zijn geen kosten of provisies.", year))
        financial = self.env["vme.financial.statements.wizard"].create({"association_id": vme.id, "year": year})
        if financial._get_statements()["has_bookings"]:
            files.append((f"rapporten/{_safe_name(self.env._('Balans en resultatenrekening %s', year))}.pdf",
                          self._render_pdf("vme_belgie.action_report_financial_statements", financial)))
        else:
            data["warnings"].append(self.env._("Geen balans en resultatenrekening voor %s: er zijn geen boekingen.", year))
        files.append((f"rapporten/{_safe_name(self.env._('Openstaande saldi eigenaars'))}.pdf",
                      self._render_pdf("vme_belgie.action_report_handover_arrears", self)))
        files.append((f"rapporten/{_safe_name(self.env._('Reservekapitaal'))}.pdf",
                      self._render_pdf("vme_belgie.action_report_handover_reserve", self)))
        return files

    # --- The package ---

    @api.model
    def _csv(self, table, rows):
        """One table in the migration format: UTF-8 with BOM and ";" so that Excel opens it as is."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", lineterminator="\n")
        writer.writerow(TABLES[table])
        for row in rows:
            writer.writerow([row.get(column, "") for column in TABLES[table]])
        return ("﻿" + output.getvalue()).encode("utf-8")

    def _build_package(self):
        """The handover package as zip bytes, and its file name."""
        self.ensure_one()
        check_not_auditor(self.env)
        data = self._handover_data()
        files = [(f"{table}.csv", self._csv(table, data["tables"][table])) for table in TABLES]
        files += self._report_files(data)
        files += data["documents"]
        form_name = f"rapporten/{_safe_name(self.env._('Overdrachtsdocument'))}.pdf"
        listed = [form_name] + [path for path, _raw in files]
        form = self.with_context(handover_files=listed, handover_warnings=data["warnings"])
        files.insert(0, (form_name, form._render_pdf("vme_belgie.action_report_handover_form", form)))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path, raw in files:
                archive.writestr(path, raw)
        name = _safe_name(self.env._("Overdracht %(vme)s %(date)s", vme=data["vme"].name,
                                     date=self.handover_date.isoformat())) + ".zip"
        return buffer.getvalue(), name

    def action_build_package(self):
        """Build the package, keep it on the VME and download it. Handing it over is up to the staff member."""
        self.ensure_one()
        raw, name = self._build_package()
        vme = self.association_id
        attachment = self.env["ir.attachment"].create({
            "name": name, "raw": raw, "res_model": "vme.association", "res_id": vme.id,
            "mimetype": "application/zip",
        })
        vme.message_post(
            body=self.env._(
                "Overdrachtspakket op %(date)s voor %(recipient)s aangemaakt. Er is niets verstuurd: bezorg het "
                "pakket zelf aan de nieuwe syndicus, uiterlijk op %(deadline)s.",
                date=format_date(self.env, self.handover_date),
                recipient=self.recipient_id.name or self.env._("de nieuwe syndicus"),
                deadline=format_date(self.env, self.deadline)),
            attachment_ids=attachment.ids, subtype_xmlid="mail.mt_note",
        )
        # "self" with download=true: the browser downloads and stays on the page. target "download" opens a
        # pop-up, which browsers block after a request of several seconds.
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "self"}


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    def action_open_handover(self):
        self.ensure_one()
        check_not_auditor(self.env)
        action = self.env["ir.actions.act_window"]._for_xml_id("vme_belgie.vme_handover_wizard_action")
        action["context"] = {"default_association_id": self.id, "dialog_size": "large"}
        return action
