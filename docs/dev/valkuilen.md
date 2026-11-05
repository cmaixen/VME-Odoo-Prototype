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

## Trage test na veel testruns

De test met een volledig demojaar (`vme_slow`) doet ongeveer 300 betalingen in één transactie. Na veel testruns heeft `vme_test` dode rijen en slechte planner-statistieken, en dan duurt één betalingsquery seconden in plaats van milliseconden (de test loopt dan tien minuten of meer). `ANALYZE` binnen de test helpt niet, omdat die de niet-gecommitte rijen niet meetelt. Oplossing: `VACUUM ANALYZE` op `vme_test` vóór de run; daarna duurt de test ongeveer 30 seconden.

## Opgelost na de review van de documentatie

- **Leveranciersfactuur met de hand ingeven in een VME-company faalde** met "Kan geen grootboekschema vinden voor dit bedrijf". Een company die met `chart_template` in `res.company.create()` wordt aangemaakt, krijgt geen standaardrekening voor leveranciers en klanten. Oplossing: `vme.association.create()` maakt de company zonder `chart_template` aan en laadt het rekeningstelsel in een precommit met `try_loading('be_comp', company)` (`_load_vme_chart`). Test: `test_bill_can_be_entered_by_hand`.
- **Land bleef leeg na het aanmaken van een VME** als de gebruiker Land niet invulde: het `related`-veld schreef `country_id: False` over België heen. `create()` vult nu België in de waarden zelf in. Test: `test_empty_country_defaults_to_belgium`.
- **De waarschuwing noemde de schakelaar "Geld verzenden"**; in de Nederlandse interface heet die **Betalen**.
- **Een provisieoproep voor volgend jaar met factuurdatum in dit jaar telde mee in de afrekening van dit jaar.** De jaarafrekening telt provisies nu per budgetjaar van hun oproep. Test: `test_next_year_call_sent_this_year_is_not_counted`.

## Bankregels en afletteren (stap 12)

- Een gewijzigde partner op een afgeletterde bankregel wist de tegenregels (`_synchronize_to_moves`). Zet de partner vóór het afletteren.
- In Community kan alleen de verborgen groep `account.group_account_basic` bankregels wijzigen; de module geeft `group_account_invoice` schrijfrecht.
- Meer in [bankafschriften.md](bankafschriften.md#valkuilen).

## Betalingsverkeer (stap 20)

- **Een betaling maakt in Community de factuur meteen betaald.** Daarom geen `account.payment` bij het versturen, maar eigen batchregels; zie [betalingsverkeer.md](betalingsverkeer.md#waarom-geen-accountpayment).
- **`with_user()` neemt de bedrijvenkiezer mee.** Een andere gebruiker met de geselecteerde bedrijven van de beheerder gaf "Toegang tot ongeautoriseerde of ongeldige bedrijven"; zet `allowed_company_ids` op de bedrijven van de VME.
- **Een SEPA-domiciliëring na de vervaldag is niet "te laat".** De koppeling van stap 12 zou dagen te laat tellen; bij een inning uit een batch staat `vme_days_late` op 0.

## Bekende problemen (nog open)

- Geen op dit moment.
