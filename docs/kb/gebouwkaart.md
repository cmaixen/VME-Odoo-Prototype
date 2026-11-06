# De gebouwkaart, de budgetopvolging en de portefeuille

Odoo geeft u drie overzichten:

- de **gebouwkaart**: één scherm per VME met alles wat u nodig hebt voor een telefoontje van een eigenaar of een vergadering van de raad;
- de **portefeuille**: al uw VME's in één lijst, met signalen waar u iets moet doen;
- de **leverancierskaart**: alles van één leverancier in al uw gebouwen.

De eigenaars zien in het portaal een eenvoudige versie van de gebouwkaart.

> De wettelijke regels hieronder (5% voor het reservefonds, de periode van de AV) zijn nog niet juridisch nagekeken.

## Hoe open ik de gebouwkaart?

1. Ga naar **VME > Gebouwkaart**. U ziet een kaartje per VME met de kapitalen, de achterstallen en het aantal signalen.
2. Klik op een VME.

U opent de gebouwkaart ook vanuit een VME (knop **Gebouwkaart** bovenaan) of vanuit de portefeuille.

De gebouwkaart toont:

| Blok | Wat u ziet |
| --- | --- |
| Signalen | Wat niet in orde is: reservefonds onder 5%, achterstallen boven de drempel, AV buiten de periode, vervallen keuring |
| Kerngegevens | Adres, KBO-nummer, kavels en eigenaars, de twee bankrekeningen, de periode van de gewone AV, de volgende AV, de raad en de commissaris |
| Werk- en reservekapitaal | De stand vandaag en het verloop per jaar: wat opgevraagd werd en wat ervan gebruikt werd. Onder de stand ziet u wat er volgens de bankafschriften en de geregistreerde betalingen op elke rekening staat |
| Budget tegenover werkelijk | Per rekening en per verdeelsleutel: het budget van het jaar, het budget tot vandaag, de werkelijke kosten en het verschil |
| Achterstallen | Het totaal, per ouderdom en per eigenaar |
| Lopende dossiers | Werken, schadegevallen, verkopen en invorderingen die nog lopen |
| Keuringen die vervallen | Installaties waarvan de keuring of de risicoanalyse binnen 90 dagen vervalt of al vervallen is |
| Contracten en opzegtermijnen | Lopende contracten met de laatste dag om op te zeggen |
| Te betalen facturen | Geboekte leveranciersfacturen die nog niet (volledig) betaald zijn; een rode regel is over de vervaldag |
| Open aanvragen | Aanvragen van bewoners, zoals sleutels en badges, zodra die functie in gebruik is |

Klik op een dossier, contract of factuur om het te openen. Met de knoppen bovenaan opent u de **Budgetopvolging**, het **Verloop kapitalen** (een grafiek) en de **Jaarafrekening**.

**Voorbeeld uit de demo.** Open de gebouwkaart van **Hof ter Beuken**. Bovenaan staat het signaal **Reservefonds onder 5%**: de VME bouwt in 2026 1.800 € reserve op, minder dan 5% van de gewone lasten (4.800 €). In het budget ziet u dat de verwarming en de loonkost van de conciërge boven het budget tot vandaag zitten (rode regels). Bij de achterstallen staat Eigenaar Beuken B7, die de laatste twee provisieoproepen niet betaalde (1.711,50 €), en dus ook het signaal voor achterstallen.

## Hoe verdeel ik het budget per rekening en sleutel?

De budgetopvolging vergelijkt wat u per rekening en sleutel voorzag met wat er werkelijk geboekt is. Daarvoor verdeelt u het werkkapitaalbudget.

1. Open het budget in **VME > Budgetten**.
2. Klik onder **Werkkapitaal per rekening en sleutel** op **Regel toevoegen**.
3. Kies de **rekening** (bv. 611000 Onderhoud en herstellingen), de **verdeelsleutel** en vul een omschrijving en het bedrag in.
4. Bewaar. Wat u niet verdeelt, staat als **Niet ingedeeld**.

Laat u de sleutel leeg, dan vallen alle kosten op die rekening onder deze regel, welke sleutel ze ook krijgen.

## Hoe lees ik de budgetopvolging?

Ga naar **VME > Budgetopvolging**. U ziet een draaitabel met per VME en rekening het budget, het budget tot vandaag, de werkelijke kosten en het verschil, met de verdeelsleutels als kolommen. U kunt ook een staafgrafiek of een lijst kiezen en filteren op VME, jaar of leverancier.

- **Budget tot vandaag**: het jaarbudget verspreid over de dagen. Op 1 juli is dat 182/365 van het jaar.
- **Werkelijk**: de geboekte leveranciersfacturen van dit jaar, btw inbegrepen (die is voor een VME een kost). Werken die uit het reservekapitaal betaald worden, tellen niet mee.
- **Verschil**: budget tot vandaag min werkelijk. Negatief is overschreden.

Op de gebouwkaart is een regel rood als de kosten meer dan 10% boven het budget tot vandaag zitten, en oranje als er kosten zijn zonder budget.

## Hoe werk ik met de portefeuille?

1. Ga naar **VME > Portefeuille**. U ziet alle VME's met de stand van de kapitalen, het verbruikte budget, de achterstallen en een vinkje per signaal. Een gele regel heeft minstens één signaal.
2. Filter met **Met signalen** of op één signaal, bv. **Reservefonds onder 5%**.
3. Klik op **Gebouwkaart** om de VME te openen.

De vier signalen:

| Signaal | Wanneer |
| --- | --- |
| Reservefonds onder 5% | De bijdrage aan het reservekapitaal in het budget van dit jaar is lager dan 5% van de gewone lasten van vorig jaar, en de AV besliste niet met 4/5 anders |
| Achterstallen boven de drempel | De vervallen, onbetaalde provisies en kosten van alle eigenaars samen zijn hoger dan de drempel van de VME |
| AV buiten de periode | De periode van de gewone AV van dit jaar is voorbij zonder gehouden AV, of de AV is of werd buiten de periode gehouden |
| Vervallen keuring | Een keuring of risicoanalyse van een installatie is vervallen |

De drempel voor achterstallen is standaard 1.000 €. U past ze aan per VME op het tabblad **Budgetten** van de VME (**Signaal achterstallen vanaf**).

**Voorbeeld uit de demo.** Op 5 november 2026 heeft Hof ter Beuken het signaal voor het reservefonds, de achterstallen van Eigenaar Beuken B7 en de AV (de periode van 12 tot 26 april is voorbij zonder gehouden AV); Kaaihuis heeft ook het signaal voor de AV. Residentie Linde heeft een vervallen keuring van de brandblussers en achterstallen boven de drempel: de syndicus wil daar al vanaf 250 € een signaal, en Eigenaar Linde A3 betaalde de laatste oproep niet (475,20 €).

## Hoe open ik de leverancierskaart?

1. Ga naar **VME > Leveranciers** en klik op een leverancier, of klik op een leverancier in Odoo op de knop **Leverancierskaart**. De lijst toont elke firma met facturen, een contract, een installatie in onderhoud of keuring, of werken in een van uw VME's.
2. U ziet:
   - de gegevens en per VME de **betaaltermijn** van de leverancier;
   - zijn **contracten** in al uw VME's, met de opzegtermijn en de jaarkost;
   - de **installaties** die hij onderhoudt of keurt, met de volgende keuring, en zijn laatste verslagen;
   - de **lopende werken** waarvoor hij aannemer is, en zijn **verdeelregels**;
   - zijn **facturen**: eerst de openstaande, dan de recentste.

**Voorbeeld uit de demo.** Open **Liftonderhoud Voorbeeld BV**. U ziet het onderhoudscontract van de lift in Residentie Linde, de lift die hij onderhoudt en de twee halfjaarlijkse facturen.

## Wat ziet de eigenaar in het portaal?

Op de pagina van zijn VME in het portaal ziet de eigenaar onder **Financiële toestand van het gebouw**:

- de stand van het werk- en het reservekapitaal;
- per verdeelsleutel het budget tot vandaag tegenover de werkelijke kosten.

Hij ziet geen achterstallen van andere eigenaars, geen leveranciers en geen signalen. Zijn eigen aandeel staat in zijn jaarafrekening.

## Wat ziet de commissaris?

De commissaris van de rekeningen ziet de gebouwkaart en de budgetopvolging van zijn VME, en niets van andere VME's. De portefeuille en de leverancierskaart ziet hij niet.

## Veelgestelde vragen

**Waarom staat het werkkapitaal negatief?**
De stand is wat opgevraagd werd min de kosten. Zijn de kosten hoger dan de provisies, dan is het werkkapitaal negatief en volgt er een bijbetaling in de jaarafrekening.

**Waarom verschilt "op de rekening" van de stand?**
De stand telt wat opgevraagd werd, betaald of niet, min de geboekte kosten, betaald of niet. Op de rekening staat wat de eigenaars al betaalden min wat de VME al aan leveranciers betaalde.

**Een jaarfactuur (bv. de verzekering) in januari maakt de rekening rood.**
Het budget tot vandaag spreidt het jaarbudget gelijk over de dagen. Een factuur voor het hele jaar loopt dus voor op het budget, tot later in het jaar.

**De gebouwkaart toont geen budget.**
Er is nog geen budget voor dit jaar. Maak het in **VME > Budgetten**.

**Kan ik het signaal voor het reservefonds uitzetten?**
Alleen als de AV met een meerderheid van 4/5 besliste om minder op te bouwen. Vink dan op het budget **AV besliste met 4/5 anders** aan.
