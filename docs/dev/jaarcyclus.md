# Jaarcyclus (stap 28)

De jaarcyclus stuurt de bestaande functies aan: een kalender per VME met vaste stappen en termijnen, en een dagelijkse cron die elke stap op tijd klaarzet als **concept of taak**. Er komt geen nieuwe rekenlogica bij; elke stap roept een bestaande methode op. Niets wordt geboekt, verstuurd of bevestigd (regel in `CLAUDE.md`).

Code: `models/vme_cycle.py`, views en cron in `views/vme_cycle_views.xml`, demo in `demo_data/vme_demo_cycle.py`, tests in `tests/test_cycle.py` (en `test_demo_cycle` in `TestAnnualStatementDemo`, tag `vme_slow`).

## Datamodel

`vme.cycle.step` (`mail.thread`, `mail.activity.mixin`):

| Veld | Betekenis |
| --- | --- |
| `association_id`, `company_id` | VME (company opgeslagen voor de record rule van de commissaris) |
| `year` | cyclusjaar = jaar van de gewone AV; het afsluiten en de jaarafrekening gaan over `year - 1` |
| `code`, `sequence`, `sequence_total` | soort stap; `sequence` is het nummer van de provisieoproep (anders 0) |
| `date_ready`, `date_deadline` | klaarzetten vanaf, uiterlijk |
| `state` | `pending` → `ready` → `done`, of `skipped` |
| `is_late` | berekend (niet opgeslagen) met zoekmethode; `vme_today` in de context zoals de AV-planner |
| `user_id` | verantwoordelijke; leeg = `vme.association.cycle_user_id` of admin |
| `res_model`, `res_id` | het concept: `vme.assembly`, `vme.provision.call` of `vme.budget` |
| `note`, `prepared_date`, `done_date` | wat klaarstaat of wat eerst opgelost moet worden |

Unieke constraint op `(association_id, year, code, sequence)`: dezelfde stap bestaat één keer. De cron zet alleen `pending`-stappen klaar, dus een stap wordt nooit twee keer klaargezet.

Op `vme.association`: `cycle_start_date` (leeg = geen cyclus; bestaande VME's veranderen niet na de upgrade), `cycle_user_id`, `cycle_step_ids`, en berekend `cycle_current_step` en `cycle_late_count`.

## Ankers en termijnen

`vme.association._cycle_plan(year)` geeft de stappen van een jaar met hun datums. Anker `L` = laatste oproepingsdag: `assembly.convocation_deadline` als de gewone AV een datum heeft, anders `period_end - convocation_days`. De termijnen zijn constanten bovenaan `vme_cycle.py`:

| Code | Klaar vanaf | Uiterlijk | Bron |
| --- | --- | --- | --- |
| `closing` | 1 jan | L − 21 | werkafspraak |
| `statement` | 1 jan | L − 7 | werkafspraak (gaat mee met de oproeping, stap 11) |
| `budget` | L − 60 | L − 7 | `# LEGAL-CHECK: art. 3.86 §3 BW` voor het minimum |
| `planning` | period_start − 120 | L − `URGENT_MARGIN_DAYS` (30, uit `vme_assembly.py`) | werkafspraak |
| `agenda` | L − 30 | L | `# LEGAL-CHECK: art. 3.91 BW`, `art. 3.89 §1 BW` |
| `convocation` | L − 14 | L | `# LEGAL-CHECK: art. 3.87 §3 BW` |
| `assembly` | period_start | AV-datum of period_end | `# LEGAL-CHECK: art. 3.87 §2 BW` |
| `minutes` | AV-datum | + 30 | `# LEGAL-CHECK: art. 3.87 §12 BW` |
| `approved_budget` | AV-datum | + 30 | werkafspraak |
| `provision` n/N | eerste dag van periode n − 14 | eerste dag van periode n | N = `budget.calls_per_year`, standaard 4 |

`date_ready` is nooit later dan `date_deadline` (een AV in januari). Zonder AV-periode komen alleen `closing` (31 maart), `statement` (30 april) en de provisieoproepen in de kalender. Stappen met een termijn vóór `cycle_start_date` worden niet aangemaakt.

## De cron

`ir_cron_vme_cycle` → `vme.cycle.step._cron_run_cycle()` → `vme.association._cycle_sync(today)` voor elke VME met `cycle_start_date`:

1. `_cycle_ensure_steps(year)` voor `today.year` en `today.year + 1`: ontbrekende stappen aanmaken, datums van open stappen bijwerken (de AV-datum kan verschuiven), provisiestappen die niet meer bestaan na een wijziging van `calls_per_year` verwijderen (alleen als ze nog `pending` zijn).
2. `_check_done()`: open stappen afronden als het feit er is.
3. `_prepare(today)` voor elke `pending`-stap met `date_ready <= today`, in volgorde van `date_ready`.
4. Opnieuw `_check_done()`: een klaargezette stap kan een vroegere afronden (de oproepingen dragen de agenda).

### Klaarzetten per stap

| Code | Hergebruikt | Resultaat |
| --- | --- | --- |
| `planning` | `vme.assembly._create_missing_assemblies`, `_propose_schedule(today)` (AV-planner, stap 6c) | AV `proposed`, nooit `confirmed` |
| `agenda` | `vme.assembly._cycle_add_renewal_items()` op `item_ids` (stap 11) | agendapunten toegevoegd als ze ontbreken |
| `convocation` | `vme.assembly.action_create_convocations()` (stap 11) | `vme.assembly.convocation` in `draft` met PDF's; alleen voor een bevestigde AV |
| `provision` | `vme.provision.call.wizard._create_call()` met `post_invoices=False` (stap 5) | `account.move` in `draft`; een oproep die al met de hand gemaakt is, wordt hergebruikt |
| `budget` | `vme.budget.reserve_warning`, `_get_previous_year_charges`, `RESERVE_MINIMUM_RATE` (stap 5) | taak met het minimum |
| `statement` | `vme.association.action_open_annual_statement` (stap 6) | taak |
| `closing`, `minutes`, `approved_budget` | — | taak |
| `assembly` | — | mijlpaal, geen taak |

Elke stap krijgt hoogstens één activiteit (`mail.mail_activity_data_todo`). Een `UserError` of `ValidationError` (geen budget, onbevestigde rekening, AV niet bevestigd) wordt per stap in een savepoint opgevangen: de stap gaat naar `ready` met de melding in `note` en een taak "Los eerst op". Eén VME blokkeert de andere niet.

### Afgerond

| Code | Afgerond als |
| --- | --- |
| `closing` | `_cycle_fiscal_year_closed(year - 1)`: standaard `company.fiscalyear_lock_date >= 31/12` |
| `statement`, `agenda` | de AV heeft oproepingen, of is gehouden |
| `budget` | budget van het jaar zonder `reserve_warning` |
| `planning` | AV `confirmed` of `held` |
| `convocation` | `convocation_sent_date` gezet, of AV gehouden |
| `assembly` | AV `held` |
| `provision` | alle niet-geannuleerde facturen van de oproep geboekt |

Stappen in `MANUAL_CODES` (`closing`, `statement`, `agenda`, `minutes`, `approved_budget`) sluiten ook als de medewerker de taak afvinkt: override van `mail.activity._action_done`. Een automatisch afgevinkte taak (context `vme_cycle_closing`) doet niets extra.

`is_late`: niet afgerond en `date_deadline < today`, behalve `minutes` en `approved_budget` zolang de AV niet gehouden is (dan is de AV zelf te laat).

## Haken voor andere stappen

- `vme.association._cycle_fiscal_year_closed(year)`: de afsluiting van het boekjaar (eigen stap) kan dit overschrijven als ze iets anders dan de afsluitdatum gebruikt.
- `vme.association._cycle_syndic_renewal_due(year)`: standaard `False`. Het mandaat van de syndicus (eigen stap) overschrijft het; dan zet de stap `agenda` "Herbenoeming van de syndicus" op de agenda.
- `vme.association._get_building_card_data()` wordt uitgebreid met `cycle_steps` (`None` als de cyclus uit staat; de gebouwkaart verbergt dan het blok).

## Portefeuille en gebouwkaart

Signaal `cycle` ("Stap in de jaarcyclus te laat") in `SIGNALS` van `vme_building_card.py`, met `signal_cycle` en `_search_signal_cycle` zoals de andere signalen. De portefeuille toont `signal_cycle` en `cycle_current_step`, de kanbankaart de volgende stap, de gebouwkaart een blok met de open stappen. `cycle_current_step` toont eerst de oudste te late stap, dan de klaargezette, dan de eerstvolgende geplande.

## Toegang

ACL voor `base.group_user`. De commissaris (`group_vme_auditor`) leest de stappen van zijn companies en kan niets schrijven (twee record rules, zoals de gebouwkaart). De cron draait als superuser; alle zoekopdrachten over companies heen gebruiken `sudo()`.

## Valkuilen

- **Volgorde binnen één run.** De agenda wordt vóór de oproeping klaargezet; pas na de oproeping bestaan de oproepingen die de agenda afronden. Daarom draait `_check_done()` ook na het klaarzetten.
- **`vme_today` overal doorgeven.** `is_late` en `cycle_current_step` hangen af van de context (`@api.depends_context("vme_today")`); `_cycle_sync(today)` zet de context zelf.

## Tests

`tests/test_cycle.py`: termijnen per stap, verschuiven met de AV-datum, maandelijkse oproepen en terug, startdatum, VME zonder AV-periode, cyclus uit; cron maakt alleen conceptfacturen, conceptoproepingen en een voorgestelde AV; dezelfde stap niet twee keer (ook de unieke constraint); met de hand gemaakte oproep hergebruikt; afronden door boeken, versturen, bevestigen, lockdatum en afvinken; fout zonder budget blokkeert andere VME's niet; herbenoeming van de syndicus via de haak; signaal en filter in de portefeuille; notulen niet te laat vóór de AV; blok op de gebouwkaart.

## Demo

`_load_demo_cycle()` draait op het einde van `_load_demo_history()` met `vme_today = 5/11/2026`: Linde vanaf 1/1/2026 (2026 afgerond, AV 2027 voorgesteld op 17 maart), Hof ter Beuken vanaf 5/4/2026 (agenda, oproeping en AV 2026 te laat), Kaaihuis vanaf 1/10/2026 (volgende stap vanaf 10 november). Zie [demo.md](../demo.md).
