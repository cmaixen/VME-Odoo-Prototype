# Omgeving, tests en demo

Alle commando's draaien vanuit de hoofdmap van het project. Docker draait op deze machine via OrbStack (`$HOME/.orbstack/bin` in het `PATH`).

## Omgeving

`docker-compose.yml` heeft twee diensten: `db` (PostgreSQL 16) en `odoo` (image `odoo:19.0`, `addons/` gemount op `/mnt/extra-addons`, server met `--db-filter=^vme_demo$`).

```bash
docker compose up -d
```

Odoo staat dan op http://localhost:8069. Logs:

```bash
docker compose logs -f odoo
```

### Database aanmaken

```bash
docker compose run --rm odoo odoo -d vme_demo -i vme_belgie --load-language=nl_BE --stop-after-init
```

Dat installeert ook `account`, `l10n_be` en `account_peppol`. Opnieuw beginnen: Odoo stoppen, `docker compose exec db dropdb -U odoo vme_demo`, opnieuw aanmaken.

### Module upgraden

```bash
docker compose run --rm odoo odoo -d vme_demo -u vme_belgie --stop-after-init
```

Gebruik `run`, niet `exec` (zie [valkuilen](valkuilen.md#shell-run-en-exec)). Kijk daarna de log na op `ERROR` en `WARNING` en test de functie in de browser.

## Tests

Unittests staan in `addons/vme_belgie/tests/` en draaien op een aparte database `vme_test` (ongeveer 20 seconden):

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie --test-enable --test-tags /vme_belgie --stop-after-init
```

| Bestand | Wat |
| --- | --- |
| `test_data_model.py` | Eigen company en Belgisch rekeningstelsel per VME, toegang voor alle gebruikers, KBO-controle, aparte bankrekeningen, som van sleutels (ook bij herschikken in één keer), kavel uit andere VME, verkoop en overlappende eigendommen |
| `test_demo_data.py` | Demodata: aantallen, sleutels die kloppen, verkoop midden in het jaar, eigenaar met meerdere kavels, fictieve contactgegevens, niet twee keer laden, hulpfuncties (`distribute_shares`, `fake_iban`) |
| `test_cost_allocation.py` | `largest_remainder`, VME uit de company, standaardkostenrekening, kostperiode, volledig jaar met verkoop, exacte afronding, btw inbegrepen, creditnota, opnieuw verdelen, weigeringen; liftfactuur op de demodata |
| `test_distribution_rules.py` | Regel vult sleutel en rekening, handmatige sleutel blijft, automatisch verdelen bij boeken, geen regel geen verdeling, mislukte verdeling blokkeert boeken niet, één regel per leverancier; import van de Peppol-factuur van Residentie Linde |
| `test_provision_call.py` | Bedragen, bankrekeningen en rekeningen per fonds, één factuur per fonds voor een eigenaar met twee kavels, eigenaar op factuurdatum, gestructureerde mededeling, concept zonder boeken, weigeringen (dubbele oproep, onbevestigde rekening, nummer buiten budget), andere company geselecteerd, voorbeeld in een open formulier, VME zonder budget, 5%-regel |
| `test_annual_statement.py` | Saldo's, reservekapitaal niet afgerekend, controle op niet-verdeelde facturen, rapport; `TestAnnualStatementDemo` met een volledig demojaar (tag `vme_slow`) |

De trage test met een volledig demojaar (meer dan 10 minuten) draai je apart, vóór een demo en na wijzigingen aan de verdeling of de afrekening:

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie --test-enable --test-tags vme_slow --stop-after-init
```

Testklassen zijn `post_install` en `-at_install`, zodat het rekeningstelsel en Peppol geladen zijn. Wie de demodata in een test laadt, doet dat als admin en draait daarna `cls.env.cr.precommit.run()` (zie [valkuilen](valkuilen.md#multi-company)).

## Demo opbouwen

1. Database aanmaken (zie hierboven) en Odoo starten.
2. Demodata laden: in Odoo **VME > Configuratie > Demodata laden** (als admin), of:

   ```bash
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_data(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   ```

3. Demohistoriek 2026 laden (ongeveer een minuut): **VME > Configuratie > Demohistoriek 2026 laden**, of:

   ```bash
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_history(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   ```

Wat er dan in de demo zit:

| Onderdeel | Inhoud |
| --- | --- |
| VME's | Residentie Linde (20 kavels, algemene sleutel + liftsleutel), Hof ter Beuken (24 kavels, algemeen + verwarming), Kaaihuis (6 kavels, algemeen) |
| Eigenaars | "Eigenaar Linde A1" … met `@example.com`-adressen; A5/G5 in Linde verkocht op 1 juli 2026; één eigenaar voor B23 en B24 |
| Nummers | KBO- en btw-nummers beginnen met 0000; IBAN's gebruiken de onbestaande bankcode 999 |
| Leveranciers | Energie (alle VME's), lift (Linde); in de historiek ook schoonmaak, verzekering en gas |
| Budgetten | 2026 en 2027, per kwartaal; Hof ter Beuken onder de 5% |
| Historiek 2026 | Vier provisieoproepen, betalingen behalve A3 (oproep 4) en B7 (oproepen 3 en 4), leveranciersfacturen, drie Peppol-facturen elektriciteit |

De Peppol-voorbeeldfacturen staan in `addons/vme_belgie/demo_data/facturen/`; importeer ze in de company van de juiste VME via **Facturatie > Leveranciers > Facturen > Upload**. Na de demohistoriek zijn ze al ingelezen.

## Een tweede demo naast de eerste

Werkt iemand anders al op de gewone demo (poort 8069), bouw dan een eigen demo in een apart Docker-project op een eigen poort. Elk `-p <project>` heeft zijn eigen database-volume.

```bash
docker compose -p vme-docs run --rm odoo odoo -d vme_demo -i vme_belgie --load-language=nl_BE --stop-after-init
```

Laad demodata en historiek met dezelfde commando's als hierboven, telkens met `-p vme-docs` na `docker compose`. Start de server dan zonder `up` (dat zou ook poort 8069 vragen):

```bash
docker compose -p vme-docs run --rm -p 8370:8069 odoo -- --db-filter=^vme_demo$
```

Zet in die demo de systeemparameter `report.url` op `http://localhost:8069` en herstart, anders komen PDF's zonder opmaak (zie [valkuilen](valkuilen.md#pdfs-zonder-opmaak)).

## Schermafbeeldingen voor de kennisbank

De schermafbeeldingen in `docs/kb/img/` zijn gemaakt op zo'n tweede demo, met Playwright en Google Chrome op 1440 × 1000 pixels, ingelogd als admin met taal Nederlands (België). Maak ze opnieuw op een verse demo als een scherm verandert, en gebruik alleen demodata.

## LEGAL-CHECK-overzicht

```bash
python3 tools/legal_checks.py          # schrijft docs/dev/legal-checks.md
python3 tools/legal_checks.py --check  # faalt als het overzicht niet up-to-date is
```

Het script zoekt in `addons/` en `ai/` naar `# LEGAL-CHECK:` (en `<!-- LEGAL-CHECK: -->` in XML). De tekst na de bron loopt door op de volgende commentaarregels tot aan het einde van een zin.
