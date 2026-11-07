# Digitale en hybride algemene vergadering (stap 24)

Breidt de AV van stap 11 ([algemene-vergadering.md](algemene-vergadering.md)) uit met online deelname via het eigenaarsportaal ([portaal.md](portaal.md)), elektronisch en schriftelijk stemmen en een eigen elektronische ondertekening van de notulen. Odoo Sign is Enterprise en wordt niet gebruikt.

Code: `models/vme_assembly_online.py`, `controllers/portal_assembly.py`, `views/vme_assembly_online_views.xml`, `views/portal_assembly_templates.xml`, demo `demo_data/vme_demo_online.py`, tests `tests/test_assembly_online.py` en `test_demo_hybrid_assembly_linde` in `test_demo_data.py`.

## Eén plaats waar geteld wordt

Een online of schriftelijke stem is een gewone `vme.assembly.vote`, met daarbij:

| Veld | Betekenis |
| --- | --- |
| `source` | `room` (ingegeven door de medewerker), `online`, `written` (vooraf) |
| `cast_at` | Tijdstip (server, UTC) |
| `voter_partner_id` | Wie stemde: de eigenaar zelf of zijn volmachthouder |
| `ip_address` | `request.httprequest.remote_addr` |

Quorum, meerderheden, plafond per eigenaar en volmachtgrenzen blijven in `_compute_quorum`, `_count_votes`, `_get_outcome` en `_check_proxy_limits` van stap 11. Er is geen tweede telling. Een online aanwezige is een `vme.assembly.attendee` met `attendance = present` en `attendance_mode = online`; een schriftelijke stemmer heeft `attendance_mode = written` en telt dus ook als aanwezig voor het quorum (`# LEGAL-CHECK: art. 3.87 §1 BW`).

## Datamodel

| Model | Nieuwe velden |
| --- | --- |
| `vme.assembly` | `assembly_type` (gewoon/buitengewoon), `subject`, `meeting_mode` (`in_person`, `hybrid`, `online`), `video_url`, `online_token`, `online_url` (compute), `online_open`, `minutes_attachment_id`, `minutes_sha256` (compute, niet opgeslagen), `signature_ids`, `signature_state` |
| `vme.assembly.item` | `voting_state` (`not_open`, `open`, `closed`), `voting_opened_at`, `voting_closed_at`, `allow_advance_vote` |
| `vme.assembly.attendee` | `attendance_mode` (`room`, `online`, `written`), `checked_in_at`, `check_in_ip`, `votes_remotely` (compute) |
| `vme.assembly.vote` | `source`, `cast_at`, `voter_partner_id`, `ip_address` |
| `vme.assembly.signature` (nieuw) | `partner_id`, `role` (voorzitter, secretaris, eigenaar), `document_sha256`, `state`, `signed_at`, `signed_name`, `ip_address`, `user_agent`, `is_valid` (compute) |

### Buitengewone AV

De unieke constraint `(association_id, year)` gold voor elke AV. Ze is vervangen door een partiële unieke index `_unique_ordinary_year` (`WHERE assembly_type = 'ordinary'`); `migrations/19.0.1.11.0/pre-migrate.py` dropt de oude constraint `vme_assembly_unique_year_per_association`. Een buitengewone AV heeft geen periode (`_compute_period` geeft `False`), krijgt bij `create` alleen het openingspunt, geen jaarafrekening bij de oproeping, en wordt overgeslagen door `_create_missing_assemblies`, `_propose_schedule` en de periodewaarschuwing van `_get_warning`. Wie AV's per VME en jaar opzoekt, filtert voortaan op `assembly_type` (zie `test_demo_assembly_linde_2026`).

## Stemrechten online

`vme.assembly._portal_voting_rights(partner)`: de eigen aanwezigheidslijn als die `present` is, plus alle lijnen `represented` met `proxy_holder_id` = de eigenaar. De partner is altijd `partner._vme_owner()` (commerciële partner), zoals in de rest van het portaal.

`vme.assembly.item._portal_vote_rights(partner)` geeft `(attendees, source)`:

- `voting_state == open` en AV bevestigd → rechten hierboven, bron `online`;
- `voting_state == not_open`, `allow_advance_vote` en het onthaal nog dicht → de eigen lijn als die afwezig of al `written` is, plus de volmachten, bron `written`;
- anders geen rechten.

`_portal_cast_votes(partner, {attendee: vote}, ip)` controleert eerst alles (recht, geldige waarde, nog geen stem voor die lijn) en schrijft dan pas, zodat een geweigerde reeks niets achterlaat. Samen met de constraint `UNIQUE (item_id, attendee_id)` van stap 11 geeft dat: geen dubbele stem, ook niet via een volmacht. Wie een volmacht gaf, kan zich niet online aanmelden (`_portal_check_in`) en heeft dus geen eigen recht.

Een stem met bron `online` of `written` is definitief: `write` en `unlink` op `vme.assembly.vote` weigeren. `action_all_for` raakt alleen stemmen uit de zaal.

### Zaal en portaal naast elkaar

`_prepare_votes` (knop **Stemmen** en **Stemlijsten aanmaken**) maakt geen standaardstem "voor" meer voor lijnen met `votes_remotely`: online of schriftelijk aanwezig, of vertegenwoordigd door een volmachthouder die zelf online is. Anders zou een vooraf aangemaakte zaalstem het portaal blokkeren. Let op: wie de stemlijsten aanmaakt vóór de volmachthouder zich online aanmeldt, krijgt voor diens volmachtgevers wel een zaalstem. Maak de zaalstemmen daarom pas na het sluiten van de online stemming, of verwijder die lijnen.

### Openen en sluiten

`action_open_voting` vereist een bevestigde AV met `meeting_mode != in_person`, een aanwezigheidslijst en een punt met stemming; een gesloten stemming gaat niet opnieuw open. `action_close_voting` zet `closed` en het tijdstip. `action_mark_held` weigert zolang een stemming open is en sluit het online onthaal.

## Ondertekening van de notulen

`action_prepare_signing` (alleen in `held`, voorzitter en secretaris verplicht):

1. rendert `action_report_assembly_minutes` en bewaart de PDF als `ir.attachment` op de AV (`minutes_attachment_id`);
2. verwijdert openstaande aanvragen voor een oudere PDF (ze hebben geen bewijswaarde);
3. maakt een `vme.assembly.signature` per ondertekenaar met `document_sha256` = de hash van die PDF: voorzitter, secretaris en alle lijnen `present` behalve `written` (`# LEGAL-CHECK: art. 3.87 §10 BW`). Wie al een handtekening of aanvraag heeft voor dezelfde hash, krijgt er geen tweede.

`minutes_sha256` wordt telkens berekend uit `attachment.raw` (gelezen met `bin_size=False`, zie [valkuilen](valkuilen.md#binaire-velden-lezen-met-bin_size-stap-24)), nooit onthouden. `is_valid` = getekend en `document_sha256 == minutes_sha256`. Wijzigt iemand de bijlage, dan worden alle handtekeningen ongeldig en toont de AV `signature_state = invalid`.

`_portal_sign(partner, naam, ip, user_agent)` controleert de ondertekenaar, de status, en herberekent de hash van de bewaarde PDF op het moment van tekenen: verschilt die van `document_sha256`, dan weigert het. Een getekende handtekening is onveranderlijk (`write` en `unlink` weigeren).

Alleen `_portal_sign` en `_portal_cast_votes` schrijven het auditspoor, en ze doen dat als superuser. Zonder superuser weigeren `create` en `write` de velden van de handtekening (`state` anders dan `pending`, `signed_at`, `signed_name`, `ip_address`, `user_agent`) en een stem met bron `online` of `written` of met `cast_at`, `voter_partner_id` of `ip_address`. Zo kan een medewerker via RPC geen handtekening of online stem namaken; een contextvlag zou dat niet tegenhouden, want die geeft een RPC-aanroep zelf mee.

Dit is een eenvoudige elektronische handtekening (eIDAS art. 3, 10°), geen gekwalificeerde. Het IP-adres is wat Odoo ziet: achter een reverse proxy moet `proxy_mode` aan staan, anders is het het adres van de proxy (in Docker de gateway).

## Portaal

| Route | Wat |
| --- | --- |
| `/av/<token>` (public) | Link uit de oproeping. Niet ingelogd → `/web/login?redirect=/my/vme/assembly/<id>`; onbekende code → 404 |
| `/my/vme/assembly/<id>` | Aanwezigheid, agenda met stemformulier per punt, uitslag van gesloten punten, ondertekening |
| `POST .../checkin` | `_portal_check_in` |
| `POST .../vote` | `item_id` en `vote_<attendee_id>` per recht |
| `POST .../sign` | `signature_id`, `signed_name`, `agree` |
| `.../minutes` | De vastgezette PDF, alleen voor wie moet tekenen |

Toegang: `res.partner._vme_portal_assembly(id)` geeft een bevestigde of gehouden AV als de eigenaar op de aanwezigheidslijst staat (of, zolang er geen lijst is, huidige eigenaar is in die VME); anders 404. Meldingen na een POST gaan via de sessie (`vme_assembly_feedback`), niet via de URL. De detailpagina van de VME (`/my/vme/<id>`) krijgt een knop naar de vergadering en een melding "Notulen te ondertekenen"; de controller vult `assemblies_to_sign` aan in de `qcontext` van de bestaande route.

Een volmachthouder die geen eigenaar is in de VME, heeft geen portaaltoegang en stemt dus in de zaal.

## Oproeping

De concept-mail (`action_open_composer`) en de PDF van de oproeping vermelden de link voor online deelname en, als er punten met `allow_advance_vote` zijn, de schriftelijke stemming vooraf (met een * in de agenda). Er wordt niets verstuurd. Stap 23 (centrale communicatie) kan deze tekst later overnemen.

## Demo

`_load_demo_hybrid_assembly` (vanuit `_load_demo_data`): buitengewone hybride AV "Laadpalen in de garage" van Residentie Linde op 19 november 2026, bevestigd, oproeping verstuurd op 3 november, aanwezigheidslijst gemaakt, A7 geeft volmacht aan A1, voorzitter A2, secretaris A6. Twee punten na de opening: laadpalen (twee derde) en schilderwerken (volstrekt, schriftelijk vooraf toegestaan). Het onthaal is nog dicht. Portaallogins: `eigenaar.linde.a1@example.com` en `eigenaar.linde.a6@example.com` (wachtwoord `portaal-demo`). A2 heeft al een interne login als commissaris en krijgt daarom geen portaallogin.

## Testen

`tests/test_assembly_online.py`:

- `TestAssemblyOnlineVoting`: link, concept-uitnodiging met de link, aanmelden en quorum, stemmen alleen bij open stemming, regels van stap 11, volmachthouder voor twee, geen dubbele stem met volmacht, sluiten, definitieve stem, zaalstemmen naast het portaal, schriftelijk vooraf, buitengewone AV en de partiële unieke index;
- `TestAssemblyMinutesSignature`: ondertekenaars en hash, hash ook met `bin_size` in de context, auditspoor (naam, tijdstip, IP, browser, hash), één keer en alleen voor jezelf, onveranderlijk na tekenen, een medewerker kan niet in de plaats tekenen, gewijzigde PDF maakt ongeldig, opnieuw klaarzetten met en zonder wijziging;
- `TestAssemblyOnlinePortal` (`HttpCase`): pagina voor de eigenaar, 404 voor een vreemde, link per AV naar de login.

In tests rendert Odoo de notulen als HTML; de hash is dan stabiel. Met wkhtmltopdf verschilt elke rendering (aanmaakdatum in de PDF), dus opnieuw klaarzetten maakt in de echte omgeving altijd nieuwe aanvragen.

## Nog niet gebouwd

- Volledig schriftelijke besluitvorming zonder vergadering (eenparigheid, art. 3.87 §1 BW).
- Automatisch vernieuwen van de portaalpagina (nu met **Vernieuwen**).
- Een eigen videovergadering; de videolink verwijst naar een externe dienst.
- Gekwalificeerde handtekening (itsme, eID) en een ondertekeningsrapport als PDF.
- Een volmacht online geven in het portaal.
