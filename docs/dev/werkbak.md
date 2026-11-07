# Mijn werk vandaag en de dossierbeheerder (stap 29)

Eén lijst per medewerker met alles wat te laat is, vandaag of deze week vervalt, over alle VME's die hij mag lezen. Gebruikersuitleg: [kb/mijn-werk-vandaag.md](../kb/mijn-werk-vandaag.md).

## Dossierbeheerder

`vme.association.manager_user_id` ("Dossierbeheerder"), standaard de gebruiker die de VME aanmaakt (niet OdooBot). De migratie `19.0.1.14.0` geeft bestaande VME's hun maker, of admin.

`vme.association._vme_task_user()` geeft de dossierbeheerder, anders admin; het werkt ook op een lege recordset. Alle taken die Odoo zelf maakt zonder eigen verantwoordelijke gaan daarheen:

| Waar | Vroeger | Nu |
| --- | --- | --- |
| `_cycle_default_user` (jaarcyclus) | `cycle_user_id` of admin | `cycle_user_id`, dan dossierbeheerder |
| `_cron_schedule_contract_activities` | `responsible_user_id` of `self.env.user` (OdooBot in de cron) | `responsible_user_id`, dan dossierbeheerder |
| `_cron_schedule_inspection_activities` | idem | idem |
| `vme.syndic.mandate._cron_schedule_mandate_activities` | `self.env.user` | dossierbeheerder |
| `vme.request.create_from_intake` zonder `user_id` (mailgateway, AI) | `self.env.user` | dossierbeheerder |
| `_cron_schedule_policy_activities` (polissen) | `user_id` van de polis of `self.env.user` | `user_id`, dan dossierbeheerder |
| `_cron_schedule_certificate_activities` (attesten) | `self.env.user` | dossierbeheerder |
| `vme.rent.contract._cron_rent_reminders` en opzeg registreren (rentmeester) | `self.env.user` | `_rent_task_user()`: het nieuwe veld **Beheerder** (`user_id`) van het huurcontract, dan de dossierbeheerder van de VME, dan admin |
| Aanvraag uit het portaal, adreswijziging | admin | dossierbeheerder |

Velden met een eigen verantwoordelijke (aanvraag, verkoop, werken, schade, contract, installatie) houden hun standaard (`self.env.user` bij aanmaken in het scherm).

## Model `vme.work.item`

`models/vme_work_item.py`, een **TransientModel**. Elke opening (`action_open_worklist`, via de serveractie van het menu of de knop **Vernieuwen**) roept `_build()`:

1. verwijdert de eigen rijen van de gebruiker;
2. zoekt de VME's met de record rules van de gebruiker (`search([])` op `vme.association`) en leest daarna met sudo binnen die VME's;
3. roept elke bron in `_work_item_sources()` op met `(vmes, today, horizon, tasks)`;
4. zet urgentie, company en verantwoordelijke (eigen gebruiker van de bron, anders de dossierbeheerder) en maakt de rijen.

Waarom transient en geen SQL-view: veel bronnen zijn berekende velden zonder opslag (`_is_late` van de jaarcyclus, `renewal_state` van het mandaat, `order_ready` van een aanvraag, de drempel van de achterstallen), en de urgentie hangt af van "vandaag" (`vme_today` in tests). Een transient model kan gegroepeerd en gefilterd worden in een gewone lijst, en elke medewerker bouwt zijn eigen rijen, dus gelijktijdige gebruikers zitten elkaar niet in de weg. De regel `rule_user_work_item` (`create_uid = user`) beperkt de rijen tot wie ze maakte; Odoo 19 doet dat niet zelf voor transient modellen.

Velden: `association_id`, `company_id`, `name`, `description`, `kind` (onderwerp), `item_type` (taak, signaal, concept), `date_deadline`, `urgency` en `urgency_rank` (te laat, vandaag, deze week), `user_id`, `res_model`/`res_id`, `activity_id`.

**Urgentie.** `late` als de termijn vóór vandaag ligt, `today` als ze vandaag is, `week` tot en met vandaag + `HORIZON_DAYS` (7). Wat later valt, komt er niet in.

**Ontdubbeling.** `tasks` is de set `(model, id)` van alle records met een open activiteit. Een signaal voor zo'n record wordt overgeslagen: de taak is het werk. De bestelling bij de slotenmaker maakt zelf een taak; die taak wordt een lijn van soort `order` (concept).

### Bronnen

| Methode | Wat | Termijn | Verantwoordelijke |
| --- | --- | --- | --- |
| `_items_activities` | Open `mail.activity` op `vme.association` en op elk model met `association_id` naar `vme.association` (`_vme_models()`). Samenvatting "AI-voorstel…" op de VME = `ai`, taak op een aanvraag met klaarstaande bestelling = `order`, beide `draft` | `date_deadline` | `activity.user_id` |
| `_items_cycle_steps` | Stappen `pending`/`ready` met `date_ready <= vandaag`, termijn binnen de horizon, zonder taak. Een stap over termijn die op de AV wacht (`_is_late` is False) wordt overgeslagen | `date_deadline` | stap, dan `_cycle_default_user` |
| `_items_requests` | Klaarstaande bestelling zonder taak (`order`, concept); nieuwe aanvraag zonder taak | vandaag; `request_date` | `user_id` |
| `_items_reminders` | `vme.collection.reminder` in concept | `min(date, vandaag)` | dossierbeheerder |
| `_items_installations` | Keuring of risicoanalyse die vervalt of vervallen is, zonder taak | `next_inspection_date`, `next_risk_analysis_date` | `responsible_user_id` |
| `_items_contracts` | Lopend contract, niet opgezegd, opzegtermijn binnen de horizon en het einde van de periode nog niet voorbij | `notice_deadline` | `responsible_user_id` |
| `_items_arrears` | Achterstallen boven `arrears_signal_threshold`, tenzij er voor de VME al een herinnering in concept staat | vandaag | dossierbeheerder |
| `_items_sale_files` | Open verkoopdossier met wettelijke termijn binnen de horizon, zonder taak | `answer_deadline` | `user_id` |
| `_items_mandates` | Mandaat syndicus `urgent`, `decided`, `expired`, of `plan` met termijn binnen de horizon; aanplakking `todo`/`late` | begin AV-periode min 2 maanden, of einde mandaat; `posting_deadline` | dossierbeheerder |

De wettelijke termijnen zelf (notaris, keuringen, mandaat, jaarcyclus) dragen hun `# LEGAL-CHECK:` in hun eigen model; de werkbak rekent geen nieuwe termijnen.

**Uitbreiden.** Een andere module (bv. `vme_rentmeester`) voegt een bron toe door `_work_item_sources()` te overschrijven en een methode met dezelfde parameters toe te voegen die `self._item(...)`-dicts teruggeeft. Een nieuw onderwerp: `kind` uitbreiden met `selection_add` in de erfgenaam.

**Openen.** `action_open_record` geeft het formulier van het record (met de company van de lijn in `allowed_company_ids`); voor achterstallen de invorderingsdossiers van de VME. Openen verandert niets aan het record en verstuurt niets.

## Schermen

- `views/vme_work_item_views.xml`: lijst zonder aanmaken of bewerken, knop **Vernieuwen** in de kop (`display="always"`), knop **Openen** per lijn; zoekscherm met **Mijn werk** (standaard), **Zonder verantwoordelijke**, urgentie, soort en groeperen per urgentie, VME, verantwoordelijke en onderwerp. Standaard één groepsniveau (urgentie, open met `expand="1"`) en daarbinnen gesorteerd per VME: Odoo klapt alleen het eerste niveau open, met urgentie > VME zou de medewerker eerst elke VME moeten openklikken. De serveractie `vme_work_item_server_action` bouwt eerst en geeft dan `vme_work_item_action` terug.
- Menu **VME > Mijn werk vandaag** (sequence 3), boven de gebouwkaart.
- Dossierbeheerder op het VME-formulier (groep Gegevens), als kolom en filter **Mijn VME's** in de VME-lijst en de portefeuille.

## Schaal

Per bron een paar zoekopdrachten over alle VME's samen; de achterstallen met één `_read_group`. Het aantal queries hangt dus niet af van het aantal VME's, behalve het lezen van de records zelf in batches van de ORM.

## Tests

`tests/test_work_items.py` (standaardtests): dossierbeheerder als standaard en als ontvanger van crontaken, urgentiegroepen en de horizon, AI-antwoord, bestelling en rappel als concept, signaal zonder taak en ontdubbeling met een taak, vervallen keuring en termijn van de notaris, jaarcyclusstap naar de dossierbeheerder, eigen lijst per gebruiker en alleen de eigen VME's, en dat bouwen en openen geen mail of bericht maakt. `test_demo_data` controleert de werkbak van admin op 5 november 2026.

## Demo

`demo_data/vme_demo_worklist.py`:
- `_load_demo_managers()` (einde van `_load_demo_data`): admin beheert Residentie Linde en Hof ter Beuken, Medewerker Voorbeeld beheert Kaaihuis; de open taken en de verantwoordelijken van de dossiers van elke VME gaan naar die beheerder. Daarna maakt de historiek de taken van de jaarcyclus al op de juiste naam.
- `_load_demo_worklist()` (einde van `_load_demo_history`): een AI-voorstel voor Linde A8 (admin) en Kaaihuis K3 (Medewerker Voorbeeld), en een sleutelaanvraag van Beuken B3 met een bestelling die klaarstaat. Niet in Linde: daar toont de demo de badge van A4 via de AI-assistent.
