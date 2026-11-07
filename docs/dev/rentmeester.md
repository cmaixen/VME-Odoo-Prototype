# Rentmeester (stap 25)

Huurcontracten, huurfacturen, indexering en afrekening van lasten aan huurders, in de aparte module `addons/vme_rentmeester`. De gebruikersuitleg staat in [`docs/kb/rentmeester.md`](../kb/rentmeester.md).

## Waarom een aparte module

De huur hoort bij de verhuurder, niet bij de VME. `vme_belgie` modelleert de vereniging (kavels, sleutels, provisies, jaarafrekening per eigenaar); de rentmeester beheert de relatie eigenaar–huurder en heeft andere klanten, een andere boekhouding en optionele installatie (een syndicus zonder rentmeesterij installeert de module niet). `vme_rentmeester` hangt af van `vme_belgie` en gebruikt er alleen de kavels, eigendommen en `_get_annual_statement` van. Zie [beslissingen](../beslissingen.md).

## Boekhouding: één beheerscompany, de verhuurder als analytische dimensie

- Een `res.company` met `is_rent_management = True` is het rentmeesterkantoor. Nieuwe contracten krijgen die company als standaard (`_default_company`), anders `env.company`.
- Huurfacturen, afrekeningsfacturen en betalingen leven in die company. Een company per verhuurder zou honderden boekhoudingen (en rekeningstelsels) geven voor particulieren die zelf geen boekhouding voeren.
- Elke verhuurder krijgt een analytische rekening in het plan **Verhuurders** (`vme_rentmeester.analytic_plan_landlords`), aangemaakt bij het contract (`_landlord_analytic_account`). Elke huurfactuurlijn krijgt `analytic_distribution = {verhuurder: 100}`.
- De lijnen staan op rekening **489100 Huur en lasten voor rekening van verhuurders** (passief, `res.company._rent_account()` maakt ze aan als ze ontbreekt): de huur is geen omzet van het kantoor maar geld dat het doorstort. Het ereloon van de rentmeester en de doorstorting aan de verhuurder staan in [Doorstorting en ereloon](#doorstorting-en-ereloon-stap-25b).

## Datamodel

| Model | Inhoud |
| --- | --- |
| `vme.rent.contract` | Pand (`lot_ids` of `property_address`), `region` (uit de postcode van de VME), verhuurder, huurders (`tenant_id` = eerste), datums, `duration_years` → `date_end`, `lease_type`, `rent` (basishuur), `charges_type` (provisie/forfait), `charges_amount`, waarborg, `epc_label`, opzeg (`notice_*`), `charge_line_ids`, `indexation_ids`, `invoice_ids`, `settlement_ids`. `current_rent` = `_get_rent_on(vandaag)`. |
| `vme.rent.contract.charge` | Percentage ten laste van de huurder per rubriek en contract. |
| `vme.rent.charge.category` | Rubriek met standaardpercentage en de criteria leveranciers, soort sleutel en begin van de kostenrekening. |
| `vme.rent.index` | Gezondheidsindex per maand (basis 2013 = 100), door een beheerder bijgewerkt. |
| `vme.rent.indexation` | Eén indexering per verjaardag: indexcijfers, correctiefactor, oude en nieuwe huur, ingangsdatum; concept → bevestigd. De bedragen worden bij het aanmaken vastgezet (`_prepare_amounts`) en alleen met **Herberekenen** opnieuw berekend. |
| `vme.rent.settlement` (+ `.line`) | Afrekening per contract en jaar: regels per factuur en rubriek, totalen, provisies, saldo, factuur. |
| `vme.rent.mandate` | Beheermandaat per verhuurder en kantoor: `fee_type` (`percent`/`fixed`), `fee_percent`, `fee_on_charges`, `fee_amount` (per maand), `fee_tax_id` (21 % diensten), `partner_bank_id`, datums; geen overlap per verhuurder. |
| `vme.rent.remittance` (+ `.line`) | Doorstorting per verhuurder, kantoor en maand: regels `rent`/`charges`/`settlement`/`cost`/`fee`, totalen, `balance`, `fee_invoice_id`, `payout_move_id`, `offset_move_id`, `payment_status` (berekend). |
| `account.move` | `rent_contract_id` (op een leveranciersfactuur: kost voor de verhuurder), `rent_period` (eerste dag van de huurmaand), `rent_landlord_id`, `rent_remittance_id`. |
| `account.move.line` | `rent_line_type`: `rent`, `charges`, `settlement`, `cost`, `fee` of `remittance`. |
| `vme.payment.batch` | `rent_company_id` naast `association_id`; `company_id` berekend uit een van beide (uitbreiding in `vme_rentmeester/models/vme_payment.py`). |
| `res.company` | `is_rent_management`, `rent_bank_id` (derdenrekening). |
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

## Doorstorting en ereloon (stap 25b)

Gebruikersuitleg: [`docs/kb/doorstorting-verhuurder.md`](../kb/doorstorting-verhuurder.md).

**Berekening** (`vme.rent.remittance._recompute_lines`, zuivere functies in `models/remittance_rules.py`):

- *Ontvangen*: per geboekte huur- of afrekeningsfactuur (ook creditnota's) van de contracten van de verhuurder in het kantoor, met factuurdatum tot het einde van de maand: `amount_total − amount_residual` min wat al in een **bevestigde** doorstorting zat. Een gedeeltelijke betaling wordt naar verhouding over huur en lasten verdeeld (`split_received`); een afrekeningsfactuur telt als `settlement`.
- *Kosten*: geboekte leveranciersfacturen (en creditnota's) in het kantoor met `rent_contract_id`, nog niet in een bevestigde doorstorting, bedrag met btw.
- *Ereloon*: per mandaat van de contracten in de regels. `percent`: percentage × huur (+ lasten en afrekeningen als `fee_on_charges`). `fixed`: bedrag × `months_to_charge` (maanden sinds de laatste bevestigde doorstorting met een ereloonregel van dat mandaat, of sinds het begin van het mandaat). Btw via `tax.compute_all`.
- *Saldo* = ontvangen − kosten − ereloon met btw. Negatief: `action_confirm` weigert, `action_carry_over` zet de doorstorting op `cancel` en de volgende neemt alles mee.

**Boekingen bij `action_confirm`** (datum = vandaag, of `rent_remittance_date` in de context voor de demohistoriek):

| Stuk | Soort | Regels |
| --- | --- | --- |
| Ereloonfactuur | `out_invoice` aan de verhuurder | 700100 Erelonen rentmeester (`_rent_fee_account`), btw 21 %, analytisch verhuurder |
| Doorstortingsstuk | `in_invoice` van de verhuurder, `partner_bank_id` uit het mandaat | 489100: + ontvangen per regel, − kosten; analytisch verhuurder |
| Verrekening | `entry` in het diversendagboek | 440 verhuurder debet / 400 verhuurder credit voor het ereloon; afgeletterd met beide stukken |

Na de verrekening is de ereloonfactuur betaald en staat het doorstortingsstuk open voor precies het saldo. 489100 per verhuurder staat dan op het nog niet betaalde deel van de huur (de test `test_confirm_books_fee_payout_and_offset` controleert dat).

**Betaling.** `vme.payment.batch` (stap 20) wordt in `models/vme_payment.py` uitgebreid: `association_id` is niet meer verplicht, `rent_company_id` wijst naar het kantoor, `company_id` is een opgeslagen compute (`related=None` met een expliciete comodel, anders faalt het laden). Voor een batch van het kantoor geven `_bank()` de derdenrekening, `_vme_party()` de naam van het kantoor, `_transfer_proposal()` de goedgekeurde doorstortingsstukken en `_build_transfer_file()` het kantoor als initiator. `_check_transfer_lines` van stap 20 blijft gelden: goedgekeurd, niet betaald, bevestigde rekening van verhuurder én kantoor. De goedkeuring is de bestaande `action_vme_approve`: `_vme_is_approvable` geldt ook voor een doorstortingsstuk, `_vme_second_approval_required` is daar `False`.

**Uitbreidingen.** Tweede goedkeurder en drempel per kantoor; terugkoppeling van de bank (stap 12) voor de derdenrekening; een maandelijkse cron die de concepten klaarzet; e-mail van afrekening en ereloonfactuur in één bericht.

## Crons (alleen concepten en taken)

| Cron | Wat |
| --- | --- |
| `ir_cron_rent_invoices` | `_cron_rent_invoices`: conceptfacturen van de lopende maand voor elk lopend contract. |
| `ir_cron_rent_reminders` | `_cron_rent_reminders`: taak 30 dagen vóór de uiterste opzegdatum (één keer per datum, `activity_notice_deadline`), en een conceptindexering met taak 45 dagen vóór de verjaardag, zodra het indexcijfer bestaat. |

## Rapporten

`report/rent_reports.xml` met `report/rent_reports.py`: **Indexatiebrief** (`vme.rent.indexation`), **Afrekening lasten huurder** (`vme.rent.settlement`) en **Afrekening verhuurder** (`vme.rent.remittance`). De rapportmodellen geven `format_date` mee (met optioneel `date_format`, bv. `'MMMM y'`).

## Demo

`demo_data/rent_demo.py` breidt `_load_demo_data` en `_load_demo_history` van `vme.association` uit:

- **Demodata**: company **Rentmeester Voorbeeld BV** (rekeningstelsel bij de commit, zoals bij een VME), drie contracten (Linde A2+G2, Linde A7, Beuken B23) met hun bevestigde indexeringen, een conceptindexering voor Linde A2 op 1 november 2026 en de taken rond de demodatum (5 november 2026), los van de echte datum (`_demo_reminders`).
- **Demodata** (stap 25b): derdenrekening van het kantoor en rekeningen van de drie verhuurders (`fake_iban(3001, 3011–3013)`, bevestigd als de gebruiker dat mag) en drie beheermandaten: Linde A2 7 % op de huur, Linde A7 6 % op huur en lasten, Beuken B23 vast 65 € per maand. De btw van het mandaat wordt in een precommit ingevuld, na het rekeningstelsel van het kantoor.
- **Demohistoriek**: de schoonmaakfirma aan de rubriek schoonmaak koppelen, huurfacturen januari–oktober 2026 boeken en betalen (behalve oktober van Linde A7); een kost van 242 € voor de verhuurder van Linde A2 (september); doorstortingen januari–september bevestigd, goedgekeurd en betaald (betaling geboekt op de 5de van de volgende maand); oktober als concept voor de demo.

De indextabel (`data/vme_rent_index_data.xml`, januari 2015 – oktober 2026) is fictief maar realistisch en staat in `noupdate`.

## Tests

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie,vme_rentmeester --test-enable --test-tags /vme_belgie,/vme_rentmeester --stop-after-init
```

| Bestand | Wat |
| --- | --- |
| `tests/test_indexation.py` | Formule en indexmaanden, indexstop per gewest (Vlaanderen, Brussel, Wallonië) met handberekende bedragen, venstergrenzen, contract na de stop, terugwerkende kracht, gewest uit postcode, opzegdatums; op een contract: opeenvolgende indexeringen, ontbrekend indexcijfer, mondeling of uitgesloten contract, waarborg per gewest. |
| `tests/test_settlement.py` | Afrekening per factuur en rubriek (handberekend), aansluiting op de jaarafrekening, percentage per contract, conceptfactuur en creditnota, forfait, einde huur midden in het jaar, huurfacturen (pro rata, na indexering, geen dubbele, ook met een andere company geselecteerd), opzeg, rapporten. |
| `tests/test_remittance.py` | Rekenregels (percentage, vast bedrag × maanden, btw, verdeling van een gedeeltelijke betaling); doorstorting met de hand nagerekend; alleen ontvangen tot het einde van de maand; boekingen en verrekening, 489100 op nul; geen dubbele opname; negatief saldo overdragen met twee maanden vast ereloon; betaalbatch met en zonder bevestigde rekening en gevalideerd SEPA-bestand; batch hoort bij VME of kantoor; rapport. |
| `tests/test_demo.py` | De drie demo-contracten, conceptindexering, opzegtaak, de indexstop van Beuken B23 en de beheermandaten met bevestigde rekeningen. |

## Uitbreidingspunten en wat ontbreekt

- **Huurders in het portaal (stap 27):** `res.partner._vme_portal_tenant_lots()` (`models/res_partner.py`) voegt de kavels van de huurcontracten van de partner toe; of het contract vandaag loopt, beslist `vme.lot._get_tenants_on`. Zo kan een huurder met een login een aanvraag indienen voor zijn kavel, ook zonder `vme.lot.contact`.

- **Registratie** van het contract, **plaatsbeschrijving** en **huurwaarborg** als eigen dossiers; nu alleen velden en een taak.
- **Opzeg met reden** door de verhuurder in een contract van negen jaar (eigen gebruik, werken, zonder reden met vergoeding) en de tussentijdse termijnen van drie jaar: niet gemodelleerd.
- **Daling van de index**: de huur daalt mee; een minimumclausule in het contract is niet voorzien.
- **bpost** voor brieven valt buiten het prototype (zie stap 23).
