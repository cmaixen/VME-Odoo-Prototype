# Raad van mede-eigendom en commissaris van de rekeningen (stap 16)

Code: `models/vme_council.py`, `models/vme_access.py`, `security/vme_council_security.xml`, `views/vme_council_views.xml`, `report/vme_council_reports.xml`, `data/council_data.xml`. Tests: `tests/test_council.py` en `test_council_and_auditors` in `tests/test_demo_data.py`.

## Datamodel

| Model | Wat | Belangrijke velden |
| --- | --- | --- |
| `vme.mandate` | Eén mandaat van één persoon in één VME | `role` (`chair`, `member`, `auditor`), `partner_id`, `date_start`, `date_end` (standaard + 1 jaar - 1 dag), `assembly_item_id` (beslissing van de AV), `audit_year`, `user_id`, berekend: `is_current` (met zoekmethode), `is_owner` |
| `vme.council.dossier` | SQL-view, alleen lezen: lopende dossiers van alle VME's | `association_id`, `company_id`, `dossier_type`, `name`, `partner_id`, `status`, `date_deadline`, `is_overdue`, `user_id`, `res_model`, `res_id` |

Op `vme.association`: `mandate_ids`, `council_member_ids` en `auditor_mandate_ids` (One2many met domein), `council_lot_count`, `council_required`, `council_warning`, `open_dossier_count`. Op `res.partner`: `vme_ownership_ids` en `vme_mandate_ids`, alleen nodig voor de record rule van de commissaris.

Een raad en een commissaris zijn geen aparte modellen: één mandaatmodel met een rol houdt de historiek per jaar bij en laat een herkiezing gewoon een nieuw mandaat zijn.

### Controles

- `_check_council_owner`: voorzitter en leden moeten op `date_start` eigenaar zijn van een kavel in de VME (`# LEGAL-CHECK: art. 3.90 §1 BW`). De commissaris niet (`art. 3.91 BW`).
- `_check_one_chair`: geen twee voorzitters met overlappende periodes in dezelfde VME (praktijkregel, geen wettelijke).
- `council_required`: twintig kavels of meer zonder `garage` en `storage` (`COUNCIL_REQUIRED_MIN_LOTS`, `COUNCIL_EXCLUDED_LOT_TYPES`). Een berging telt als kelder. Alleen een waarschuwing op de VME, geen blokkade.

## Toegang van de commissaris

### Groep en regels

`vme_belgie.group_vme_auditor` ("Commissaris van de rekeningen", privilege "VME") impliceert `account.group_account_readonly`, dat zelf `base.group_user` impliceert. De commissaris is dus een **interne** gebruiker:

- op de boekhouding geven de ACL's van `group_account_readonly` hem alleen leesrecht (facturen, boekingen, bankafschriften, rapporten);
- op de VME-modellen heeft `base.group_user` alle rechten (lezen tot verwijderen). ACL's tellen op over groepen, dus die kunnen we voor hem niet afnemen. Daarom de record rules.

Record rules van groepen worden per bewerking met OF gecombineerd, en gelden alleen voor wie in de groep zit. Per model zijn er twee regels voor `group_vme_auditor`:

| Regel | Bewerking | Domein |
| --- | --- | --- |
| `rule_auditor_read_<model>` | lezen | `[('company_id', 'in', company_ids)]`; voor `vme.assembly.attendee`, `vme.assembly.vote` en `vme.collection.reminder.line` via de ouder |
| `rule_auditor_no_write_<model>` | schrijven, aanmaken, verwijderen | `[(0, '=', 1)]` |

Voor de zalen en blokken van het kantoor (`vme.assembly.room`, `vme.assembly.slot`) is er alleen de schrijfregel. Medewerkers zitten niet in de groep, dus voor hen verandert er niets; `test_staff_keeps_access` controleert dat.

`res.partner` krijgt een leesregel: zijn eigen partner, partners met een `company_id` of `ref_company_ids` van zijn VME, eigenaars (`vme_ownership_ids`), mandaathouders, partners met een factuur in zijn company, en partners van interne gebruikers. Die laatste zijn nodig omdat de chatter de volgers van een record leest (`message_partner_ids`), en dat zijn meestal medewerkers. Schrijven op partners kan hij al niet: `base.group_user` heeft er alleen leesrecht.

`company_ids` in een regel is de lijst van companies die de gebruiker geselecteerd heeft, binnen zijn toegestane companies. Daarom houden we die toegestane companies van de commissaris strikt op zijn VME's.

### Toegestane companies

- `vme.mandate.action_grant_access()` (alleen `base.group_erp_manager`) maakt een gebruiker met `group_ids = [group_vme_auditor]`, login = e-mailadres van de partner, `no_reset_password=True`: er vertrekt geen uitnodiging. Bestaat er al een gebruiker voor de partner die geen commissaris is, dan weigert Odoo (anders zouden we een medewerker beperken).
- `res.users._vme_sync_auditor_access()` zet `company_ids` op de companies van de lopende commissarismandaten van de gebruiker, en archiveert hem zonder lopend mandaat (of activeert hem weer).
- Een dagelijkse cron (`ir_cron_auditor_access`) roept die sync op voor alle commissarissen.
- `vme.association.create()` geeft elke interne gebruiker toegang tot de nieuwe company (stap 1). De override in `vme_council.py` draait daarna de sync voor commissarissen, zodat een nieuwe VME niet bij hen terechtkomt.

### Knoppen die met sudo schrijven

Record rules stoppen alleen wat de gebruiker zelf schrijft. Een knop die daarna `sudo()` gebruikt, omzeilt ze. `vme_access.check_not_auditor(env)` weigert zulke knoppen voor de commissaris; het staat bovenaan:

- `vme.collection`: `action_charge_costs`, `action_propose_reminder`, `action_forward`, `action_refresh`, en `vme.arrears.action_refresh_collections`;
- `account.bank.statement.line`: `action_vme_reconcile`, `action_vme_book_on_partner`, `action_vme_undo`, `action_vme_rematch`.

`self.check_access("write")` volstaat hier niet: op een lege recordset (een `@api.model`-knop) toetst het alleen de ACL, niet de record rules. Een nieuwe knop met `sudo()` hoort deze controle ook te krijgen.

### Alleen-lezen-schermen

`base._get_view()` zet voor de commissaris `create="0" edit="0" delete="0"` op elke list-, form- en kanbanweergave, behalve op `res.users` (voorkeuren) en wizards. `_get_view_cache_key()` krijgt daarvoor een extra element, anders deelt de commissaris de gecachte weergave van een medewerker. Dit is gebruiksgemak; de regels blijven de bescherming. Knoppen in de koptekst van een formulier blijven zichtbaar en geven bij klikken een toegangsfout.

## Overzicht voor de raad

`vme.council.dossier` is een `UNION ALL` van de queries uit `_dossier_queries()`:

| Soort | Bron | Wanneer lopend | Termijn |
| --- | --- | --- | --- |
| `sale` | `vme_sale_file` | `state` niet `done` of `cancelled` | `answer_deadline`, anders `deed_date` |
| `collection` | `vme_collection` | `state` in `open`, `forwarded` | geen |
| `inspection` | `vme_inspection_remark` | `state` in `open`, `planned` | `deadline` |
| `assembly` | `mail_activity` op `vme.assembly.item` | actieve activiteit | `date_deadline` |

Het id is `bron-id * 10 + cijfer per soort` (1 tot 4). De selectie `dossier_type` kent al `works` en `damage`: **stap 14 voegt haar werken en schadegevallen toe door `_dossier_queries()` te overschrijven** en twee queries met de cijfers 5 en 6 toe te voegen, met dezelfde kolommen in dezelfde volgorde. Statusteksten staan in de SQL in het Nederlands; bij de Franse vertaling worden dat selectievelden of een vertaalde compute.

`action_open_record()` opent het brondossier. De PDF `action_report_council_dossiers` op `vme.association` toont dezelfde rijen per soort.

## Sjabloon voor het verslag van de commissaris

`action_report_auditor` op `vme.mandate`. `_get_audit_figures()` controleert eerst dat de gebruiker het mandaat mag lezen en rekent dan met `sudo()` binnen de company van het mandaat, omdat een commissaris van twee VME's maar één company geselecteerd kan hebben:

- geboekte leveranciersfacturen en creditnota's (`date` in het boekjaar), aantal en totaal;
- verkoopfacturen en -creditnota's (provisies, afrekeningen, kosten), aantal en totaal;
- per bankdagboek: aantal bankregels in het jaar en saldo op 31 december van de standaardrekening van het dagboek, dus volgens de ingelezen bankafschriften;
- saldo debiteuren en crediteuren, en de stand van rekening 100200 (reservekapitaal) op 31 december.

Controles, bevindingen en besluit zijn lege vakken.

## Demodata

`_load_demo_council()` draait aan het einde van `_load_demo_data()` (`DEMO_COUNCIL`):

- Residentie Linde: eigenaar A2 is commissaris, gekoppeld aan het agendapunt "Benoeming van de commissaris van de rekeningen" van de AV van 10 maart 2026, met een login.
- Hof ter Beuken: voorzitter B1, leden B6 en B11, en de externe "Commissaris Voorbeeld Beuken" zonder login.

Login van de demo-commissaris: `eigenaar.linde.a2@example.com`, wachtwoord `DEMO_AUDITOR_PASSWORD` in `demo_data/vme_demo_data.py` (een fictieve waarde, alleen voor een lokale demodatabase). Omdat `action_grant_access` een lopend mandaat vraagt, laadt de demo na 9 maart 2027 niet meer zonder de datums aan te passen.

## Testen

`tests/test_council.py` (17 tests, enkele seconden) maakt twee VME's met elk een geboekte leveranciersfactuur, een commissaris met login in de eerste en een medewerker met toegang tot beide. Het test onder meer:

- lezen: de commissaris ziet zijn VME, kavels, eigendommen, factuur en mandaat;
- isolatie: VME, kavel, factuur en eigenaar van de andere VME geven een `AccessError`, ook met de andere company in de context;
- niets wijzigen: schrijven, aanmaken, verwijderen, een factuur terug naar concept zetten, een bericht plaatsen, toegang geven, en knoppen die met `sudo()` schrijven;
- de schermen zonder Nieuw/Bewerken voor hem, en ongewijzigd voor een medewerker;
- toegestane companies volgen de mandaten; na het einde wordt de gebruiker gearchiveerd;
- het overzicht voor de raad en het verslag (HTML, als commissaris).

## Valkuilen

- De chatter faalde voor de commissaris tot de partners van interne gebruikers in zijn leesregel kwamen: `_compute_message_partner_ids` schrijft de volgers in de cache en controleert daarbij leesrecht op elke partner.
- `check_access("write")` op een lege recordset toetst geen record rules (zie hierboven).

## Voor later

- Portaaltoegang (stap 15) voor de commissaris en de leden van de raad, in plaats van een interne gebruiker.
- Koptekstknoppen verbergen voor de commissaris (nu krijgt hij een foutmelding).
- Werken en schadegevallen (stap 14) in het overzicht.
- Het verslag als bewerkbaar document en de goedkeuring ervan op de AV.
