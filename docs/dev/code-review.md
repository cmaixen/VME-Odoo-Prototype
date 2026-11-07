# Code review van main (november 2026)

Review van `addons/vme_belgie`, `addons/vme_rentmeester`, `addons/vme_website`, `ai/` en `tools/` op main @ 3d13d40, tegen de best practices van Odoo 19 en Python en tegen de harde regels uit `CLAUDE.md`. Elke bevinding is nagekeken in de code; regelnummers gelden voor 3d13d40.

**Ernst.** *Kritiek*: verkeerd bedrag, crash in een demopad, gegevenslek of verboden gedrag. *Belangrijk*: reëel risico of een duidelijke afwijking van de best practices met gevolgen. *Klein*: onderhoudbaarheid of cosmetisch.

**Status.** ✅ hersteld op deze branch (met test), ⏳ voorstel, niet uitgevoerd.

## Samenvatting

- **Harde regels: in orde.**
  - **Niets vertrekt vanzelf.** Er is geen `force_send`, `send_mail(`, `auto_send` of instelling in `addons/` of `ai/`, en de oude haak `_auto_send_order` is weg. Berichten die crons posten, zijn interne notities; de providers voor sms, push en aangetekende post zijn mocks.
  - **`# LEGAL-CHECK:`** staat bij elke wettelijke regel die we vonden, met één ontbrekende (K-D11). `tools/legal_checks.py --check` is groen.
  - **Fictieve data.** Alleen adressen op `example.com`, IBAN's met bankcode 999 en btw-nummers `BE00000…`.
  - **Geen Enterprise-code.**
- **Veiligheid: geen lek gevonden.**
  - Elke portaalroute vertrekt van de ingelogde partner en geeft 404 voor de rest.
  - Geen enkele route heeft `csrf=False`.
  - Geen `t-raw` of `|safe`; elke `Markup` escapet zijn argumenten.
  - De AI-uitvoer wordt volledig ge-escapet, en `ai/.env` staat in `.gitignore`.
  - Wel een paar zwakke plekken in de **verificatie** (huurder of vervalste afzender als eigenaar) en in de **schrijfrechten** (handtekeningen, consumptieprijsindex).
- **Rekenlogica: goed getest.** Er waren twee fouten met geldgevolgen: een tegengeboekte provisie telde als betaald, en de 5%-basis was te breed. Beide zijn hersteld, net als de controles bij SEPA en de bankimport (tweede ronde).
- **Performance bij 200 VME's.** De portefeuille is al geoptimaliseerd (`docs/dev/schaal.md`). Ernaast staan nog lijsten met N+1-queries: invorderingsdossiers, leverancierskaart en werken, en de invorderingscron. Geen enkele cron behalve de provisieoproepen gebruikt `_commit_progress`.
- **Odoo-idioom.**
  - Nergens `check_company=True` of `_check_company_auto`.
  - Crons maken taken voor OdooBot.
  - Activiteiten worden teruggevonden op hun vertaalde samenvatting.
  - Een handvol teksten zit buiten `env._()`.
- **Tests**: 506 tests, allemaal groen vóór de review. Ze gebruiken `freeze_time` of vaste datums en hangen niet af van voorgeladen demodata.

## Hersteld op deze branch

Elke fix staat in een eigen commit, met een test waar dat kan.

| # | Wat | Bestanden |
| --- | --- | --- |
| K-F1 | Een tegengeboekte provisie (creditnota, `payment_state = reversed`) telt niet meer als betaald in de jaarafrekening | `models/vme_annual_statement.py`, test `test_reversed_call_is_not_paid` |
| K-D1 | Een aanvraag zonder kavel crashte bij opslaan (`owner_id = vme.lot()`) | `models/vme_request.py`, test `test_request_without_lot` |
| B-D1 | Eenparigheid werd verworpen als één eigenaar meer dan de helft heeft (de beperking van art. 3.87 §6 werd ook op eenparigheid toegepast) | `models/vme_assembly_meeting.py`, test `test_unanimity_with_a_majority_owner` |
| B-F1 | Een sleutel zonder kavels liet het boeken crashen met een `ValueError`, ondanks "blokkeer het boeken nooit" | `models/account_move.py`, `wizard/vme_provision_call_wizard.py`, test `test_key_without_lots_does_not_block_posting` |
| B-F6 | De SQL-views `vme.arrears` en `vme.budget.analysis` kregen `_depends`, zodat het ORM openstaande wijzigingen eerst wegschrijft | `models/vme_collection.py`, `models/vme_budget_tracking.py` |
| B-R1 | Een bevestigde doorstorting kan niet meer verwijderd worden (anders betaalt de volgende doorstorting dezelfde huur opnieuw uit) | `vme_rentmeester/models/rent_remittance.py`, test in `test_remittance.py` |
| B-S3 | Vroegere eigenaars zien de actuele kapitalen en het budget van het gebouw niet meer in het portaal | `views/vme_building_card_templates.xml`, test in `test_portal.py` |
| B-S5 | De consumptieprijsindex (gedeeld door alle VME's, bepaalt het ereloon) is alleen nog door de beheerder te wijzigen, zoals `vme.rent.index` | `security/ir.model.access.csv` |
| K-D15 | `_search_is_overdue` keerde het domein om voor `is_overdue = False` (Odoo 19 geeft `in [False]` door) | `models/vme_installation.py`, test in `test_installations.py` |
| K-D3 | `check_not_auditor` toegevoegd aan twee knoppen die als sudo schrijven (`action_register_delivery`, communicatie `action_confirm`) | `models/vme_request.py`, `models/vme_communication.py` |
| B-R6 | De afrekening aan huurders las alle rubrieken opnieuw voor elke kostenverdeling | `vme_rentmeester/models/rent_charge_category.py`, `rent_settlement.py` |
| K-R9 | De footer van de website toonde letterlijk `&copy;` | `vme_website/views/layout_templates.xml` |

**Tweede ronde** (op vraag van de hoofdsessie, na de merge van de eerste):

| # | Wat | Bestanden |
| --- | --- | --- |
| B-S1 | De rol van een aanvrager komt uit de partner, niet uit een e-mailadres dat de huurder zelf kiest | `models/vme_request.py`, test `test_tenant_with_owner_email_stays_tenant` |
| B-S2 | Handtekeningen en online of schriftelijke stemmen kunnen alleen uit het portaal komen, niet via RPC | `models/vme_assembly_online.py`, tests in `test_assembly_online.py` |
| K-F1 | Een gedeeltelijke creditnota op een provisie telt niet als betaald | `models/vme_annual_statement.py`, test `test_partial_credit_note_is_not_paid` |
| B-F4 | De 5%-basis telt werken uit het reservekapitaal en privékosten niet meer mee | `models/vme_budget.py`, test `test_reserve_minimum_counts_only_ordinary_charges` |
| B-F2 | Een bankbestand wordt herkend aan een sleutel, niet aan de vertaalde naam van het afschrift | `models/account_bank_statement_line.py`, `wizard/vme_bank_import_wizard.py` |
| B-F3 | SEPA-bestanden weigeren een bedrag dat niet meer openstaat | `models/vme_payment.py`, tests in `test_payments.py` |
| B-F5, B-D5, B-D7 | Invordering, leverancierskaart en werken: geen queries meer per rij | `vme_collection.py`, `res_partner_supplier_card.py`, `vme_works.py` |
| B-F7 | `check_company` op rekeningen, sleutels en werkdossiers; constraint op de bankrekeningen van VME en mandaat | `test_check_company.py` |
| K-P1 | `partner_autocomplete` stuurt niets meer naar Odoo of VIES | `models/partner_autocomplete.py` |
| K-D7 | Oproepingen: één pdf-run per rapport in plaats van twee per eigenaar | `models/vme_assembly_meeting.py` |

## Kritiek

### K-F1. Jaarafrekening telt een tegengeboekte provisie als betaald ✅
- **Waar:** `addons/vme_belgie/models/vme_annual_statement.py:42-46` en `:96-105`
- **Probleem:**
  - Betaald wordt berekend als "gefactureerd min openstaand".
  - Een provisie die met een creditnota geannuleerd is, blijft `posted`, met `payment_state = 'reversed'` en 0 openstaand.
  - De creditnota heeft geen `vme_provision_call_id`.
- **Risico:** het saldo van de eigenaar daalt met een provisie die hij nooit betaald heeft. Het portaal toont hetzelfde.
- **Herstel:**
  - Uitgevoerd: volledig tegengeboekte facturen tellen niet meer mee.
  - Uitgevoerd (tweede ronde): een gedeeltelijke creditnota verlaagt nu het gefactureerde bedrag, niet het betaalde. Het deel dat met een `out_refund` afgepunt is (`matched_credit_ids`), gaat af van "gefactureerd". Test: `test_partial_credit_note_is_not_paid`.

### K-D1. Aanvraag zonder kavel crasht bij opslaan ✅
- **Waar:** `addons/vme_belgie/models/vme_request.py:215`
- **Probleem:** `request.lot_id and ...` gaf het lege recordset `vme.lot()` aan een Many2one naar `res.partner`, wat een `ValueError` geeft.
- **Risico:** elke manuele aanvraag zonder kavel crashte, en ook elke AI-intake van een onbekend adres.
- **Herstel:** `... if request.lot_id else False`, plus een test.

## Belangrijk

### Veiligheid

**B-S1. Een huurder kan zich in het portaal als eigenaar voordoen** ✅
- **Waar:** `models/vme_portal_requests.py:85-90`; `models/vme_request.py:279-292`, `:320-322`, `:412-413`
- **Probleem:**
  - De rol (eigenaar, huurder of onbekend) volgt uit een vergelijking van `partner.email` met het e-mailadres van de eigenaar, niet uit de ingelogde partner.
  - Een huurder die zijn e-mailadres in /my/account verandert in dat van de eigenaar, krijgt een sleutelaanvraag die meteen als "geverifieerd" staat, en de bestelling bij de slotenmaker staat klaar.
- **Herstel (uitgevoerd):** de rol komt nu uit de partner zelf (`_identify_partner_in`, met `_get_owner_on()` en `_get_tenants_on()`), ook in `create_from_intake` als het portaal `requester_id` meegeeft. Test: `test_tenant_with_owner_email_stays_tenant`. De mail-intake herkent een onbekende afzender nog altijd aan het adres; zie B-S4.

**B-S2. Medewerkers kunnen een elektronische handtekening of een online stem vervalsen** ✅
- **Waar:**
  - `security/ir.model.access.csv`: `vme.assembly.signature` en `vme.assembly.vote` staan op 1111 voor `base.group_user`;
  - `models/vme_assembly_online.py:351-354` en `:387-390`.
- **Probleem:** via RPC kan een medewerker een handtekening op `signed` zetten met een willekeurige naam en IP-adres, of een stem aanmaken met `source="online"`. Het auditspoor van de digitale AV is dan geen bewijs meer.
- **Herstel (uitgevoerd):** `create` en `write` weigeren zonder superuser de auditvelden van de handtekening en een stem met bron online of schriftelijk. `_portal_sign` en `_portal_cast_votes` schrijven als superuser. Geen contextvlag, want die kan een RPC-aanroep zelf meegeven. Tests: `test_staff_cannot_forge_an_online_vote`, `test_staff_cannot_sign_for_an_owner`.

**B-S4. Bij de mail-intake wordt de eigenaar alleen herkend aan het afzenderadres** ✅
- **Waar:** `models/vme_request.py:279-292`, `:412-413`
- **Probleem:** een vervalste `From:` geeft een sleutelaanvraag die meteen geverifieerd is.
- **Herstel (uitgevoerd):** een sleutel- of badgeaanvraag van een eigenaar via `channel == "mail"` wacht op het bewijs "Eigenaar bevestigde de aanvraag" (`proof_sender_confirmed`, `_owner_by_mail()`), met de gewone bewijsvraag en taak. De bewijsvraag gaat naar het gekende adres, dus naar de echte eigenaar. Portaal en manueel blijven meteen geverifieerd. Later kan het SPF/DKIM-resultaat van de mailgateway meetellen. Test: `test_owner_by_mail_confirms_first`.

### Geld en boekhouding

**B-F2. Hetzelfde bankbestand kan twee keer ingelezen worden** ✅
- **Waar:** `wizard/vme_bank_import_wizard.py:45-49`
- **Probleem:** dubbels worden herkend aan de naam van het afschrift, en die naam is vertaald ("van" wordt "du" in `fr.po`). Een Franstalige medewerker leest zo een tweede afschrift in, en de lijnen worden opnieuw afgepunt.
- **Herstel (uitgevoerd):** een nieuw veld `vme_import_key` (formaat, nummer en datum) op `account.bank.statement`. Dubbels worden herkend aan dagboek en sleutel, of aan de oude naam voor afschriften van vóór het veld. Test: uitbreiding van `test_import_routes_each_account_to_its_fund_journal`.

**B-F3. SEPA-bestanden controleren niet opnieuw of de factuur nog openstaat voor hetzelfde bedrag** ✅
- **Waar:** `models/vme_payment.py:502-531` (domiciliëring) en `:476-486` (overschrijving)
- **Probleem:** een eigenaar die tussen het voorstel en het bestand per overschrijving betaalt, wordt toch voor het volle bedrag geïnd.
- **Herstel (uitgevoerd):** `vme.payment.batch.line._check_still_open` weigert in beide bestanden een bedrag boven het huidige `amount_residual`. Tests: `test_file_refused_when_paid_since_the_proposal`, `test_transfer_refused_when_paid_since_the_proposal`.

**B-F4. De basis voor de minimale reserve van 5% telt ook lasten mee die niet gewoon zijn** ✅
- **Waar:** `models/vme_budget.py:86-92`
- **Probleem:** de basis bevat werken die uit het reservekapitaal betaald zijn (`vme_reserve_move_id`) en privékosten van aanvragen (`vme_request_id`). Een jaar met grote werken verhoogt zo het wettelijke minimum van het jaar erna, en blokkeert de cyclusstap "budget".
- **Herstel (uitgevoerd):** het domein van `_get_previous_year_charges_by_budget` sluit `vme_reserve_move_id` en `vme_request_id` uit, met `# LEGAL-CHECK: art. 3.86 §3 BW`. `docs/dev/rekenregels.md` en `legal-checks.md` zijn bijgewerkt. Test: `test_reserve_minimum_counts_only_ordinary_charges`. Het minimum daalt in een jaar na grote werken; dat is de bedoeling.

**B-F7. Nergens `check_company`** ✅ (deels)
- **Voorbeelden:**
  - `vme_distribution_rule.py:22` (`account_id`);
  - `vme_budget_tracking.py:54-61`;
  - `vme_payment.py:235` (bankrekening van het mandaat);
  - `vme_association.py:35-44`;
  - `vme_works.py:415`, `vme_damage.py:339`;
  - de koppelingen in rentmeester.
- **Probleem:** alleen de domeinen in de views beschermen. Een import, RPC (het AI-script) of code met sudo kan een record uit de company van een andere VME koppelen.
- **Herstel:**
  - Uitgevoerd: `_check_company_auto` en `check_company=True` op de rekening van de verdeelregel, rekening en sleutel van een budgetregel, en `vme_works_id` en `vme_reserve_move_id` op facturen. Bankrekeningen hebben geen eigen company, dus daar zou `check_company` alles doorlaten. Een constraint eist nu dat de rekeningen van de VME van haar eigen partner zijn, en dat de rekening van een SEPA-mandaat van de eigenaar is. Tests: `test_check_company.py`.
  - Uitgevoerd in rentmeester: `_check_company_auto` op contract, mandaat en doorstorting, `check_company` op mandaat, analytische rekening, btw van het ereloon, de stukken van de doorstorting en de koppelingen op `account.move`; constraints op de rekening van de verhuurder (mandaat, doorstorting) en op de derdenrekening van het kantoor. De analytische rekening van een verhuurder kwam in de company waarin de gebruiker toevallig werkte; nu in die van het contract. Tests: `vme_rentmeester/tests/test_check_company_rent.py`.
  - Nog open ⏳: `vme_damage.py` en de andere Many2one's naar records met een company (installaties, contracten).

**B-R3. Waalse indexstop voor EPB-label D staat op 50%** ⏳ (juridisch na te kijken)
- **Waar:** `vme_rentmeester/models/rent_rules.py:57-64`
- **Probleem:** volgens het Waalse decreet van 19 oktober 2022 zou het 75% zijn voor D.

**B-R4. Retroactieve indexering begint midden in de maand** ⏳ (juridisch na te kijken)
- **Waar:** `vme_rentmeester/models/rent_rules.py:180-183`
- **Probleem:** "de drie maanden voorafgaand aan de maand van het verzoek" begint op de 1e. Nu is het de aanvraagdatum min drie maanden.

**B-R5. Bij een doorstorting telt "ontvangen" de betalingen van vandaag, niet die tot het einde van de maand** ⏳
- **Waar:** `vme_rentmeester/models/rent_remittance.py:136-156`
- **Probleem:** er gaat geen geld verloren, maar de periode klopt niet.

**B-R7. Een indexering bevestigen verwijdert conceptfacturen als superuser** ⏳
- **Waar:** `vme_rentmeester/models/rent_indexation.py:91-104`
- **Probleem:** manuele wijzigingen op die concepten gaan stil verloren, en de sudo staat er zonder commentaar.

### Wettelijke logica

**B-D2. Een oproeping geldt als "op tijd" zodra de eerste verstuurd is** ✅
- **Waar:** `models/vme_assembly_meeting.py:520-524`
- **Probleem:** `convocation_sent_date` wordt gezet bij de eerste oproeping die vertrekt. Komen de andere te laat, dan verschijnt er geen waarschuwing. `# LEGAL-CHECK: art. 3.87 §3 BW` (15 dagen, voor elke eigenaar).
- **Herstel (uitgevoerd):** `vme.assembly._get_warning` kijkt nu ook naar elke oproeping: een oproeping die na de uiterste dag vertrok, of een concept na die dag, geeft "Te laat" met de namen van de eigenaars. `convocation_sent_date` blijft de eerste verzending. Test: `test_every_convocation_must_leave_on_time`.

**B-D3. Oproepingen gaan zonder schriftelijk akkoord per e-mail of gewone brief** ✅
- **Waar:**
  - `models/vme_communication.py:53-56` (standaard "email"), `:643`, `:651`;
  - de composer in `vme_assembly_meeting.py:468`.
- **Probleem:** art. 3.87 §3 BW vraagt een aangetekende brief, tenzij de eigenaar schriftelijk met een ander middel instemde. Die regel wordt alleen bij verzendingen toegepast, niet bij oproepingen.
- **Herstel:**
  - een veld voor het akkoord, met de datum;
  - zonder akkoord gaat de oproeping via `vme.registered.mail`;
  - tests en documentatie.
- **Uitgevoerd:** `res.partner.vme_convocation_consent_date` en `vme.assembly.convocation.channel`. Zonder akkoord weigert **Versturen** en zet **Aangetekend versturen** de oproeping in het verzendregister; de knop **Per post verstuurd** is weg. Een aangetekende oproeping telt pas als vertrokken bij de afgifte bij de post (`_left_on`). In de demo hebben de eigenaars met e-mail een akkoord, die op papier niet. Test: `test_convocation_without_consent_goes_registered`. Nog na te kijken: of het akkoord per VME moet gelden in plaats van per persoon.

### Performance bij 200 VME's

| # | Waar | Probleem | Herstel |
| --- | --- | --- | --- |
| B-F5 / B-D6 ✅ (deels) | `models/vme_collection.py:296-336`, `:388-399`, `:535-569` | Invorderingsdossiers: ongeveer 3 searches per dossier in de lijst. De nachtelijke cron zoekt per dossier, maakt nieuwe dossiers één per één aan en gebruikt geen `_commit_progress`. | Uitgevoerd: `_open_lines_by_collection()` (één search voor de lijst en de cron), kavels in één search, batch-create; test `test_list_does_not_query_per_dossier`. De cron blijft één transactie: hij werkt nu in batch (zie K-D18) |
| B-D5 ✅ | `models/res_partner_supplier_card.py:96-137` | Leverancierslijst: 4 searches per rij, en alle facturen van de leverancier worden geladen om een saldo op te tellen | Uitgevoerd: één search per model en één `_read_group` voor de hele lijst; test `test_supplier_list_does_not_query_per_supplier` |
| B-D7 ✅ | `models/vme_works.py:58-70`, `:200-216` | Werkenlijst: per rij een search plus een optelling in Python over alle lijnen van het reservekapitaal | Uitgevoerd: saldo en vastgelegde werken één keer per VME, `_get_fund_balance` met `_read_group`; test `test_reserve_in_the_list_does_not_query_per_works` |
| B-F8 | `wizard/vme_provision_call_wizard.py:37-61` | Voorbeeld in de provisiewizard: ongeveer 400 queries per wijziging bij 200 VME's | Eén `vme.budget`-search en de waarschuwing voor de hele recordset |
| K-D18 ✅ | crons `ir_cron_vme_cycle`, `ir_cron_vme_contract_activities`, `ir_cron_vme_inspection_activities` | Geen `_commit_progress`. De cycluscron maakt oproepingen met pdf's voor alle VME's in één transactie, dus één fout rolt alles terug. | Uitgevoerd: `cron_tools.run_per_record()` met een savepoint en `_commit_progress` per VME of record; een mislukte VME wordt gelogd en overgeslagen. Elke cron zoekt alleen wat vandaag nog te doen is (nieuw veld `cycle_sync_date`), zodat Odoo hem na een time-out verder laat lopen. Test `test_cron_commits_per_vme_and_skips_a_failing_one`. De invorderingscron werkt in batch en blijft één transactie |
| K-D7 ✅ | `models/vme_assembly_meeting.py:439-466` | Twee pdf's per eigenaar, één voor één gerenderd | Uitgevoerd: één wkhtmltopdf-run voor alle oproepingen en één voor alle jaarafrekeningen (`_render_pdf_per_record`), met terugval per record; de overbodige afrekening per eigenaar ter controle is weg. Test `test_convocation_pdfs_in_one_run`. Nog niet gemeten op de schaaldatabase |

### Odoo-idioom

**B-D4 / B-R2. Crons maken taken voor OdooBot** ✅
- **Waar:**
  - `models/vme_syndic.py:876` en `:881`;
  - `vme_rentmeester/models/rent_contract.py:417` en `:434`;
  - terugval naar `self.env.user` in `vme_contract.py:306` en `:322` en `vme_installation.py:201` en `:210`.
- **Probleem:** de crons draaien als superuser, dus de taken landen bij OdooBot en geen medewerker ziet ze.
- **Herstel:** wijs ze toe aan de verantwoordelijke van de VME (`_cycle_default_user()` bestaat al), of aan een veld op het contract of mandaat.
- **Uitgevoerd:** mandaten, contracten en installaties gingen al naar de dossierbeheerder (`_vme_task_user()`, sessie werkbak). Nu ook de polissen (`user_id` van de polis, dan dossierbeheerder), de attesten (dossierbeheerder) en de rentmeester: een nieuw veld **Beheerder** op het huurcontract, met `_rent_task_user()` als terugval naar de dossierbeheerder van de VME of admin. Tests: `test_cron_tasks_go_to_the_case_manager`, `test_notice_task_goes_to_the_manager`.

**B-D8. AI-documenten komen nooit in een map terecht** ⏳
- **Waar:** `models/vme_document_intake.py:15-24` en `:71-78`
- **Probleem:** `_vme_document_folder` geeft altijd `False`. Niets overschrijft de methode, en de mapcodes in `DOCUMENT_TYPES` komen met niets overeen.
- **Herstel:** koppel de codes aan de xml-id's van de mappen en maak een `vme.document` aan met `portal_visible=False`.

**B-D9. Een schadeaanvraag wordt nooit een schadedossier** ⏳
- **Waar:** `models/vme_request.py:738-752`
- **Probleem:** de code test op `vme.damage.claim._create_from_request`, maar die methode bestaat niet; die tak is dode code.
- **Herstel:** de methode bouwen, of de tak schrappen.

### Proces

**B-R8. Parallelle branches verhoogden `vme_belgie` naar dezelfde versie** ⏳
- **Waar:** vijf commits (504926b, 7ec481c, 41edbf5, d7517e5, 0d256a2) gingen elk van 1.11.0 naar 1.12.0.
- **Probleem:** een database die op een andere branch geüpgraded werd, slaat `migrations/19.0.1.12.0` (btw als kost) en `19.0.1.11.0` (beperking op één AV per jaar) over.
- **Herstel:**
  - Draai beide scripts (ze kunnen veilig opnieuw) één keer op langlevende databases, of maak `vme_demo` opnieuw aan.
  - Spreek af dat alleen de merge-commit de versie verhoogt.

### Privacy

**K-P1. `partner_autocomplete` stuurt partnergegevens naar Odoo** ✅
- **Probleem:** de module installeert zichzelf en stuurt getypte namen, btw-nummers (ook naar VIES) en het maildomein van elke nieuwe company naar buiten. Elke VME is een company.
- **Herstel (uitgevoerd):** `models/partner_autocomplete.py` blokkeert de oproepen; `vme_belgie` hangt van de module af, zodat de overrides na haar komen. Test: `test_partner_autocomplete.py`.

## Klein

| # | Waar | Probleem | Voorstel |
| --- | --- | --- | --- |
| K-F-a | `wizard/vme_provision_call_wizard.py:173` | Elke oproep wordt apart afgerond: 10 000 over 3 oproepen laat per fonds en per jaar 1 cent liggen | Het restbedrag op de laatste oproep zetten |
| K-F-b | `models/vme_provision_call.py:31-35` | De totalen tellen geannuleerde facturen mee | Filteren op `state != 'cancel'` |
| K-F-c | `models/account_move.py:326-338` | Bij meerdere UBL-bestanden krijgt elke boeking de periode van het laatste bestand | Bestand en boeking aan elkaar koppelen |
| K-F-d | `models/account_move.py:67-73` | Wie de factuurdatum van een concept corrigeert, houdt de oude kostperiode | Ook bijwerken als de periode nog de oude datum volgt |
| K-F-e | `models/account_bank_statement_line.py:271-273` | Leveranciersbetalingen worden gekoppeld op een deel van de referentie ("12" past op veel mededelingen) | Woordgrens of minimale lengte |
| K-F-f | `models/vme_financial_statements.py:172`, `vme_budget_tracking.py:124` | Vergelijking met en SQL-literal van het onvertaalde "Niet ingedeeld" | Op de code vergelijken, het label in Python vertalen |
| K-F-g | `vme_payment.py:48-58`, `vme_collection.py:366,783`, `vme_syndic.py:522`, `bank_formats.py`, `sepa_xml.py`, `rent_remittance.py:178`, `rent_contract.py:169`, `vme_meter_import_wizard.py:227` | Gebruikersteksten buiten `env._()` (`dict(SELECTION)`, `f"€ ..."`, foutmeldingen) | `_lt`/`env._`, `_description_selection(env)`, `format_amount` |
| K-F-h | `vme_budget.py:21`, `vme_assembly.py:218`, de jaarwizards | `fields.Date.today()` in standaardwaarden in plaats van `context_today` | `fields.Date.context_today(self)` |
| K-F-i | `models/bank_formats.py:274` | Een opgeladen XML-bestand wordt ingelezen met de standaard `ElementTree` | lxml met `resolve_entities=False`, `no_network=True` |
| K-F-j | `models/vme_payment.py:263-265` | De referentie van een mandaat is `search_count + 1`; na een verwijdering botst ze met de UNIQUE-beperking | `ir.sequence` |
| K-F-k | `models/vme_syndic.py:182-188`, `account_move_ai.py:213-217` | `search_count` per overeenkomst; alle companies laden om op btw-nummer te zoeken | `_read_group`; zoeken met `ilike` |
| K-F-l | `models/vme_key.py:137-149` | Een losse `vme.key.line` aanmaken (import, RPC) controleert het totaal van de sleutel niet | Dezelfde controle in `create` |
| K-D2 | `models/vme_request.py:212` | `owner_id` hangt niet af van de eigendommen van de kavel | `lot_id.ownership_ids.*` toevoegen aan de depends |
| K-D4 | `models/vme_request.py:676-678` | `action_cancel` kan ook een afgewerkte aanvraag met factuur annuleren | Weigeren voor `CLOSED_STATES` |
| K-D5 | `vme_contract.py:263-270`, `vme_works.py:311`, `vme_sale_file.py:340`, `vme_syndic.py:872,879` | Activiteiten worden teruggevonden op hun vertaalde samenvatting; met fr_BE dubbel of niet afgesloten | Id van de activiteit bewaren, of filteren op deadline en `res_id` |
| K-D6 | `models/vme_assembly_meeting.py:473-496` | HTML van de oproepingsmail gebouwd in een vertaalbare tekst met namen en links die niet ge-escapet zijn | `Markup(...) % {...}`, HTML buiten `_()` |
| K-D8 | `models/vme_assembly_meeting.py:54-59` | De tweede zitting moet minstens 15 dagen later (art. 3.87 §5), maar niets controleert dat | Waarschuwing in `_get_warning` |
| K-D9 | `models/vme_building_card.py:416-440` | Defensieve controles op modellen uit dezelfde module, en de onbestaande state `closed` | Schrappen |
| K-D10 | `models/vme_council.py:392-436` | Statusteksten hard in het Nederlands in de SQL | Codes in SQL, labels via `Selection` |
| K-D11 | `models/vme_sale_file.py:366-397` | `action_deed_done` heeft geen controle op de status, en de overdrachtsdatum (pro rata) mist `# LEGAL-CHECK: art. 3.94 BW` | Statuscontrole, LEGAL-CHECK toevoegen, `tools/legal_checks.py` |
| K-D12 | `vme_works.py:58-70`, `vme_building_card.py:57-140`, `vme_sale_file.py:264-273`, `vme_council.py:239`, view `vme_capital_movement` | Het saldo van het reservekapitaal wordt op 4 à 5 manieren berekend | Eén `vme._get_fund_balance(fund, on_date)` |
| K-D13 | `vme_meter_import_wizard._check_file` (118 regels), `vme_sale_file._get_notary_information` (82), `_get_building_card_data` (76), `_get_capital_history` (74), `vme_migration._import` (73), `_load_demo_data` (193) | Te lange methodes | Opsplitsen in helpers per blok |
| K-S1 | `ai/assistant.py:170-177` en `connect()` in `pdf_facturen.py`, `documenten.py`, `facturen_mailgate.py` | Zonder `ai/.env` valt het script terug op admin/admin | Stoppen met een duidelijke melding; een aparte gebruiker met een API-sleutel |
| K-S2 | `models/vme_communication.py:40-47` | Het onderwerp van de mail wordt HTML-ge-escapet ("Jansen &amp; Co") | Een variant in platte tekst voor het onderwerp |
| K-S4 | `views/portal_assembly_templates.xml:58` | `video_url` wordt niet op het schema gecontroleerd (`javascript:`); alleen medewerkers vullen het in | Constraint `https://` |
| K-S5 | Odoo's /my/invoices | Toont de facturen voor invorderingskosten die de VME-pagina bewust verbergt | Beslissen, of de tegel verbergen |
| K-S6 | `models/vme_portal.py:200`, `vme_portal_requests.py:89` | Taken uit het portaal gaan hard naar `base.user_admin` | Instelling of de gebruiker van de syndicus |
| K-S7 | `models/vme_communication.py:625` | `Markup(self.env._(...))` vertrouwt een vertaling als HTML | `Markup("%s") % ...` |
| K-R1 | `rent_contract.py:317,336`, `rent_settlement.py:161-174`, `report/rent_reports.xml:104` | Huurfacturen en afrekeningen mengen de taal van de gebruiker en die van de huurder; het rapport van de doorstorting heeft geen `t-lang` | Overal `tenant_env._`, `t-lang` |
| K-R3 | `rent_indexation.py:15` | `_rec_name = "display_name"` | `_rec_names_search` |
| K-R4 | `rent_contract.py:116-121` | `_compute_property_address` kent niet altijd een waarde toe | `else`-tak |
| K-T1 | `tests/test_access_rules.py:28` | `TestAccessRules` erft van `TestCouncil`, dus de 17 tests van TestCouncil draaien twee keer | Fixture in een mixin zonder tests |
| K-T2 | `tests/test_collection.py:80` | Echte datum tegenover `CURRENT_DATE` van de view: kan rond middernacht UTC haperen | `freeze_time` |
| K-T3 | `TestBankFormats`, `TestSepaXml` | Zonder `@tagged`, dus at_install (ze draaien wel) | `@tagged("post_install", "-at_install")` |
| K-M1 | `migrations/19.0.1.10.0/post-migrate.py:26-41` | Schrapt de oude kolommen ook als er installaties overgeslagen zijn | Niet schrappen bij overgeslagen records |
| K-X1 | `vme_portal_requests.py:136` `_portal_is_open`, `vme_syndic.py:851` `action_print_posting`, `vme_lot_contact.py:86` `action_return` | Dode code (nergens aangeroepen) | Knop toevoegen of schrappen |
| K-X2 | `account_move_ai.py:53-84`, `vme_migration.py:65-98`, `vme_association.py:171`, `sepa_xml.py:78`, `tools/make_demo_bank_files.py` | Dubbele helpers: KBO-controle (3×), IBAN-controle (2×), `parse_date`/`parse_amount` (2×, verschillend; de AI-versie leest "1,234.56" als 1,23456), `fake_iban` (2×) | Eén `be_tools.py` |
| K-X3 | rentmeester: `rent_contract.py:293,306`, `rent_settlement.py:44,149`, `vme_lot.py:23`, `account_move.py:21`, `rent_remittance.py:303` | De analytische verdeling (4×) en het einde van de huur (3×) worden telkens opnieuw berekend | `contract._analytic_distribution()`, `contract._lease_end()` |

## Derde ronde: nieuw samengevoegde code

Nagekeken na de merge van boekjaarafsluiting, Belcotax, overdracht en `vme_mail_plugin`: company-regels, sudo, toegang en verzenden zonder klik.

| # | Waar | Probleem | Status |
| --- | --- | --- | --- |
| C-F1 | `models/vme_fiscal_closing.py` | Status, "afgesloten door" en de bewaarde overdracht waren via RPC te schrijven door elke medewerker (alleen readonly in het scherm); zo kon een medewerker de controles overslaan of een afgesloten jaar op concept zetten. | ✅ `create`/`write` weigeren die velden zonder superuser; de knoppen schrijven als superuser. Test `test_state_and_snapshot_only_through_the_buttons` |
| C-F2 | `vme_fiscal_closing.py`, `action_reopen` | Heropenen zette de vergrendeling op het einde van het vorige jaar of op leeg, ook als de boekhouder ze intussen verder had gezet of een oudere vergrendeling buiten dit model stond. | ✅ De vergrendeling van vóór de afsluiting wordt bewaard (`lock_date_before`) en teruggezet, alleen als niemand ze intussen verlegde. Test `test_reopen_keeps_a_lock_set_by_someone_else` |
| C-F3 | `vme_fiscal_closing.py` | `account.move.vme_fiscal_closing_id` zonder `check_company`; afsluiten en heropenen schreven als superuser zonder `check_not_auditor`. | ✅ |
| C-F4 | `models/vme_belcotax.py`, `_paid_by_partner` | De facturen werden gezocht met de companies die in de schakelaar aan stonden: met een andere VME actief kreeg een medewerker een leeg overzicht, en herberekenen wiste correcte lijnen. | ✅ Zoeken en lijnen maken in de company van de VME. Test `test_staff_with_another_company_switched_on` |
| C-F5 | `vme_belcotax.py`, `ir.model.access.csv` | Status, "nagekeken door" en "opgeladen op" waren via RPC te schrijven; lijnen bleven wijzigbaar na "Nagekeken" of "Opgeladen", een opgeladen overzicht kon verwijderd worden, en de knoppen hadden geen statuscontrole. | ✅ Auditvelden alleen via de knoppen, lijnen en verwijderen alleen in concept, statuscontrole in de knoppen. Zelfde test |
| C-D1 | `wizard/vme_handover_wizard.py` | Het overdrachtspakket leest alles als superuser na een leescontrole op de VME: een medewerker zonder boekhoudrechten krijgt saldi, achterstallen en rekeningnummers. Ontwerpvraag, geen fout. | ⏳ Voorstel: `account.group_account_invoice` eisen |
| C-X1 | `vme_mail_plugin` | Nagekeken: alles draait als de aangemelde gebruiker onder de record rules; een notitie vraagt schrijfrecht (de commissaris niet); niets wordt verstuurd. Een aanvraag vanuit Outlook volgt nu ook B-S4. | in orde |

## Nagekeken en in orde

- **Portaal**: elke `<int:…>`-route en elke download vertrekt van `request.env.user.partner_id` en filtert via de helpers. Stemmen en handtekeningen worden met de eigen lijnen vergeleken. `/av/<token>` is 128 bit en stuurt alleen door naar een pagina achter de login.
- **Record rules**: elk `vme.*`-model heeft een globale company-regel en regels voor de commissaris. Portaal en publiek hebben geen ACL. Knoppen die als sudo schrijven, roepen `check_not_auditor` aan; op deze branch zijn er twee bijgekomen.
- **Rekenlogica**:
  - `largest_remainder` telt exact op, en geldvergelijkingen gebruiken `float_compare`/`compare_amounts`.
  - `ondelete` is bewust gekozen: cascade alleen op afgeleide data, restrict op boekingen.
  - Er zijn geen hardgecodeerde ids, en `ensure_one()` staat op de knoppen voor één record.
- **Rauwe SQL**: alleen in statische rapportviews (`vme.arrears`, `vme.budget.analysis`, `vme.capital.movement`, `vme.council.dossier`), zonder invoer van gebruikers.
- **Manifests**: elk data-bestand staat erin, in de juiste volgorde. De hoogste migratiemap is gelijk aan de manifestversie (1.13.0), en de migraties zijn veilig om opnieuw te draaien.
- **Tests**:
  - elk `test_*.py` staat in `tests/__init__.py`;
  - de trage tests hebben de tag `vme_slow`;
  - tests laden hun demodata zelf;
  - datums staan vast of zijn relatief.
- **ai/**:
  - de API-sleutel komt alleen uit de omgeving (`ai/.env`), en `.env.example` heeft een lege sleutel;
  - verzoeken hebben een timeout en fouten worden niet ingeslikt;
  - de scripts maken alleen concepten en activiteiten.

## Niet nagekeken

- Of de beta-parameters in `ai/classifier.py` en `ai/pdf_reader.py` werken met de geïnstalleerde versie van de `anthropic`-SDK (`requirements.txt` vraagt alleen `>=2.5`).
- Of Odoo 19 een HTML- of SVG-bestand dat een portaalgebruiker oplaadt als `text/plain` bewaart.
