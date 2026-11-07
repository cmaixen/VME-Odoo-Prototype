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

## Rentmeester: facturen in de company van het kantoor (stap 25)

- **Huurfacturen zijn onzichtbaar zonder de company van het kantoor.** Ze leven in de company van het rentmeesterkantoor; een lijst van facturen toont alleen de geselecteerde companies. De teller op het contract en de controle "al een factuur voor deze maand" lezen daarom met `sudo()`: zonder dat maakte de wizard een tweede factuur voor dezelfde maand zodra een gebruiker een andere company geselecteerd had.
- **Rekeningcodes zijn per company.** In Odoo 19 is `account.account.code` afhankelijk van de company in de context. Lees de code van een rekening uit een VME met `account.with_company(vme_company).code`, anders is ze leeg (zo vielen verzekering en energie eerst in geen enkele rubriek).
- **`format_date` in een QWeb-rapport** bestaat niet vanzelf: geef het mee via een `report.<module>.<template>`-model met `_get_report_values`, zoals de rapporten van de rentmeester en het verkoopdossier.

## Doorstorting en betaalbatch van het kantoor (stap 25b)

- **Een `related` veld overschrijven met een compute.** `company_id` van `vme.payment.batch` was `related="association_id.company_id"`. In `vme_rentmeester` wordt het `fields.Many2one("res.company", related=None, compute=..., store=True)`; zonder de comodel faalt het laden met "unknown comodel_name '???'", want een related veld haalt die anders van zijn bron.
- **Een niet-opgeslagen statusveld zonder `@api.depends` blijft in de cache hangen.** De betaalstatus van een doorstorting bleef "klaar voor betaalbatch" nadat de batch gevuld was; met depends op de status van het doorstortingsstuk wordt ze opnieuw berekend.
- **Knoppen met een andere company geselecteerd.** Bevestigen, goedkeuren en het SEPA-bestand lazen btw, facturen en het doorstortingsstuk van het kantoor en gaven "Toegangsfout" zodra de gebruiker alleen een andere company had aangevinkt. Doorstorting en betaalbatch van het kantoor draaien hun knoppen daarom met `with_company(kantoor)` (`_in_own_company` op de batch); de test `test_confirm_with_other_company_selected` doet het als admin met alleen de hoofdcompany.
- **De ereloonfactuur vraagt een bevestigde rekening van het kantoor.** Odoo weigert een klantfactuur te boeken met een niet-bevestigde eigen rekening ("The company bank account ... is not trusted"), behalve voor de superuser. Tests die als gewone gebruiker bevestigen, laten de rekening eerst door admin bevestigen; de demo laadt als admin.
- **Het rekeningstelsel van het kantoor bestaat pas bij de commit.** De btw van de demomandaten wordt daarom in een precommit ingevuld, en `_get_fee_tax()` valt terug op 21 % diensten van het kantoor als het mandaat geen btw heeft.

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

## Sessiecookies per hostnaam

Browsers bewaren cookies per hostnaam, niet per poort. Draaien er meerdere demo's op `localhost` (8069, een tweede demo, het portaal), dan overschrijven ze elkaars `session_id`: je wordt telkens uitgelogd, of krijgt "Session expired (invalid CSRF token)". Gebruik per demo een eigen hostnaam onder `.localhost`, bv. `http://portaal.localhost:8570` voor de eigenaar en `http://syndicus.localhost:8570` voor de syndicus. Zo kun je ook eigenaar en syndicus naast elkaar ingelogd houden.

## Facturen van een VME in Odoo's eigen portaal (stap 15)

Odoo's lijst `/my/invoices` zoekt met de rechten van de portaalgebruiker, en de multi-company-regel op `account.move` laat alleen facturen uit zijn eigen companies door. Provisiefacturen staan in de company van de VME, dus die lijst blijft leeg. We tonen de provisies in `/my/vme/<id>` (sudo, gefilterd op de eigenaar) en linken naar de PDF met het toegangstoken van de factuur.
## Betalingsverkeer (stap 20)

- **Een betaling maakt in Community de factuur meteen betaald.** Daarom geen `account.payment` bij het versturen, maar eigen batchregels; zie [betalingsverkeer.md](betalingsverkeer.md#waarom-geen-accountpayment).
- **`with_user()` neemt de bedrijvenkiezer mee.** Een andere gebruiker met de geselecteerde bedrijven van de beheerder gaf "Toegang tot ongeautoriseerde of ongeldige bedrijven"; zet `allowed_company_ids` op de bedrijven van de VME.
- **Een SEPA-domiciliëring na de vervaldag is niet "te laat".** De koppeling van stap 12 zou dagen te laat tellen; bij een inning uit een batch staat `vme_days_late` op 0.

## Gebouwkaart en leverancierskaart (stap 22)

- **Rekeningcodes zijn per company opgeslagen.** `account.account.code` is berekend uit `code_store` (jsonb per hoofdcompany). Met sudo zonder `with_company` is de code van een rekening van een VME leeg; in SQL lees je `account.code_store->>(company_id::text)`.
- **Een betaling zonder tussenrekening boekt niet op de bankrekening.** Geregistreerde betalingen van provisies staan pas op de standaardrekening van het bankdagboek na een gekoppeld afschrift. "Op de rekening" telt daarom ook de betalingen met `is_matched = False`.
- **De cache van een berekend veld is gedeeld tussen gebruikers.** Zonder `@api.depends_context("uid")` gaf de leverancierskaart in dezelfde transactie de versie van de commissaris aan de medewerker (en omgekeerd). Velden waarvan de inhoud van de gebruiker afhangt, krijgen die decorator.
- **`%` in een QWeb-uitdrukking.** `t-out="'%.0f %%' % x"` gaf "incomplete format"; gebruik `str(round(x)) + ' %'`.
- **Niet-opgeslagen signalen en de cache.** Een zoekmethode die het berekende veld leest, kreeg in dezelfde transactie een oude waarde na een wijziging aan het budget. `_search_signal` rekent de signalen daarom opnieuw uit.

## Binaire velden lezen met `bin_size` (stap 24)

De webclient leest records met `bin_size=True` in de context. Een binair veld (ook `ir.attachment.raw` en `datas`) geeft dan de grootte als tekst ("33.21 Kb") in plaats van de inhoud. Een compute die een hash van een bijlage maakt, gaf daardoor in het formulier een andere SHA-256 dan in het portaal, en de handtekeningen leken ongeldig. Lees bestanden voor een berekening altijd met `with_context(bin_size=False)` (zie `attachment_sha256` in `models/vme_assembly_online.py`). De test `test_hash_ignores_bin_size` vangt dit op.

## Een tweede AV in hetzelfde jaar (stap 24)

Sinds er buitengewone AV's zijn, kan een VME meer dan één AV per jaar hebben. Code of tests die "de AV van VME X in jaar Y" zoeken, filteren op `assembly_type = 'ordinary'`, anders krijgen ze twee records (`ensure_one` faalt, of een vergelijking op een recordset van twee).

## Btw op aankopen en de verdeelregels van een belasting (stap 26)

- **Btw kwam op 411000 terecht.** Het Belgische rekeningstelsel boekt aankoopbtw als terug te vorderen; voor een VME is ze een kost. Een btw-verdeelregel zonder rekening laat Odoo de btw op de rekening van de factuurregel boeken. Belastingen met een negatieve verdeelregel (verlegging) slaan we over, anders komen +21% en −21% op dezelfde kostenrekening.
- **Facturen van vóór de migratie** houden hun btw op 411000. Op een bestaande database staat die dan als "diverse vorderingen" op de balans; een verse demo heeft dat niet.
- **`_read_group` met `move_id` in de groepering** geeft één groep per boeking. Voor 200 VME's per rapport is dat snel genoeg (één VME per keer); voor een rapport over alle VME's samen zou je per rekening en dagboek groeperen en de fondsen apart opzoeken.

## Record rules: OR tussen groepen, AND met globale regels (review toegangsrechten)

- Regels van verschillende groepen waarin een gebruiker zit, worden met OR gecombineerd. Een regel "alleen eigen companies" voor `base.group_user` zou de commissaris (ook een interne gebruiker) weer laten schrijven, ondanks zijn regel `[(0, '=', 1)]`. Afscherming voor iedereen hoort daarom in een globale regel (zonder groep), die met AND geldt.
- `company_ids` in een regel zijn de companies die in de bedrijvenkiezer geselecteerd zijn; `user.company_ids.ids` zijn alle toegestane. Onze VME-regels gebruiken de tweede, anders verdwijnen VME's uit de lijsten zodra een medewerker één company selecteert.
- Een test die als superuser (`cls.env.user`) een company aanmaakt en daarna als `base.user_admin` leest, moet admin die company ook geven (zie `vme_rentmeester/tests/test_settlement.py`).
- `vme.request` zonder kavel faalt bij het opslaan: `owner_id = request.lot_id and ...` geeft een lege `vme.lot`-recordset aan een veld op `res.partner`. Nog open.

## Vertaling: rapporten in de taal van de ontvanger

- **Een `t-lang` op `web.external_layout` vertaalt de inhoud niet.** De body van een `t-call` hoort bij het aanroepende template en wordt in de taal van dat template vertaald. De inhoud moet in een eigen `_document`-template dat met `t-lang` aangeroepen wordt; zie [vertaling.md](vertaling.md#rapporten-qweb).
- **`--i18n-overwrite`.** Zonder die optie laat `-u` bestaande vertalingen in de database staan; een verbeterde vertaling in `fr.po` komt er dan niet door.
- **`odoo i18n export` via `docker compose run`** faalt met "unrecognized arguments: --db_host": het entrypoint plakt de databaseverbinding achter elk commando. Gebruik een configbestand (`-c`), zie [vertaling.md](vertaling.md#nieuwe-termen-bijwerken).
- **Tekst in een datumformaat of zinnen in stukken** (`'\'om\' HH:mm'`, "op de `<t t-if>`buitengewone`</t>` algemene vergadering") zijn niet te vertalen. Volledige zinnen per tak.

## Afsluiting van het boekjaar

- **De vergrendeldatum weigert niets.** In Odoo 19 weigert `fiscalyear_lock_date` een nieuwe boeking in het afgesloten jaar niet. `_post` verschuift de boekingsdatum naar de eerste open periode. Daarom telt de jaarafrekening een factuur nu ook op de boekingsdatum (zie [boekjaarafsluiting.md](boekjaarafsluiting.md)). Een test op "boeken faalt" moet controleren dat de datum verschoven is.
- **Documenten van een ander bedrijf zijn onzichtbaar, ook in een One2many.** Zonder `sudo()` telde het dossier 0 afrekeningsdocumenten als bovenaan een ander bedrijf stond. "Opnieuw voorbereiden" had dan alles dubbel geboekt.
- **Rekeningcodes hangen van het bedrijf af.** `account.code` is `False` buiten het bedrijf van de rekening. In tests lees je de code daarom `with_company`.

## Demorepetitie (november 2026)

Gevonden bij het doorlopen van `docs/demo.md` op een verse database:

- **Eigenaarsportaal zonder tegels.** `/my/counters` geeft alles terug wat `_prepare_home_portal_values` invult. Odoo's script zet voor elke sleutel een teller op de pagina en stopt met een fout bij een sleutel zonder teller (`vme_owner`): de tegel "Mijn mede-eigendom" verscheen nooit en het laadicoon bleef draaien. Zet een sleutel die geen teller is alleen bij het opbouwen van `/my` (`counters` leeg); test in `test_portal.py`.
- **Dialoog "Configureer de lay-out van je document" bij de eerste PDF.** Odoo opent die wizard in plaats van het rapport zolang de company geen `external_report_layout_id` heeft, en elke VME is een company. "Negeren" sluit hem zonder PDF. Elke company krijgt nu de standaardlay-out (`models/res_company.py`, ook bij elke upgrade via `data/bill_aliases.xml`).
- **"My Company, Verenigde Staten" bovenaan de PDF van een factuur per mail.** Bij een UBL zonder PDF maakt Odoo zelf een PDF, met de company uit de omgeving. Die omgeving is die van de mailgebruiker, en Odoo bindt de decoder al bij het groeperen van de bijlagen. `account.move._extend_with_attachments` schakelt naar de company van de factuur en gooit `decoder_info` weg, zodat Odoo hem opnieuw opzoekt. Niet te testen in een unittest: in testmodus maakt Odoo geen PDF.
- **Taak "Keuring plannen" bleef staan na de keuring.** De cron maakte een taak per vervaldatum, maar niets vinkte ze af. Een nieuw keuringsverslag dat de vervaldatum voorbij die taak schuift, sluit ze nu af (`vme.inspection.create`).
- **`options="{'format': false}"` doet niets meer in Odoo 19:** het jaartal toonde als "1.995". De optie heet `enable_formatting`.
- **`t-options="{'tz': ...}"` wordt genegeerd.** Odoo's datetime-veld in QWeb kent alleen `tz_name`. In het portaal (zonder tijdzone in de context) toonde een AV van 19:00 als 18:00; in de oproeping hing het uur af van de tijdzone van wie afdrukte. Alle templates gebruiken nu `tz_name`.
- **Parallelle testservers op `localhost` loggen elkaar uit.** Een cookie geldt voor de hostnaam, niet voor de poort. Gebruik per server een eigen naam, bv. `http://demo.localhost:8679`.

## Bekende problemen (nog open)

- **De `.pot` van `vme_belgie` loopt achter.** Een export na de merges van november 2026 voegt ruim 2.000 regels toe (offertes, overname, verzekering, werkbak); die termen staan dus ook niet in `fr.po`. Bijwerken volgens [vertaling.md](vertaling.md#nieuwe-termen-bijwerken), samen met de nieuwe teksten van de demorepetitie.

## Parallel gebouwde stappen samenvoegen

Stappen die tegelijk op aparte branches gebouwd worden, botsen soms zonder dat git een conflict meldt:

- **Twee keer dezelfde methode in één module.** Stap 19 en 23 definieerden allebei `vme.lot._get_tenants_on`; de klasse die later in `models/__init__.py` staat wint, en dat was een lege haak. Nu bestaat de methode alleen in `vme_lot_contact.py` (huurders per kavel), en `vme_rentmeester` voegt de huurders van lopende huurcontracten toe met `super()`.
- **Twee keer dezelfde veldnaam op een model.** Stap 16 en 20 voegden allebei `mandate_ids` toe aan `vme.association` (mandaten van de raad en SEPA-mandaten); de laatste definitie overschreef de eerste en de view faalde. De SEPA-mandaten heten nu `sepa_mandate_ids`.
- **Iedereen toegang geven tot een nieuwe company.** De demo van `vme_rentmeester` gaf alle interne gebruikers toegang tot het rentmeesterkantoor, ook de commissaris van de rekeningen, die alleen zijn eigen VME mag zien. Sla gebruikers uit `group_vme_auditor` over.

Na het samenvoegen van meerdere branches: altijd de volledige testsuite van beide modules draaien, niet alleen die van de eigen stap.
