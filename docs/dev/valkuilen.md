# Valkuilen

Wat misliep tijdens de bouw, en hoe we het oplosten. Onderaan staan bekende problemen die nog open zijn.

## Modules die Odoo zelf installeert

Zodra de eerste Belgische company bestaat, wil Odoo `l10n_be` installeren, en daarna `account_peppol`. Gebeurt dat midden in het opslaan van een VME, dan herlaadt Odoo de registry in hetzelfde verzoek en loopt het vast. Oplossing: beide staan in `depends` van de manifest, zodat ze bij de installatie van `vme_belgie` al geïnstalleerd worden. `-i vme_belgie` installeert dus ook `account`, `l10n_be` en `account_peppol`.

## Bevestigde bankrekeningen

Odoo zet een bankrekening van de eigen company pas op een klantfactuur als `allow_out_payment` aanstaat ("Betalen" / "Vertrouwd" in de interface). Dat mag alleen een gebruiker met de juiste rechten (`res.partner.bank._user_can_trust()`); de superuser en scripts als systeemgebruiker mogen het bewust niet.

- Zonder bevestigde rekening laat Odoo `partner_bank_id` stil weg van de provisiefactuur. Daarom weigert de wizard met een melding als `untrusted_fund_bank_ids` niet leeg is, en toont het VME-formulier een waarschuwing.
- De demodata bevestigt de rekeningen alleen als de gebruiker dat mag. Laad de demo daarom als `admin` (`env(user=env.ref('base.user_admin'))` in de shell). De demohistoriek weigert te laden met onbevestigde rekeningen.
- In tests: `with_user(admin)` voor het laden van de demo.

## Multi-company

Elke VME is een company, en een medewerker heeft meestal maar een deel van de companies geselecteerd.

- **Boeken in de juiste company.** De provisiewizard boekt met `vme_invoices.with_company(vme.company_id).action_post()`, anders weigert Odoo records van een company buiten `env.company`.
- **Lezen over VME's heen.** Berekeningen die alle VME's tonen (betaalstatus van oproepen, jaarafrekening, 5%-regel, `vme_association_id`) lezen met `sudo()` of `compute_sudo=True`. Anders telt een oproep alleen de facturen van de companies die toevallig in de bedrijvenkiezer aanstaan.
- **Na de wizard een lijst van oproepen, geen lijst van facturen.** Een factuurlijst toont alleen de geselecteerde companies; de lijst van oproepen telt over alle companies.
- **Toegang tot nieuwe companies.** `vme.association.create()` koppelt elke interne gebruiker aan de nieuwe company. Zonder dat zou een VME die een script (of de systeemgebruiker) aanmaakt onzichtbaar zijn voor de medewerkers.
- **Rekeningstelsel bij de commit.** Een company met `chart_template` krijgt haar rekeningstelsel pas bij de commit (een `precommit`-haakje). Wie meteen na het aanmaken rekeningen zoekt, vindt niets. Daarom vult `_post_load_data` de VME-rekeningen aan, en zet de demodata de rekeningen van de verdeelregels via `self.env.cr.precommit.add(...)`. In tests roep je `cls.env.cr.precommit.run()` aan na het laden.

## Tijdelijke records in formulieren (`_origin`)

In een open formulier of wizard zijn Many2one- en Many2many-waarden tijdelijke `NewId`-records. Een `search` met `vme.id` vindt dan niets. Gebruik `record._origin` (of `record._origin.id`) om het echte record te krijgen, zoals in `vme.provision.call.wizard._get_budget()` en `vme.annual.statement.wizard._get_statement()`. Het voorbeeld (`preview_html`) wordt berekend terwijl het formulier nog open is, dus elke compute die zoekt, moet dit doen.

## Som van een sleutel tijdens het bewerken

Een formulier stuurt regelcommando's één voor één. Een constraint op de regel zou na de eerste gewijzigde regel al falen. Daarom zet `vme.key.write()` de context `vme_skip_line_check` en controleert de constraint op de sleutel het eindresultaat. Wie een regel los bewerkt of verwijdert (zonder die context), wordt wel meteen gecontroleerd.

## Trage tests en de tag `vme_slow`

De test met een volledig demojaar (`TestAnnualStatementDemo`) maakt ongeveer 300 betalingen in één testtransactie en duurt meer dan 10 minuten. Hij draagt de tags `-standard` en `vme_slow`, zodat `--test-tags /vme_belgie` hem overslaat.

- In een testdatabase zijn de statistieken van PostgreSQL leeg ("0 rijen"), waardoor de planner slechte plannen kiest. De test draait `ANALYZE` op `account_move`, `account_move_line`, `account_partial_reconcile` en `res_partner` na het laden van de demodata; dat maakt het verschil tussen minuten en seconden per stap.
- Draai hem vóór een demo en na elke wijziging aan de verdeling of de afrekening.

## PDF's zonder opmaak

wkhtmltopdf draait in de Odoo-container en haalt de stylesheets van het rapport op via HTTP bij Odoo zelf.

- **Databasefilter.** Zonder `--db-filter` weet de server bij dat verzoek niet welke database bedoeld is (er staan er twee: `vme_demo` en `vme_test`), en de PDF komt zonder opmaak. `docker-compose.yml` start de server daarom met `--db-filter=^vme_demo$`. Dat haalt meteen ook de databasekeuze van het loginscherm weg.
- **Andere poort.** wkhtmltopdf gebruikt `report.url` of anders `web.base.url`. Die laatste wordt bij de eerste login van admin gezet op de URL in de browser. Draai je Odoo op een andere hostpoort (bijvoorbeeld `-p 8370:8069`), dan kan de container `localhost:8370` niet bereiken ("wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError"). Zet dan de systeemparameter `report.url` op `http://localhost:8069`.
- Bij het laden van de demohistoriek via `odoo shell --no-http` verschijnt dezelfde waarschuwing (Odoo maakt een PDF-voorbeeld van de opgeladen UBL-facturen). Die is onschuldig.

## Shell, `run` en `exec`

- `docker compose run --rm odoo odoo ...` geeft het entrypoint de databaseverbinding mee; `docker compose exec odoo odoo ...` blijft hangen.
- Wijzigingen die je met `odoo shell` maakt aan systeemparameters of `ir.default`, ziet een lopende server pas na een herstart: de shell verwittigt de caches van de server niet.

## Bekende problemen (nog open)

- **Leveranciersfactuur met de hand ingeven in een VME-company faalt** met "Kan geen grootboekschema vinden voor dit bedrijf" (`account.move._onchange_partner_id`). Een company die met `chart_template` in `res.company.create()` wordt aangemaakt, krijgt geen `ir.default` voor `property_account_payable_id` en `property_account_receivable_id`. Met `env['account.chart.template'].try_loading('be_comp', company)` na het aanmaken wel. Code die facturen aanmaakt zonder onchange (demohistoriek, tests, UBL-import via `_create_document_from_attachment`) merkt het niet. Tijdelijke oplossing in een demo: per VME-company `ir.default.set('res.partner', 'property_account_payable_id', <440000>, company_id=...)` en idem voor 400000, en Odoo herstarten.
- **Land leeg na het aanmaken van een VME in de interface**, als de gebruiker Land niet invulde. Het formulier stuurt `country_id: False` mee; `create()` zet België op de company, maar het `related`-veld schrijft het daarna weer leeg.
- **"Geld verzenden"** in de waarschuwing en de wizardmelding heet in de Nederlandse interface **Betalen**.
- **Provisieoproep voor volgend jaar met factuurdatum in dit jaar** telt mee in de jaarafrekening van dit jaar. De wizard stelt vandaag voor als factuurdatum.
