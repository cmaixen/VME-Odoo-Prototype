# Rentmeester (stap 25)

Huurcontracten, huurfacturen, indexering en afrekening van lasten aan huurders, in de aparte module `addons/vme_rentmeester`. De gebruikersuitleg staat in [`docs/kb/rentmeester.md`](../kb/rentmeester.md).

## Waarom een aparte module

De huur hoort bij de verhuurder, niet bij de VME. `vme_belgie` modelleert de vereniging (kavels, sleutels, provisies, jaarafrekening per eigenaar); de rentmeester beheert de relatie eigenaar–huurder en heeft andere klanten, een andere boekhouding en optionele installatie (een syndicus zonder rentmeesterij installeert de module niet). `vme_rentmeester` hangt af van `vme_belgie` en gebruikt er alleen de kavels, eigendommen en `_get_annual_statement` van. Zie [beslissingen](../beslissingen.md).

## Boekhouding: één beheerscompany, de verhuurder als analytische dimensie

- Een `res.company` met `is_rent_management = True` is het rentmeesterkantoor. Nieuwe contracten krijgen die company als standaard (`_default_company`), anders `env.company`.
- Huurfacturen, afrekeningsfacturen en betalingen leven in die company. Een company per verhuurder zou honderden boekhoudingen (en rekeningstelsels) geven voor particulieren die zelf geen boekhouding voeren.
- Elke verhuurder krijgt een analytische rekening in het plan **Verhuurders** (`vme_rentmeester.analytic_plan_landlords`), aangemaakt bij het contract (`_landlord_analytic_account`). Elke huurfactuurlijn krijgt `analytic_distribution = {verhuurder: 100}`.
- De lijnen staan op rekening **489100 Huur en lasten voor rekening van verhuurders** (passief, `res.company._rent_account()` maakt ze aan als ze ontbreekt): de huur is geen omzet van het kantoor maar geld dat het doorstort. Het ereloon van de rentmeester en de doorstorting aan de verhuurder zitten nog niet in het prototype.

## Datamodel

| Model | Inhoud |
| --- | --- |
| `vme.rent.contract` | Pand (`lot_ids` of `property_address`), `region` (uit de postcode van de VME), verhuurder, huurders (`tenant_id` = eerste), datums, `duration_years` → `date_end`, `lease_type`, `rent` (basishuur), `charges_type` (provisie/forfait), `charges_amount`, waarborg, `epc_label`, opzeg (`notice_*`), `charge_line_ids`, `indexation_ids`, `invoice_ids`, `settlement_ids`. `current_rent` = `_get_rent_on(vandaag)`. |
| `vme.rent.contract.charge` | Percentage ten laste van de huurder per rubriek en contract. |
| `vme.rent.charge.category` | Rubriek met standaardpercentage en de criteria leveranciers, soort sleutel en begin van de kostenrekening. |
| `vme.rent.index` | Gezondheidsindex per maand (basis 2013 = 100), door een beheerder bijgewerkt. |
| `vme.rent.indexation` | Eén indexering per verjaardag: indexcijfers, correctiefactor, oude en nieuwe huur, ingangsdatum; concept → bevestigd. De bedragen worden bij het aanmaken vastgezet (`_prepare_amounts`) en alleen met **Herberekenen** opnieuw berekend. |
| `vme.rent.settlement` (+ `.line`) | Afrekening per contract en jaar: regels per factuur en rubriek, totalen, provisies, saldo, factuur. |
| `account.move` | `rent_contract_id`, `rent_period` (eerste dag van de huurmaand), `rent_landlord_id`. |
| `account.move.line` | `rent_line_type`: `rent`, `charges` of `settlement`. |
| `vme.lot` | `rent_contract_ids`, `current_tenant_ids` (berekend, getoond op het kavelformulier). |

## Rekenregels

Alle wettelijke parameters staan in `models/rent_rules.py`, als constanten en zuivere functies met een `# LEGAL-CHECK:` per gewest.

### Indexering (`compute_indexation`)

```text
aanvangsindex  = index(maand vóór de maand van ondertekening)
nieuw cijfer   = index(maand vóór de verjaardag)
theoretisch    = basishuur × nieuw cijfer / aanvangsindex
nieuwe huur    = theoretisch / correctiefactor            (afgerond op de cent)
ingangsdatum   = max(verjaardag, datum brief − 3 maanden)
```

**Correctiefactor** (`freeze_correction`). `ENERGY_FREEZE` geeft per gewest het venster van verjaardagen en het toegelaten deel per EPC-label (1, 0,5 of 0). Valt een verjaardag van het contract in het venster en is het deel kleiner dan 1:

```text
groei          = index(maand vóór die verjaardag) / index(maand vóór de verjaardag een jaar eerder)
                 (of de aanvangsindex als die vorige verjaardag de ingangsdatum is)
correctiefactor = 1 + (1 − toegelaten deel) × (groei − 1)
```

De factor geldt voor die verjaardag en alle latere; daarvoor is hij 1. Bij deel 0 geeft de bevroren verjaardag precies de huur van het jaar ervoor; bij 0,5 ongeveer de helft van de stijging. Een contract dat na het venster begon, heeft geen factor. Zo werkt één formule voor de drie gewesten; alleen de parameters verschillen.

Voorbeeld uit de demo (Linde A2, Vlaanderen, label E, getekend oktober 2021): aanvangsindex september 2021 = 114,66; bevroren verjaardag 1 november 2022 met groei 124,99 / 114,66 = 1,090092. Op 1 november 2026: 850 × 138,21 / 114,66 / 1,090092 = 939,90.

**Voorwaarden** (`_check_can_index`): schriftelijk contract en geen uitsluiting. Eén indexering per verjaardag (niet-geannuleerd).

### Huurfactuur (`_rent_invoice_vals`)

Periode = de maand ∩ [ingangsdatum, min(einddatum, einde opzeg, einde huur)]. Bedrag = huur op de eerste dag van die periode × dagen / dagen van de maand, apart voor huur en lasten. Factuurdatum en vervaldag: de eerste van de maand (huur is vooraf te betalen). Hoogstens één niet-geannuleerde factuur per contract en maand. Bij **Bevestigen** van een indexering worden de conceptfacturen vanaf de nieuwe ingangsmaand opnieuw gemaakt.

### Afrekening aan de huurder (`vme.rent.settlement._prepare_values`)

1. `association._get_annual_statement(jaar, partners=verhuurder)` geeft de facturen van het jaar met het aandeel van de verhuurder.
2. Per factuur de `vme.cost.allocation`s van de verhuurder op de kavels van het contract.
3. Per allocatie: rubriek via `vme.rent.charge.category._match` (leverancier > soort sleutel > langste rekeningprefix), en `bedrag × overlap(allocatieperiode, huurperiode) / dagen van de allocatie`. De huurperiode is niet begrensd tot het jaar: welke facturen meetellen, bepaalt de jaarafrekening (factuurdatum in het jaar).
4. Per factuur en rubriek één regel; aandeel huurder = afgerond(deel tijdens de huur) × percentage van het contract, opnieuw afgerond.
5. Provisies = som van de `charges`-lijnen van geboekte huurfacturen met `rent_period` in het jaar (gefactureerd, niet betaald: een onbetaalde provisie blijft een eigen schuld).
6. Saldo = totaal huurder − provisies. De factuur is een concept: een `out_invoice` met een regel per rubriek en een negatieve regel voor de provisies, of een `out_refund` als het saldo negatief is.

Een forfait wordt nooit afgerekend (`UserError`). Is de jaarafrekening niet volledig (`is_complete`), dan staat `statement_incomplete` aan.

### Opzeg (`notice_deadline`, `notice_end_date`)

- Uiterste opzegdatum: kortlopend 3 maanden, negen jaar 6 maanden (verhuurder) vóór de einddatum, telkens de laatste dag van de maand vóór de termijn begint.
- Einde na opzeg: de termijn begint de eerste dag van de maand na de opzeg.

## Crons (alleen concepten en taken)

| Cron | Wat |
| --- | --- |
| `ir_cron_rent_invoices` | `_cron_rent_invoices`: conceptfacturen van de lopende maand voor elk lopend contract. |
| `ir_cron_rent_reminders` | `_cron_rent_reminders`: taak 30 dagen vóór de uiterste opzegdatum (één keer per datum, `activity_notice_deadline`), en een conceptindexering met taak 45 dagen vóór de verjaardag, zodra het indexcijfer bestaat. |

## Rapporten

`report/rent_reports.xml` met `report/rent_reports.py`: **Indexatiebrief** (`vme.rent.indexation`) en **Afrekening lasten huurder** (`vme.rent.settlement`). De rapportmodellen geven `format_date` mee (met optioneel `date_format`, bv. `'MMMM y'`).

## Demo

`demo_data/rent_demo.py` breidt `_load_demo_data` en `_load_demo_history` van `vme.association` uit:

- **Demodata**: company **Rentmeester Voorbeeld BV** (rekeningstelsel bij de commit, zoals bij een VME), drie contracten (Linde A2+G2, Linde A7, Beuken B23) met hun bevestigde indexeringen, een conceptindexering voor Linde A2 op 1 november 2026 en de taken rond de demodatum (5 november 2026), los van de echte datum (`_demo_reminders`).
- **Demohistoriek**: de schoonmaakfirma aan de rubriek schoonmaak koppelen, huurfacturen januari–oktober 2026 boeken en betalen (behalve oktober van Linde A7).

De indextabel (`data/vme_rent_index_data.xml`, januari 2015 – oktober 2026) is fictief maar realistisch en staat in `noupdate`.

## Tests

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie,vme_rentmeester --test-enable --test-tags /vme_belgie,/vme_rentmeester --stop-after-init
```

| Bestand | Wat |
| --- | --- |
| `tests/test_indexation.py` | Formule en indexmaanden, indexstop per gewest (Vlaanderen, Brussel, Wallonië) met handberekende bedragen, venstergrenzen, contract na de stop, terugwerkende kracht, gewest uit postcode, opzegdatums; op een contract: opeenvolgende indexeringen, ontbrekend indexcijfer, mondeling of uitgesloten contract, waarborg per gewest. |
| `tests/test_settlement.py` | Afrekening per factuur en rubriek (handberekend), aansluiting op de jaarafrekening, percentage per contract, conceptfactuur en creditnota, forfait, einde huur midden in het jaar, huurfacturen (pro rata, na indexering, geen dubbele, ook met een andere company geselecteerd), opzeg, rapporten. |
| `tests/test_demo.py` | De drie demo-contracten, conceptindexering, opzegtaak en de indexstop van Beuken B23. |

## Uitbreidingspunten en wat ontbreekt

- **Huurders in het portaal (stap 27):** `res.partner._vme_portal_tenant_lots()` (`models/res_partner.py`) voegt de kavels van de huurcontracten van de partner toe; of het contract vandaag loopt, beslist `vme.lot._get_tenants_on`. Zo kan een huurder met een login een aanvraag indienen voor zijn kavel, ook zonder `vme.lot.contact`.

- **Doorstorting aan de verhuurder** en het **ereloon van de rentmeester**: een afrekening per verhuurder uit de analytische rekening (geïnde huur min ereloon en kosten).
- **Registratie** van het contract, **plaatsbeschrijving** en **huurwaarborg** als eigen dossiers; nu alleen velden en een taak.
- **Opzeg met reden** door de verhuurder in een contract van negen jaar (eigen gebruik, werken, zonder reden met vergoeding) en de tussentijdse termijnen van drie jaar: niet gemodelleerd.
- **Daling van de index**: de huur daalt mee; een minimumclausule in het contract is niet voorzien.
- **bpost** voor brieven valt buiten het prototype (zie stap 23).
