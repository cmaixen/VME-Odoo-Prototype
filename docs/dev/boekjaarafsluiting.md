# Afsluiting van het boekjaar

Code: `addons/vme_belgie/models/vme_fiscal_closing.py`, views in `views/vme_fiscal_closing_views.xml`, tests in `tests/test_fiscal_closing.py`. Gebruikersuitleg: [docs/kb/boekjaar-afsluiten.md](../kb/boekjaar-afsluiten.md).

## Model `vme.fiscal.closing`

Eén dossier per VME en boekjaar (SQL-uniek op `association_id`, `year`), met `mail.thread` voor de historiek. Het formulier is de "wizard": er is geen transient model, omdat het dossier bewaard moet blijven (wie sloot af, wanneer, welke documenten, welke overdracht).

| Veld | Uitleg |
| --- | --- |
| `state` | `draft` (te controleren) → `prepared` (afrekening voorbereid) → `closed` (afgesloten). Heropenen gaat van `closed` terug naar `prepared`. |
| `settlement_move_ids` | De afrekeningsdocumenten: `account.move.vme_fiscal_closing_id` (`ondelete="restrict"`). |
| `settlement_total`, `settlement_count`, `settlement_draft_count` | Berekend; het totaal is bijbetalingen min teruggaven (zonder geannuleerde documenten). |
| `check_html`, `can_prepare`, `can_close` | Berekend uit `_get_checks()`. |
| `summary_html` | Berekend uit `_get_carry_forward()`. |
| `working_result`, `reserve_result`, `working_capital`, `reserve_capital`, `owner_receivable`, `supplier_payable`, `bank_working`, `bank_reserve` | Snapshot van de overdracht, geschreven door `action_close()`. |

Toegang: `base.group_user` mag lezen, schrijven en aanmaken, maar niet verwijderen. Zoals elk VME-model heeft het een globale company-regel op `user.company_ids` (de toegestane bedrijven, niet de geselecteerde), zodat een medewerker het dossier ook opent terwijl bovenaan een ander bedrijf staat. De commissaris volgt het patroon van `vme_council_security.xml`: hij leest alleen de dossiers van zijn VME's en kan niets wijzigen (`security/vme_fiscal_closing_security.xml`). Afsluiten en heropenen controleren zelf op `account.group_account_manager` (`_check_manager`) en schrijven de vergrendeling als `sudo()`.

### Meerdere bedrijven

De record-regels van `account.move` verbergen de documenten van een bedrijf dat niet in de bedrijfskeuze staat, ook in een One2many. Daarom gelden deze regels:

- `_settlement_moves()` leest de afrekeningsdocumenten als `sudo()`, voor de tellers, het totaal en "al geboekt". Zonder `sudo()` zou "Opnieuw voorbereiden" de geboekte documenten niet zien en dubbel boeken.
- `_settlement_moves_as_user()` neemt dezelfde ids als de gebruiker, `with_company(company_id)`, om ze te verwijderen of te boeken. Zo gelden de gewone rechten van de boekhouding.
- Staat het bedrijf van de VME niet in de keuze (`company_selected`), dan toont het tabblad een HTML-tabel (`settlement_html`) met een melding in plaats van de lijst.

## Toegangspunten (ook voor de jaarcyclus)

- `vme.association._get_fiscal_closing(year)`: zoekt of maakt het dossier.
- `vme.association.action_open_fiscal_closing(year=None)`: opent het formulier. Met `year` het dossier van dat jaar. Zonder jaar het oudste dossier dat nog niet afgesloten is, of een nieuw formulier voor het jaar na het laatst afgesloten jaar (standaard vorig jaar).
- `vme.fiscal.closing._get_checks()`: lijst van dicts `{code, ok, blocking, message, records}`. Codes: `complete`, `draft_bills`, `draft_provisions`, `bank`, `settlement`, `year_over`, `previous`. `blocking` is `"prepare"` (blokkeert voorbereiden en afsluiten), `"close"` (blokkeert alleen afsluiten) of `False` (waarschuwing).
- Acties: `action_prepare()`, `action_post_settlements()`, `action_close()`, `action_reopen()`.

## Jaarcyclus

De stap "Boekjaar afsluiten" van de jaarcyclus (`vme.cycle.step`, code `closing`) koppelt bij het klaarzetten het dossier van het vorige jaar (`_prepare_closing` maakt het als concept aan als het nog niet bestaat), zodat **Open** naar het dossier gaat. De stap is afgerond zodra `fiscalyear_lock_date` op 31/12 staat (`_cycle_fiscal_year_closed`), wat `action_close` doet.

## Controles

| Code | Wat | Blokkeert |
| --- | --- | --- |
| `complete` | `is_complete` van de jaarafrekening: alle geboekte kosten verdeeld | voorbereiden |
| `draft_bills` | leveranciersfacturen in concept met factuurdatum in het jaar | voorbereiden |
| `draft_provisions` | provisiefacturen van het budgetjaar in concept | voorbereiden |
| `bank` | bankregels tot 31/12 niet afgepunt, met het domein van Odoo zelf (`res.company._get_unreconciled_statement_lines_domain`) | afsluiten |
| `settlement` | nog niet voorbereid, of afrekeningsdocumenten in concept | afsluiten |
| `year_over` | vandaag na 31/12 van het jaar | waarschuwing |
| `previous` | vorig jaar afgesloten, of geen boekingen vóór dit jaar | waarschuwing |

`check_html` toont onder een mislukte controle links naar de records (`records`, maximaal tien, via `_record_links`), zodat de medewerker de factuur in concept of de bankregel meteen opent. De demohistoriek laat de ereloonfacturen van de syndicus als concept in de VME staan; die houden het voorbereiden tegen tot een medewerker ze bevestigt (in de `vme_slow`-test gebeurt dat in `setUpClass`).

De controle `bank` vangt op wat Odoo zelf weigert bij het zetten van een vergrendeldatum (`_validate_locks`, met een Engelse melding).

## Afrekening per eigenaar (`action_prepare`)

Uit `_get_annual_statement(year)`, per eigenaar:

```
bedrag = aandeel in de kosten − gefactureerde provisies werkkapitaal − al geboekte afrekening
```

- `> 0`: concept-`out_invoice`; `< 0`: concept-`out_refund`; `0`: niets.
- Factuur- en boekingsdatum 31/12 van het jaar, verkoopdagboek, één lijn op 100100 zonder btw, `vme_fund = "working"`, vervaldag 30 dagen na vandaag (of na 31/12 als dat later is).
- `vme_fund` zorgt dat een bijbetaling de bankrekening van het werkkapitaal krijgt (`_compute_partner_bank_id`). Voor een creditnota slaat die compute nu over (`move_type != "out_refund"`): de terugbetaling gaat naar de rekening van de eigenaar, niet naar de eigen rekening van de VME.
- Gefactureerd en niet betaald: de onbetaalde provisie blijft een eigen open factuur. Afrekening + open provisie = saldo uit de jaarafrekening (kosten − betaald). Dezelfde regel als bij de huurafrekening (stap 25).
- Opnieuw voorbereiden verwijdert alleen concepten. Geboekte documenten tellen mee in "al geboekt", en alleen het verschil komt erbij.
- Het reservekapitaal wordt niet aangeraakt (`# LEGAL-CHECK: art. 3.86 §3 BW`).
- Afrekeningsdocumenten hebben geen `vme_provision_call_id` en tellen dus niet mee als provisie in een volgende jaarafrekening.

## Resultaat en overdracht (`_get_carry_forward`)

Hergebruikt `vme.association._get_capital_history(31/12)` uit de gebouwkaart (stap 22):

- werkkapitaal: in = credit op 100100 (provisies, bijbetalingen), uit = debet op 100100 (teruggaven) + kosten van leveranciersfacturen (`price_total`, zonder facturen uit het reservekapitaal);
- reservekapitaal: in = credit op 100200, uit = debet (aanwending voor werken);
- resultaat = in − uit van het jaar; over te dragen = stand op 31/12;
- daarnaast het saldo op 31/12 van de debiteurenrekeningen (`asset_receivable`), de leveranciersrekeningen (`liability_payable`) en de bank per fonds.

Er komt **geen afsluitboeking**. Odoo draagt balansrekeningen vanzelf over, en de resultatenrekening van stap 26 (branch `claude/elegant-moser-d947ec`) leest de kosten van een jaar uit de 6-rekeningen en zet 100100 en het resultaat samen onder 489 "over te dragen middelen". Een boeking 6/7 → 100100 op 31/12 zou daar de kosten van het jaar op nul zetten. De afrekening zelf komt op rekeningen die stap 26 indeelt in het minimumrekeningstelsel: 100100 → 701 (voorschotten werkkapitaal) en 48902, de vordering met `vme_fund = "working"` → 4101.

## Vergrendeling

`action_close()` zet `res.company.fiscalyear_lock_date` op 31/12, maar nooit terug naar een vroegere datum. Het gaat om de "soft lock" van Odoo 19:

- Geboekte documenten tot en met die datum kunnen niet meer naar concept of van datum veranderen.
- Een **nieuwe** boeking of factuur met een datum in het afgesloten jaar wordt **niet geweigerd**. `account.move._post()` verschuift de boekingsdatum naar de eerste open periode (einde van de eerste open maand, of vandaag). De factuurdatum blijft wel staan.
- `hard_lock_date` gebruiken we niet, want die kan nooit meer terug.

`action_reopen()` zet de vergrendeling terug op 31/12 van het vorige jaar (als dat afgesloten is) of leeg. Dat kan alleen als geen later jaar afgesloten is.

### Gevolg voor de jaarafrekening

Door die verschuiving kan een factuur een factuurdatum in het afgesloten jaar hebben en een boekingsdatum in het nieuwe jaar. `_get_annual_statement` neemt daarom een factuur op in jaar J als:

- de factuurdatum in J ligt én de boekingsdatum ≤ 31/12 van J, **of**
- de boekingsdatum in J ligt én de factuurdatum vóór J.

Zo verandert een afgesloten jaar niet meer, en telt een late factuur mee in het jaar waarin ze geboekt is. Voor gewone facturen zijn factuurdatum en boekingsdatum gelijk, en verandert er niets. De gebouwkaart en de budgetopvolging rekenen nog op de factuurdatum.

## Tests

- `TestFiscalClosing` (standaard): klein scenario 2025, met de hand na te rekenen (zie de docstring). Het test het bedrag per eigenaar, factuur of creditnota, 100100 en `vme_fund`, het totaal = kosten − gefactureerde provisies, een open provisie, het reservekapitaal, een verkoop op 1/7, de blokkerende controles, vergrendelen en heropenen, een late factuur, opnieuw voorbereiden en de rechten.
- `TestFiscalClosingDemo` (`vme_slow`): de demohistoriek 2026 van de drie VME's afrekenen (afrekening + open provisie = saldo voor elke eigenaar) en Residentie Linde afsluiten.

## Uitbreidingen voor later

- Verrekenen met de volgende provisieoproep in plaats van een creditnota (nu met de hand via "openstaand tegoed").
- Een PDF van het afsluitdossier (resultaat en overdracht) voor de AV.
- De 693-boeking van het KB als echte boeking, als de boekhouder dat vraagt. Stap 26 en deze afsluiting moeten dan samen aangepast worden.

## Beveiliging

Status, `closed_by_id`, `closed_on`, `lock_date_before` en de bewaarde overdracht schrijft alleen de code van de knoppen, als superuser (`PROTECTED_FIELDS`); een gewone `write` of `create` met die velden geeft een `AccessError`. Afsluiten bewaart de vergrendeling van daarvoor in `lock_date_before`; heropenen zet die terug, maar alleen als de vergrendeling nog op 31 december van dat jaar staat. Een oudere afsluiting zonder `lock_date_before` valt terug op het einde van een afgesloten vorig jaar.
