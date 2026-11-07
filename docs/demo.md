# Demoscenario: tien minuten, van mail tot jaarafrekening

Eén verhaal voor een pilotsyndicus of een investeerder. Het is begin november 2026 bij een syndicus met drie fictieve gebouwen. Een eigenaar meldt een lek, een leverancier mailt een factuur, er liggen offertes voor de gevel, de provisies en de AV's van 2027 moeten klaar, en aan het eind ziet de eigenaar zijn jaarafrekening in het portaal. Rode draad: **de software zet alles klaar, een mens beslist.**

Elke stap is nagekeken op een verse database met demodata en demohistoriek (7 november 2026). De bedragen hieronder gelden voor die volgorde.

> Alle gebouwen, eigenaars, bedragen en rekeningnummers zijn verzonnen. De Belgische regels zijn nog niet juridisch nagekeken.

## Vooraf (ongeveer 15 minuten, niet in de tien minuten)

In de map van het project, met Docker (OrbStack) aan.

1. **Verse database** (ongeveer 2 minuten):

   ```bash
   docker compose stop odoo
   docker compose exec db dropdb -U odoo --if-exists vme_demo
   docker compose run --rm odoo odoo -d vme_demo -i vme_belgie,vme_rentmeester,vme_website,vme_mail_plugin --load-language=nl_BE --stop-after-init
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_data(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_history(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   docker compose up -d odoo
   ```

2. **Python voor de scripts in `ai/`** (eenmalig, Python 3.10 of nieuwer):

   ```bash
   cd ai && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..
   ```

   Met een Anthropic-API-sleutel in `ai/.env` leest Claude de mails en offertes; zonder sleutel gebruikt u `--mock` of `--offline` (vaste antwoorden, zonder netwerk).

3. **De mails van eigenaars laten lezen** (ongeveer een minuut met Claude, een seconde met `--mock`):

   ```bash
   cd ai && .venv/bin/python assistant.py && cd ..
   ```

   Acht mails worden aanvragen of taken op de juiste VME. Live draaien duurt te lang voor de demo.

4. **De offertes voor de gevel laten vergelijken** (ongeveer 15 seconden): log in (stap 6), open **VME > Werken en schade > Werkdossiers > Gevelrenovatie voor- en achtergevel** en klik op **Offertes vergelijken**. Dan:

   ```bash
   cd ai && .venv/bin/python offertes.py && cd ..
   ```

5. **Twee browservensters op volledig scherm.**
   - Venster 1, de syndicus: http://localhost:8069, **Inloggen > Medewerker van de syndicus**, `admin` / `admin`. Kies rechtsboven het bedrijf **Residentie Linde** (de leveranciersfacturen staan per bedrijf; de schermen van de app VME tonen altijd alle VME's).
   - Venster 2, de eigenaar: een privévenster op **http://a1.localhost:8069** (een eigen hostnaam, zodat de twee sessies elkaar niet uitloggen). Log in met `eigenaar.linde.a1@example.com` / `portaal-demo` en laat **Mijn account** open staan.
   - Geeft de eerste login na het opbouwen "400 Bad Request", herlaad dan en log opnieuw in.

6. **Een terminal** in de map `ai`, met `.venv/bin/python facturen_mailgate.py --inbox demo_inbox` al getypt maar nog niet uitgevoerd.

## Het scenario

| # | Minuut | Wat | Waar |
| --- | --- | --- | --- |
| 1 | 0:00 | Uw dag in één lijst | VME > Mijn werk vandaag |
| 2 | 1:00 | Een eigenaar mailt een lek | Aanvraag van Linde A4 |
| 3 | 2:30 | Een leverancier mailt een factuur | terminal + Facturatie |
| 4 | 4:30 | Drie offertes, door de AI naast elkaar gelegd | VME > Werken en schade |
| 5 | 5:30 | Provisies 2027 voor alle gebouwen | VME > Provisieoproepen |
| 6 | 6:30 | De AV's van 2027 plannen | VME > Algemene vergaderingen |
| 7 | 7:30 | De jaarafrekening 2026 | Residentie Linde > Jaarafrekening |
| 8 | 9:00 | De eigenaar ziet zijn afrekening | portaal (venster 2) |

### 1. Uw dag in één lijst (1 minuut)

1. **VME > Mijn werk vandaag**: wat te laat is, vandaag of deze week vervalt, over alle gebouwen, gegroepeerd per urgentie.
2. Wijs aan:
   - **Vandaag**: *Defect of schade doorsturen naar een schadedossier, AANV/2026/0003 Dringend: waterlek in het plafond van mijn badkamer*. Die mail kwam vannacht binnen.
   - **Deze week**: *Keuring plannen: Lift blok A* (12 november). Onthoud die voor stap 3.
   - Overal **Concept**: rappels, bestellingen en AI-antwoorden die op een klik wachten.

> Zeg: "Uw dag begint met één lijst over al uw gebouwen, en alles wat naar buiten moet, staat klaar als concept."

*Als er iets misgaat:* de lijst is leeg of kort? Haal de filter **Mijn werk** weg (`admin` is dossierbeheerder van Linde en Hof ter Beuken, niet van Kaaihuis). Staat AANV/2026/0003 er niet, dan is stap 3 van "Vooraf" overgeslagen: draai `assistant.py --mock` (een seconde) en herlaad.

### 2. Een eigenaar mailt een lek (1,5 minuut)

1. Klik op **Openen** bij AANV/2026/0003.
2. Toon de aanvraag: VME **Residentie Linde**, kavel **A4**, soort **Defect of schade**, kanaal **E-mail**, en de oorspronkelijke mail eronder. Niemand heeft iets overgetikt.
3. Rechts in de historiek: **Voorgesteld antwoord van de AI-assistent (niet verstuurd)**, met wat de eigenaar intussen kan doen en wie de schade draagt.
4. Bovenaan de geplande taak *Defect of schade doorsturen naar een schadedossier*: de vaste procedure loopt verder, maar de medewerker kijkt het antwoord na en verstuurt het zelf.

> Zeg: "De AI leest de mail, vindt het gebouw en de kavel en schrijft een antwoord; uw medewerker beslist en verstuurt."

*Als er iets misgaat:* zonder API-sleutel komt het antwoord uit `--mock`, met plaatshouders zoals `[kavel erboven]`. Zeg dat erbij: de medewerker vult ze in.

### 3. Een leverancier mailt een factuur (2 minuten)

1. In de terminal, druk op Enter: de Keuringsdienst mailt de factuur van de liftinspectie naar het factuuradres van Residentie Linde.

   ```bash
   .venv/bin/python facturen_mailgate.py --inbox demo_inbox
   ```

   Uitvoer: *Residentie Linde: conceptfactuur KD-2026-1105 van Keuringsdienst Voorbeeld vzw, 217.80 EUR, ... sleutel: Liftsleutel*.
2. In venster 1: **Facturatie > Leveranciers > Leveranciersfacturen**, open de conceptfactuur **KD-2026-1105**. Leverancier, bedrag en btw komen uit de Peppol-e-factuur in bijlage; de **Verdeelsleutel** *Liftsleutel* vulde de verdeelregel voor deze leverancier in.
3. Klik op **Bevestigen**. De slimme knop **Verdeling** toont 12 eigenaars: alleen de appartementen, want garages gebruiken de lift niet.
4. Scroll naar de historiek: *Automatisch verdeeld over 12 eigenaars* en *Keuring van Lift blok A geregistreerd ... volgende keuring: 05/05/2027*.
5. **VME > Mijn werk vandaag**: de taak *Keuring plannen: Lift blok A* is weg.

> Zeg: "Eén mail van een leverancier: geboekt, verdeeld over de juiste eigenaars, en uw keuringsagenda is bijgewerkt. U klikte één keer."

*Als er iets misgaat:* geen conceptfactuur? Staat het bedrijf rechtsboven op Residentie Linde? De mail kan maar één keer per database (Odoo herkent haar Message-ID); een tweede keer gebeurt er niets. Plan B: importeer `addons/vme_belgie/demo_data/facturen/` via **Upload** in de lijst van leveranciersfacturen.

### 4. Drie offertes, door de AI naast elkaar gelegd (1 minuut)

1. **VME > Werken en schade > Offertevergelijkingen**, open *Offertevergelijking Gevelrenovatie voor- en achtergevel* (status **Concept**).
2. De **aandachtspunten** in het geel: het btw-tarief verschilt (6% tegenover 21%), het werkdossier vermeldt 44.000 € voor Bouwonderneming Denkbeeld terwijl de offerte 53.240 € incl. btw zegt, de stelling ontbreekt bij Renovatiebedrijf Voorbeeld.
3. In de **tabel**: klik op een paginanummer **(p. 2)**; de offerte opent op die bladzijde.
4. Benadruk: de samenvatting is neutraal, zonder aanbeveling. **Goedkeuren** en **Voor de AV** zijn de klik van de syndicus.

> Zeg: "Een avond offertes naast elkaar leggen wordt tien minuten nakijken, met de bron bij elk getal. De AV kiest; wij zetten de feiten klaar."

*Als er iets misgaat:* staat de vergelijking op **Wacht op AI**, draai `.venv/bin/python offertes.py --offline` (direct, zonder netwerk) en herlaad. Klik in het werkdossier niet opnieuw op **Offertes vergelijken**: dat zet een klaargezette vergelijking terug op "Wacht op AI".

### 5. Provisies 2027 voor alle gebouwen (1 minuut)

1. **VME > Provisieoproepen > Nieuwe provisieoproep**. VME's: alle drie. Budgetjaar *2027*, oproep *1*; laat de datums staan.
2. Het voorbeeld toont per VME werk- en reservekapitaal, en bij **Hof ter Beuken** de waarschuwing dat het reservekapitaal onder de wettelijke 5% van de lasten van vorig jaar zit.
3. **Maak provisieoproepen**: 82 facturen in een paar seconden, per eigenaar één voor werkkapitaal en één voor reservekapitaal, elk met de eigen bankrekening en een gestructureerde mededeling.

> Zeg: "Uw kwartaaloproep voor tweehonderd gebouwen is één wizard, en de 5%-regel bewaakt zichzelf."

*Als er iets misgaat:* een melding over onbevestigde bankrekeningen betekent dat de demodata niet als `admin` geladen is; bouw de database opnieuw op.

### 6. De AV's van 2027 plannen (1 minuut)

1. **VME > Algemene vergaderingen > AV-planner**, jaar *2027*, **Indeling voorstellen**.
2. Resultaat: Residentie Linde op 17 maart, Kaaihuis op 23 maart, Hof ter Beuken op 20 april, elk binnen de wettelijke periode van vijftien dagen en zonder dubbel geboekte zaal of medewerker. Alles staat op **Voorgesteld**; bevestigen doet de medewerker.
3. Vertel erbij (zonder te klikken): de eigenaars stemmen thuis mee in een hybride AV en ondertekenen de notulen in het portaal. Dat kan getoond worden in de extra vijf minuten.

> Zeg: "Uw AV-seizoen in één voorstel, binnen elke wettelijke termijn, en wie niet kan komen, stemt online."

*Als er iets misgaat:* een datum die afwijkt, komt van een eerdere proef op deze database; vink **Voorstellen opnieuw indelen** aan.

### 7. De jaarafrekening 2026 (1,5 minuut)

1. **VME > VME's > Residentie Linde**, knop **Jaarafrekening** (jaar 2026).
2. Bovenaan de **controle** in het groen: de som van alle aandelen (18.816,80 €) is gelijk aan de geboekte kosten, inclusief de liftfactuur van daarnet.
3. In de tabel: Eigenaar Linde A1 krijgt 547,83 € terug, A3 heeft nog 432 € provisies open staan, en de verkoper en de koper van A5 (verkocht op 1 juli) hebben elk hun eigen afrekening, pro rata hun dagen.
4. **Afdrukken (PDF)** en toon één pagina: kosten per sleutel, provisies, saldo, reservekapitaal apart, detail per factuur.

> Zeg: "De afrekening die u nu een week kost, staat klaar zodra de laatste factuur geboekt is, tot op de cent en ook bij een verkoop midden in het jaar."

*Als er iets misgaat:* een oranje controle noemt de factuur die nog niet verdeeld is; open ze en klik **Verdeel over eigenaars**. Komt de PDF als download in plaats van in een tabblad, open hem uit de downloads van de browser.

### 8. De eigenaar ziet zijn afrekening (1 minuut)

1. Venster 2 (Eigenaar Linde A1): herlaad **Mijn account** en klik op **Mijn mede-eigendom**, dan **Residentie Linde**.
2. Toon kort: zijn kavels A1 en G1, de volgende AV met de agenda, de stand van werk- en reservekapitaal, de provisies van 2026 en de nieuwe oproep van 2027 (stap 5), en de documenten van het gebouw.
3. Klik op **Jaarafrekening 2026 voorlopig**: *Saldo in uw voordeel 547,83 €*, en onderaan in de facturen *Keuringsdienst Voorbeeld vzw, KD-2026-1105*, zijn aandeel 7,84 €: de mail van de leverancier van zeven minuten geleden.
4. Vertel erbij: hij ziet nooit een ander gebouw of een andere kavel, en de verkoper van A5 ziet niets meer van na de verkoop.

> Zeg: "Van de mail van de leverancier tot de afrekening bij de eigenaar: niemand heeft iets overgetikt, en niets is vertrokken zonder een klik van uw medewerker."

*Als er iets misgaat:* toont **Mijn account** alleen "Adressen" en "Verbinding & Beveiliging", herlaad de pagina. Is de sessie verlopen, log opnieuw in op `a1.localhost`.

## Extra vijf minuten (op vraag)

Doe deze blokken na stap 8; ze veranderen niets aan de bedragen van het scenario hierboven, behalve blok A en D.

### A. Een factuur zonder regel zelf verdelen (1 minuut)

1. **Facturatie > Leveranciers > Leveranciersfacturen > Nieuw** (bedrijf Residentie Linde). Leverancier **Brandbeveiliging Voorbeeld BV** (kies de fictieve bovenaan, niet een resultaat van "Zoek wereldwijd"), factuurdatum vandaag, kostperiode 01/01/2026 tot 31/12/2026, lijn *Jaarlijks onderhoud brandblussers 2026*, 350 € met 21% btw.
2. Kies in de lijn de **Verdeelsleutel** *Algemene sleutel* en klik op **Verdeel over eigenaars**: 423,50 € over 13 eigenaars; de verkoper en de koper van A5 krijgen elk hun dagen.
3. Terug naar de factuur, **Bevestigen**. De jaarafrekening wordt 19.240,30 €; A1 krijgt dan 515,64 € terug.

> Zeg: "Geen Excel meer: btw is voor de VME een kost, en de verdeling klopt tot op de cent."

### B. Een gebouw overnemen met de basisakte (2 minuten)

Doe stap 1 en 2 vooraf; ze duren samen een minuut.

1. **VME > Configuratie > Overstap uit ander pakket > Nieuw.** Bij **Exportbestanden** de vier CSV-bestanden uit `addons/vme_belgie/demo_data/migratie/residentie-wilg/`; bij **Basisakte en notulen** `basisakte-scan.pdf`, `notulen-av-2025.pdf` en `notulen-av-2026.pdf` uit `residentie-wilg-documenten/`. Opslaan.
2. Terminal: `.venv/bin/python overname.py --mock` (altijd hetzelfde resultaat) of zonder `--mock` (Claude leest de scan).
3. In de demo: herlaad de overstap. *61 regels, 2 onzeker.* Tabblad **Aandelen en sleutels**: elke regel met bladzijde en fragment uit de akte; A2 en B3 zijn rood.
4. Klik op A2: het fragment toont "1?0", de AI zegt "Onleesbaar". **Document openen** toont de vlek op blz. 2. Typ 110 en **Aanvaarden**.
5. **Zekere regels aanvaarden**, B3 apart aanvaarden, **Proefrun**, **Importeren**: de VME met haar sleutels, twee werkdossiers uit de notulen, de raad en de commissaris.

> Zeg: "De AI leest de akte; uw medewerker kijkt elke regel na naast de bron, en het systeem telt alles na."

### C. Een hybride AV: online stemmen en ondertekenen (2 minuten)

Gebruik naast venster 2 een tweede eigenaar op een eigen hostnaam: `http://a6.localhost:8069`, `eigenaar.linde.a6@example.com` / `portaal-demo`. Dit kan maar één keer per database.

1. Venster 1: **VME > Algemene vergaderingen > AV's**, open **Buitengewone AV 2026 Residentie Linde: Laadpalen in de garage** (19 november, hybride). Tabblad **Online**: A7 gaf volmacht aan A1. Klik **Online onthaal openen**.
2. A1 en A6: **Mijn mede-eigendom > Residentie Linde > Online deelnemen en stemmen**, **Ik ben aanwezig (online)**.
3. Syndicus: bij de laadpalen **Stemming openen**. A1 stemt in één formulier voor zichzelf en voor A7. **Stemming sluiten**: de eigenaars zien de uitslag.
4. **Gehouden** en **Notulen ter ondertekening**; A1 ondertekent in het portaal. Tabblad **Ondertekening**: naam, tijdstip, IP-adres en vingerafdruk (SHA-256) van de PDF.

Te weinig aanwezigen voor het quorum? Zet enkele eigenaars op "Aanwezig" in de aanwezigheidslijst.

> Zeg: "Thuis meestemmen met dezelfde regels als in de zaal, en notulen die bewijsbaar ongewijzigd ondertekend zijn."

### D. Het boekjaar afsluiten (1 minuut)

1. Open **Residentie Linde** en klik op **Boekjaar afsluiten**. Kies het boekjaar *2026*. De controles tonen wat nog ontbreekt, bv. een factuur in concept; klik op de link, **Bevestig** de factuur en ga terug. Alleen "het boekjaar loopt nog" blijft oranje.
2. **Afrekening voorbereiden**: per eigenaar een concept-factuur of -creditnota. Bij A3 blijft de onbetaalde oproep een eigen factuur, en de verkoper en de koper van A5 krijgen elk hun deel.
3. **Resultaat en overdracht**: werkkapitaal 0,00 € na de afrekening, het reservekapitaal gaat naar 2027.
4. Benadruk: alles is een concept. **Alles bevestigen** boekt, maar verstuurt niets. **Boekjaar afsluiten** (alleen voor een beheerder) vergrendelt 2026. Doe dat in de demo niet, of heropen meteen: anders komen nieuwe facturen in 2027 terecht.

Op een verse database zonder het scenario hierboven waren het 13 concept-creditnota's, samen 4.334,51 €. Na stap 3 en blok A liggen de bedragen anders.

> Zeg: "De afrekening wordt geboekt met één klik van uw medewerker, en het jaar gaat dicht zonder dat er iets vertrekt."

### E. Een mail van een eigenaar in Outlook (2 minuten)

De AI-assistent heeft de mails al gelezen (stap 3 van "Vooraf"). Nu ziet de medewerker hetzelfde zonder Odoo te openen, in het paneel naast de mail.

**Zonder Outlook (browservoorbeeld, altijd mogelijk):**

1. Open http://localhost:8069/vme_mail_plugin/static/outlook/taskpane.html?demo=1 (ingelogd als `admin`), of **VME > Configuratie > Outlook-invoegtoepassing > Voorbeeld in de browser**. Bovenaan staat een keuzelijst met de acht fictieve mails; daaronder het paneel zoals in Outlook.
2. De eerste keer: **Verbinden met Odoo** en **Toestaan**. Zo verbindt een medewerker ook zijn echte Outlook.
3. Mail **01 (lek bij Linde A4)**: het paneel toont Residentie Linde, kavels A4 en G4, eigenaar, en het voorstel van de AI-assistent met *nog niet verstuurd*. Klik op **Antwoord invoegen**: het antwoordvenster toont het voorstel, en er is niets verstuurd.
4. Mail **02 (Beuken B7)**: onder **Wat staat er open** staan de achterstallige provisies van B7, met bedrag en vervaldag.
5. Mail **04 (lift, van een privéadres)**: de afzender is onbekend. Klik op **Koppeling van de AI-assistent gebruiken** (of zoek *Linde A11*) en maak met **Aanvraag maken** een aanvraag *Defect of schade*. Ze verschijnt meteen bij de open punten.
6. **Bewaren bij dossier** zet de mail als interne notitie bij de VME of de aanvraag, met de bijlagen (probeer mail 08).

**Met echte Outlook (vooraf voorbereiden):** start https met `docker compose --profile outlook up -d`, vertrouw het certificaat en zet het adres `https://localhost:8443` in **VME > Configuratie > Outlook-invoegtoepassing** (zie `docs/dev/outlook.md`). Download het manifest en voeg het toe in Outlook op het web (**Apps > Mijn invoegtoepassingen > Aangepaste invoegtoepassing toevoegen > Toevoegen vanuit bestand**). Zet uw eigen testadres tijdelijk op een fictieve eigenaar (bv. Eigenaar Linde A4), **alleen in uw lokale database**, nooit in git of de demodata, en stuur uzelf de lekmail. Het paneel herkent u dan als eigenaar van A4.

> Zeg: "Uw medewerkers blijven in Outlook en zien bij elke mail het gebouw, de kavel en wat er openstaat, met een antwoord klaar om na te kijken. Verzenden blijft hun klik."

## Op vraag tonen

Elk onderwerp heeft een artikel in **VME > Help** met de stappen en een voorbeeld uit de demodata.

| Vraag | Waar in Odoo | Kennisbank |
| --- | --- | --- |
| "Hoe zie ik al mijn gebouwen?" | VME > Portefeuille, VME > Jaarcyclus | `docs/kb/gebouwkaart.md`, `docs/kb/jaarcyclus.md` |
| "En de keuringen?" | VME > Keuringen > Installaties en vervaldata | `docs/kb/keuringen.md` |
| "Een verkoop, de notaris?" | VME > Verkoopdossiers, *Verkoop A3, G3 Residentie Linde* | `docs/kb/verkoop-notaris.md` |
| "Sleutels en badges?" | VME > Aanvragen (AANV/2026/0006 en 0007 uit de mails) | `docs/kb/aanvragen-sleutels-badges.md` |
| "Werken en schade?" | VME > Werken en schade > Werkdossiers en Schadedossiers | `docs/kb/werken.md`, `docs/kb/schadegevallen.md` |
| "Brandverzekering en attesten?" | Hof ter Beuken, tabblad Verzekering en attesten | `docs/kb/verzekeringen-en-attesten.md` |
| "Mijn eigen ereloon en mandaat?" | VME > Syndicus | `docs/kb/ereloon-en-mandaat.md` |
| "De commissaris van de rekeningen?" | Residentie Linde, tabblad Raad en commissaris | `docs/kb/raad-en-commissaris.md` |
| "Balans en resultatenrekening?" | Residentie Linde, knop Balans en resultatenrekening | `docs/kb/balans-en-resultatenrekening.md` |
| "Brieven en mails aan eigenaars?" | VME > Communicatie > Verzendingen | `docs/kb/communicatie.md` |
| "Huur en rentmeesterij?" | Rentmeester (bedrijf Rentmeester Voorbeeld BV aanvinken) | `docs/kb/rentmeester.md`, `docs/kb/doorstorting-verhuurder.md` |
| "En als we van syndicus wisselen?" | Residentie Linde, knop Overdracht aan nieuwe syndicus | `docs/kb/overdracht-syndicus.md` |
| "De fiches 281.50 voor Belcotax?" | VME > Fiches 281.50 | `docs/kb/fiches-281-50.md` |
| "De website?" | http://localhost:8069 in een privévenster | `docs/kb/website-en-inloggen.md` |

## Na de demo

- De database is niet meer vers: de factuur, de provisieoproep 2027, de AV-planning en de AI-aanvragen staan erin. Bouw ze opnieuw op voor een volgende demo.
- Stap 3 kan maar één keer per database (Message-ID); blok C ook maar één keer.
- Lever **niet** de mails in `ai/facturen_inbox/` aan op een demo met historiek: die elektriciteitsfacturen zitten al in de historiek en zouden dubbel geboekt worden.

## Bekende aandachtspunten

- **De demodatums liggen vast rond 5 november 2026.** Op een latere dag staat meer in "Te laat" (bv. het AI-antwoord voor A8) en meer keuringen in het rood. De jaarcyclus draait elke nacht op de echte datum: vanaf 10 november zet hij de AV 2027 van Kaaihuis klaar, vanaf 18 december de provisieoproep 1 van 2027. Bouw de database dan opnieuw op.
- **"Zoek wereldwijd" bij een leverancier** toont echte Belgische bedrijven uit Odoo's bedrijvengegevens. Kies altijd de fictieve leverancier bovenaan.
- **"Your logo"** bovenaan de PDF's is Odoo's plaatshouder zolang de syndicus geen logo opgeladen heeft.
- **"My Company"** in de bedrijvenkiezer is Odoo's eigen startbedrijf; het hoort niet bij de demo. Kies Residentie Linde.
- **Een paar Odoo-knoppen zijn nog Engels** (bv. "Journal Items" op een factuur): dat zijn vertalingen van Odoo zelf.
- **Oproepingen van een AV aanmaken duurt ongeveer een minuut** voor twaalf eigenaars (twee PDF's per eigenaar); daarom zit dat niet in het scenario.
