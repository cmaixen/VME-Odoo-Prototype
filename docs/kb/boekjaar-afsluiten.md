# Hoe sluit ik het boekjaar van een VME af?

Bij de afsluiting wordt de jaarafrekening ook echt geboekt. Wie moet bijbetalen, krijgt een afrekeningsfactuur; wie te veel betaalde, krijgt een creditnota. Daarna toont Odoo het resultaat van het jaar en wat naar het nieuwe jaar overgaat, en vergrendelt het het afgesloten jaar. Alles blijft een concept tot jij het bevestigt, en er wordt nooit iets vanzelf verstuurd.

## Stappen

1. Open de VME en klik bovenaan op **Boekjaar afsluiten**, of open **VME > Afsluiting boekjaar** en klik op **Nieuw**.
2. Kijk of **VME** en **Boekjaar** kloppen. Het boekjaar kun je alleen wijzigen zolang er nog niets is voorbereid.
3. Lees het tabblad **Controles**:
   - Een **groen vinkje** betekent in orde.
   - Een **rood kruis** blokkeert: los het eerst op. Voorbeelden: een geboekte factuur die nog niet verdeeld is, een leveranciersfactuur of provisiefactuur die nog in concept staat, of bankafschriften die nog niet afgepunt zijn.
   - Een **oranje driehoek** is een waarschuwing, bijvoorbeeld als het jaar nog niet voorbij is. Daar beslis je zelf.
4. Klik op **Afrekening voorbereiden**. Odoo maakt per eigenaar een concept:
   - een **factuur** als de eigenaar moet bijbetalen;
   - een **creditnota** als de eigenaar geld terugkrijgt.

   Het bedrag is het aandeel van de eigenaar in de kosten, min de provisies werkkapitaal die hem voor dat jaar gevraagd zijn. De documenten zijn gedateerd op 31 december van het boekjaar.
5. Open het tabblad **Afrekening per eigenaar** en kijk de concepten na. Je kunt elk document openen, aanpassen, apart bevestigen of verwijderen.
6. Klik op **Alles bevestigen** om alle concepten in één keer te boeken. Er wordt niets verstuurd: de documenten verstuur je zelf, met de knop **Verzenden** op de factuur of via de communicatie met eigenaars.
7. Bekijk het tabblad **Resultaat en overdracht** (zie hieronder).
8. Klik op **Boekjaar afsluiten**. Odoo vergrendelt het jaar tot en met 31 december. Alleen een beheerder van de boekhouding ziet deze knop.

Moet er toch nog iets in het afgesloten jaar veranderen? Dan klikt een beheerder op **Heropenen**. De vergrendeling gaat eraf en het dossier staat weer op "Afrekening voorbereid". Na de correctie klik je op **Opnieuw voorbereiden**: de concepten worden vervangen, en bevestigde documenten blijven staan. Is er een verschil, dan komt er een extra document bij.

## Resultaat en overdracht

Het tabblad toont per fonds (werkkapitaal en reservekapitaal):

- de **stand op 1 januari**;
- wat in het jaar **gevraagd** is (provisies en de afrekening);
- de **kosten, teruggaven en werken**;
- het **resultaat van het jaar**: na de afrekening is dat voor het werkkapitaal normaal nul, want de eigenaars betalen precies de kosten;
- wat **overgaat naar 1 januari** van het nieuwe jaar.

Daaronder staan de open vorderingen op eigenaars, de schulden aan leveranciers en het saldo op de twee bankrekeningen op 31 december. Bij het afsluiten bewaart Odoo deze cijfers in het dossier. Je hoeft geen openingsbalans te boeken: de saldi op 31 december zijn vanzelf de beginsaldi van het nieuwe jaar.

## Voorbeeld uit de demo

Na het laden van de demohistoriek opent u **Residentie Linde**, klikt u op **Boekjaar afsluiten** en kiest u het boekjaar **2026**.

- De controles zijn groen. Alleen "Het boekjaar 2026 loopt nog" is een oranje waarschuwing, want de demo speelt in november 2026.
- **Afrekening voorbereiden** maakt 13 concept-creditnota's, samen 5.401,00 €. Alle eigenaars krijgen geld terug: de vier provisieoproepen van 2026 zijn gevraagd, maar de kosten lopen pas tot november.
- **Eigenaar Linde A1** krijgt 555,67 € terug.
- **Eigenaar Linde A3** betaalde de vierde oproep (432 €) niet. Die blijft een open factuur. Zijn creditnota (526,81 €) gaat alleen over het verschil tussen zijn kosten en de gevraagde provisies.
- Kavel **A5** is op 1 juli verkocht. Verkoper en koper krijgen elk een eigen creditnota voor hun deel van het jaar.
- Op **Resultaat en overdracht** is het resultaat van het werkkapitaal na de afrekening 0,00 €. Het reservekapitaal van 2.400,00 € gaat volledig over naar 2027.

Staat bovenaan rechts een ander bedrijf dan Residentie Linde, dan toont het tabblad de documenten als tabel. Zet het bedrijf op Residentie Linde om ze te openen.

Sluit het jaar 2026 in de demo pas als laatste af, of heropen het daarna. Zolang het afgesloten is, komt elke nieuwe boeking met een datum in 2026 in 2027 terecht.

## Veelgestelde vragen

**Waarom krijgt een eigenaar een creditnota en niet minder te betalen op de volgende provisie?**
Zo blijven de provisieoproepen gelijk aan het budget dat de algemene vergadering goedkeurde. Een bevestigde creditnota staat in Odoo als "openstaand tegoed" bij die eigenaar. Op zijn volgende provisiefactuur verschijnt ze vanzelf, en met één klik verreken je ze. Je kunt ze ook terugbetalen, bijvoorbeeld aan een eigenaar die verkocht heeft.

**Wordt het reservekapitaal ook afgerekend?**
Nee. Het reservekapitaal is van de VME en wordt niet terugbetaald, ook niet aan wie zijn kavel verkocht. De afsluiting raakt het niet aan; het gaat volledig over naar het nieuwe jaar.

**Een eigenaar betaalde een provisie niet. Wordt die meegerekend?**
De afrekening trekt de gevraagde provisies af, niet de betaalde. De onbetaalde provisie blijft een eigen open factuur die je via de invordering opvolgt. Afrekening plus open provisie is samen precies het saldo uit de jaarafrekening.

**Er komt nog een factuur van het afgesloten jaar binnen. Wat nu?**
Je kunt ze gewoon boeken. Odoo zet de boekingsdatum dan automatisch in de eerste open periode van het nieuwe jaar, en de kost telt mee in de jaarafrekening van dat nieuwe jaar. De afrekening van het afgesloten jaar verandert niet meer. Hoort ze toch in het oude jaar, dan laat je het jaar heropenen.

**Ik zie de documenten niet in de lijst, alleen in een tabel.**
Bovenaan rechts staat een ander bedrijf. Zet het bedrijf van de VME aan; dan kun je elk document openen.

**De knop "Boekjaar afsluiten" staat er niet.**
De knop verschijnt pas als alle rode controles opgelost zijn en alle afrekeningsdocumenten bevestigd zijn. Je moet ook beheerder van de boekhouding zijn. Kijk het tabblad **Controles** na.

**Ik krijg "Dit kan nog niet" met een lijst.**
De lijst noemt wat nog moet gebeuren, bijvoorbeeld welke factuur niet verdeeld is. Los dat op en klik opnieuw.

**Kan ik het vorige jaar nog afsluiten als ik dit jaar al afsloot?**
Begin altijd bij het oudste jaar. Odoo waarschuwt als het vorige jaar nog niet afgesloten is.
