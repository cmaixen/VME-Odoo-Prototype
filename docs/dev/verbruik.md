# Verbruik en meterstanden (stap 17)

Sleutels van het type `consumption` ("Op verbruik") verdelen een factuurregel in een vast deel volgens de quotiteiten van de sleutel en een variabel deel volgens het verbruik van de tellers per kavel in de kostperiode.

## Datamodel

| Model | Bestand | Velden en regels |
| --- | --- | --- |
| `vme.meter` | `models/vme_meter.py` | `name` (tellernummer, uniek per VME), `lot_id` (verplicht), `meter_type` (`water`, `heating` = kostenverdeler, `electricity`), `factor` (coëfficiënt, > 0), `location`, `unit` (berekend: m³, eenheden, kWh), `reading_ids`, `active`. |
| `vme.meter.reading` | idem | `meter_id`, `date`, `value`, `source` (`manual`/`import`), `import_ref`. Uniek per (teller, datum). Constraint `_check_increasing`: een stand is nooit lager dan een vroegere of hoger dan een latere. |
| `vme.key` | `models/vme_key.py` | Nieuw: `meter_type` (welke tellers), `fixed_percent` (standaard 30, 0–100), `variable_percent` (berekend). Alleen gebruikt als `key_type == "consumption"`. |
| `vme.cost.allocation` | `models/vme_cost_allocation.py` | Nieuw: `fixed_amount`, `variable_amount`, `consumption`. Voor andere sleutels blijven ze leeg; `amount` blijft het enige bedrag dat telt. |
| `vme.lot` | `models/vme_lot.py` | Nieuw: `meter_ids`. |

Elektriciteit van de gemene delen heeft als soort bestaan, maar het prototype verdeelt alleen tellers die aan een kavel hangen. Een teller zonder kavel (de hoofdteller van het gebouw) is buiten scope.

## Index en verbruik

`vme.meter._index_at(day)`: de stand op het **einde** van `day`.

- Opname op die dag: die stand.
- Anders lineair per dag tussen de vorige en de volgende opname.
- Geen opname vóór of geen opname na: `MissingReading(meter, day)`.

`vme.meter._consumption(date_from, date_to)` = (`_index_at(date_to)` − `_index_at(date_from − 1 dag)`) × `factor`. Een opname op 31/12 sluit dus aan op een kostperiode die op 1/1 begint. Omdat de interpolatie lineair is, is het verbruik additief: het verbruik van verkoper plus koper is exact het verbruik van de kavel.

## Verdeling

`account.move._vme_distribute()` kiest per regel:

- `_vme_share_rows(key, ...)`: de bestaande verdeling (quotiteiten, dan dagen), ongewijzigd.
- `_vme_consumption_rows(key, ...)` voor `consumption`:
  1. `largest_remainder(bedrag, [vast %, 100 − vast %], 2)` → vast en variabel deel.
  2. Vast over alle sleutelregels volgens `shares` (een kavel met quotiteit 0 kan dus wel een variabel deel krijgen).
  3. `_vme_ownership_segments` per kavel (zelfde dekking als altijd: elke dag een eigenaar).
  4. Is het variabel deel niet nul: `_vme_segment_consumption` berekent het verbruik per eigendomssegment, som over de actieve tellers van `key.meter_type` op de kavel. Alle problemen worden verzameld en in één `UserError` gemeld: kavels zonder teller, tellers met een ontbrekende opname. Totaal verbruik ≤ 0 is ook een fout.
  5. Variabel over de kavels volgens hun verbruik, per kavel vast over de eigenaars volgens dagen en variabel volgens hun verbruik, telkens met `largest_remainder`.
  6. Eén rij per (kavel, eigenaar) met `amount = vast + variabel`.

De som per factuur blijft exact het factuurtotaal, dus `_get_annual_statement` en zijn `is_complete` werken zonder aanpassing. De afrekening geeft per sleutel op verbruik ook `consumption` (verbruik, eenheid, vast en variabel deel) mee, en het rapport toont dat onder de quotiteit.

Bij het boeken vangt `_vme_auto_distribute` de `UserError` op: de factuur blijft geboekt, de reden staat in de chatter. Na het inlezen van de ontbrekende standen klikt de medewerker op **Verdeel over eigenaars**.

## CSV-import

`wizard/vme_meter_import_wizard.py`, menu **VME > Verbruik > Meterstanden inlezen**. Eigen formaat, want we kennen de exports van de meteropnamebedrijven (Ista, Techem …) niet; een omzetter per bedrijf kan later naar dit formaat schrijven.

- UTF-8 (of cp1252), `;` of `,` (zelfde lezer als de overstap: `vme.migration._read_csv`), kopregel verplicht.
- Kolommen: **kavel**, **teller** (of `tellernummer`), **soort** (`water`, `verwarming`/`kostenverdeler`/`warmte`, `elektriciteit`), **datum** (`DD/MM/JJJJ`, `JJJJ-MM-DD`, …: `parse_date`), **stand** (decimale komma mag: `parse_amount`), optioneel `coefficient` en `plaats`.
- `_check_file(vme, raw)` → `(plan, messages)` en schrijft niets. Fouten: onbekende kavel of soort, ongeldige datum, stand of coëfficiënt, teller van een andere kavel of soort, andere stand voor een datum die er al is, dalende stand (bestaande opnames en bestand samen). Waarschuwingen: nieuwe teller (wordt aangemaakt), andere coëfficiënt dan de bestaande teller (niet gewijzigd), standen die al ingelezen waren (overgeslagen).
- `_import_file(vme, raw, filename)` controleert opnieuw, weigert bij elke fout en maakt alles in één transactie.

## Demo

- `demo_data/vme_demo_data.py`: Hof ter Beuken heeft `["general", "consumption"]`; de sleutel "Verwarming op verbruik" krijgt de verwarmingsgewichten als quotiteiten en `CONSUMPTION_KEY` (heating, 30% vast).
- `demo_data/vme_demo_history.py`: `_demo_history_meter_readings` leest `demo_data/meterstanden/hof_ter_beuken_2026-09-30.csv` in vóór de facturen (48 kostenverdelers, opnames 31/12/2025, 31/03, 30/06, 30/09). De gasregel wijst naar de sleutel op verbruik.
- `hof_ter_beuken_2026-10-31.csv` blijft over voor de demo in de browser (zie de kennisbank).
- De standen zijn verzonnen met een vaste verbruiksfactor per kavel tussen 0,75 en 1,30 en een seizoensfactor per kwartaal. De spreiding is klein genoeg dat elke eigenaar van Hof ter Beuken die alles betaalde nog bijbetaalt (`test_hof_ter_beuken_pays_extra`).

## Tests

`tests/test_consumption.py`: het handberekende voorbeeld (1000 = A1 180 + 175, A2 120 + 525), som = factuurtotaal met btw, 0% en 100% vast, creditnota, ontbrekende stand, periode na de laatste opname, kavel zonder teller, geen verbruik, boeken met ontbrekende stand, verkoop met en zonder tussenopname, jaarafrekening; en voor de import: proefrun zonder schrijven, alle fouten, ontbrekende kolom, tweede keer hetzelfde bestand, de wizard.

## Valkuilen

- Een gearchiveerde teller telt niet mee. Archiveer een vervangen teller pas als alle facturen over zijn periode verdeeld zijn.
- `largest_remainder` weigert gewichten die samen nul zijn; daarom slaat de code het variabele deel over als het nul is, en verdeelt het per kavel alleen als die kavel verbruik had.
