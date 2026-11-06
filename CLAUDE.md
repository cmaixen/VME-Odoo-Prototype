# VME-platform op Odoo: prototype

## Doel

Een werkend prototype van een syndicusplatform op Odoo 19, om te tonen aan een pilotsyndicus (ongeveer 200 VME's) en aan investeerders. Het prototype hoeft niet productieklaar te zijn, maar moet een geloofwaardige demo geven van:

1. VME's, kavels, quotiteiten en verdeelsleutels
2. Een leveranciersfactuur automatisch verdelen over de eigenaars
3. Provisieoproepen voor werk- en reservekapitaal
4. Een jaarafrekening per eigenaar
5. Een AI-assistent die inkomende mails van eigenaars aan de juiste VME en kavel koppelt en een antwoord voorstelt

## Harde regels

- **Alleen fictieve data.** Nooit echte namen, adressen, e-mailadressen of rekeningnummers van eigenaars of VME's. Gebruik verzonnen gebouwen zoals "Residentie Linde" en eigenaars zoals "Eigenaar A1".
- **Odoo 19 Community.** Het prototype moet draaien zonder Enterprise-licentie. Gebruik geen code uit het Enterprise-pakket "Property Owner Association" (condominium, licentie OEEL-1) en kopieer er niets uit.
- **Eigen modules:** `vme_belgie` in `addons/` voor alles van de VME. De rentmeesterij (huur, indexering, afrekening aan huurders) staat apart in `vme_rentmeester`, omdat de huur bij de verhuurder hoort en niet bij de VME (zie `docs/beslissingen.md`). De productwebsite met de knop Inloggen staat in `vme_website` (hangt af van `website` en `website_crm`), zodat `vme_belgie` geen website nodig heeft. Splits verder pas op als dat nodig is.
- **Code en technische namen in het Engels**, labels en gebruikersteksten in het Nederlands. Vertalingen naar het Frans komen later via `.po`-bestanden.
- **Elke stap werkt voor je verder gaat.** Na elke wijziging: module upgraden, Odoo-log nakijken op fouten, en de functie in de browser testen.
- **Een mens beslist altijd.** Niets naar buiten vertrekt vanzelf: bestellingen (bv. bij de slotenmaker), brieven, rappels, betalingen en antwoorden van de AI staan als concept klaar en een medewerker verstuurt ze. Bouw ook geen haak of instelling om dat later automatisch te maken.
- **Belgische regels zijn nog niet juridisch gevalideerd.** Markeer elke wettelijke regel in de code met een commentaar `# LEGAL-CHECK:` en de bron (artikel Burgerlijk Wetboek of KB).

## Omgeving

- `docker compose up -d` start Odoo op http://localhost:8069 met PostgreSQL.
- De map `addons/` is gemount als extra addons-pad.
- Module upgraden: `docker compose run --rm odoo odoo -d vme_demo -u vme_belgie,vme_rentmeester,vme_website --stop-after-init`. Gebruik `run`, niet `exec`: alleen via `run` geeft het entrypoint de databaseverbinding mee; `exec` blijft hangen.
- Database opnieuw aanmaken: `docker compose run --rm odoo odoo -d vme_demo -i vme_belgie,vme_rentmeester,vme_website --load-language=nl_BE --stop-after-init` (installeert ook `account`, `l10n_be`, `account_peppol`, `website` en `crm`)
- Logs: `docker compose logs -f odoo`
- Database voor de demo: `vme_demo`, met de modules `account`, `l10n_be`, `account_peppol`, `vme_belgie`, `vme_rentmeester` en `vme_website`. Op http://localhost:8069 staat dan de productwebsite (werktitel Quotis, zie `docs/dev/website.md`); **Inloggen** brengt medewerkers naar de app VME en eigenaars naar hun portaal.
- Unittests op een aparte database: `docker compose run --rm odoo odoo -d vme_test -u vme_belgie,vme_rentmeester,vme_website --test-enable --test-tags /vme_belgie,/vme_rentmeester,/vme_website --stop-after-init` (ongeveer 20 seconden).
- De trage test met een volledig demojaar staat apart (tag `vme_slow`, meer dan 10 minuten): `docker compose run --rm odoo odoo -d vme_test -u vme_belgie,vme_rentmeester --test-enable --test-tags vme_slow --stop-after-init`. Draai die vóór een demo of na wijzigingen aan de afrekening. Duurt hij langer dan een paar minuten, dan heeft de testdatabase slechte statistieken na veel testruns: draai eerst `docker compose exec db psql -U odoo -d vme_test -c "VACUUM ANALYZE"` (dan ongeveer 30 seconden).
- Demodata laden (drie fictieve VME's): in Odoo via **VME > Configuratie > Demodata laden**, of op de commandline: `echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_data(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http`. Draai het als admin: Odoo laat de systeemgebruiker geen bankrekeningen bevestigen, en zonder bevestigde rekeningen staan ze niet op de provisieoproepen. Laadt maar één keer; voor een verse demo eerst de database opnieuw aanmaken (Odoo stoppen, `docker compose exec db dropdb -U odoo vme_demo`, aanmaken, laden, Odoo starten).
- Demohistoriek 2026 laden (provisieoproepen, betalingen en leveranciersfacturen; ongeveer een minuut), ná de demodata: **VME > Configuratie > Demohistoriek 2026 laden**, of `echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_history(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http`. Daarna toont **VME > Jaarafrekening** voor 2026 een volledig jaar.
- Het demoscenario van tien minuten, met de voorbereiding, staat in `docs/demo.md`.
- De lopende server dient alleen `vme_demo` (`--db-filter` in `docker-compose.yml`); tests en shell-commando's via `docker compose run` geven hun eigen database mee.
- Fictieve exportbestanden voor een overstap uit een ander pakket (Residentie Esdoorn, met en zonder bewuste fouten) staan in `addons/vme_belgie/demo_data/migratie/`. Laad ze op via **VME > Configuratie > Overstap uit ander pakket**; het formaat staat in `docs/dev/migratie.md`.
- Fictieve Peppol-facturen (UBL BIS Billing 3.0) voor de demo staan in `addons/vme_belgie/demo_data/facturen/`, één per VME. Importeer ze in de company van die VME via **Facturatie > Leveranciers > Facturen > Upload**; de verdeelregels vullen sleutel en rekening in en bij "Bevestigen" wordt automatisch verdeeld.

## Domeinbegrippen

| Begrip | Betekenis | Technisch |
| --- | --- | --- |
| VME | Vereniging van mede-eigenaars, eigen rechtspersoon met KBO-nummer | `vme.association`, gekoppeld aan een `res.company` per VME |
| Kavel | Privatief deel (appartement, garage, berging) | `vme.lot` |
| Quotiteit | Aandeel in de gemene delen, meestal in duizendsten | veld op `vme.key.line` |
| Verdeelsleutel | Regel om kosten te verdelen: algemeen, lift, verwarming, op verbruik | `vme.key` met lijnen per kavel |
| Eigenaar | Partner met eigendom van een kavel, met begin- en einddatum | `vme.ownership` |
| Werkkapitaal | Voorschotten voor de gewone werking, afgerekend per jaar | apart journaal of rekening |
| Reservekapitaal | Opbouw voor grote werken, niet terugvorderbaar bij verkoop | apart journaal of rekening |
| Provisieoproep | Periodieke vraag tot betaling aan elke eigenaar | facturen per eigenaar |
| Jaarafrekening | Werkelijke kosten per sleutel min betaalde provisies, per eigenaar | QWeb-rapport |

## Belgische regels voor het prototype

- Elke VME is een aparte company met eigen boekhouding. Werk- en reservekapitaal zitten op aparte bankrekeningen. `# LEGAL-CHECK: art. 3.89 §5 BW`
- Jaarlijkse minimale opbouw van het reservefonds: 5% van de gewone gemeenschappelijke lasten van het vorige jaar, tenzij de AV met 4/5 anders beslist. `# LEGAL-CHECK: art. 3.86 §3 BW`
- Bij verkoop van een kavel worden kosten pro rata verdeeld tussen verkoper en koper op basis van de eigendomsdatums.
- De meeste VME's zijn niet btw-plichtig: btw op leveranciersfacturen is voor hen een kost.

## Architectuur van de AI-assistent

- Een los Python-script in `ai/` leest fictieve mails uit `ai/inbox/` (één `.eml` of `.txt` per mail).
- Het script haalt via de Odoo JSON-RPC-API de VME's, kavels en eigenaars op, laat een taalmodel bepalen over welke VME, kavel en welk onderwerp de mail gaat, en maakt een concept-antwoord.
- Het resultaat wordt als activiteit of bericht op de juiste VME in Odoo gezet, zodat een medewerker het kan nakijken en versturen. Er wordt nooit automatisch iets verstuurd.
- De API-sleutel van het taalmodel staat in `ai/.env`, nooit in de code of in git.

## Werkwijze

- Werk met kleine stappen en gebruik plan mode voor elke nieuwe functie.
- Schrijf voor de rekenlogica (verdeling, provisies, afrekening) unittests in `addons/vme_belgie/tests/`.
- Hou `docs/beslissingen.md` bij: elke ontwerpkeuze in twee zinnen.
- Werk bij elke stap ook de documentatie bij, in hetzelfde commit:
  - `docs/kb/`: de kennisbank voor syndici en hun medewerkers, in het Nederlands en zonder technische termen. Per functie een artikel "Hoe doe ik …?" met de stappen in Odoo, een voorbeeld uit de demodata en de veelgestelde vragen.
  - `docs/dev/`: de interne ontwikkelaarsdocumentatie. Architectuur, datamodel, hoe een berekening werkt, uitbreidingspunten in Odoo die we overschrijven, valkuilen die we tegenkwamen, en hoe je test en de demo opbouwt.
  - Een nieuw kennisbankartikel krijgt een item in het menu **VME > Help** (`addons/vme_belgie/data/help_menu.xml`). Na een wijziging aan een `# LEGAL-CHECK:` draai je `python3 tools/legal_checks.py`, dat `docs/dev/legal-checks.md` bijwerkt.
