# Documenten en eigenaarsportaal (stap 15)

## Wat is er gebouwd

- **Documentenbeheer** zonder de Enterprise-module `documents`: een eigen model `vme.document` met een binair veld (`attachment=True`, dus opgeslagen als `ir.attachment`) in vaste mappen `vme.document.folder` (`data/document_folders.xml`, `noupdate`). Een map heeft een `scope`: `vme` of `lot`.
- **Eigenaarsportaal** op de Community-module `portal` (LGPL, al geïnstalleerd als afhankelijkheid van `account`): routes onder `/my/vme`, templates in `views/portal_templates.xml`, controller in `controllers/portal.py`.
- **Register van eigenaars** (`vme.ownership` met `is_current`, contactvelden en knop naar Odoo's `portal.wizard`) en **adreswijzigingen** (`vme.address.request`) met goedkeuring door de syndicus.

## Beveiliging in lagen

1. **Geen toegangsrechten voor portaalgebruikers** op welk `vme.*`-model ook. Een portaalgebruiker die via JSON-RPC rechtstreeks `vme.document`, `vme.sale.file` of `vme.collection` leest, krijgt een `AccessError` (getest).
2. **Eén plaats per regel.** De controllers lezen als `sudo`, maar uitsluitend via:
   - `res.partner._vme_portal_ownerships()`: alle eigendommen van de commerciële partner van de gebruiker; daaruit volgen `_vme_portal_associations()` en `_vme_portal_check_association(id)`.
   - `vme.document._portal_domain_for(partner)`: de zichtbaarheidsregel voor documenten (zie hieronder).
   - `_vme_portal_provisions(vme)`: geboekte `out_invoice` met `vme_provision_call_id`. Kostenfacturen van de invordering (stap 10, `vme_collection_id`) hebben geen provisieoproep en komen er dus nooit in.
   - `_vme_portal_statement(vme, year)`: `vme.association._get_annual_statement(year, partners=owner)`, alleen voor jaren met kosten of provisies van die eigenaar.
   - `_vme_portal_next_assembly(vme)`: alleen voor huidige eigenaars.
3. **404 voor alles wat niet van de eigenaar is**, ook bij geraden id's: een andere VME, een document van een andere kavel, een afrekening van een andere VME.

Verkoopdossiers (stap 9) en invorderingsdossiers en herinneringen (stap 10) hebben geen route in het portaal en geen toegangsrecht voor portaalgebruikers.

### Zichtbaarheid van documenten

Alleen documenten met `portal_visible`. Daarnaast, per eigendom (kavel, begin, einde) van de partner:

| Document | Zichtbaar als |
| --- | --- |
| van de VME (`lot_id` leeg) | eigendom in die VME en `date <= date_end` (of geen einde) |
| van een kavel | eigendom van díe kavel en `date_start <= date <= date_end` |

Een nieuwe eigenaar ziet dus de oudere documenten van het gebouw (basisakte, notulen), maar niet de briefwisseling met de vorige eigenaar. De verkoper ziet na de verkoop niets nieuws meer. De regel staat als `Domain` in `_portal_domain_for`, zodat er één zoekopdracht is en de controller nooit zelf filtert.

## Routes

| Route | Wat |
| --- | --- |
| `/my` | Tegel "Mijn mede-eigendom" (teller `vme_count`); Odoo's tegel "Je facturen" verborgen voor eigenaars |
| `/my/vme` | VME's en kavels, link naar de adreswijziging |
| `/my/vme/<id>` | Volgende AV, provisies met betaalstatus, jaarafrekeningen, documenten per map |
| `/my/vme/<id>/statement/<jaar>` en `/pdf` | Afrekening van die eigenaar; de PDF gebruikt het bestaande rapport via een tijdelijke `vme.annual.statement.wizard` met alleen die eigenaar |
| `/my/vme/document/<id>` | Bestand via `ir.binary._get_stream_from`; `?download=1` als bijlage |
| `/my/vme/address` | Formulier; maakt `vme.address.request` en een taak voor de beheerder |
| `/my/vme/requests`, `/my/vme/requests/new`, `/my/vme/request/<id>` (+ `/proof`) | Aanvragen indienen en opvolgen, bewijs opladen (stap 27) |
| `/my/vme/survey/<log_id>` | Een bevraging beantwoorden (stap 27) |
| `/av/<code>`, `/my/vme/assembly/<id>` | Online deelnemen, stemmen en notulen ondertekenen (stap 24, zie [digitale-av.md](digitale-av.md)) |

`/my/counters` (Odoo's script voor de tellers op `/my`) mag alleen tellers teruggeven die op de pagina staan: bij een andere sleutel stopt het script en verschijnt geen enkele tegel. `vme_owner` (om Odoo's factuurtegel te verbergen) wordt daarom alleen bij het opbouwen van `/my` gezet.

De PDF van een provisie is Odoo's eigen factuurroute (`move.get_portal_url(report_type="pdf")`), met het toegangstoken van de factuur: de portaalgebruiker heeft geen toegang tot de company van de VME, het token volstaat.

## Adreswijziging

Odoo's eigen portaal laat een klant zijn adres rechtstreeks aanpassen (`/my/account`, `/my/addresses`, `/my/address/submit`). Voor eigenaars:

- `res.partner._can_be_edited_by_current_customer()` geeft `False` voor een niet-interne gebruiker die eigenaar is; Odoo's eigen submitroute weigert dan (`Forbidden`).
- De routes `/my/account` en `/my/addresses` sturen een eigenaar door naar `/my/vme/address`.
- `vme.address.request.action_approve()` schrijft de velden naar de partner; `action_refuse()` niet. Eén openstaande aanvraag per eigenaar tegelijk (in de controller).

## Portaaltoegang geven

De knop **Portaaltoegang** in het register opent Odoo's `portal.wizard`. Die stuurt de uitnodiging pas als de syndicus op "Toegang verlenen" klikt. De demo maakt de twee testlogins rechtstreeks aan met een wachtwoord en `no_reset_password`, zodat er niets verstuurd wordt.

## Tests

`tests/test_portal.py`: `TestPortalAccess` (helpers, ORM-rechten, adreswijziging) en `TestPortalRoutes` (`HttpCase`, ingelogd als portaalgebruiker: 200 voor eigen documenten, 404 voor andere VME, andere kavel, intern document en documenten na de verkoop; doorsturen van `/my/account`).

## Testen in de browser

Testlogins in de demo (wachtwoord `portaal-demo`): `eigenaar.linde.a1@example.com` (A1 en G1), `eigenaar.linde.a5@example.com` (verkocht A5 en G5 op 1 juli 2026) en `eigenaar.linde.a6@example.com` (A6 en G6, secretaris van de hybride AV van stap 24). Gebruik voor een tweede demo een eigen hostnaam, zoals `http://portaal.localhost:8570`: zie [valkuilen](valkuilen.md#sessiecookies-per-hostnaam).

## Aanvragen en bevragingen (stap 27)

Controller `controllers/portal_requests.py`, helpers in `models/vme_portal_requests.py`, templates in `views/portal_request_templates.xml`. Dezelfde lagen als hierboven: geen toegangsrechten op `vme.request` of `vme.communication.*` voor portaalgebruikers (getest), sudo alleen via de helpers, 404 voor alles wat niet van de partner is.

| Helper | Regel |
| --- | --- |
| `_vme_portal_tenant_lots()` | Kavels met een `vme.lot.contact` (rol `tenant`) van de partner op vandaag; `vme_rentmeester` voegt de kavels van zijn huurcontracten toe. |
| `_vme_portal_current_tenant_lots()` | Dezelfde kavels, nagekeken met `vme.lot._get_tenants_on(today)`: de ene regel voor huurders. |
| `_vme_portal_request_lots()` | Kavels die de partner vandaag bezit (`is_current`) of huurt. Alleen die staan in het formulier; een ander `lot_id` in de POST geeft 404 en geen aanvraag. |
| `_vme_portal_requests()` | Aanvragen met `requester_id` = de commerciële partner. Een eigenaar ziet de aanvragen van zijn huurder niet. |
| `_vme_portal_create_request()` | `create_from_intake(channel="portal", requester_id=…, user_id=admin)`: zelfde herkenning en procedure als per mail. Heeft de aanvraag daarna geen taak (attest, overlast), dan krijgt de medewerker "Aanvraag uit het portaal behandelen". Bijlagen: max. 5 bestanden van 10 MB. |
| `vme.request._portal_messages()` | Alleen berichten met subtype `mt_comment` van of aan de aanvrager; notities, de bewijsvraag als concept en de bestelling blijven intern. |
| `vme.request._portal_add_proof()` | Alleen de aanvrager, alleen in `waiting_proof`: bijlagen bij `proof_attachment_ids`, een notitie en een To-do. Er wordt niets goedgekeurd. |
| `_vme_portal_surveys()` | Loglijnen van de partner, van verzendingen met `kind = survey` en `state = sent`. |
| `vme.communication.log._portal_answer()` | Eigen lijn, verzending verstuurd, vóór `answer_deadline`; wijzigen kan tot dan. |

**Huurders in het portaal.** Een huurder met een login krijgt de tegel en `/my/vme` (kaart "Gehuurde kavels"), aanvragen en bevragingen, maar `/my/vme/<id>` blijft eigenaar-only (`_vme_portal_check_association` kijkt naar eigendommen), dus geen documenten, provisies of afrekeningen. `_vme_portal_has_access()` = eigenaar (nu of vroeger) of huurder vandaag.

**Verantwoordelijke.** Onder `sudo()` blijft `env.user` de portaalgebruiker. Zonder `user_id` zou de aanvraag (en elke taak) bij de eigenaar zelf staan; daarom geeft het portaal `base.user_admin` mee, zoals de adreswijzigingen. Een verantwoordelijke per VME bestaat nog niet.

**Controllers samenvoegen.** `VmeAssemblyPortal` en `VmeRequestPortal` erven allebei van `VmeOwnerPortal` en overschrijven `portal_my_vme_detail`; Odoo maakt uit alle subklassen één controller, dus beide `super()`-ketens lopen. Feedback na een POST gaat via de sessie, zoals bij de AV.

Tests: `tests/test_portal_requests.py` (`TestPortalRequests` op de helpers, `TestPortalRequestRoutes` als portaalgebruiker over HTTP, met CSRF-token via `http.Request.csrf_token(self)`).

## Nog niet gebouwd

- Notulen, keuringsverslagen en jaarafrekeningen komen nog niet automatisch in de mappen.
- Eigenaars kunnen zelf geen documenten opladen in de mappen (wel bewijsstukken bij een eigen aanvraag, stap 27).
- De commissaris van de rekeningen (stap 16) bouwt verder op deze routes en helpers.
