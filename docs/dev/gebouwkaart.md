# Gebouwkaart, budgetopvolging en portefeuille (stap 22)

Code: `models/vme_budget_tracking.py`, `models/vme_building_card.py`, `models/res_partner_supplier_card.py`, `views/vme_building_card_templates.xml` (QWeb), `views/vme_building_card_views.xml`, `security/vme_building_card_security.xml`. Demodata: `BUDGET_LINES` in `demo_data/vme_demo_data.py`. Tests: `tests/test_building_card.py`.

Geen Enterprise-dashboards: alleen standaardweergaven (form, list, kanban, pivot, graph) en één QWeb-sjabloon dat in een Html-veld gerenderd wordt.

## Datamodel

| Model | Wat | Belangrijke velden |
| --- | --- | --- |
| `vme.budget.line` | Werkkapitaalbudget per rekening en sleutel | `budget_id`, `account_id` (kostenrekening van de company), `key_id` (optioneel), `name`, `amount` (≥ 0); `association_id`, `company_id`, `year` opgeslagen related |
| `vme.budget.analysis` | SQL-view voor pivot en graph | `kind` (`budget`, `unassigned`, `actual`), `association_id`, `year`, `date`, `account_id`, `key_id`, `move_id`, `partner_id`, `budget_amount`, `budget_to_date`, `actual_amount`, `difference` |
| `vme.capital.movement` | SQL-view voor het verloop van de kapitalen (lijngrafiek, `cumulated="1"`) | `fund`, `kind` (`in`, `out`), `date`, `move_id`, `partner_id`, `amount` |

Op `vme.budget`: `line_ids`, `lines_total`, `unassigned_amount` (= `working_capital_budget` − som van de regels).

Op `vme.association` (niet opgeslagen, berekend in één `_compute_portfolio`): `working_capital_balance`, `reserve_capital_balance`, `arrears_amount`, `budget_to_date_amount`, `actual_to_date_amount`, `budget_usage`, `signal_reserve`, `signal_arrears`, `signal_assembly`, `signal_inspection`, `signal_count`, `signal_summary`; opgeslagen `arrears_signal_threshold` (standaard 1.000). `building_card_html` is het gerenderde sjabloon.

Op `res.partner`: `vme_supplier_contract_count`, `vme_supplier_open_amount`, `vme_supplier_vme_names`, `vme_supplier_card_html`, met `@api.depends_context("uid")` (zie valkuilen).

## Budgetopvolging

`vme.association._get_budget_tracking(year, date_to)` is de enige Python-berekening; kaart, portaal en tests gebruiken ze.

1. **Budget**: de regels van het budget van `year`, plus één regel zonder rekening en sleutel voor het niet-ingedeelde deel.
2. **Werkelijk**: productregels (`display_type = 'product'`) van geboekte leveranciersfacturen en -creditnota's met `invoice_date` van 1 januari tot `date_to`, bedrag `price_total` (btw inbegrepen, zoals de kostenverdeling), creditnota's negatief. Facturen met `vme_reserve_move_id` (werken uit het reservekapitaal, stap 14) tellen niet mee.
3. **Koppeling**: een kost hoort bij (rekening, sleutel) van zijn factuurregel. Is er voor die rekening alleen een budgetregel zonder sleutel, dan valt de kost daaronder.
4. **Budget tot vandaag** = budget × `budget_elapsed_ratio(year, date_to)`: (dagen van 1 januari tot en met `date_to`) / (dagen in het jaar), begrensd op 0 en 1. Gelijk per dag, ook in een schrikkeljaar.
5. **Status** per rij: `over` als werkelijk > budget tot vandaag × 1,10 (`BUDGET_TOLERANCE`), `no_budget` als er kosten zijn zonder budget, anders `ok`.

Het resultaat geeft `rows` (per rekening en sleutel), `by_account`, `by_key` en `total`.

De SQL-view `vme.budget.analysis` heeft dezelfde bron en dezelfde spreiding per dag, maar met `CURRENT_DATE`, en ze bevat alle geboekte facturen van het jaar (filteren op datum kan in de zoekbalk). Een kost op een rekening met alleen een budgetregel zonder sleutel blijft in de view onder zijn eigen sleutel: per rekening klopt de draaitabel, per sleutel kan ze van de kaart afwijken. `test_analysis_view_matches_tracking` vergelijkt de totalen met de databankdatum.

Vreemde munt: `price_total` staat in de munt van de factuur. Alle VME's werken in euro; een factuur in een andere munt zou in de budgetopvolging niet omgerekend worden (de kostenverdeling rekent wel om).

## Kapitalen

`_get_capital_history(date_to)` geeft per jaar (vanaf het eerste jaar met boekingen) per fonds `opening`, `in`, `out`, `closing`, de stand vandaag en `bank`.

- **Reservekapitaal**: credit op 100200 (provisies) min debet (werken uit het reservekapitaal, stap 14). Dat is hetzelfde als `_get_fund_balance("reserve")`.
- **Werkkapitaal**: credit op 100100 (provisies) min de kosten van de leveranciersfacturen die niet uit het reservekapitaal komen (`price_total`). Rekening 100100 alleen zou blijven groeien: kosten worden op 6xx geboekt, niet op 100100.
- **Op de rekening** (`bank`): saldo van de standaardrekening van het bankdagboek van het fonds (de bankafschriften) plus geregistreerde betalingen in dat dagboek die nog door geen afschrift gekoppeld zijn (`is_matched = False`). In Odoo 19 boekt een betaling zonder tussenrekening op het betaalmiddel niet op de bankrekening zelf.

`vme.capital.movement` toont dezelfde bewegingen (rekeningcodes uit `code_store`, zie valkuilen) voor de grafiek en een draaitabel per jaar.

## Signalen

`_get_signals(today)` geeft een lijst van `{code, label, message}`:

| Code | Regel | Bron |
| --- | --- | --- |
| `reserve` | `reserve_warning` van het budget van `today.year` (stap 5) | `# LEGAL-CHECK: art. 3.86 §3 BW` |
| `arrears` | som van `vme.arrears.amount_residual` > `arrears_signal_threshold` | praktijkregel |
| `assembly` | `_get_assembly_signal`: een niet-geannuleerde AV van dit jaar met een datum buiten haar periode (gehouden, of nog te komen), of de periode van dit jaar is voorbij zonder gehouden AV in de periode | `# LEGAL-CHECK: art. 3.87 §2 BW` |
| `inspection` | een installatie met `due_state` of `risk_analysis_due_state` = `overdue` (stap 6b) | de termijnen zelf staan in `vme_installation.py` |

"Vandaag" komt uit `fields.Date.context_today`, of uit de context `vme_today` zoals bij de AV-planner. De zoekmethodes (`_search_signal`, `_search_signal_count`) berekenen de signalen opnieuw voor alle VME's die de gebruiker mag lezen: de waarden hangen af van veel andere modellen en zitten niet in de cache-afhankelijkheden. Voor 200 VME's is dat een paar seconden; wordt het te traag, dan kan een nachtelijke cron de signalen opslaan.

`vme.arrears` gebruikt `CURRENT_DATE` van de databank, niet `vme_today`.

## Gebouwkaart en leverancierskaart

- `vme_association_view_form_card` is een tweede formulier (priority 90, `create/edit/delete="0"`) met `building_card_html`. `_compute_building_card_html` rendert `vme_belgie.building_card_content` met `_get_building_card_data()`. Alle gegevens worden als sudo gelezen in de company van de VME (`with_company`), zoals de jaarafrekening.
- Lopende dossiers komen rechtstreeks uit `vme.works`, `vme.damage.claim`, `vme.sale.file` en `vme.collection`, niet uit de SQL-view `vme.council.dossier` (die bevat geen werken en schade).
- **Optionele stappen**: open aanvragen (`vme.request`, stap 19) en betaalbatches (`vme.payment.batch`, stap 20) worden alleen gelezen als het model bestaat (`"vme.request" in self.env`); de velden `state` en `company_id` worden eerst nagekeken. Zonder het model toont de kaart een plaatshouder. De statussen volgen main 091ae4f: aanvragen zonder `done`, `closed`, `cancelled` of `refused`; batches in `draft`, `generated` of `sent`. Bestaat `account.move.vme_approval_state` (stap 20), dan toont de kaart bij de te betalen facturen ook de goedkeuring.
- Links in het sjabloon zijn `/odoo/<model>/<id>`, de URL's van de Odoo 19-webclient.
- `res_partner_view_form_supplier_card` doet hetzelfde voor `res.partner` met `supplier_card_content`. De gegevens zijn beperkt tot `_vme_supplier_card_scope()`: de VME's die de gebruiker mag lezen.
- Het portaal erft van `portal_my_vme_detail` en roept in het sjabloon `vme._get_portal_finances()` op (`vme` is daar al sudo en door de controller nagekeken). De controller hoefde niet te veranderen.

## Toegang

| Wie | Gebouwkaart | Portefeuille | Leverancierskaart | Budgetopvolging |
| --- | --- | --- | --- | --- |
| Medewerker (`account.group_account_invoice`) | alle VME's | menu | menu en knop op de partner | alle VME's |
| Commissaris (`group_vme_auditor`) | alleen zijn VME (record rule op `vme.association`) | geen menu; een zoekactie geeft alleen zijn VME | geen menu; zou alleen zijn VME tonen | alleen zijn VME (nieuwe leesregels) |
| Eigenaar (portaal) | eenvoudige versie op `/my/vme/<id>` | - | - | - |

`security/vme_building_card_security.xml` geeft de commissaris leesregels op `vme.budget.line`, `vme.budget.analysis` en `vme.capital.movement`, en een schrijfverbod op `vme.budget.line` (de twee views zijn alleen-lezen via de ACL). De kaarten zelf lezen met sudo, dus de bescherming is de leesregel op `vme.association` en `_vme_supplier_card_scope()`.

## Tests

`tests/test_building_card.py` (16 tests, ongeveer 3 seconden) en `test_demo_portfolio_signals` in `tests/test_demo_data.py` (de signalen van de demo op 5 november 2026): spreiding per dag, budget per rekening en sleutel tot een datum (creditnota, concept, ander jaar), kosten zonder budget en regels zonder sleutel, werken uit het reservekapitaal, view tegenover Python, kapitalen per jaar en op de rekening, elk signaal met en zonder uitzondering, de zoekfilters, de inhoud van beide kaarten, het portaal en de toegang van de commissaris.

## Demo

`BUDGET_LINES` verdeelt het werkkapitaalbudget 2026 en 2027 van de drie VME's. De regels worden in de precommit gemaakt, samen met de rekeningen van de verdeelregels: het rekeningstelsel van een nieuwe company bestaat pas dan. Hof ter Beuken budgetteert de verwarming en de conciërge te laag, zodat de kaart overschrijdingen toont, en bouwt te weinig reserve op (stap 5). `ARREARS_SIGNAL_THRESHOLDS` zet de drempel voor achterstallen van Residentie Linde op 250 €, zodat de portefeuille alle vier de signalen toont. Op 5 november 2026: Hof ter Beuken reservefonds, achterstallen (B7, 1.711,50 €) en AV, Kaaihuis AV, Residentie Linde achterstallen en keuring.

Het werkkapitaalbudget van Hof ter Beuken is 96.000 €, afgestemd op het gascontract (48.000 € per jaar, stap 18) en de conciërge (3.250 € per maand). Met 48.000 € stond het werkkapitaal in oktober op ongeveer −46.000 €, wat voor een syndicus ongeloofwaardig is; nu liggen verwarming en conciërge iets boven het budget, zonder een gat van tienduizenden euro.
