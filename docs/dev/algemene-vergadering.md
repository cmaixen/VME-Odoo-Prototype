# Algemene vergadering: oproeping, stemming en notulen (stap 11)

Bouwt verder op `vme.assembly` uit de AV-planner ([av-planner.md](av-planner.md)). Code: `models/vme_assembly_meeting.py`, rapporten `report/vme_assembly_reports.xml`, views `views/vme_assembly_meeting_views.xml` (en het AV-formulier in `views/vme_assembly_views.xml`), tests `tests/test_assembly_meeting.py` en `test_demo_assembly_linde_2026` in `test_demo_data.py`.

## Datamodel

```
vme.assembly ─┬─< vme.assembly.item ──< vme.assembly.vote >── vme.assembly.attendee
              ├─< vme.assembly.attendee (eigenaar, quotiteiten, aanwezigheid, volmachthouder)
              └─< vme.assembly.convocation (concept per eigenaar, bijlagen)
```

| Model | Rol |
| --- | --- |
| `vme.assembly` (uitbreiding) | `item_ids`, `attendee_ids`, `convocation_ids`, `second_session`, voorzitter/secretaris; quorumvelden (niet opgeslagen). Bij `create` krijgt elke AV de standaardagenda (`DEFAULT_AGENDA`). |
| `vme.assembly.item` | Agendapunt met `majority` (`none`, `absolute`, `two_thirds`, `four_fifths`, `unanimous`). Opgeslagen compute `votes_for/against/abstain` en `outcome`. Erft `mail.thread` en `mail.activity.mixin` voor de opvolgtaak. `decision_number` vormt het register. |
| `vme.assembly.attendee` | Eén lijn per eigenaar op de datum van de AV, met de som van de quotiteiten van zijn kavels in de **algemene** sleutel. `attendance`: absent/present/represented, `proxy_holder_id` (elke partner). |
| `vme.assembly.vote` | Stem per (agendapunt, aanwezige); uniek. Standaard `for`. |
| `vme.assembly.convocation` | Concept-oproeping per eigenaar; erft `mail.thread`. Status `draft` → `sent`. |

De quotiteiten worden bij het aanmaken van de aanwezigheidslijst vastgezet, zodat een latere verkoop of sleutelwijziging de notulen niet verandert.

## Rekenregels

Stemmen worden in honderdsten van een quotiteit geteld (`_units`, integer), zodat vergelijkingen als "precies vier vijfde" niet door afronding mislopen.

- **Quorum** (`_is_quorum_reached`, art. 3.87 §5): `2·aanwezigen > eigenaars` en `2·quotiteiten aanwezig ≥ totaal`, of `4·quotiteiten aanwezig > 3·totaal`. Bij `second_session` altijd bereikt.
- **Uitgebrachte stemmen**: voor + tegen; onthoudingen tellen niet mee.
- **Meerderheden** (`MAJORITY_RULES`, art. 3.88): volstrekt = `voor·2 > uitgebracht` (strikt); twee derde = `voor·3 ≥ 2·uitgebracht`; vier vijfde = `voor·5 ≥ 4·uitgebracht`. Geen uitgebrachte stemmen → verworpen.
- **Eenparigheid**: elke eigenaar op de lijst (met quotiteiten) is aanwezig of vertegenwoordigd en stemt voor, dus ook afwezigen tellen. De beperking van art. 3.87 §6 speelt hier niet: wie meer dan de helft heeft, telt wel mee voor de eenparigheid.
- **Plafond per eigenaar** (art. 3.87 §6): de stemmen van een eigenaar worden begrensd op de som van de andere aanwezige of vertegenwoordigde eigenaars.
- **Volmachten** (art. 3.87 §7, `_check_proxy_limits`): meer dan `MAX_PROXIES` (3) per volmachthouder alleen als eigen stemmen (als hij aanwezig is) + volmachten ≤ 10% van alle stemmen. Constraint op de aanwezigheid, gecontroleerd over alle aanwezigen van de AV.
- **Uitslag**: `info` (geen stemming), `pending` (nog geen stemlijnen), `no_quorum`, anders `adopted`/`rejected`.

## Oproepingen

`action_create_convocations` vereist een datum (gepland blok) en een agenda. Per eigenaar wordt een concept aangemaakt en `_generate_documents` rendert:

1. `action_report_assembly_convocation`: brief met datum/uur/plaats, agenda met meerderheden, aantal stemmen, en op een nieuwe pagina het volmachtformulier;
2. de bestaande jaarafrekening (`action_report_annual_statement`) van `jaar − 1` voor die eigenaar, via een tijdelijke `vme.annual.statement.wizard`, alleen als er gegevens zijn.

Er wordt niets verstuurd. `action_open_composer` opent `mail.compose.message` met de bijlagen en context `mark_convocation_as_sent`; de override van `message_post` zet de oproeping dan op `sent` en vult `convocation_sent_date` van de AV (patroon van `mark_so_as_sent` in `sale`). Een notificatie waarschuwt als de oproepingstermijn (art. 3.87 §3) al voorbij is.

Elke PDF kost een wkhtmltopdf-run (ongeveer 2 seconden): voor een VME met 12 eigenaars en jaarafrekeningen duurt het aanmaken dus bijna een minuut. In tests rendert Odoo HTML, dus daar is het snel.

## Afsluiten

`action_mark_held` weigert als er nog punten `pending` zijn, roept dan de bestaande overgang naar `held` op en `_register_decisions`:

- nummert alle aangenomen en verworpen punten per VME en jaar (`2026/01`, ...), verder tellend als er al beslissingen van dat jaar zijn;
- maakt voor elke aangenomen beslissing met `follow_up_summary` een `mail.activity` (To-do) op het agendapunt, voor `follow_up_user_id`, anders de medewerker van het blok.

Het register is de actie `vme_assembly_item_register_action` met domein `decision_number != False`. De notulen zijn `action_report_assembly_minutes` op `vme.assembly`.

## LEGAL-CHECK-punten

- `art. 3.87 §3 BW`: oproepingstermijn (waarschuwing bij aanmaken).
- `art. 3.87 §5 BW`: quorum en tweede vergadering.
- `art. 3.87 §6 BW`: stemmen volgens quotiteiten en plafond per eigenaar.
- `art. 3.87 §7 BW`: volmachtgrens (3 of 10%).
- `art. 3.87 §8 BW`: onthoudingen tellen niet als uitgebrachte stem (artikelnummer nakijken).
- `art. 3.87 §10 BW`: notulen.
- `art. 3.88 §1-3 BW`: meerderheden en eenparigheid.
- `art. 3.93 §4 BW`: register van beslissingen (artikelnummer nakijken).

## Demodata

`DEMO_ASSEMBLY_2026` in `demo_data/vme_demo_data.py` en `_load_demo_assembly_2026`: een gehouden AV van Residentie Linde op 10 maart 2026 (eigen blok in de vergaderzaal), oproeping verstuurd op 18 februari, 7 aanwezigen en 3 volmachten (A1 heeft er twee), voorzitter A2 en secretaris A6, twee extra punten: dakwerken (twee derde, aangenomen, opvolgtaak) en een statutenwijziging (vier vijfde, verworpen). Er worden geen PDF's gerenderd bij het laden.

## Valkuilen

- Een actie in `next` van een `display_notification` moet een `views`-lijst hebben; anders crasht de webclient (`Cannot read properties of undefined (reading 'map')`). Daarom geven `action_open_convocations` en `action_open_votes` expliciet `views` mee.
- wkhtmltopdf haalt de opmaak via `web.base.url`. In een Docker-run met een andere poortmapping (bv. 8170 → 8069) faalt dat met `ConnectionRefusedError` en wordt de PDF zonder opmaak gemaakt; op de gewone demo (8069) is er geen probleem.
- `_order` op `lot_names` sorteert alfabetisch (A10 vóór A2); de aanwezigheidslijst sorteert daarom op id, wat de volgorde van de sleutellijnen volgt.

## Digitale en hybride AV

Online deelname, elektronisch en schriftelijk stemmen, buitengewone AV's en de ondertekening van de notulen staan in [digitale-av.md](digitale-av.md) (stap 24). De rekenregels hierboven blijven ongewijzigd: een online stem is een gewone `vme.assembly.vote` met een bron en een tijdstip. `_prepare_votes` slaat sindsdien eigenaars over die via het portaal stemmen (`votes_remotely`), en `action_all_for` raakt alleen zaalstemmen.

## Uitbreidingen voor later

- Stemmen per eigenaar vooraf vanuit het volmachtformulier invullen (steminstructies).
- Een tweede vergadering automatisch aanmaken als het quorum niet bereikt is.
