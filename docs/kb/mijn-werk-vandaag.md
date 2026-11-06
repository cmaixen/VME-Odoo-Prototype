# Mijn werk vandaag: alles wat vandaag moet, over al uw VME's

Met 200 gebouwen zit het werk verspreid: een taak op een contract, een stap van de jaarcyclus, een vraag van een notaris, een rappel die klaarstaat. **VME > Mijn werk vandaag** zet alles wat te laat is, vandaag vervalt of deze week vervalt in één lijst, gegroepeerd per urgentie en per gebouw.

**De lijst toont en opent, maar doet zelf niets.** Er vertrekt geen mail, brief, bestelling of betaling. U opent de lijn, kijkt na en klikt zelf.

## Wie is de dossierbeheerder van een VME?

Elke VME heeft een **dossierbeheerder**: de medewerker die het gebouw opvolgt.

1. Open de VME in **VME > VME's**.
2. Kies onder **Gegevens** de **Dossierbeheerder**. Wie een nieuwe VME aanmaakt, is standaard zelf dossierbeheerder.

De dossierbeheerder krijgt de taken die Odoo zelf aanmaakt als er geen andere verantwoordelijke is: de stappen van de jaarcyclus (tenzij de VME een eigen verantwoordelijke voor de jaarcyclus heeft), een opzegtermijn van een contract of een keuring zonder verantwoordelijke, de herbenoeming en de aanplakking van de syndicus, en aanvragen en adreswijzigingen uit het eigenaarsportaal. Signalen zonder eigen verantwoordelijke (bijvoorbeeld achterstallen) staan ook bij hem.

In **VME > VME's** en in de **Portefeuille** ziet u de dossierbeheerder als kolom, met de filter **Mijn VME's** en groeperen per **Dossierbeheerder**.

## Hoe gebruik ik Mijn werk vandaag?

1. Open **VME > Mijn werk vandaag**. Odoo stelt de lijst op dat moment samen.
2. De lijst staat gegroepeerd per **Urgentie** en is daarbinnen gesorteerd per **VME** (groepeer ook per **VME** of **Verantwoordelijke** via het zoekveld):
   - **Te laat** (rood): de termijn is voorbij.
   - **Vandaag** (oranje): de termijn is vandaag. Een herinnering die vandaag klaargezet is, staat hier; een die al dagen wacht, staat bij **Te laat**.
   - **Deze week**: de termijn valt in de zeven dagen na vandaag.
   Wat later vervalt, staat er nog niet in.
3. Klik op **Openen** om de taak, het dossier of het concept te openen. Daar werkt u het af zoals gewoonlijk: een taak afvinken, een rappel versturen, een bestelling versturen, een stap afronden.
4. Klik bovenaan op **Vernieuwen** om de lijst opnieuw samen te stellen nadat u iets afwerkte.

Standaard staat de filter **Mijn werk** aan: alleen wat op uw naam staat. Haal die weg om het werk van uw collega's te zien, of groepeer per **Verantwoordelijke**. Met **Zonder verantwoordelijke** ziet u wat niemand heeft (een VME zonder dossierbeheerder).

## Wat staat er in de lijst?

| Soort | Wat | Voorbeeld |
| --- | --- | --- |
| **Taak** | Elke geplande activiteit op een VME of op een dossier ervan (contract, keuring, aanvraag, verkoop, werken, schade, jaarcyclus, mandaat) | "Keuring plannen: Brandblussers" |
| **Concept** | Iets dat klaarstaat en op één klik wacht: een antwoord van de AI-assistent, een bestelling bij de slotenmaker, een herinnering, aanmaning of ingebrekestelling | "AI-voorstel: Vraag over afrekening of provisies (A8)" |
| **Signaal** | Iets met een termijn zonder taak: een stap van de jaarcyclus, een keuring of risicoanalyse die vervalt, een opzegtermijn van een contract, een vraag van de notaris met een wettelijke termijn, een mandaat van de syndicus om te hernieuwen of aan te plakken, achterstallen boven de drempel, een nieuwe aanvraag | "AV 2026 houden" bij Hof ter Beuken |

Heeft een dossier een taak, dan staat alleen de taak in de lijst en niet nog eens het signaal: de taak is het werk.

**Voorbeeld uit de demo (5 november 2026).** Log in als `admin`: u bent dossierbeheerder van Residentie Linde en Hof ter Beuken.

- **Te laat**: de AV 2026 van Hof ter Beuken (de vorige syndicus plande ze niet) en de keuring van de brandblussers van Residentie Linde.
- **Vandaag**: de taken van de jaarcyclus van Hof ter Beuken, het AI-antwoord voor Linde A8, de bestelling van een sleutel voor Beuken B3 en de herinneringen voor Linde A3 en Beuken B7, die klaarstaan maar niet verstuurd zijn.
- **Deze week**: de vraag van de notaris voor de verkoop van Linde A3 (uiterlijk 12 november), de keuring van de lift van blok A en de evaluatie van het elektriciteitscontract.

Haal de filter **Mijn werk** weg: uw collega **Medewerker Voorbeeld** beheert Kaaihuis en heeft een AI-antwoord voor K3 en de aanplakking van de aanstelling van de syndicus.

## Veelgestelde vragen

**Ik werkte een taak af, maar ze staat nog in de lijst.**
De lijst is een momentopname. Klik op **Vernieuwen**.

**Waarom staat een taak van een collega bij mij?**
De lijst toont de verantwoordelijke van de taak zelf. Staat ze toch op uw naam, dan werd ze aan u toegewezen. Wijzig de verantwoordelijke in de taak (het klokje in het dossier).

**Waarom zie ik een VME niet?**
U ziet alleen de VME's waartoe u toegang hebt. Vraag een beheerder om u toegang te geven (zie [Toegang voor medewerkers](toegang-medewerkers.md)).

**Een AI-antwoord staat in de lijst. Is het al verstuurd?**
Nee. De AI-assistent maakt alleen een taak met een voorstel. Open de VME, lees het voorstel, pas aan en verstuur het zelf. Vink daarna de taak af.

**Kan de lijst taken automatisch afhandelen of herinneringen versturen?**
Nee, en dat is bewust: een mens beslist altijd. De lijst verzamelt alleen.

**Waarom staan de achterstallen van een VME er niet in, terwijl ze boven de drempel zijn?**
Omdat er voor die VME al herinneringen klaarstaan. Die staan als concept in de lijst; zodra ze verstuurd zijn en de achterstallen blijven, komt het signaal terug.
