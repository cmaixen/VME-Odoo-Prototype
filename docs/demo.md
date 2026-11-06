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
   docker compose run --rm odoo odoo -d vme_demo -i vme_belgie,vme_rentmeester,vme_website --load-language=nl_BE --stop-after-init
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_data(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_history(); env.cr.commit()" | docker compose run --rm -T odoo odoo shell -d vme_demo --no-http
   docker compose up -d odoo
   ```

2. **Python-omgeving voor de scripts in `ai/`** (eenmalig; Python 3.10 of nieuwer, bv. `python3.12`):

   ```bash
   cd ai && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..
   ```

   Met een Anthropic-API-sleutel in `ai/.env` schrijft de AI-assistent echte antwoorden met Claude; zonder sleutel gebruikt u `--mock` (vaste sjablonen met plaatshouders zoals `[datum]`). De offertevergelijking (`offertes.py`) valt zonder sleutel vanzelf terug op haar testmodus.

3. **Inloggen**: open http://localhost:8069 (de productwebsite), klik op **Inloggen > Medewerker van de syndicus** en log in met `admin` / `admin`, in een browservenster op volledig scherm. U komt meteen in de app VME. Werkt de eerste login na het opbouwen niet ("400 Bad Request"), herlaad de pagina en log opnieuw in.

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
5. Kies daarna *Hof ter Beuken*: daar betalen de grote verbruikers bij en krijgen de kleine geld terug, door de gasfactuur van de centrale verwarming. Die is verdeeld op verbruik (30% vast, 70% volgens de kostenverdelers): onder de verwarmingssleutel staat per eigenaar zijn verbruik.
6. Open de VME *Residentie Linde* en klik op **Balans en resultatenrekening**, boekjaar *2026*: de balans sluit (groene controle), de kosten staan per rubriek van het wettelijke rekeningstelsel, en wat overblijft, gaat per fonds naar 2027. Toon de PDF; de commissaris van de rekeningen kan hetzelfde openen voor zijn VME.

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

### Extra: een badge aanvragen, eigenaar of huurder (1,5 minuut)

Na stap 8 staan er ook drie aanvragen in **VME > Aanvragen**, naast de sleutel voor Beuken B3 die de demohistoriek al klaarzette.

1. **Eigenaar Linde A4** vraagt een extra badge: meteen geverifieerd. Toon het tabblad **Berichten** (de bestelling aan Slotenmaker Voorbeeld BV, met het sleutelcertificaat) en de bestelbon in bijlage. Klik op **Bestelling versturen**, vul een nummer in (bv. BA-L-101) en klik op **Levering registreren**: de badge staat in het register van A4 en de eigenaar krijgt een factuur van 25 euro.
2. **Huurder Linde A6** vraagt een sleutel zonder bewijs: de aanvraag wacht op de toestemming van de eigenaar en het huurcontract. **Bewijs goedkeuren** weigert; **Bewijs opvragen** stuurt de vraag en plant een herinnering na 7 dagen.
3. **Huurder Beuken B12** stuurde de toestemming en het huurcontract mee: ze staan in het tabblad **Bewijs**. Vink beide aan en klik op **Bewijs goedkeuren**: de bestelling staat klaar.
4. Optioneel: het verkoopdossier van Linde A3 toont in het antwoord aan de notaris de uitgereikte sleutels en badges.

> Boodschap: "De vaste procedures lopen vanzelf, maar niets vertrekt zonder uw klik."

### Extra: een verkoop, de notaris vraagt inlichtingen (1 minuut)

1. **VME > Verkoopdossiers**: het dossier *Verkoop A3, G3 Residentie Linde* staat oranje. Notariskantoor Voorbeeld vroeg op 28 oktober inlichtingen; het antwoord moet er binnen 15 dagen zijn, dus uiterlijk op 12 november.
2. Open het dossier. Het tabblad **Antwoord aan de notaris** toont het antwoord, samengesteld uit de boekhouding en de AV:
   - het reservekapitaal en het aandeel van A3 en G3,
   - de onbetaalde vierde provisie van A3 (475,20 euro),
   - het aandeel in de dakwerken die de AV van maart besliste (2.736 euro op 38.000 euro),
   - de lopende procedures.
3. Klik op **Antwoord eerste vraag (PDF)**: de PDF komt in de chatter en de taak is afgevinkt. Doorsturen naar de notaris doet de medewerker zelf.
4. Vertel erbij: bij de akte klikt de syndicus op **Akte verleden**, en vanaf dan gaan kosten en provisies naar de koper. Odoo zet dan ook een concept-welkomstbrief voor de koper klaar (knop **Welkomstbrief**).

> Boodschap: "Een vraag van de notaris is twee minuten werk in plaats van een half uur zoeken, en de termijn ontsnapt u niet."

### Extra: het kantoor van de syndicus (1 minuut)

1. **VME > Syndicus > Beheerovereenkomsten**: Residentie Linde rekent 14 euro per kavel per maand aan, geïndexeerd met de consumptieprijsindex; het tarief van vandaag staat ernaast.
2. **VME > Syndicus > Prestaties**: de aangifte van de waterschade van A4 staat klaar om te factureren. Beantwoord de notaris in het verkoopdossier van A3 (zie hieronder) en er komt een prestatie bij.
3. **VME > Syndicus > Ereloonfacturen**: de facturen van het derde kwartaal zijn bevestigd. Open die van Residentie Linde en klik op **Factuur in de VME**: in Linde wacht de leveranciersfactuur als concept op goedkeuring, met de algemene sleutel en de rekening "Andere erelonen".
4. **VME > Syndicus > Mandaten**: het mandaat in Linde loopt tot 11 maart 2027 en staat oranje (herbenoeming op de AV van maart 2027). Plan de AV's van 2027 (stap 7): het agendapunt staat er vanzelf op. In Kaaihuis is de aanstelling nooit aangeplakt: **Aanplakbrief maken** zet de PDF bij de documenten.

> Boodschap: "Uw eigen omzet en uw mandaat in hetzelfde platform, en geen prestatie die u vergeet aan te rekenen."

### Extra: werken en een schadegeval (1 minuut)

1. **VME > Werken en schade > Werkdossiers**: *Renovatie plat dak blok A* van Residentie Linde, aan beslissing 2026/06 van de AV. Toon het tabblad **Offertes**: drie offertes naast het budget van 38.000 euro, gegund aan de goedkoopste (36.450 euro). De oranje melding toont dat het reservekapitaal niet volstaat.
2. Optioneel: kies rechtsboven Residentie Linde, upload `addons/vme_belgie/demo_data/facturen/voorschot_dakwerken_residentie_linde_2026-11.xml` bij de leveranciersfacturen en bevestig: de factuur hangt aan het dossier, is verdeeld en ten laste van het reservekapitaal geboekt.
3. **Schadedossiers**: *Waterschade badkamer A4*, uit de mail van A4 (zie stap 8), aangegeven bij de verzekeraar op 3 november, expertise op 12 november.

> Boodschap: "Van AV-beslissing tot oplevering in één dossier, en geen aangiftetermijn die ontsnapt."
### Extra: brandverzekering en verplichte attesten (1 minuut)

1. **VME > Portefeuille**: Kaaihuis heeft het signaal **Brandverzekering vervalt of ontbreekt** (vervaldag 1 december 2026), Hof ter Beuken het signaal **Verplicht attest ontbreekt** (geen asbestattest, bouwjaar 1978).
2. Open Hof ter Beuken, tabblad **Verzekering en attesten**: het asbestattest staat in het rood, het EPC en de elektrische keuring zijn in orde. De taak *Asbestattest gemene delen laten opmaken* staat klaar.
3. Klik **Asbestattest toevoegen**, kies een PDF en sla op: het attest is tien jaar geldig, de taak is afgevinkt en het signaal is weg.
4. Open de polis van Kaaihuis (**VME > Werken en schade > Verzekeringspolissen**): vervaldag, opzegdatum, verzekerde waarde en schadegevallen. **Verlengd** schuift de vervaldag een jaar op; er gaat niets naar de verzekeraar.
5. In een verkoopdossier toont het voorbeeld van de inlichtingen aan de notaris nu ook de attesten (een ontbrekend attest staat er uitdrukkelijk) en de brandverzekering.

> Boodschap: "Geen polis die stilzwijgend verloopt zonder dat iemand ze nakeek, en de notaris krijgt meteen de attesten van de gemene delen."


### Extra: drie offertes vergelijken met de AI (1,5 minuut)

1. **VME > Werken en schade > Werkdossiers**: *Gevelrenovatie voor- en achtergevel* van Residentie Linde. Tabblad **Offertes**: drie aannemers, elk met hun PDF. Open er één: drie pagina's, elke aannemer met een andere opbouw.
2. Klik op **Offertes vergelijken**: de vergelijking staat op **Wacht op AI**.
3. In een terminal, in de map `ai`: `.venv/bin/python offertes.py` (met sleutel in `ai/.env` leest Claude de PDF's; zonder sleutel of met `--offline` de vaste testmodus, zonder netwerk). Het script meldt "Concept klaar" en de aandachtspunten.
4. Herlaad de vergelijking. Toon de **tabel**: de stelling in het rood bij Renovatiebedrijf Voorbeeld ("niet inbegrepen", p. 2), 21% btw in het geel bij Bouwonderneming Denkbeeld. Klik op een **(p. 2)**: de offerte opent op die pagina.
5. Toon de **aandachtspunten**: het btw-tarief verschilt, en in het werkdossier staat 44.000 euro voor Denkbeeld terwijl de offerte 53.240 euro incl. btw vermeldt. De **samenvatting** somt verschillen op, zonder aanbeveling.
6. Kies **Voor de AV** (bv. een AV van 2027 als die al bestaat), klik op **PDF bekijken** (CONCEPT bovenaan) en dan op **Goedkeuren**: de PDF staat bij het werkdossier en gaat mee met de oproepingen van die AV. Er vertrekt niets.

> Boodschap: "Een avond offertes naast elkaar leggen wordt tien minuten nakijken, met de bron bij elk getal. De AV kiest; wij zetten de feiten klaar."
### Extra: de website en de knop Inloggen (1 minuut)

Doe dit vóór u inlogt, of in een privévenster.

1. Open http://localhost:8069: de productwebsite (werktitel **Quotis**) met de sterke punten, **Functies**, **Voor eigenaars** en **Prijzen**. Alles is fictief: geen echte klanten of getuigenissen.
2. Klik op **Inloggen**: één knop met twee routes, **Medewerker van de syndicus** en **Eigenaar of huurder**.
3. Kies bewust **Medewerker van de syndicus** en log in als eigenaar (`eigenaar.linde.a1@example.com`, `portaal-demo`): u komt toch in het eigenaarsportaal, nooit in de beheeromgeving.
4. Optioneel: **Prijzen > Demo aanvragen** maakt een lead in **CRM**, zonder mail naar de bezoeker.

> Boodschap: "Eén adres voor uw kantoor en uw eigenaars; het platform weet wie waar hoort."

### Extra: het eigenaarsportaal (1 minuut)

1. Open een privévenster (of een tweede browser) op http://localhost:8069, klik op **Inloggen > Eigenaar of huurder** en log in als eigenaar: `eigenaar.linde.a1@example.com`, wachtwoord `portaal-demo`. Zo blijft de sessie van de syndicus open.
2. **Mijn mede-eigendom > Residentie Linde**: zijn kavels A1 en G1, de provisies van 2026 met de betaalstatus en een PDF per oproep, de voorlopige jaarafrekening 2026, en de documenten van het gebouw en van A1.
3. Vertel erbij: de verkoper van A5 (`eigenaar.linde.a5@example.com`) ziet niets meer van na de verkoop, en een eigenaar ziet nooit een ander gebouw of een andere kavel.
4. **Adres wijzigen**: de aanvraag van A1 wacht al op goedkeuring. Terug als syndicus: **VME > Eigenaars > Adreswijzigingen > Goedkeuren**.
5. **Mijn aanvragen**: A1 vroeg in het portaal een attest van de betaalde provisies ("In behandeling"). Bij **Bevragingen** heeft hij al geantwoord op de laadpalen. Log in als `huurder.linde.a6@example.com` (eigen hostnaam, bv. `http://huurder.localhost:8069`), klik **Nieuwe aanvraag**, kies een badge voor A6: de aanvraag wacht op bewijs; laad een PDF op bij **Bewijs bezorgen**. Als syndicus: **VME > Aanvragen**, kanaal Portaal, met de taak "Bewijs uit het portaal nakijken". De verzending *Interesse in een laadpaal in Residentie Linde?* toont per eigenaar het antwoord en of het via het portaal kwam.

> Boodschap: "Eigenaars vinden hun documenten en hun saldo zelf, en het register van eigenaars blijft juist."
### Extra: een hybride AV met online stemmen en ondertekenen (2 minuten)

Gebruik drie hostnamen, zodat de sessies elkaar niet uitloggen: `http://localhost:8069` voor de syndicus, `http://a1.localhost:8069` en `http://a6.localhost:8069` voor de eigenaars (wachtwoord `portaal-demo`).

1. **VME > Algemene vergaderingen**, open **Buitengewone AV 2026 Residentie Linde: Laadpalen in de garage** (19 november, hybride). Tabblad **Online**: de link per AV en de videolink. A7 gaf volmacht aan A1.
2. Als A6 (`eigenaar.linde.a6@example.com`): **Mijn mede-eigendom > Residentie Linde > Online deelnemen en stemmen**. Stem vooraf schriftelijk over de schilderwerken.
3. Als syndicus: **Online onthaal openen**. Als A1 en A6: **Ik ben aanwezig (online)**; de videolink verschijnt.
4. Als syndicus: bij de laadpalen **Stemming openen**. A1 stemt in één formulier voor zichzelf en voor A7; A6 stemt ook. Toon bij **Stemmen** dat de online stemmen alleen-lezen zijn, met tijdstip en stemmer.
5. **Stemming sluiten**: in het portaal zien de eigenaars de uitslag. Sluit of handel de andere punten af, en klik **Gehouden** en **Notulen ter ondertekening**.
6. A1 en A6 ondertekenen in het portaal. Tabblad **Ondertekening**: naam, tijdstip, IP-adres en SHA-256 van de PDF per ondertekenaar.

Zijn er te weinig aanwezigen voor het quorum, zet dan enkele eigenaars op "Aanwezig" in de aanwezigheidslijst (in de zaal). De AV kan maar één keer doorlopen worden: voor een nieuwe demo de database opnieuw aanmaken.

> Boodschap: "Thuis meestemmen met dezelfde regels als in de zaal, en notulen die bewijsbaar ongewijzigd ondertekend zijn, zonder Enterprise-licentie."

### Extra: de commissaris van de rekeningen kijkt mee (1 minuut)

1. Open Residentie Linde, tabblad **Raad en commissaris**: eigenaar Linde A2 is commissaris sinds de AV van 10 maart, met een eigen login. Hof ter Beuken heeft 24 appartementen en dus een raad (B1 voorzitter, B6 en B11).
2. Meld je in een privévenster aan als `eigenaar.linde.a2@example.com` (wachtwoord: `DEMO_AUDITOR_PASSWORD` in `demo_data/vme_demo_data.py`). In **VME > Commissaris** ziet hij de facturen, provisies en bankbewegingen van Linde, en niets van de andere gebouwen. Knoppen om iets te wijzigen zijn er niet.
3. **VME > Raad en commissaris > Lopende dossiers**: de verkoop van A3, de invordering, de keuringsopmerkingen en de dakwerken uit de AV, met hun termijnen.
4. In **Mijn mandaten en verslag** drukt hij het sjabloon voor zijn verslag aan de AV af, met de cijfers van 2026 al ingevuld.

> Boodschap: "De commissaris kijkt zelf na, wanneer het hem past, zonder dat u mappen moet kopiëren."
### Extra: een waterafsluiting in blok A (1 minuut)

1. **VME > Communicatie > Verzendingen > Nieuw**: VME Residentie Linde, sjabloon **Waterafsluiting**, ontvangers "Eigenaars van een blok", blok `A`.
2. **Ontvangers ophalen**: twaalf eigenaars, één bericht per eigenaar (ook wie een garage heeft), A4 en A9 per brief omdat ze papier vroegen, A5 naar de nieuwe eigenaar.
3. **Bevestigen en versturen**: de e-mails gaan in de wachtrij, de twee brieven staan samen in één PDF. Elke eigenaar ziet het in zijn communicatielog.
4. Vertel erbij: een ingebrekestelling gaat met **Aangetekend versturen** in het verzendregister met haar PDF en volgnummer; sms en elektronisch aangetekend zijn voorzien met een simulatie.

> Boodschap: "Eén plaats voor alles wat een eigenaar van u kreeg, en niets vertrekt zonder dat u het bevestigt."
### Extra: de rentmeester, indexatiebrief en afrekening aan de huurder (1,5 minuut)

Kies rechtsboven ook het bedrijf **Rentmeester Voorbeeld BV**, anders blijven de huurfacturen verborgen.

1. **Rentmeester > Huurcontracten**: drie verhuurde appartementen. Het contract van *Linde A7* heeft een taak: de uiterste opzegdatum van het kortlopende contract is 30 november.
2. Open **Rentmeester > Indexeringen** en de conceptindexering van *Linde A2* op 1 november 2026. Toon de berekening: met EPC-label E werd in 2022 niet geïndexeerd, de correctiefactor 1,090092 houdt die gemiste indexering eruit. Nieuwe huur 939,90 euro.
3. Klik op **Indexatiebrief (PDF)**: een concept, nog niet verstuurd. Klik op **Bevestigen**.
4. Open het contract *Linde A2* en klik op **Afrekening lasten**, jaar 2026, **Berekenen**: per factuur uit de jaarafrekening van de VME het deel van de huurder (schoonmaak, lift en elektriciteit wel, brandverzekering niet), min 900 euro provisies.
5. **Afrekening (PDF)** en **Conceptfactuur maken**.

> Boodschap: "De jaarafrekening van de VME is meteen de basis voor de afrekening aan de huurder, zonder overtikken."

### Extra: de huur doorstorten aan de verhuurder (1 minuut)

1. **Rentmeester > Doorstortingen**: januari tot september zijn doorgestort; oktober staat klaar als concept, per verhuurder. *Linde A7* betaalde oktober niet, dus die huur zit er niet in.
2. Open de doorstorting van oktober voor de verhuurder van *Linde A2*: ontvangen huur en lasten, ereloon 7 % op de huur met 21 % btw, saldo. Klik op **Afrekening (PDF)**.
3. **Bevestigen** (ereloonfactuur, doorstortingsstuk en verrekening worden geboekt, niets verstuurd), **Goedkeuren voor betaling**, **Betaalbatch maken**.
4. In de betaalbatch: **SEPA-bestand maken**. Vertel erbij: het bestand gaat pas naar de bank als iemand het daar oplaadt, en een niet-bevestigde rekening van de verhuurder komt er nooit in.

> Boodschap: "Elke maand per verhuurder één klik: afrekening, ereloonfactuur en overschrijving, en niets vertrekt zonder uw handtekening in de bank."

### Extra: de jaarcyclus, waar staat elke VME? (1,5 minuut)

1. **VME > Portefeuille**: de kolom **Volgende stap** toont per VME waar ze staat in haar jaar. **Hof ter Beuken** heeft het signaal **Jaarcyclus** aan.
2. **VME > Jaarcyclus** (gegroepeerd per VME):
   - **Hof ter Beuken**, overgenomen op 5 april 2026: agenda, oproeping en AV van 2026 in het rood. De vorige syndicus plande de AV niet; de stappen erna (notulen, goedgekeurd budget) wachten.
   - **Residentie Linde**: alles van 2026 is afgerond; **AV 2027 plannen** is klaargezet (blauw). Open de stap: de AV-planner stelt 17 maart 2027 voor. **Open concept** en **Bevestigen** doet de syndicus zelf.
   - **Kaaihuis**, overgenomen op 1 oktober: de oproep van het vierde kwartaal is afgerond, de AV 2027 wordt klaargezet vanaf 10 november.
3. Open bij Linde **Provisieoproep 1/4 2027** en klik op **Nu klaarzetten**: twee conceptfacturen per eigenaar staan klaar, niets is geboekt. Het activiteitenicoon toont de taak "nakijken en boeken".

> Boodschap: "Uw jaar per gebouw loopt vanzelf: elke stap staat op tijd klaar als concept, u kijkt na en klikt. En u ziet in één lijst welk gebouw achterloopt."

Doe deze extra **na** stap 5 (de provisieoproep 1 van 2027 met de hand) of sla stap 5 over: een oproep die al bestaat, wordt door de jaarcyclus hergebruikt en niet een tweede keer gemaakt. Wie de AV-planner (stap 7) na deze extra draait met **Voorstellen opnieuw indelen**, krijgt hetzelfde voorstel voor Linde.

### Extra: mijn werk vandaag, over alle gebouwen (1 minuut)

1. **VME > Mijn werk vandaag**: één lijst met wat te laat is, vandaag of deze week vervalt, gegroepeerd per urgentie en per VME. De filter **Mijn werk** staat aan: `admin` is dossierbeheerder van Residentie Linde en Hof ter Beuken.
   - **Te laat**: de AV 2026 van Hof ter Beuken, de agenda en oproeping ervan, en de keuring van de brandblussers van Linde.
   - **Vandaag**: het AI-antwoord voor Linde A8, de bestelling van een sleutel voor Beuken B3 en de herinneringen voor Linde A3 en Beuken B7, allemaal concepten die op een klik wachten.
   - **Deze week**: het antwoord aan de notaris voor Linde A3 (uiterlijk 12 november) en de keuring van de lift van blok A.
2. Klik op **Openen** bij de bestelling: de aanvraag van B3 opent met de bestelbon in bijlage. Niets is verstuurd; **Bestelling versturen** is de klik van de medewerker.
3. Haal de filter **Mijn werk** weg en groepeer per **Verantwoordelijke**: collega **Medewerker Voorbeeld** beheert Kaaihuis, met een AI-antwoord voor K3.

> Boodschap: "Uw dag begint met één lijst over al uw gebouwen: wat te laat is, wat vandaag moet, en wat klaarstaat voor uw klik."

## Na de demo

- De demo is daarna niet meer "vers": de factuur, de provisieoproep 2027, de AV-planning, de AI-taken en aanvragen en eventueel het antwoord aan de notaris staan erin. Bouw de database opnieuw op met de commando's hierboven voor een volgende demo.
- Stap 2 kan maar één keer per database: Odoo herkent de mail aan haar Message-ID en verwerkt ze geen tweede keer.
- Lever **niet** de mails in `ai/facturen_inbox/` aan op een demo met historiek: die elektriciteitsfacturen zitten al in de historiek en zouden dubbel geboekt worden. Ze zijn bedoeld voor een demo zonder historiek.

## Bekende aandachtspunten tijdens de demo

- **Oproepingen aanmaken duurt ongeveer een minuut** voor 12 eigenaars (twee PDF's per eigenaar). Maak ze vooraf aan of vertel er intussen iets bij. Voor honderden VME's moet dit later sneller.
- **"Zoek wereldwijd" bij het kiezen van een leverancier** toont echte Belgische bedrijven uit Odoo's eigen bedrijvengegevens. Kies altijd de fictieve leverancier bovenaan de lijst.
- **De demodatums liggen vast rond 5 november 2026.** Wie de demo veel later toont, ziet meer keuringen in het rood.
- **De jaarcyclus draait elke nacht op de echte datum.** Vanaf 10 november zet hij ook de AV 2027 van Kaaihuis klaar, vanaf 18 december de provisieoproep 1 van 2027 als concept. Voor een demo op een latere datum bouwt u de database opnieuw op.
- **"Your logo"** bovenaan de PDF is Odoo's plaatshouder zolang er geen logo van de syndicus is.
