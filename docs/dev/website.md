# Productwebsite (stap 27, module `vme_website`)

Een publieke productwebsite op Odoo Community `website`, met één knop **Inloggen** naar de backend of het eigenaarsportaal, en een formulier "Demo aanvragen" dat een lead maakt.

## Waarom een aparte module

`vme_website` hangt af van `website`, `website_crm` en `vme_belgie`. Zo heeft `vme_belgie` geen website nodig: wie alleen de backend en het portaal wil (bv. een testdatabase), installeert `website` niet. Met `website` geïnstalleerd verandert Odoo meer dan je zou denken (zie [Gevolgen](#gevolgen-van-website)), dus dat blijft een keuze.

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `models/website.py` | `website._vme_setup_product_website()`: naam, logo, `configurator_done`, taal nl_BE, geen standaardverkoper voor leads, Odoo's `/contactus` ongepubliceerd, hoofdmenu |
| `data/website_data.xml` | roept de setup aan bij elke installatie en upgrade |
| `data/page_data.xml` | `website.page` voor `/functies`, `/voor-eigenaars`, `/prijzen`, `/contact`, `/demo-aangevraagd`, `/inloggen`; `website.rewrite` 301 van `/contactus` naar `/contact` |
| `views/page_templates.xml` | de pagina's (standaardsnippets `s_text_image`, `s_features`, `s_three_columns`, `s_call_to_action`, `s_title`, `s_website_form`) en de homepage (erft van `website.homepage`) |
| `views/layout_templates.xml` | knop **Inloggen** (erft van `portal.user_sign_in`), uitleg op `/web/login`, header zonder zoekbalk en telefoonnummer, CTA, footer en copyright |
| `controllers/main.py` | `_login_redirect` op type gebruiker |
| `static/src/scss/primary_variables.scss` | palet `vme-quotis` (diep groenblauw `#1F5F6B`, oker `#C8893B`) en lettertype Inter via `$o-website-values-palettes` |
| `static/src/img/` | logo (svg) en vier schermafbeeldingen uit de fictieve demo |
| `data/help_menu.xml` | **VME > Help > De website en inloggen** |

## Inloggen

De knop **Inloggen** is een dropdown met twee links: `/web/login?redirect=/odoo/action-vme_belgie.vme_association_action` (medewerkers) en `/web/login?redirect=/my` (eigenaars en huurders). Op een gsm staat dezelfde dropdown in het offcanvas-menu. `/inloggen` toont de twee keuzes als kaarten.

Odoo zelf stuurt al portaalgebruikers naar `/my` en interne gebruikers naar `/odoo` (`website.controllers.main.Website._login_redirect` en `portal.controllers.web.Home._login_redirect`), maar alleen **zonder** expliciete `redirect`. Met de knop is er altijd een redirect, dus `VmeWebsite._login_redirect` beslist op het type gebruiker:

| Gebruiker | redirect | Landt op |
| --- | --- | --- |
| intern | leeg, `/odoo` of `/my` | `/odoo/action-vme_belgie.vme_association_action` (app VME) |
| intern | iets anders | ongewijzigd |
| portaal | leeg of een backend-URL (`/odoo…`, `/web…`) | `/my` |
| portaal | iets anders (`/my/vme/…`, `/av/<code>`) | ongewijzigd, zodat links uit een uitnodiging blijven werken |

`/web/login` toont boven het e-mailveld een korte uitleg als de redirect met `/odoo` of `/my` begint (`login_route_hint`, erft van `web.login`).

## Demo aanvragen: een lead, geen mail

Odoo's eigen `/contactus` gebruikt `data-model_name="mail.mail"` en verstuurt een mail naar de company. Dat botst met "een mens beslist altijd". Daarom:

- Een eigen formulier (`demo_request_form`, gebruikt op `/prijzen#demo` en `/contact`) met `data-model_name="crm.lead"`. `website_crm` zet `crm.lead` open voor de form builder (`website_form_access`, whitelist van `contact_name`, `partner_name`, `email_from`, `phone`, `description`, `name`). Het onderwerp (`name`) is een verborgen veld "Demo-aanvraag via de website"; "Aantal VME's" is een vrij veld en komt in `description` onder "Overige informatie".
- `website.crm_default_user_id` staat leeg: zonder verkoper verstuurt Odoo geen toewijzingsmail.
- Odoo's `/contactus` is ongepubliceerd en stuurt met een 301 door naar `/contact`. Een `website.rewrite` alleen volstaat niet: een gepubliceerde `website.page` gaat voor op een redirect.

Test: `test_demo_form_creates_lead_without_mail` (het aantal `mail.mail` blijft gelijk).

## Gevolgen van `website`

- `/` toont de homepage in plaats van naar de login te sturen.
- `/web/login` en het eigenaarsportaal (`/my`, stap 15) krijgen de header en footer van de website. De CTA **Demo aanvragen** is er alleen voor bezoekers zonder login.
- Odoo installeert de app **CRM** mee (via `website_crm`).
- De bestaande portaaltests van `vme_belgie` blijven groen met `website` geïnstalleerd (nagekeken op `vme_web_test`).

## De naam wijzigen

**Quotis** is een werktitel; de naam bestaat al en wordt vervangen. Hij staat in:

- `PRODUCT_NAME` in `models/website.py` (websitenaam; de setup schrijft het logo opnieuw zodra de naam verschilt);
- `static/src/img/logo.svg`;
- de teksten in `views/page_templates.xml` en `views/layout_templates.xml`, het e-mailadres `info@quotis.example`;
- `docs/kb/website-en-inloggen.md` en deze pagina.

`grep -rn -i quotis addons/vme_website docs` vindt ze allemaal. Teksten die al in de website-editor bewerkt zijn, staan als kopie in de database en moet je daar aanpassen.

## Valkuilen

- **Odoo website scrolt in `#wrapwrap`, niet in het document.** Een schermafbeelding van een volledige pagina met `captureBeyondViewport` verschuift; maak de viewport zo hoog als `#wrapwrap.scrollHeight`.
- **Het menu van een website is een kopie.** Odoo kopieert `website.main_menu` naar elke website bij het aanmaken, dus records onder `website.main_menu` toevoegen verandert de bestaande website niet. De setup bouwt het menu van de standaardwebsite opnieuw op, maar alleen zolang er nog geen menu `/functies` is: wijzigingen in de editor blijven bij een upgrade.
- **Desktopheader vanaf 992 px.** Onder die breedte toont Odoo de gsm-header met offcanvas-menu; test de dropdown op beide.

## Testen

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie,vme_rentmeester,vme_website --test-enable --test-tags /vme_belgie,/vme_rentmeester,/vme_website --stop-after-init
```

`tests/test_website.py`: publieke pagina's, beide routes in de header, de 301 van `/contactus`, de landing na het inloggen voor medewerker en eigenaar (ook via de andere route, en een expliciete portaallink blijft), en het formulier.

In de browser: gebruik eigen hostnamen per rol (bv. `syndicus.localhost` en `eigenaar.localhost`), want cookies gelden per hostnaam (zie [valkuilen](valkuilen.md#sessiecookies-per-hostnaam)).
