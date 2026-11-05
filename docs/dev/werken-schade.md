# Werken, offertes en schadegevallen (stap 14)

Code: `models/vme_works.py`, `models/vme_damage.py`, `views/vme_works_views.xml`, `views/vme_damage_views.xml`, demodata in `demo_data/vme_demo_works.py`, tests in `tests/test_works.py` en `tests/test_damage.py`. Kennisbank: [werken](../kb/werken.md) en [schadegevallen](../kb/schadegevallen.md).

## Datamodel

| Model | Doel | Belangrijke velden |
| --- | --- | --- |
| `vme.works` | Werkdossier | `decision_id` (`vme.assembly.item`, aangenomen), `budget` en `key_id` (compute uit `works_amount` en `works_key_id` van de beslissing, `readonly=False`), `financing` (`working`/`reserve`), `state`, `quote_ids`, `awarded_quote_id`, `contractor_id` en `contract_amount` (related, stored), `bill_ids` |
| `vme.works.quote` | Offerte | `partner_id`, `amount` (incl. btw), `state` (`received`/`awarded`/`rejected`), `budget_difference`, `is_cheapest` |
| `vme.insurance.policy` | Verzekeringspolis per VME | `insurer_id`, `policy_number`, `deductible`, `declaration_days` |
| `vme.damage.claim` | Schadedossier | `lot_ids`, `policy_id` (compute: brandverzekering van de VME), `declaration_deadline`, `prescription_date`, `expert_id`, `bill_ids`, `compensation_amount`, `mail_reference` |

Uitbreidingen: `vme.association` (`works_quote_threshold`, `works_min_quotes`, `works_ids`, `insurance_policy_ids`, `damage_claim_ids`, `_get_fund_balance()`), `vme.assembly.item` (`works_ids`, `action_create_works`), `account.move` (`vme_works_id`, `vme_reserve_move_id`, `vme_damage_claim_id`).

De velden `works_amount`, `works_key_id` en `works_done` op `vme.assembly.item` komen uit stap 9 (`models/vme_sale_file.py`). `action_deliver()` zet `works_done`, zodat de werken uit de inlichtingen aan de notaris verdwijnen.

## Statussen

Werken: `draft` → `quotes` (`action_request_quotes`, vraagt een budget) → `awarded` (`vme.works.quote.action_award` → `_award`) → `in_progress` (`action_start`) → `delivered` (`action_deliver`) → `closed` (`action_close`). Annuleren kan tot en met `awarded`, niet met geboekte facturen. Elke stap controleert de vorige status (`_check_state`) en sluit of maakt taken (`mail.activity`).

Schade: `reported` → `declared` (vraagt een polis) → `expertise` (vraagt een expert) → `repair` → `paid` (vraagt bedrag en datum), of `refused` (vraagt een reden), of `cancelled` (vóór de expertise). `repair` en `paid` kunnen ook zonder expertise.

## Minimum aantal offertes

`_required_quotes(amount)`: vanaf `works_quote_threshold` van de VME zijn `works_min_quotes` offertes nodig, anders één. Bij het gunnen geldt het hoogste van budget en offertebedrag, zodat een offerte die boven de drempel uitvalt niet met één offerte gegund wordt. `# LEGAL-CHECK: art. 3.88 §1, 1°, c) en 3.89 §5, 15° BW`: de wet legt geen aantal vast.

## Financiering uit het reservekapitaal

- **Beschikbaar**: `_get_fund_balance("reserve")` (saldo van rekening 100200, geboekt) min het nog niet gefactureerde deel van andere gegunde reservewerken. Het tekort is een waarschuwing, geen blokkering.
- **Facturen koppelen**: `account.move._compute_vme_works_id` vult het dossier op een conceptfactuur of -creditnota als de leverancier de aannemer is van precies één dossier in `awarded`, `in_progress` of `delivered`. De regels krijgen de sleutel van het dossier (override van `account.move.line._compute_vme_key_id`; een met de hand gekozen sleutel blijft).
- **Boeken**: `_post()` roept `_vme_book_reserve_use()` aan voor facturen van reservewerken: een diverse boeking in het eerste `general`-dagboek, debet 100200 voor het totaal met btw, credit de kostenrekeningen van de regels (verdeeld met `largest_remainder` op `price_total`). Een creditnota draait de richting om. `button_draft()` keert die boeking om (`_reverse_moves(cancel=True)`) en maakt het veld leeg.
- **Jaarafrekening**: `_get_annual_statement` neemt facturen met `vme_reserve_move_id` niet op in `cost_total` en het saldo, maar geeft per eigenaar `reserve_works` (aandeel per werkdossier) en `reserve_works_total`. De kostenverdeling zelf blijft bestaan, ook voor de controle `is_complete`. Het rapport toont ze onder "Reservekapitaal".
- `# LEGAL-CHECK: art. 3.86 §3 BW en KB 12 juli 2012`: rekeningen en de behandeling van de niet-aftrekbare btw zijn af te stemmen met een boekhouder.

## Termijnen bij schade

- `declaration_deadline` = datum schadegeval (of melding) + `declaration_days` van de polis (standaard 8). `# LEGAL-CHECK: art. 74 §1 wet 4 april 2014 betreffende de verzekeringen`.
- `prescription_date` = datum schadegeval + 3 jaar. `# LEGAL-CHECK: art. 88 §1 wet 4 april 2014`.
- `deadline_state` (oranje vanaf 3 dagen voor de termijn, rood erna) alleen zolang de status `reported` is.

## Melding uit een mail (ai/)

`vme.damage.claim.create_from_mail(association_id, subject, body, reference, lot_id, owner_id, mail_date)` maakt een dossier in `reported` met `source = "mail"` en geeft het id terug. Met dezelfde `reference` (Message-ID zonder `<>`, zoals `Mail.reference` in `ai/mails.py`) geeft het het bestaande dossier terug. Een kavel van een andere VME wordt genegeerd. `ai/assistant.py` roept het aan via `VmeDirectory.create_damage_claim` voor onderwerpen in `DAMAGE_TOPICS` (nu `leak`), niet bij `--dry-run`, en vermeldt het dossier in de notitie van de activiteit.

## Demo

`_load_demo_works()` loopt aan het einde van `_load_demo_data()`: polissen voor de drie VME's, het dakwerken-dossier van Linde aan beslissing "Dakwerken" (2026/06, 38.000 euro) met drie offertes, gegund op 2 juni 2026 aan Dakrenovatie Fictief NV (36.450 euro), start 16 november 2026, en de waterschade van A4 (status expertise, `mail_reference` van `ai/inbox/01_lek_badkamer.eml`). De opvolgtaak van de AV-beslissing ("Drie offertes vragen voor de dakwerken") wordt afgesloten. De verzekeraar wordt hier aangemaakt; `_demo_history_bills` zoekt hem nu op btw-nummer in plaats van een tweede partner te maken.

De Peppol-factuur `demo_data/facturen/voorschot_dakwerken_residentie_linde_2026-11.xml` (voorschot 30%, 10.316,04 + 6% btw = 10.935 euro) wordt niet automatisch geladen, zodat de demohistoriek en de `vme_slow`-test onveranderd blijven.

## Valkuilen

- **Context van het factuurformulier.** De knop **Facturen** geeft `default_vme_works_id` mee. Zonder `clean_context` kreeg ook de diverse boeking op het reservekapitaal dat werkdossier, en telde ze als factuur mee (gefactureerd 0 euro). `bill_ids` is daarom ook beperkt tot `in_invoice`/`in_refund`.
- **Company van een nieuwe factuur.** `allowed_company_ids` in de context van een actie wordt door de webclient genegeerd; een nieuwe factuur kwam in "My Company" in USD. De actie geeft nu `default_company_id` mee en weigert met een duidelijke melding als de VME rechtsboven niet aangevinkt is (`_check_company_selected`).
- **Sessies in de browser.** Meerdere Odoo-servers op `localhost` of `127.0.0.1` met andere poorten delen hun `session_id`-cookie (cookies kijken niet naar de poort): je wordt telkens uitgelogd. Gebruik een eigen hostnaam per server, bv. `http://werken.localhost:8470`.

## Uitbreidingspunten

- Een bijzondere provisieoproep voor het reservekapitaal vanuit het tekort van een dossier.
- Een `vme.insurance.policy` koppelen aan een verzekeringscontract (stap 18) en de vergoeding van de verzekeraar boeken.
- Het overzicht voor de raad van mede-eigendom (stap 16) kan `vme.works` en `vme.damage.claim` in status lopend tonen.
