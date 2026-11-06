# Balans en resultatenrekening per VME (stap 26)

Odoo 19 Community heeft geen financiële rapporten: balans, resultatenrekening en grootboekrapporten zitten in de Enterprise-module `account_reports`. Die gebruiken of kopiëren we niet. `vme_belgie` maakt een eigen balans en resultatenrekening per VME, ingedeeld volgens het minimumrekeningstelsel voor VME's (KB 12 juli 2012, bijlage; uitgewerkt voorbeeld in CBN-advies 2012/14).

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `models/vme_financial_statements.py` | Rubrieken van het KB, koppeling van onze PCMN-rekeningen, `vme.association._get_financial_statements(year)` |
| `models/account_chart_template.py` | `_vme_make_purchase_vat_non_deductible`: btw op aankopen wordt een kost |
| `wizard/vme_financial_statements_wizard.py` (+ views) | Scherm met VME, boekjaar en voorbeeld; menu **VME > Balans en resultatenrekening** |
| `report/vme_financial_statements_report.xml` (+ `.py`) | Eén QWeb-body voor scherm en PDF, PDF in `web.external_layout` |
| `migrations/19.0.1.12.0/post-migrate.py` | Niet-aftrekbare btw voor bestaande VME's |
| `tests/test_financial_statements.py` | Standaardtests; `test_financial_statements_of_demo_history` in `test_annual_statement.py` (`vme_slow`) |

Knoppen **Balans en resultatenrekening** staan op het VME-formulier en op de gebouwkaart (`action_open_financial_statements`).

## Wat het KB vraagt, en hoe wij boeken

Het KB kent **geen klasse 10**: een VME heeft geen eigen vermogen. Provisies zijn opbrengsten (700 voorschotten reservekapitaal, 701 werkkapitaal); op het einde van het jaar gaat het verschil tussen opbrengsten en kosten via 693 naar **489 over te dragen middelen** (48901 reserve, 48902 werk), een schuld aan de eigenaars. In het nieuwe jaar wordt 489 terug als opbrengst geboekt.

Wij boeken anders, en herboeken niet:

| Wat | Onze boeking | Voorstelling in het rapport |
| --- | --- | --- |
| Provisie reservekapitaal | krediet 100200 | 700 Voorschotten reservekapitaal |
| Provisie werkkapitaal | krediet 100100 | 701 Voorschotten werkkapitaal |
| Werken uit het reservekapitaal | factuur op 6xx, daarna debet 100200 / krediet 6xx (`vme_reserve_move_id`) | bruto kost (meestal 611), afgetrokken van het reservekapitaal in "over te dragen middelen" |
| Stand van de fondsen | saldo 100100/100200 + resultaat van alle jaren (Odoo maakt geen afsluitboeking) | 48901 = saldo 100200; 48902 = saldo 100100 + gecumuleerd resultaat |
| Overschot van het jaar | geen boeking | 693, uitgewerkt in de tabel "Over te dragen middelen per fonds" |
| Btw op leveranciersfacturen | op de kostenrekening (vanaf stap 26) | in de kost |

De keuze staat in `docs/beslissingen.md`: 100100/100200 worden in heel de module gebruikt (provisiewizard, kapitalen, raad, verkoopdossier, migratie, werken). Herboeken naar 700/701 en 489 zou al die plaatsen raken; het rapport geeft dezelfde cijfers in de vorm van het KB.

## Indeling van de rekeningen

### Balans (per 31/12, met het vorige jaar)

De regels worden per rekening, dagboek en boeking samengeteld (`_read_group` op `account.move.line`, gepost, company van de VME) en ingedeeld in `_financial_balance_sheet`:

| Rekening | Rubriek |
| --- | --- |
| 100200 | 48901 Over te dragen middelen reservekapitaal |
| 100100 en alle kosten- en opbrengstenrekeningen | 48902 Over te dragen middelen werkkapitaal |
| Klanten (`asset_receivable`) | 4100 / 4101 volgens `vme_fund` van de factuur, anders het fonds van het bankdagboek, anders 416 |
| Bank (`asset_cash`) en betalingen nog zonder afschrift | 550 / 551 volgens het bankdagboek van het fonds, 552 andere bank, 57 kas |
| Overige vlottende activa | 53, 58, 49 (overlopend en wachtrekening), anders 416 |
| Leveranciers (`liability_payable`) | 440, of 444 te ontvangen facturen |
| Overige schulden | 17, 42, 43, 45, 49, anders 48 |
| Andere eigen-vermogensrekeningen | "Niet ingedeeld", met een waarschuwing |

Onder elke rubriek staan de onderliggende rekeningen in kleine letters, zodat de commissaris kan narekenen.

### Resultatenrekening (van 1/1 tot 31/12)

Kosten op prefix van onze PCMN-code (langste prefix wint, `COST_PREFIXES`), facturen van een werkdossier altijd op 611:

| PCMN | KB-rubriek |
| --- | --- |
| 611 onderhoud en herstellingen | 610 Onderhoud gebouw, tuin en terreinen |
| factuur met `vme_works_id` | 611 Renovatie en andere uitzonderlijke werken |
| 60, 612 leveringen (6125 water, elektriciteit, gas) | 612 Leveringen aan de vereniging |
| 613 erelonen | 613 Erelonen, raad en commissaris (613310/613311 software: 616) |
| 614 verzekeringen | 614 Verzekeringen |
| 610 huur, 616, 617, 618 | 616 Administratie- en beheerskosten |
| 62, 63, 64, 65, 66 | zelfde rubriek; 67–69 naar 64 |
| 75 | 75 Financiële opbrengsten (o.a. 751000 nalatigheidsinterest) |
| andere 7 | 76 Uitzonderlijke en andere opbrengsten (o.a. 743000 schadevergoeding) |

615 Conciërgewoning heeft geen PCMN-tegenhanger: de loonkost van een conciërge staat op 62. Andere opbrengsten gaan naar het werkkapitaal.

### Controles

- `balance_ok`: activa = passiva, voor beide jaren. Klopt altijd bij dubbel boekhouden zolang elke rekening ingedeeld is.
- `carry_ok`: eindstand van "over te dragen middelen" per fonds = 48901/48902 op de balans. Faalt als er op een eigen-vermogensrekening `equity_unaffected` geboekt is, of als de reserveboekingen niet gekoppeld zijn.
- `unclassified`: rekeningen die niet in het KB passen.

Het scherm toont bovenaan groen of oranje.

## Niet-aftrekbare btw

Een VME is meestal niet btw-plichtig en trekt de btw niet af (`# LEGAL-CHECK: art. 45 §1 WBTW`). Tot stap 26 boekte Odoo de btw van leveranciersfacturen op 411000 (terug te vorderen btw); de verdeling, de afrekening en de budgetopvolging rekenden wel met `price_total`. Nu maakt `_vme_make_purchase_vat_non_deductible` de rekening van de btw-verdeelregels van elke aankoopbtw leeg (en `use_in_tax_closing` uit). Odoo boekt de btw dan op de rekening van de factuurregel (`account_tax.py`: `tax_rep_data['account'].id or base_line_grouping_key['account_id']`). Btw met verlegging (een negatieve verdeelregel) blijft ongemoeid. Een btw-plichtige VME kan later een schakelaar krijgen.

Voor bestaande databases doet het migratiescript hetzelfde; geboekte facturen blijven op 411000 staan.

## Toegang

`_get_financial_statements` doet `check_access("read")` op de VME en leest daarna met `sudo()`. De commissaris van de rekeningen (`group_vme_auditor`) kan de VME's van zijn mandaten kiezen (record rule op `vme.association`) en krijgt een `AccessError` voor een andere VME. De wizard is een TransientModel met ACL voor `base.group_user` en schrijft niets in de boekhouding; de alleen-lezenweergave van stap 16 slaat transient models over.

## Uitbreiden

- Een rubriek toevoegen: in `BALANCE_ASSETS`, `BALANCE_LIABILITIES`, `INCOME_STATEMENT_COSTS` of `INCOME_STATEMENT_INCOME`, en de indeling in `_financial_balance_sheet` of `COST_PREFIXES`.
- Subrekeningen per kavel (zoals het CBN-voorbeeld voor 410 en 489 aanraadt) kunnen uit `vme_fund` en de partner van de regel; nu staan ze per rubriek.
- Kosten verdelen over reserve en werk op andere opbrengsten (interest op de reserverekening) gebeurt niet: alle andere opbrengsten gaan naar het werkkapitaal.
