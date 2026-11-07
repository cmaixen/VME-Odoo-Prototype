# Het jaar van een VME opvolgen: de jaarcyclus

Elk jaar komen bij elke VME dezelfde stappen terug: het boekjaar afsluiten, de jaarafrekening maken, het budget voorbereiden, de algemene vergadering plannen en oproepen, de notulen bezorgen en elk kwartaal de provisies opvragen. De **jaarcyclus** zet die stappen per VME in een kalender, met hun uiterste datum, en zet elke stap op het juiste moment voor u klaar.

**Odoo beslist niets in uw plaats.** Een stap klaarzetten betekent: een concept maken (conceptfacturen, conceptoproepingen, een voorstel voor de datum van de AV) of een taak voor u aanmaken. Boeken, versturen en bevestigen doet u altijd zelf.

> De wettelijke termijnen hieronder (oproeping 15 dagen vooraf, periode van de AV, notulen binnen 30 dagen, 5% reservefonds, benoemingen) zijn nog niet juridisch nagekeken. De andere termijnen zijn werkafspraken die we met de pilotsyndicus kunnen bijstellen.

## Hoe zet ik de jaarcyclus aan voor een VME?

1. Open de VME in **VME > VME's** en ga naar het tabblad **Jaarcyclus**.
2. Vul **Jaarcyclus vanaf** in, bijvoorbeeld de dag waarop u het gebouw overnam. Stappen met een uiterste datum vóór die dag maakt Odoo niet aan.
3. Kies eventueel een **Verantwoordelijke jaarcyclus**. Die krijgt de taken. Laat u het leeg, dan krijgt de dossierbeheerder van de VME ze (zie [Mijn werk vandaag](mijn-werk-vandaag.md)).
4. Klik op **Kalender bijwerken en klaarzetten**. Daarna doet Odoo dat zelf, elke nacht.

De periode van de gewone AV (tabblad met de AV-gegevens) moet ingevuld zijn: de meeste termijnen rekenen vanaf die periode.

## Welke stappen zijn er, en wanneer?

De stappen hangen vast aan de **laatste dag om de oproeping te versturen**: de datum van de AV min de oproepingstermijn (standaard 15 dagen), of, zolang de AV nog geen datum heeft, de laatste dag van de AV-periode min 15 dagen.

| Stap | Klaargezet vanaf | Uiterlijk | Wat staat er klaar |
| --- | --- | --- | --- |
| Boekjaar vorig jaar afsluiten | 1 januari | 21 dagen vóór de laatste oproepingsdag | Een taak. De stap is afgerond als de afsluitdatum van het boekjaar gezet is, of als u de taak afvinkt |
| Jaarafrekening vorig jaar | 1 januari | 7 dagen vóór de laatste oproepingsdag | Een taak om de afrekening na te kijken; ze gaat mee met de oproeping |
| Budget en reservefonds | 60 dagen vóór de laatste oproepingsdag | 7 dagen vóór de laatste oproepingsdag | Een taak met het minimum voor het reservefonds (5% van de gewone lasten van vorig jaar). Afgerond als het budget bestaat en het minimum haalt |
| AV plannen | 120 dagen vóór de AV-periode | 30 dagen vóór de laatste oproepingsdag | De AV-planner stelt een datum voor in een vrij blok. U bevestigt |
| Agenda: herbenoemingen | 30 dagen vóór de laatste oproepingsdag | de laatste oproepingsdag | De benoeming van de commissaris van de rekeningen (en, als het mandaat afloopt, de herbenoeming van de syndicus) komt op de agenda als ze er nog niet op stond |
| Oproeping AV | 14 dagen vóór de laatste oproepingsdag | de laatste oproepingsdag | Conceptoproepingen per eigenaar met de agenda, een volmacht en de jaarafrekening. Alleen als de AV bevestigd is |
| AV houden | begin van de AV-periode | de datum van de AV (of het einde van de periode) | Niets: dit is een mijlpaal |
| Notulen bezorgen | de dag van de AV | 30 dagen na de AV | Een taak |
| Goedgekeurd budget verwerken | de dag van de AV | 30 dagen na de AV | Een taak: het budget aanpassen aan de beslissing van de AV |
| Provisieoproep (elk kwartaal) | 14 dagen vóór de eerste dag van het kwartaal | de eerste dag van het kwartaal | Conceptfacturen per eigenaar, voor werk- en reservekapitaal. Met een maandelijks budget is er een oproep per maand |

## Hoe zie ik waar elke VME staat?

- **VME > Portefeuille**: per VME de kolom **Volgende stap** en het signaal **Jaarcyclus** als een stap te laat is. Met de filter **Stap in de jaarcyclus te laat** ziet u alleen die VME's.
- **VME > Jaarcyclus**: alle open stappen van al uw VME's, gegroepeerd per VME. Rood = te laat, blauw = klaargezet. Met de filters **Te laat**, **Klaargezet**, **Deze maand** en **Mijn stappen**, en een kalenderweergave.
- Op de **gebouwkaart** staat een blok **Jaarcyclus** met de open stappen van die VME.

Een stap is **te laat** als de uiterste datum voorbij is en de stap nog niet afgerond is. De notulen en het goedgekeurde budget zijn nooit te laat zolang de AV niet gehouden is: dan is de AV zelf te laat.

## Hoe werk ik een klaargezette stap af?

1. Open de stap in **VME > Jaarcyclus**. Onder **Toelichting** staat wat klaarstaat.
2. Klik op **Open concept** om de conceptfacturen, de oproepingen of de AV te openen.
3. Kijk na en doe zelf de beslissende klik: **Boeken** op de facturen, **Versturen** op de oproepingen, **Bevestigen** op de AV.

De stap wordt vanzelf **Afgerond** zodra de facturen geboekt zijn, de oproeping verstuurd is of de AV gehouden is. Stappen die alleen een taak zijn (afsluiten, jaarafrekening, agenda, notulen, goedgekeurd budget) rondt u af door de taak af te vinken of op **Afgerond** te klikken. Geldt een stap niet voor deze VME, klik dan op **Niet van toepassing**.

Wilt u een stap vroeger klaarzetten, bijvoorbeeld de provisieoproep van januari al begin december? Klik op **Nu klaarzetten**.

**Voorbeeld uit de demo (5 november 2026).**

- **Residentie Linde** volgt de cyclus het hele jaar. Alles van 2026 is afgerond. De stap **AV 2027 plannen** is klaargezet: de planner stelt 17 maart 2027 voor. Klik op **Open concept** en daarna op **Bevestigen**.
- **Hof ter Beuken** is overgenomen op 5 april 2026. De vorige syndicus had de AV van 2026 niet gepland, dus de agenda, de oproeping en de AV van 2026 staan in het rood. In de portefeuille staat het signaal **Jaarcyclus**.
- **Kaaihuis** is overgenomen op 1 oktober 2026. De oproep van het vierde kwartaal is afgerond; de volgende stap is **AV 2027 plannen** vanaf 10 november.

## Veelgestelde vragen

**Verstuurt Odoo de provisieoproepen nu zelf?**
Nee. Odoo maakt conceptfacturen. Zolang u ze niet boekt, ziet geen enkele eigenaar ze.

**Wat als het budget voor volgend jaar er nog niet is?**
Dan kan de provisieoproep niet klaargezet worden. U krijgt een taak "Los eerst op" met de uitleg. Zodra het budget er is, klikt u op **Nu klaarzetten**, of de stap wordt de volgende nacht opnieuw geprobeerd na **Heropenen**.

**De AV kreeg een andere datum. Kloppen de termijnen nog?**
Ja. Elke nacht rekent Odoo de termijnen van de open stappen opnieuw uit met de datum van de AV.

**Wat als de planner geen vrij blok vindt?**
Dan staat de stap klaar met de taak "met de hand plannen". Voeg een blok toe in **VME > Algemene vergaderingen > Blokken** of kies er een op de AV.

**Waarom zie ik geen stappen voor een VME?**
Het veld **Jaarcyclus vanaf** is leeg, of de VME heeft nog geen periode voor de gewone AV (dan ziet u alleen de afsluiting, de jaarafrekening en de provisieoproepen).

**Kan de commissaris van de rekeningen de jaarcyclus zien?**
Hij ziet de stappen van zijn eigen VME, maar kan niets wijzigen.
