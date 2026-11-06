# Schaal: 200 VME's (stap 27)

De pilotsyndicus beheert ongeveer 200 VME's; de demo heeft er drie. Dit document toont hoe we het prototype op die schaal meten, wat te traag was en wat we eraan deden.

## Schaaldatabase opbouwen

Altijd in een eigen Docker-project en een eigen database `vme_scale`, nooit in `vme_demo` (de generator weigert elders te draaien).

```bash
docker compose -p vme-schaal up -d db
docker compose -p vme-schaal run --rm odoo odoo -d vme_scale -i vme_belgie,vme_rentmeester --load-language=nl_BE --stop-after-init
docker compose -p vme-schaal run --rm -T odoo odoo shell -d vme_scale --no-http < tools/scale_data.py
```

`tools/scale_data.py` roept per tien VME's `vme.association._load_scale_data()` en `_load_scale_history()` aan (`demo_data/vme_scale_data.py`) en commit na elke stap: het rekeningstelsel van een nieuwe company laadt pas bij de commit. Een onderbroken run hervat waar hij stopte. `SCALE_COUNT` en `SCALE_BATCH` in de omgeving veranderen de grootte. De volledige run duurt ongeveer anderhalf uur (vooral de betalingen).

Wat de generator maakt, per VME met een eigen vaste seed (dezelfde portefeuille bij elke run):

- "Residentie Test 001" tot "Residentie Test 200", met 6 tot 60 kavels op 1 tot 6 verdiepingen, soms garages; eigenaars "Eigenaar T001-A1" (`@example.com`), af en toe een belegger met twee appartementen. KBO, btw en IBAN zijn fictief zoals in de demo (0000…, bankcode 999).
- Algemene sleutel en, vanaf drie verdiepingen, een liftsleutel; budget 2026 en 2027 met budgetregels; ongeveer 10% van de VME's bouwt te weinig reserve op.
- Brandblussers en lift met een keuring die soms vervallen is; een gehouden gewone AV 2026 (behalve ongeveer 5%), geleid door tien fictieve medewerkers (Odoo laat één medewerker maar een paar AV's per avond leiden).
- Historiek 2026: vier provisieoproepen met betalingen (ongeveer 6% van de eigenaars betaalt oproep 3 en 4 niet), en per VME 7 tot 9 leveranciersfacturen (schoonmaak, energie, verzekering, lift) die bij het boeken automatisch verdeeld worden. De oproepen en betalingen hergebruiken `_demo_history_provisions()` van de demohistoriek.

Er wordt niets naar buiten verstuurd: de oproepen worden geboekt (zoals "Meteen boeken" in de wizard), maar niet gemaild of via Peppol verzonden, en de fictieve medewerkers krijgen geen uitnodigingsmail. Ook de achtergrondverwerking van provisieoproepen boekt alleen; versturen blijft een klik van een medewerker.

Volume na de volledige run:

| | Aantal |
| --- | ---: |
| VME's (companies) | 200 |
| Kavels | 6.344 (6 tot 60 per VME) |
| Eigenaars | 5.453 |
| Provisiefacturen 2026 | 43.624 |
| Betalingen | 42.356 |
| Leveranciersfacturen | 1.748 |
| Kostenverdelingsregels | 55.774 |
| Boekingslijnen | 184.132 |

## Meten

```bash
docker compose -p vme-schaal run --rm -T odoo odoo shell -d vme_scale --no-http < tools/scale_benchmark.py
```

Het script meet als admin met alle companies geselecteerd (zoals in de browser), met een lege recordcache, de mediaan van drie runs, en telt de SQL-queries (`cr.sql_log_count`). Wat records maakt (verdeling van een factuur, provisieoproep voor alle VME's) draait één keer in een savepoint die teruggedraaid wordt. Er wordt niets gecommit. Voor de meting vóór de verbeteringen draaiden we hetzelfde script met de code van vóór stap 27 als addons-map (`-v <kopie>/addons:/mnt/extra-addons`).

## Resultaten

Gemeten op 6 november 2026 in Docker op een MacBook (PostgreSQL 16, Odoo 19 Community), na `VACUUM ANALYZE`. Tijd = mediaan van drie runs; de provisieoproep voor alle VME's één run. "Residentie Test 002" is de grootste VME (60 kavels).

| Scenario | Vóór: tijd | Vóór: queries | Na: tijd | Na: queries |
| --- | ---: | ---: | ---: | ---: |
| Portefeuille, lijst (80 VME's) | 1,98 s | 2.395 | 0,11 s | 28 |
| Portefeuille, kanban (alle 200 VME's) | 7,50 s | 5.960 | 0,22 s | 35 |
| Filter "Met signalen" + lijst (149 VME's) | 2,62 s | 3.515 | 0,31 s | 40 |
| Filter "Achterstallen boven de drempel" + lijst (67 VME's) | 2,78 s | 2.762 | 0,21 s | 33 |
| Gebouwkaart van de grootste VME | 0,03 s | 61 | 0,03 s | 65 |
| Jaarafrekening 2026 van de grootste VME | 0,11 s | 77 | 0,11 s | 77 |
| Voorbeeld jaarafrekening (wizard) | 0,11 s | 78 | 0,11 s | 78 |
| Verdeling van één factuur over 60 kavels | 0,44 s | 191 | 0,40 s | 191 |
| Klik op "Maak provisieoproepen" voor 200 VME's | 790 s | 146.949 | 0,01 s | 17 |
| Provisieoproep 2027/1 voor 200 VME's (10.906 facturen), zelf | 790 s | 146.949 | 329 s | 192.203 |

In de browser (`http://schaal.localhost:8629`) gaf dat na de verbeteringen: portefeuille 146 ms, kanban 123 ms, filter "Met signalen" 339 ms, gebouwkaart 89 ms (de netwerktijd van `web_search_read` of `web_read`). Een provisieoproep voor 80 VME's (4.340 facturen) liep in de cron van de server in 3,5 minuten af, zonder fouten; de gebruiker kon intussen verder werken. Die test liet oproep 4 van 2027 voor Residentie Test 001 tot 080 in `vme_scale` staan; het meetscript gebruikt oproep 1 van 2027 en draait die terug.

Wat de cijfers zeggen:

- **De portefeuille was te traag** (2 tot 7,5 seconden, oplopend met het aantal VME's) en is nu constant: een dertigtal queries, of er nu 1 of 200 VME's zijn. De resultaten zijn dezelfde: voor alle 200 VME's gaven de nieuwe berekening en die van de gebouwkaart dezelfde kapitalen, achterstallen en budgetcijfers (tot op de cent), en dezelfde VME's met signalen.
- **Gebouwkaart, jaarafrekening en verdeling** blijven ruim onder een halve seconde op de grootste VME, ook met 184.000 boekingslijnen in de database: ze zoeken per company en de indexen van Odoo volstaan.
- **Provisieoproepen voor alle VME's** waren met 13 minuten in één webverzoek onbruikbaar. Op de achtergrond, met de recordcache leeg na elke VME, duurt het werk zelf 5,5 minuten (de cache die groeit met duizenden facturen maakte elke volgende VME trager), en de gebruiker wacht niet.
- Eerste meting van de gebouwkaart gaf 9,3 seconden: het meetscript las de kaart van een VME die in de prefetch-set van alle 200 zat, zodat Odoo de kaart voor alle 200 berekende. In de browser opent het formulier één record, dus dat was een meetfout; het script leest de VME nu los.

## Wat we veranderden

### Portefeuille en signalen: alles in één keer lezen

`_compute_portfolio` rekende per VME `_get_capital_history`, `_get_budget_tracking`, `_get_signals` en `_get_arrears_total`, elk met eigen zoekopdrachten en lussen over alle boekingslijnen: ongeveer twintig queries per VME. De zoekfilters op signalen (`signal_count > 0`, `signal_arrears = True`) deden dat opnieuw voor álle VME's, en daarna de lijst nog eens.

Nu leest `_get_portfolio_figures(today)` alles voor een hele recordset in een vast aantal queries:

- kapitalen: één `_read_group` op de SQL-view `vme.capital.movement` (per VME en fonds, tot vandaag);
- achterstallen: één `_read_group` op `vme.arrears`;
- werkelijke kosten tot vandaag: één `_read_group` op `vme.budget.analysis`; het budget tot vandaag uit de budgetten en hun regels;
- AV's van dit jaar: één zoekopdracht; `_get_assembly_signal()` krijgt ze mee;
- 5%-regel: `vme.budget._get_previous_year_charges_by_budget()` leest de lasten van vorig jaar voor alle budgetten in één `_read_group` (de compute van `reserve_warning` gebruikt die).

`_get_signals()` van één VME en de zoekfilters gebruiken dezelfde functie, zodat er één plaats is waar signalen bepaald worden. De gebouwkaart van één VME blijft `_get_capital_history` en `_get_budget_tracking` gebruiken (met de details per jaar en per rekening); `test_portfolio_matches_card_figures` controleert dat beide wegen dezelfde bedragen geven, en `test_portfolio_query_count_does_not_grow_per_vme` dat het aantal queries niet groeit met het aantal VME's.

### Provisieoproepen voor alle VME's: op de achtergrond

Odoo heeft twee à drie seconden per VME nodig om de facturen van een oproep te maken en te boeken (vooral de eigen logica van `account.move`: nummering, regels, analytische modellen, chatter). Dat is geen N+1 van onze code: het profiel toont dat de tijd in `account.move.create()` en `_post()` zit, en zonder chatterbericht (`mail_create_nolog`) wint het maar 13%. Voor 200 VME's duurt één klik dus minuten, langer dan een webverzoek mag duren (`limit_time_real` is standaard 120 seconden op een productieserver met workers).

Daarom maakt de wizard vanaf 21 VME's (`BACKGROUND_THRESHOLD`) een `vme.provision.call.run` aan en start de cron "VME: provisieoproepen op de achtergrond". Die maakt de oproepen VME per VME met dezelfde `_create_calls()` als de wizard, commit na elke VME via `ir.cron._commit_progress()` en gaat bij de volgende run verder als de tijd op is. Een VME die faalt (geen budget, onbevestigde rekening, geen sleutel) komt in het logboek van de run, de andere lopen door. De gebruiker krijgt een melding als alles klaar is. Tot 20 VME's werkt de wizard zoals voorheen.

## Valkuilen

- `ir.cron._commit_progress()` commit ook buiten een cron. Daarom geeft `_cron_process()` het als functie mee aan `_process(progress)`, en roepen tests `_process()` aan zonder of met een eigen functie.
- `cr.flush()` voert ook de precommit-haakjes uit, dus ook het laden van rekeningstelsels. Een test die alleen veel VME's nodig heeft, maakt companies zonder rekeningstelsel aan en geeft ze mee als `company_id`.
- De historiektest met betalingen (`TestScaleHistory`) is traag in de testomgeving om dezelfde reden als de demojaar-test, en draagt daarom de tag `vme_slow`. Alleen die test: `--test-tags vme_slow/vme_belgie:TestScaleHistory` (ongeveer 10 seconden na `VACUUM ANALYZE`).
- Elke nieuwe VME-company komt bij alle interne gebruikers (`vme.association.create()`); bij 200 VME's heeft admin 200 companies. Dat werkt, maar de bedrijvenkiezer wordt lang.

## Nog open

- **Bedrijvenkiezer met 200 companies.** Elke VME is een company, dus de kiezer bovenaan toont er 200. Voor de pilot kan dat; later een zoekbare kiezer of groepen van VME's per medewerker.
- **Cron in een echte installatie.** De meting draaide in Docker met de cron-threads van één server. Met workers (`--workers`) gelden `limit_time_real_cron` en de cron-workers; de run commit per VME, dus een afgebroken cron gaat bij de volgende start verder.
- **Grotere VME's.** De generator gaat tot 60 kavels. Een VME van een paar honderd kavels (grote residenties aan de kust) is nog niet gemeten; de verdeling en de jaarafrekening schalen per kavel.
- **De provisiewizard rekent het voorbeeld per VME.** Voor 80 VME's duurt dat 0,1 seconde, voor 200 enkele tienden; geen probleem nu.
