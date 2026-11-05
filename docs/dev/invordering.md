# Invordering van achterstallen (stap 10)

Code: `models/vme_collection.py`, sjablonen en cron in `data/collection_data.xml`, rapporten in `report/vme_collection_reports.xml`, views en menu's in `views/vme_collection_views.xml`, demodata in `demo_data/vme_demo_collection.py`, tests in `tests/test_collection.py`.

## Datamodel

```
vme.arrears (SQL-view) ──> vme.collection ──< vme.collection.reminder ──< vme.collection.reminder.line
                               │
                               └──< account.move (vme_collection_id: aangerekende kosten)
```

| Model | Rol |
| --- | --- |
| `vme.arrears` | Alleen-lezen SQL-view (`_auto = False`, `_table_query`): één rij per open, vervallen debiteurenlijn (`asset_receivable`, geboekt, niet afgepunt, `amount_residual > 0`, `date_maturity < CURRENT_DATE`) in een VME-company. Velden: VME, eigenaar, factuurnummer en mededeling als tekst, fonds, `days_overdue`, `aging` (`0_30`, `31_60`, `61_90`, `90_plus`), `collection_id` (join op het lopende dossier). |
| `vme.collection` | Dossier per (VME, eigenaar). Status `open` → `forwarded` → `closed`. Opgeslagen: `level` en `last_reminder_date` (uit de verstuurde herinneringen), `interest_until`, `penalty_date`, `forward_partner_id`, `forward_date`. Niet opgeslagen (`compute_sudo`, `depends_context("vme_today")`): `amount_due`, `oldest_due_date`, `days_overdue`, `aging`, `next_level`, `next_step`, `interest_preview`, `penalty_preview`. Partiële unieke index: één niet-afgesloten dossier per VME en eigenaar. |
| `vme.collection.reminder` | Brief per niveau (`1` vriendelijke herinnering, `2` aanmaning, `3` ingebrekestelling). Status `draft` → `sent` (of `cancel`). Momentopname: `line_ids`, `amount_due`, `interest_rate`, `first_reminder_date`, `second_reminder_date`, plus `subject` en `body_html` uit het sjabloon. Erft `mail.thread`. |
| `vme.collection.reminder.line` | Openstaand bedrag op een herinnering, als tekst: factuur, omschrijving, fonds, vervaldag, gestructureerde mededeling, rekeningnummer, bedrag. |
| `vme.association` (uitbreiding) | Regels uit het reglement: `collection_first_reminder_days`, `collection_interval_days`, `collection_interest_rate`, `collection_penalty_percent`, `collection_penalty_min`, `collection_consumer_rules`; berekend `collection_effective_rate`. |
| `account.move` (uitbreiding) | `vme_collection_id` op de kostenfactuur. |

Facturen staan in de company van hun VME. Het overzicht en de dossiers tonen alle VME's samen, dus alles wat facturen leest gebeurt als `sudo`, en de herinnering en de SQL-view bewaren factuurnummer, mededeling en rekening als tekst in plaats van een link naar `account.move` (een many2one-link zou een toegangsfout geven voor een company die de gebruiker niet geselecteerd heeft).

## Ouderdom

`aging_bucket(days)` en de `CASE` in de SQL-view gebruiken dezelfde grenzen: 1-30, 31-60, 61-90, meer dan 90 dagen na de vervaldag. De SQL-view rekent met `CURRENT_DATE`; de dossiers met `vme_today` uit de context (anders vandaag), zodat tests een datum kunnen vastzetten. De test voor de SQL-view maakt daarom facturen relatief tegenover de echte datum van vandaag.

## Niveaus

`_get_next_level(today, overdue)`:

- geen voorstel als het dossier niet `open` is, er niets vervallen is, of er al een concept is (één concept tegelijk, ook afgedwongen met een constraint);
- niveau 1 als de oudste vervaldag minstens `max(collection_first_reminder_days, 1)` dagen voorbij is;
- niveau 2 en 3 als de laatste verstuurde herinnering minstens `collection_interval_days` dagen oud is;
- na niveau 3 geen voorstel meer; `next_step` zegt dan "Doorsturen naar advocaat of deurwaarder".

`_refresh(today)` (knop **Invordering bijwerken** en dagelijkse cron `ir_cron_collection_refresh`):

1. groepeert alle vervallen open debiteurenlijnen per company en partner en maakt een dossier waar er nog geen lopend is;
2. sluit dossiers zonder enige open debiteurenlijn (ook niet-vervallen) en annuleert hun concepten;
3. maakt voor elk open dossier met een `next_level` een concept met `_create_reminder`.

Er wordt nooit iets verstuurd.

## Sjablonen en PDF's

De drie Nederlandse teksten zijn `mail.template`-records op `vme.collection.reminder` (`mail_template_collection_reminder`, `_demand`, `_notice`), met een gedeelde QWeb-tabel `collection_reminder_table`. `_update_content()` neemt een momentopname van de open lijnen (vervallen lijnen plus de kostenfacturen van het dossier, die meteen vervallen zijn) en rendert onderwerp en tekst met `_render_field`. De medewerker kan die tekst nog aanpassen; **Bijwerken** maakt ze opnieuw.

Prestaties: bij het aanmaken van een concept wordt geen PDF gemaakt (een wkhtmltopdf-run kost ongeveer 2 seconden). De PDF van de brief (`action_report_collection_reminder`, toont `body_html` op het briefhoofd van de VME) wordt pas gerenderd bij **Versturen** (`render_attachment` + mailcomposer) of **Afdrukken**. Hetzelfde voor het dossieroverzicht (`action_report_collection_overview`) bij **Doorsturen** of **Overzicht (PDF)**.

Versturen volgt het patroon van de oproepingen voor de AV: `action_open_composer` opent `mail.compose.message` met context `mark_reminder_as_sent`, en de override van `message_post` zet de herinnering op `sent`. **Doorsturen** gebruikt `mark_collection_as_forwarded` op het dossier. **Per post verstuurd** (`action_mark_sent`) werkt ook op een selectie in de lijst.

## Interest en schadevergoeding

`_compute_costs(today)` geeft per open, vervallen factuur (zonder de kostenfacturen zelf) de interest en eenmalig de schadevergoeding:

- **Startdatum interest** = de laatste van: vervaldag, `interest_until` (al aangerekend tot), en bij consumentenregels de verzenddatum van de eerste vriendelijke herinnering + `collection_interval_days`. Zonder verstuurde vriendelijke herinnering zijn er bij consumentenregels geen kosten (`blocked`).
- **Interest** = open bedrag × `collection_effective_rate` / 100 × dagen / 365, afgerond per factuur.
- **Interestvoet**: bij consumentenregels hoogstens `vme_belgie.legal_interest_rate` (systeemparameter, standaard 4,5) + 8.
- **Schadevergoeding** (alleen als `penalty_date` leeg is): `max(saldo × percent, minimum)`, bij consumentenregels begrensd door `legal_max_penalty(saldo)` (20 euro; 30 + 10% boven 150; 65 + 5% boven 500, maximum 2000).

`action_charge_costs` boekt een `out_invoice` in de company van de VME op naam van de eigenaar: interestlijnen op 751000 (Opbrengsten uit vlottende activa), schadevergoeding op 743000 (Diverse bedrijfsopbrengsten), zonder btw, `vme_fund = "working"` zodat de rekening van het werkkapitaal erop staat, vervaldag = vandaag. Daarna worden `interest_until` en `penalty_date` gezet en de concepten van het dossier bijgewerkt.

Voorbeeld uit de tests: 1650 euro open (1500 werk, 150 reserve), vriendelijke herinnering op 5 februari, aangerekend 30 dagen na het einde van de termijn: interest 9,86 + 0,99; schadevergoeding min(165, 65 + 5% × 1150) = 122,50.

## LEGAL-CHECK-punten

- `art. XIX.2 §1 WER`: eerste herinnering kosteloos, kosten pas na een termijn van 14 dagen. Na te kijken: of Boek XIX geldt tussen een VME en een eigenaar, en of interest vanaf de vervaldag mag lopen als het reglement dat zegt.
- `art. XIX.4 §1 WER`: interest hoogstens wettelijke interestvoet + 8 procentpunten.
- `art. XIX.4 §2 WER`: schaal van de forfaitaire schadevergoeding (artikelnummers nakijken).
- `wet 5 mei 1865`: wettelijke interestvoet, jaarlijks bij te werken in de systeemparameter.
- `art. 3.85 BW`: interest en schadevergoeding volgens het reglement van mede-eigendom, enkelvoudige interest op 365 dagen.

## Demodata

`_load_demo_collection` (aangeroepen aan het einde van `_load_demo_history`) maakt een dossier voor Beuken B7 met een verstuurde vriendelijke herinnering (11 augustus 2026) en aanmaning (1 september 2026) voor oproep 3, en de partner "Gerechtsdeurwaarder Voorbeeld" als deurwaarder. Daarna draait `_refresh()` met de echte datum: B7 krijgt een concept-ingebrekestelling, Linde A3 (oproep 4, vervallen op 4 november 2026) een concept-vriendelijke herinnering. Er worden geen PDF's gerenderd.

## Valkuilen

- Een `many2one` naar `account.move` in een overzicht over alle VME's heen geeft een toegangsfout zodra de gebruiker niet alle companies geselecteerd heeft. Daarom tekstvelden in `vme.arrears` en de herinneringslijnen.
- De SQL-view rekent met `CURRENT_DATE` van de databaseserver, de dossiers met de datum van Odoo; rond middernacht in een andere tijdzone kan dat een dag verschillen.
- Een `account.move` dat met `sudo()` gemaakt is en met `|=` aan een recordset zonder `sudo` toegevoegd wordt, verliest de `sudo`: het resultaat neemt de omgeving van de linkse recordset. Het lezen van `name` gaf dan een toegangsfout. De test `test_buttons_work_without_the_vme_company_selected` draait de knoppen als admin met alleen het hoofdbedrijf geselecteerd.
- Een knopmethode mag geen recordset teruggeven: de webclient verwacht een actie of niets. `action_charge_costs` roept daarom `_charge_costs` op, dat de facturen teruggeeft voor de tests.
- De kostenfactuur vervalt op de dag zelf: ze staat meteen op de herinneringen en in het saldo van het dossier, maar pas de dag nadien in het overzicht **Achterstallen** (dat telt alleen wat vervallen is).

## Uitbreidingen voor later

- Betalingen uit bankafschriften (stap 12) koppelen, zodat dossiers vanzelf sluiten.
- Een afbetalingsplan als apart object met vervaldagen.
- Kosten van de advocaat of deurwaarder doorrekenen aan de eigenaar.
- Een overzicht van de lopende dossiers voor de raad van mede-eigendom (stap 16).
