# AV-planner (stap 6c)

Plant de gewone algemene vergaderingen van alle VME's in blokken van de syndicus. Code: `addons/vme_belgie/models/vme_assembly.py`, wizard `wizard/vme_assembly_planner_wizard.py`, views `views/vme_assembly_views.xml`, tests `tests/test_assembly_planner.py` (plus `test_assembly_planner_solves_conflict` in `test_demo_data.py`).

## Datamodel

```
vme.association ──< vme.assembly >── vme.assembly.slot >── vme.assembly.room
   (periode,           (jaar, status,      (datum, uur, duur,       (zaal)
    oproepingstermijn)  oproeping)          max. AV's, medewerker)
                            │
                            └── calendar.event (na bevestigen)
res.users.vme_max_assemblies_per_evening
```

| Model | Rol |
| --- | --- |
| `vme.association` (uitbreiding) | `assembly_period_month` + `assembly_period_day`: begin van de periode van 15 dagen (`ASSEMBLY_PERIOD_DAYS`); `convocation_days` (standaard 15). `_get_assembly_period(year)` geeft (begin, einde). |
| `vme.assembly.room` | Vergaderzaal van de syndicus. Niet per VME: één zaal dient veel VME's. |
| `vme.assembly.slot` | Blok: datum, beginuur (float, lokale tijd), duur per AV, max. AV's, zaal of online, medewerker. `datetime_start/end` zijn opgeslagen in UTC en dekken het hele blok (max. AV's × duur). |
| `vme.assembly` | Gewone AV per VME en jaar (unieke constraint). Status `draft` (te plannen) → `proposed` → `confirmed` → `held`, of `cancelled`. Erft `mail.thread` voor de historiek. |
| `vme.assembly.planner.wizard` | Maakt ontbrekende AV's aan en roept `_propose_schedule()` op. |
| `res.users` (uitbreiding) | `vme_max_assemblies_per_evening`, standaard 2. |

Blokken en zalen hebben geen `company_id`: ze horen bij het kantoor van de syndicus, niet bij een VME. Een AV heeft een opgeslagen `company_id` (related) voor latere record rules.

## Planning binnen een blok

AV's in hetzelfde blok volgen elkaar op in volgorde van id: positie *n* begint op `slot.datetime_start + n × assembly_duration`. Dat is een opgeslagen compute (`_compute_schedule`) die afhangt van `slot_id.assembly_ids`, zodat alle AV's in het blok herberekend worden als er een bij komt of weggaat.

Tijdzone: blokken worden ingegeven in `Europe/Brussels` (`LOCAL_TZ`) en omgezet naar naive UTC met `local_to_utc`. Zomertijd wordt dus correct verwerkt (test: 25 maart 2027 19:00 → 18:00 UTC, 29 maart 2027 20:00 → 18:00 UTC).

## Het voorstel (`vme.assembly._propose_schedule`)

1. Neem alle AV's met status `draft` en een periode.
2. Haal alle blokken op tussen de vroegste periodestart en het laatste periode-einde, gesorteerd op datum en uur.
3. Tel per (medewerker, datum) hoeveel AV's al voorgesteld/bevestigd zijn.
4. Loop de blokken chronologisch af. Zolang het blok plaats heeft en de medewerker onder zijn maximum per avond zit: kies uit de nog niet geplande AV's die op die datum passen de AV waarvan de periode het **eerst afloopt** (bij gelijkheid: naam van de VME).
5. Een AV past als `period_start ≤ datum ≤ period_end` en `datum − convocation_days ≥ vandaag`.
6. Wat overblijft, krijgt een bericht in de chatter en wordt teruggegeven.

Waarom zo: elke AV is een interval (haar periode) en elk blok een punt met capaciteit. Punten chronologisch aflopen en telkens het interval met de vroegste deadline kiezen, plant het maximale aantal AV's (klassieke greedy voor interval-punt-toewijzing). Een naïeve volgorde per VME faalt in de demo: Kaaihuis (10–24 maart) zou 17 maart nemen, waarna Linde (4–18 maart) geen blok meer heeft. De extra limiet per medewerker per avond kan de optimaliteit in theorie breken; voor de grootte van een syndicuskantoor (enkele honderden AV's per jaar) is dat aanvaardbaar.

De wizard zet bij "Voorstellen opnieuw indelen" eerst alle `proposed` AV's terug op `draft`. Bevestigde AV's blijven staan en hun plaats telt mee als bezet.

## Dubbele boekingen

Drie lagen, allemaal als `ValidationError`:

- `vme.assembly.slot._check_double_booking`: geen twee overlappende blokken in dezelfde zaal, en geen twee overlappende blokken voor dezelfde medewerker. De constraint staat op de bronvelden (`date`, `time_start`, ...), niet op de opgeslagen computes: `@api.constrains` reageert alleen op velden in `create`/`write`.
- `vme.assembly._check_slot_capacity`: niet meer actieve AV's in een blok dan `max_assemblies`, en niet meer AV's per medewerker per avond dan zijn limiet. Wordt ook opgeroepen als een blok van datum, medewerker of capaciteit verandert.
- Uniek: één gewone AV per VME en jaar.

## Waarschuwingen (`_get_warning`)

Niet opgeslagen compute `warning` + `warning_level` (`ok`/`warning`/`danger`), met een `search`-methode zodat de filter "Dreigt te laat" werkt. "Vandaag" komt uit de context-sleutel `vme_today` (tests) of `fields.Date.context_today`.

| Situatie | Niveau |
| --- | --- |
| Geen datum, laatste oproepdag (`period_end − convocation_days`) voorbij | danger: "Niet meer haalbaar" |
| Geen datum, laatste oproepdag binnen 30 dagen (`URGENT_MARGIN_DAYS`) | warning: "Dringend plannen" |
| Datum, oproeping na `convocation_deadline` verstuurd | danger |
| Datum, geen oproeping en vandaag na `convocation_deadline` | danger |
| Datum buiten de periode | warning |

## Agenda (`calendar`)

`calendar` is toegevoegd aan `depends` (Community). Bij **Bevestigen** maakt `_sync_calendar_event` een `calendar.event` met de medewerker als organisator en enige deelnemer, de zaal (met adres) als locatie en een link terug via `res_model_id`/`res_id`. Context `no_mail_to_attendees` en `dont_notify` voorkomen uitnodigingsmails. De afspraak volgt de AV: ander blok of gewijzigd blok → `write` op de afspraak; opnieuw plannen of annuleren → `unlink`. `vme.assembly` erft geen `mail.activity.mixin`, dus `calendar` maakt er geen activiteit voor aan.

## LEGAL-CHECK-punten

- `art. 3.87 §2 BW`: gewone AV elk jaar in de periode van 15 dagen uit het reglement van mede-eigendom (`ASSEMBLY_PERIOD_DAYS`, velden op `vme.association`).
- `art. 3.87 §3 BW`: oproeping minstens 15 dagen vooraf, tenzij het reglement anders bepaalt (`DEFAULT_CONVOCATION_DAYS`, `convocation_days`, `convocation_deadline`).

## Demodata

In `demo_data/vme_demo_data.py`: `ASSEMBLY_PERIODS` per gebouw, twee fictieve zalen (`ASSEMBLY_ROOMS`), een fictieve gebruiker "Medewerker Voorbeeld" (`medewerker.voorbeeld@example.com`, zonder wachtwoord) en vier blokken in 2027 (`ASSEMBLY_BLOCKS`), geladen door `_load_demo_assembly_blocks`. De AV's zelf maakt de demo aan via de AV-planner, zodat de demo de echte flow toont. Verwacht resultaat (test `test_assembly_planner_solves_conflict`): Linde 17 maart, Kaaihuis 23 maart, Hof ter Beuken 20 april; blok 11 mei blijft vrij.

## Testen

```
docker compose run --rm odoo odoo -d vme_test -u vme_belgie --test-enable --test-tags /vme_belgie:TestAssemblyPlanner --stop-after-init
```

Tests geven `today` expliciet mee (`vme_today` in de context of `_propose_schedule(today=...)`), zodat ze ook na het voorjaar van 2027 blijven werken.

## Valkuilen

- Een xpath in een geërfde view mag niet selecteren op `@string` (Odoo 19 weigert het); we selecteren de groep via `//field[@name='reserve_capital_bank_id']/..`.
- Opgeslagen en niet-opgeslagen velden in dezelfde compute geven een waarschuwing ("inconsistent 'store'"); `location` heeft daarom een eigen compute.
- Een `target="new"`-actie (de wizard) rechtstreeks via de URL openen geeft een leeg scherm; open ze via het menu.

## Uitbreidingen voor later

- Buitengewone AV's (meerdere per jaar) naast de gewone AV.
- Agenda, oproeping en notulen (stap 11) hangen aan `vme.assembly`.
- Een blok voorstellen per regio of op basis van het aantal eigenaars (zaalcapaciteit).
