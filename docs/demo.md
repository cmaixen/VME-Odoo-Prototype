# Demoscenario: tien minuten voor een syndicus

Een rondgang langs het werk van een syndicus, op de fictieve demo. Het verhaal: het is 5 november 2026. Er komt een factuur binnen, er moet een factuur zonder regel verdeeld worden, de jaarafrekening 2026 staat klaar, de provisies voor 2027 moeten de deur uit, er vervalt een keuring, het AV-seizoen 2027 moet gepland worden en een eigenaar meldt een lek.

Elke stap is nagekeken op een verse database met demodata en demohistoriek.

> Alle gebouwen, eigenaars, bedragen en rekeningnummers zijn verzonnen. De Belgische regels zijn nog niet juridisch nagekeken.

## Vooraf (niet in de tien minuten)

Draai dit ongeveer 15 minuten voor de demo, in de map van het project. Docker (OrbStack) moet draaien.

1. **Verse database** (ongeveer 3 minuten):

   ```bash
   docker compose stop odoo
   docker compose exec db dropdb -U odoo --if-exists vme_demo
   docker compose run --rm odoo odoo -d vme_demo -i vme_belgie --load-language=nl_BE --stop-after-init
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_data(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_history(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   docker compose up -d odoo
   ```

2. **Python-omgeving voor de scripts in `ai/`** (eenmalig; Python 3.10 of nieuwer, bv. `python3.12`):

   ```bash
   cd ai && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..
   ```

   Met een Anthropic-API-sleutel in `ai/.env` schrijft de AI-assistent echte antwoorden met Claude; zonder sleutel gebruikt u `--mock` (vaste sjablonen met plaatshouders zoals `[datum]`).

3. **Inloggen** op http://localhost:8069 met `admin` / `admin`, in een browservenster op volledig scherm. Werkt de eerste login na het opbouwen niet ("400 Bad Request"), herlaad de pagina en log opnieuw in.

4. **Zet bovenaan rechts het bedrijf op Residentie Linde** (bedrijvenkiezer). De schermen van de app VME tonen altijd alle VME's; de facturen ziet u per bedrijf.

5. **Optioneel, om wachten te vermijden:** maak de oproepingen van de AV vooraf aan (stap 7). Dat duurt ongeveer een minuut, omdat Odoo per eigenaar twee PDF's maakt.

## Het scenario

| # | Minuut | Wat | Waar |
| --- | --- | --- | --- |
| 1 | 0:00 | Het gebouw | VME > VME's |
| 2 | 1:00 | Een factuur komt binnen per mail en verdeelt zichzelf | terminal + Facturatie |
| 3 | 3:00 | Een factuur zonder regel zelf verdelen | Facturatie |
| 4 | 4:00 | De jaarafrekening 2026 | VME > Jaarafrekening |
| 5 | 5:30 | Provisieoproep 2027 voor alle VME's | VME > Provisieoproepen |
| 6 | 6:30 | Keuringen en opmerkingen | VME > Keuringen |
| 7 | 7:30 | Het AV-seizoen 2027 plannen | VME > Algemene vergaderingen |
| 8 | 8:30 | Een mail van een eigenaar, een voorgesteld antwoord | terminal + VME |

### 1. Het gebouw (1 minuut)

- **VME > VME's**: drie gebouwen, elk een eigen bedrijf met eigen boekhouding, KBO-nummer en twee bankrekeningen (werk- en reservekapitaal).
- Open **Residentie Linde**: 20 kavels, 12 eigenaars, twee verdeelsleutels.
- Tabblad **Kavels**: A5 en G5 zijn op 1 juli 2026 verkocht. Open A5 om de verkoper (tot 30/06) en de koper (vanaf 01/07) te tonen.
- **Verdeelsleutels**: de algemene sleutel telt exact op tot 1.000; een sleutel die niet klopt kan niet opgeslagen worden.

> Boodschap: "Uw basisakte zit erin, en het systeem weet op elke dag wie eigenaar is."

### 2. Een factuur komt binnen per mail (2 minuten)

1. In een terminal: de Keuringsdienst mailt de factuur voor de liftinspectie naar het factuuradres van Residentie Linde.

   ```bash
   cd ai && .venv/bin/python facturen_mailgate.py --inbox demo_inbox
   ```

   Uitvoer: *Residentie Linde: conceptfactuur KD-2026-1105 van Keuringsdienst Voorbeeld vzw, 217.80 EUR, sleutel: Liftsleutel*.

2. In Odoo: **Facturatie > Leveranciers > Facturen**, open de conceptfactuur **KD-2026-1105**.
   - Leverancier, bedrag en btw komen uit de Peppol-e-factuur in bijlage; niemand heeft iets overgetikt.
   - **Verdeelsleutel**: *Liftsleutel*, ingevuld door de verdeelregel voor deze leverancier.
3. Klik op **Bevestigen**.
   - De slimme knop **Verdeling** toont 12 eigenaars: alleen de appartementen, want garages gebruiken de lift niet.
   - In de historiek: *"Automatisch verdeeld over 12 eigenaars"* en *"Keuring van Lift blok A geregistreerd op 05/11/2026 … volgende keuring: 05/05/2027"*.
4. **VME > Keuringen**: de lift stond oranje (vervalt 12 november) en staat nu groen.

> Boodschap: "Eén mail van een leverancier: geboekt, verdeeld over de juiste eigenaars, en uw keuringsagenda is bijgewerkt."

### 3. Een factuur zonder regel zelf verdelen (1 minuut)

1. **Facturatie > Leveranciers > Facturen > Nieuw** (bedrijf Residentie Linde).
2. Leverancier **Brandbeveiliging Voorbeeld BV**, factuurdatum vandaag, kostperiode 01/01/2026 tot 31/12/2026, lijn *Jaarlijks onderhoud brandblussers 2026*, 350 € (21% btw).
3. Kies in de lijn de **Verdeelsleutel** *Algemene sleutel* en klik op **Verdeel over eigenaars**: 423,50 € over 13 eigenaars; de verkoper en de koper van A5 krijgen elk hun dagen.
4. Ga terug naar de factuur en klik op **Bevestigen**.

> Boodschap: "Geen Excel meer: één klik, tot op de cent, ook bij een verkoop midden in het jaar."

### 4. De jaarafrekening 2026 (1,5 minuut)

1. **VME > Jaarafrekening**, VME *Residentie Linde*, jaar *2026*.
2. Bovenaan staat de **controle** in het groen: de som van alle aandelen is gelijk aan de geboekte kosten (19.240,30 € na stap 2 en 3).
3. In de tabel: eigenaar A1 krijgt 515,64 € terug, A3 heeft nog 432 € open staan, en de verkoper en de koper van A5 hebben elk hun eigen afrekening.
4. Klik op **Afdrukken (PDF)** en toon één pagina: kosten per sleutel, provisies, saldo, reservekapitaal apart, detail per factuur.
5. Kies daarna *Hof ter Beuken*: daar moeten de eigenaars bijbetalen, door de gasfactuur van de centrale verwarming.

> Boodschap: "De afrekening die u nu een week kost, staat klaar zodra de laatste factuur geboekt is."

### 5. Provisieoproep 2027 (1 minuut)

1. **VME > Provisieoproepen > Nieuwe provisieoproep**.
2. VME's: alle drie. Budgetjaar *2027*, oproep *1*, factuurdatum 15/12/2026, vervaldatum 15/01/2027.
3. Het voorbeeld toont per VME de bedragen en bij **Hof ter Beuken** de waarschuwing dat het reservefonds onder de wettelijke 5% zit.
4. **Maak provisieoproepen**: 82 facturen, per eigenaar één voor werkkapitaal en één voor reservekapitaal, elk met de eigen bankrekening en een gestructureerde mededeling.

> Boodschap: "Uw kwartaaloproep voor 200 VME's: één wizard, en de 5%-regel bewaakt zichzelf."

### 6. Keuringen en opmerkingen (1 minuut)

1. **VME > Keuringen > Installaties en vervaldata**: rood = vervallen (brandblussers Residentie Linde), oranje = binnen 30 dagen (rookluiken Hof ter Beuken), blauw = binnen 60 dagen.
2. Klik rechtsboven op het **kalendericoon** voor dezelfde vervaldata in een kalender.
3. **VME > Keuringen > Opmerkingen keuringen**, filter **Over termijn**: *"Noodverlichting in de liftkooi werkt niet"* (ernstig, termijn 31/08/2026) staat in het rood.
4. Het activiteitenicoon bovenaan toont de taken die Odoo zelf maakte voor keuringen die binnen 60 dagen vervallen.

> Boodschap: "Geen vergeten keuring meer, en elke opmerking uit een liftverslag wordt opgevolgd tot ze opgelost is."

### 7. Het AV-seizoen 2027 plannen (1 minuut)

1. **VME > Algemene vergaderingen > AV-planner**, jaar *2027*, **Indeling voorstellen**.
2. Resultaat: Residentie Linde op 17 maart, Kaaihuis op 23 maart, Hof ter Beuken op 20 april. Linde en Kaaihuis wilden allebei 17 maart, maar die zaal heeft plaats voor één AV: Linde krijgt voorrang omdat haar periode op 18 maart afloopt.
3. Open de AV van Residentie Linde en klik op **Bevestigen**: de afspraak staat in de agenda van de medewerker (knop **Agenda**).
4. **Oproepingen aanmaken** (of toon de vooraf aangemaakte): twaalf concepten, met per eigenaar de quotiteiten, een volmachtformulier en de jaarafrekening in bijlage. A5 gaat naar de nieuwe eigenaar. Er wordt niets automatisch verstuurd.
5. Optioneel: **VME > Algemene vergaderingen > Register van beslissingen** toont de beslissingen van de AV 2026.

> Boodschap: "Uw AV-seizoen in één voorstel, binnen elke wettelijke periode, zonder dubbele boekingen."

### 8. Een mail van een eigenaar (1,5 minuut)

1. In de terminal: de AI-assistent leest de mails van eigenaars.

   ```bash
   cd ai && .venv/bin/python assistant.py          # met API-sleutel (Claude)
   cd ai && .venv/bin/python assistant.py --mock   # zonder API-sleutel
   ```

   Per mail toont hij de VME, de kavel, het onderwerp en de urgentie.
2. In Odoo: open **Residentie Linde**. Bij **Geplande activiteiten** staat *"AI-voorstel: Lek of waterschade (A4)"* voor vandaag. Klik op het **i**-icoontje voor de oorspronkelijke mail en het conceptantwoord.
3. Benadruk: de assistent verstuurt nooit zelf iets. De medewerker kijkt het antwoord na, vult de plaatshouders in en verstuurt het.

> Boodschap: "Uw inbox gesorteerd per gebouw en kavel, met een antwoord klaar om na te kijken."

## Na de demo

- De demo is daarna niet meer "vers": de factuur, de provisieoproep 2027, de AV-planning en de AI-taken staan erin. Bouw de database opnieuw op met de commando's hierboven voor een volgende demo.
- Stap 2 kan maar één keer per database: Odoo herkent de mail aan haar Message-ID en verwerkt ze geen tweede keer.
- Lever **niet** de mails in `ai/facturen_inbox/` aan op een demo met historiek: die elektriciteitsfacturen zitten al in de historiek en zouden dubbel geboekt worden. Ze zijn bedoeld voor een demo zonder historiek.

## Bekende aandachtspunten tijdens de demo

- **Oproepingen aanmaken duurt ongeveer een minuut** voor 12 eigenaars (twee PDF's per eigenaar). Maak ze vooraf aan of vertel er intussen iets bij. Voor honderden VME's moet dit later sneller.
- **"Zoek wereldwijd" bij het kiezen van een leverancier** toont echte Belgische bedrijven uit Odoo's eigen bedrijvengegevens. Kies altijd de fictieve leverancier bovenaan de lijst.
- **De demodatums liggen vast rond 5 november 2026.** Wie de demo veel later toont, ziet meer keuringen in het rood.
- **"Your logo"** bovenaan de PDF is Odoo's plaatshouder zolang er geen logo van de syndicus is.
