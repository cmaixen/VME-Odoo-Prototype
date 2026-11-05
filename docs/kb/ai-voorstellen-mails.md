# Hoe behandel ik een antwoord dat de AI-assistent voorstelt?

De AI-assistent leest de mails van eigenaars, zoekt uit over welk gebouw (VME) en welk appartement, welke garage of berging (kavel) het gaat, en schrijft een voorstel van antwoord. Dat voorstel komt als taak op de VME in Odoo terecht.

**De assistent verstuurt nooit zelf iets.** Elk antwoord vertrekt pas nadat u het nagekeken en zelf verstuurd hebt.

## Waar vind ik de voorstellen?

- Bovenaan rechts in Odoo staat het klokje van de **activiteiten**. Het getal toont hoeveel taken voor u klaarstaan.
- Open een VME via **VME > VME's**. Onderaan het formulier, bij **Geplande activiteiten**, staat elk voorstel als taak met de titel **AI-voorstel: …**, bijvoorbeeld *AI-voorstel: Lek of waterschade (A4)*.
- De vervaldatum hangt af van hoe dringend de mail is: een lek of een stilstaande lift staat op vandaag, een gewone vraag op binnen twee dagen.

## Stappen

1. Open de VME en klik bij de taak op het **i**-icoontje om alles te zien.
2. Lees bovenaan de **gegevens**: van wie de mail komt, over welke kavel, het onderwerp, hoe dringend het is en hoe zeker de assistent is van de koppeling.
3. Staat bij **Zekerheid koppeling** "laag (nakijken!)", controleer dan eerst of de mail echt over deze VME en kavel gaat. De uitleg erachter zegt waarop de assistent zich baseerde.
4. Lees de **oorspronkelijke mail** onderaan en daarna het **conceptantwoord**.
5. Vul de plaatshouders tussen vierkante haken in, zoals `[datum]`. De assistent belooft nooit zelf een datum, bedrag of beslissing.
6. Pas de tekst aan waar nodig en verstuur het antwoord zelf, vanuit uw mailprogramma of via **Bericht verzenden** op de VME.
7. Klik bij de taak op **Markeren als gedaan**. Zo weet uw team dat de mail behandeld is.

Moet er nog iets gebeuren, zoals een loodgieter bellen, plan dan met **Activiteit** een nieuwe taak op dezelfde VME.

## Voorbeeld uit de demodata

In de demo staan vijf verzonnen mails klaar. Na het verwerken staan deze taken in Odoo:

| VME | Kavel | Onderwerp | Dringend |
| --- | --- | --- | --- |
| Residentie Linde | A4 | Lek in het plafond van de badkamer | ja, vandaag |
| Hof ter Beuken | B7 | Vraag over de verwarmingskosten en de provisies | nee |
| Kaaihuis | K4 | Verkoop van het appartement en verhuis | nee |
| Residentie Linde | A11 | Klacht: de lift staat al drie dagen stil | ja, vandaag |
| Hof ter Beuken | B23 | Wanneer is de volgende algemene vergadering? | nee |

De mail over de lift komt van een privéadres dat niet in Odoo staat. De assistent herkent toch het gebouw en appartement A11 uit de tekst, en zegt dat ook in de uitleg bij de koppeling.

## Schademeldingen

Gaat een mail over een lek of waterschade, dan maakt de assistent ook een **schadedossier** in de status **Gemeld** (VME > Werken en schade > Schadedossiers), en vermeldt dat in de activiteit. Kijk het na en doe de aangifte bij de verzekeraar; zie [Een schadegeval behandelen met de verzekering](schadegevallen.md).

## Veelgestelde vragen

**Kan de assistent per ongeluk een mail versturen?**
Nee. Hij kan alleen taken aanmaken. Versturen doet altijd een medewerker.

**Wat als de assistent de mail aan de verkeerde VME koppelt?**
Markeer de taak als gedaan met een korte opmerking en maak de taak opnieuw aan op de juiste VME, of behandel de mail gewoon zelf. Laat het ook aan de beheerder weten, zodat we de assistent kunnen verbeteren.

**Wat gebeurt er met een mail die over geen enkel gebouw lijkt te gaan?**
Daarvan maakt de assistent geen taak. De beheerder ziet in het verslag van de verwerking dat die mail met de hand behandeld moet worden.

**Komt een mail twee keer binnen als de assistent opnieuw draait?**
Nee. Een mail die al een taak heeft, wordt overgeslagen.

**Hoe zeker is "gemiddeld" of "hoog"?**
"Hoog" betekent dat het afzenderadres bij een gekende eigenaar hoort en de inhoud klopt. Bij "gemiddeld" of "laag" kijkt u de koppeling best even na.

**Kan ik de tekst van het voorstel zomaar overnemen?**
Lees ze altijd na. De assistent kent de feiten niet altijd (bijvoorbeeld of de technieker al gebeld is) en schrijft dan een plaatshouder of een voorzichtige formulering.
