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

Testlogins in de demo (wachtwoord `portaal-demo`): `eigenaar.linde.a1@example.com` (A1 en G1) en `eigenaar.linde.a5@example.com` (verkocht A5 en G5 op 1 juli 2026). Gebruik voor een tweede demo een eigen hostnaam, zoals `http://portaal.localhost:8570`: zie [valkuilen](valkuilen.md#sessiecookies-per-hostnaam).

## Nog niet gebouwd

- Notulen, keuringsverslagen en jaarafrekeningen komen nog niet automatisch in de mappen.
- Eigenaars kunnen zelf geen documenten opladen.
- De commissaris van de rekeningen (stap 16) bouwt verder op deze routes en helpers.
