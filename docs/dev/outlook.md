# Outlook-invoegtoepassing (module `vme_mail_plugin`)

Een paneel in Outlook dat bij een mail van een eigenaar of huurder meteen de VME, de kavel en wat er openstaat toont, met het voorstel van de AI-assistent (`ai/assistant.py`). Vanuit het paneel bewaart de medewerker de mail in het dossier, maakt hij een aanvraag of zet hij het conceptantwoord in het antwoordvenster van Outlook. **Er vertrekt nooit iets vanzelf**: "Antwoord invoegen" opent het antwoordvenster en de medewerker drukt zelf op Verzenden.

## Waarom zo

- **Eigen module.** `vme_mail_plugin` hangt af van `vme_belgie` en Odoo's Community-module `mail_plugin`, zodat `vme_belgie` geen mailplugin nodig heeft (zoals `vme_website` de website apart houdt).
- **Backend en login van `mail_plugin`, eigen paneel.** De officiële Odoo-invoegtoepassing voor Outlook toont alleen contacten, leads en taken: de opmaak zit in de invoegtoepassing zelf, niet in Odoo. We hergebruiken wat Odoo Community al heeft (de API-sleutel met scope `outlook`, `auth="outlook"`, CORS) en bouwen een klein eigen Office.js-paneel zonder buildstap.
- **De juiste instance.** Elke syndicus heeft een eigen Odoo. Odoo maakt zelf het manifest, met zijn eigen adres erin, en dient het paneel. Zo praat de invoegtoepassing altijd met de instance waar ze vandaan komt. Binnen die instance koppelt het paneel op de afzender (eigenaar of huurder op vandaag) of toont het het AI-voorstel dat al bestaat.

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `models/vme_mail_context.py` | `vme.mail.context` (AbstractModel): alle logica, testbaar zonder HTTP |
| `models/vme_mail_plugin_setup.py` | wizard **VME > Configuratie > Outlook-invoegtoepassing** (https-adres, manifest, voorbeeld) |
| `controllers/mail_plugin.py` | de routes van het paneel, subklasse van `MailPluginController` |
| `controllers/manifest.py` | `/vme_mail_plugin/manifest.xml` en `/vme_mail_plugin/demo/inbox` |
| `static/outlook/taskpane.html`, `.js`, `.css` | het paneel, gewoon JavaScript |
| `static/outlook/auth_done.html` | eindpunt van de login, geeft de code terug aan het paneel |
| `static/outlook/demo_office.js` | vervanger van office.js voor het browservoorbeeld |
| `static/outlook/i18n/nl.json`, `fr.json` | teksten van het paneel per taal |
| `demo_data/inbox/` | kopie van de 8 fictieve mails van `ai/inbox/` (de Odoo-container mount alleen `addons/`) |
| `tools/outlook/Caddyfile` | https voor Outlook, lokaal |

## Routes

Alle routes van het paneel zijn `type="jsonrpc", auth="outlook", cors="*"`: een API-sleutel met scope `odoo.plugin.outlook` in de header `Authorization: Bearer …`. De gebruiker van de sleutel is de ingelogde gebruiker; company-regels en de regels van de commissaris gelden gewoon.

| Route | Doet |
| --- | --- |
| `/mail_plugin/vme/context` | `_vme_mail_context(email, name, subject, message_id[, association_id, lot_id])` |
| `/mail_plugin/vme/search` | VME of kavel op naam, voor een onbekende afzender (`Linde`, `Linde A4`, `A4`) |
| `/mail_plugin/vme/log` | bewaart de mail (tekst en bijlagen) als **interne notitie** (`mail.mt_note`) op de VME, een aanvraag of een schadedossier. Volgers krijgen geen mail, anders dan bij Odoo's eigen `log_mail_content` (subtype discussie) |
| `/mail_plugin/vme/request` | `vme.request.create_from_intake(..., channel="mail", reference=<Message-ID>)`; de vaste procedure volgt (concepten en taken, niets verstuurd) |
| `/vme_mail_plugin/manifest.xml` | `auth="user"`, alleen interne gebruikers: het manifest van deze instance |
| `/vme_mail_plugin/demo/inbox` | `auth="user"`, alleen beheerders of in debugmodus: de demomails voor het browservoorbeeld |

`_mail_content_logging_models_whitelist` krijgt `vme.association`, `vme.request` en `vme.damage.claim` erbij, zodat ook Odoo's eigen `log_mail_content` daar mag loggen.

## Hoe de koppeling werkt

`_vme_mail_matches(email)`:

1. Partners met dat `email_normalized` zoeken, **als superuser**: een commissaris mag huurders niet lezen, maar het adres staat in de mail zelf.
2. Kandidaatkavels via `vme.ownership` en `vme.lot.contact` (rol huurder), **als de gebruiker**: de record rules houden andere VME's buiten.
3. Per kavel `lot._get_owner_on(vandaag)` en `lot._get_tenants_on(vandaag)` vergelijken met het adres. Een vorige eigenaar (eigendom afgelopen) koppelt dus niet meer.
4. Eén match per (VME, rol, partner), met alle kavels: de eigenaar van B23 en B24 is één match met twee kavels. Een eigenaar in twee VME's krijgt twee matches; het paneel laat kiezen.

Naam en link van de partner komen alleen mee als de gebruiker het contact mag lezen (`_vme_mail_partner`); de commissaris ziet bij een huurder dus de rol en de kavel, niet de naam.

Per match de **open punten**: achterstallige provisies uit `vme.arrears` (SQL-view op de openstaande vorderingen, `CURRENT_DATE` van de database), open aanvragen van deze partner of over deze kavels (`state` niet in `CLOSED_STATES`; een aanvraag uit een mail van een onbekend adres heeft een nieuwe aanvrager, maar wel de kavel) en open schadedossiers op deze kavels of gemeld door deze partner.

Een **onbekende afzender** (bv. een privéadres) krijgt geen match. Het paneel toont dan een zoekveld (`_vme_mail_search`) en, als er een AI-voorstel is, de knop **Koppeling van de AI-assistent gebruiken**: die vraagt de context opnieuw op met de `association_id` en `lot_id` uit het voorstel. Zo'n gekozen koppeling heeft rol `manual`, met de eigenaar van vandaag als partner.

Het **AI-voorstel** (`_vme_mail_proposal`) zoekt op de Message-ID zonder `<>` (zoals `ai/mails.py` hem bewaart):

1. een `vme.request` met `source_reference` = referentie, als die een antwoord van de AI heeft (de notitie "Voorgesteld antwoord van de AI-assistent (niet verstuurd)");
2. anders een activiteit op de VME met samenvatting `AI-voorstel…` en de referentie in de notitie (zelfde zoekvraag als `ai/odoo_api.py find_activity`). De notitie van `assistant.activity_note` wordt gelezen met lxml: de `<li>` met **Kavel**, **Onderwerp**, **Dringendheid** en **Zekerheid koppeling** (zekerheid en reden gescheiden door een em-dash), en de `<blockquote>` na `<h4>Conceptantwoord: …</h4>`.

Een aanvraag die de medewerker later vanuit het paneel maakt, krijgt dezelfde referentie maar geen AI-antwoord; daarom wint de aanvraag alleen als ze een antwoord heeft, anders blijft het voorstel dat van de activiteit. Het voorstel geeft ook `lot_id` (de kavel uit de notitie, op naam binnen de VME).

Wie het formaat van `activity_note` wijzigt, past `NOTE_LABELS` en de test `test_proposal_from_an_activity_note` mee aan.

## Het paneel

- **Login**: "Verbinden met Odoo" opent `Office.context.ui.displayDialogAsync` op `/mail_plugin/auth?scope=outlook&redirect=<origin>/vme_mail_plugin/static/outlook/auth_done.html`. Na **Allow** stuurt Odoo naar `auth_done.html?success=1&auth_code=…`, dat de code met `messageParent` teruggeeft. Het paneel ruilt ze bij `/mail_plugin/auth/access_token` voor een API-sleutel (30 dagen, `mail_plugin.access_token_expiration_days`) en bewaart die in `localStorage`. Een geweigerde of verlopen sleutel (`Access token invalid`) wist de sleutel en toont opnieuw de knop.
- **Per mail** (ook bij een andere selectie in een vastgepind paneel, `ItemChanged`, Mailbox 1.5): `item.from`, `subject`, `internetMessageId`, `body.getAsync("text")`, dan `/mail_plugin/vme/context`.
- **Antwoord invoegen**: `item.displayReplyForm({htmlBody})`. Het HTML wordt in het paneel opgebouwd uit tekst (eerst `textContent`, daarna ge-escaped), niet doorgegeven zoals Odoo het bewaarde.
- **Bewaren bij dossier** stuurt de bijlagen mee als `getAttachmentContentAsync` bestaat (Mailbox 1.8); anders alleen de tekst.
- **Openen in Odoo**: `Office.context.ui.openBrowserWindow`, met links van de vorm `<adres>/odoo/<model>/<id>`.
- Teksten van het paneel in `static/outlook/i18n/<taal>.json` (`nl`, `fr`); de taal volgt `Office.context.displayLanguage` (`fr…` geeft Frans, anders Nederlands). De teksten in Odoo zelf (wizard, notitie) staan in `i18n/vme_mail_plugin.pot` en `fr.po`, zoals in de andere modules (zie [vertaling.md](vertaling.md)).

### Browservoorbeeld

`/vme_mail_plugin/static/outlook/taskpane.html?demo=1` laadt `demo_office.js` in plaats van office.js. Die vervanger implementeert alleen wat `taskpane.js` gebruikt, op de 8 demomails (`/vme_mail_plugin/demo/inbox`), en toont bij "Antwoord invoegen" wat er in het antwoordvenster van Outlook zou komen. De login loopt door de echte flow van `mail_plugin` in een popup: `auth_done.html?demo=1` stuurt de code met `postMessage` naar het paneel. Opent de browser de popup in hetzelfde tabblad (geen `window.opener`, bv. in een ingebouwde browser), dan ruilt `auth_done.html` de code zelf in, bewaart de sleutel en gaat terug naar het voorbeeld. Parameters: `&mail=01_lek_badkamer.eml` kiest een mail, `&lang=fr` het Frans.

`demo_data/inbox/` is een kopie van `ai/inbox/`; `ai/tests/test_assistant.py::test_outlook_demo_mails_are_the_inbox` faalt als ze uit elkaar lopen. Kopieer na een wijziging aan `ai/inbox/`:

```bash
cp ai/inbox/* addons/vme_mail_plugin/demo_data/inbox/
```

## Manifest en https

- `GET /vme_mail_plugin/manifest.xml` geeft een XML-manifest (MailApp, `ReadItem`, leesformulier van een bericht, een knop **VME-dossier** in het lint). Het adres is de systeemparameter `vme_mail_plugin.base_url` (ingesteld in de wizard), anders `web.base.url`. Het id is een vaste GUID per database (`vme_mail_plugin.addin_id`), zodat een nieuw manifest de invoegtoepassing vervangt.
- Outlook laadt invoegtoepassingen **alleen over https**. Lokaal zet een optionele Caddy-service https voor Odoo:

  ```bash
  docker compose --profile outlook up -d
  ```

  Dat start `https://localhost:8443` met een eigen certificaat (`tls internal`). Vertrouw het rootcertificaat van Caddy eenmalig op de Mac:

  ```bash
  docker compose cp https:/data/caddy/pki/authorities/local/root.crt /tmp/caddy-root.crt
  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /tmp/caddy-root.crt
  ```

  Zet daarna in **VME > Configuratie > Outlook-invoegtoepassing** het adres op `https://localhost:8443` en download het manifest. De demoserver op 8069 blijft zoals hij is.
- In productie staat Odoo al achter https (met `proxy_mode`); dan volstaat `web.base.url`.

## Testen

- `tests/test_mail_context.py`: koppeling (eigenaar van twee kavels, eigenaar in twee VME's, huurder, onbekend, vorige eigenaar, manuele keuze na zoeken), open punten alleen van deze partner en VME, AI-voorstel uit een activiteit en uit een aanvraag, bewaren als interne notitie, aanvraag met `channel="mail"`, toegang (medewerker met één VME, commissaris leest maar schrijft niets).
- `tests/test_routes.py` (HttpCase): echte API-sleutel met scope `odoo.plugin.outlook`, zonder of met een verkeerde sleutel een fout, een sleutel met een andere scope geweigerd, `/vme/log` en `/vme/request` over HTTP, het manifest met het adres van de instance en een vast id, de demomails alleen voor beheerders.

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_mail_plugin --test-enable --test-tags /vme_mail_plugin --stop-after-init
```

## Valkuilen

- **`auth="outlook"` is geen sessie.** De routes zien de sessiecookie niet; het paneel stuurt `credentials: "omit"` en altijd de bearer-sleutel. Het browservoorbeeld gebruikt dus ook de echte login, niet de sessie van de beheerder.
- **Een fout in de authenticatie komt als JSON-RPC-fout terug**, met HTTP 200 en `Access token invalid` of `Access token missing` in de boodschap. Het paneel herkent die tekst om opnieuw te laten verbinden.
- **Outlook op het web opent een dialoog ook als popup.** `auth_done.html` gebruikt `postMessage` naar het venster dat hem opende alleen met `?demo=1`; anders altijd `Office.context.ui.messageParent`.
- **Odoo geeft statische bestanden een week browsercache** (`Cache-Control: max-age=604800`). Na een upgrade zou Outlook dan oude code tonen. `taskpane.html` laadt daarom `taskpane.js`, `taskpane.css` en de teksten met `?v=<tijd>`, en het manifest wijst naar `taskpane.html?v=<moduleversie>`.
- **Cookies op `localhost` delen alle poorten.** Draait er een tweede Odoo naast de demo (bv. op 8690), dan overschrijven de sessiecookies elkaar en wordt u telkens uitgelogd. Gebruik voor de tweede een eigen naam, bv. `http://outlook.localhost:8690`.
- **`vme.arrears` rekent op de echte datum** van de database, ook in tests met `freeze_time`; gebruik vervaldagen ruim in het verleden.
