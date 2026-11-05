# Hoe behandel ik een schadegeval met de verzekering?

Meldt een eigenaar waterschade, een ruit die gebarsten is of stormschade aan het dak, dan opent u een **schadedossier**. Daarin staan de melding, de betrokken kavels, de verzekeringspolis, de aangifte bij de verzekeraar, de expertise, de herstelling en de vergoeding. Odoo bewaakt de termijn om de schade aan te geven en maakt bij elke stap een taak. De aangifte zelf en alle brieven verstuurt u zelf.

## Vooraf: de verzekeringspolissen

Open de VME, tabblad **Werken en verzekeringen**, of **VME > Werken en schade > Verzekeringspolissen**. Vul per polis de verzekeraar, het polisnummer, de vrijstelling en de termijn voor de aangifte in (staat in de polis, vaak 8 dagen).

## Stappen

1. **Melding.** Ga naar **VME > Werken en schade > Schadedossiers > Nieuw**. Kies de VME, de soort schade, de datum van het schadegeval, wie het meldde en hoe, en de betrokken kavels. Vink **Gemene delen beschadigd** aan als het gebouw zelf schade heeft. Odoo kiest de brandverzekering van het gebouw als polis en maakt een taak **Schade aangeven bij** de verzekeraar met de uiterste datum.
2. **Aangifte.** Doe de aangifte bij de verzekeraar of de makelaar. Vul de datum en het dossiernummer van de verzekeraar in en klik op **Aangegeven bij verzekeraar**. Odoo maakt een taak om twee weken later na te gaan of er een expert is aangesteld.
3. **Expertise.** Vul de expert en de datum van de expertise in en klik op **Expert aangesteld**. Er komt een taak op de dag van de expertise. Komt er geen expert (kleine schade), klik dan meteen op **Herstelling gestart (zonder expertise)**.
4. **Herstelling.** Kies de hersteller en klik op **Herstelling gestart**. Hang de facturen van de hersteller aan het dossier via het veld **Schadedossier** op de factuur, of via de knop **Facturen** van het dossier.
5. **Uitbetaling.** Vul de vergoeding van de verzekeraar en de datum in en klik op **Vergoeding ontvangen**. Odoo toont wat ten laste van de VME blijft (kosten van de herstelling min de vergoeding).

Weigert de verzekeraar, vul dan de reden in en klik op **Geweigerd**.

## Termijnen

- **Aangifte:** binnen de termijn van de polis na het schadegeval. In de lijst kleurt een dossier oranje vanaf drie dagen voor de uiterste datum, en rood als die voorbij is. Een te late aangifte kan nog, maar Odoo zet een waarschuwing in de chatter: de verzekeraar kan de vergoeding verminderen.
- **Verjaring:** drie jaar na het schadegeval kan de VME de verzekeraar niet meer aanspreken. U ziet de datum in het dossier.

## Een melding uit een mail van een eigenaar

De AI-assistent leest de mails van eigenaars (zie [Een antwoord behandelen dat de AI-assistent voorstelt](ai-voorstellen-mails.md)). Gaat een mail over een lek of waterschade, dan maakt hij ook een schadedossier met de status **Gemeld**, de VME, de kavel van de eigenaar en de tekst van de mail. Kijk dat dossier na en vul de kavel aan waar de schade vandaan komt. De assistent doet zelf geen aangifte. Wordt dezelfde mail opnieuw verwerkt, dan komt er geen tweede dossier.

## Voorbeeld uit de demodata

In **Residentie Linde** mailde Eigenaar Linde A4 op 2 november 2026 dat er water langs het plafond van de badkamer loopt (mail `01_lek_badkamer.eml`). Het schadedossier **Waterschade badkamer A4** heeft de kavels A4 en A7 (het lek kwam uit de afvoer in de leidingkoker naast A7), gemene delen beschadigd, de polis Brandverzekering gebouw bij Verzekeringen Voorbeeld NV (vrijstelling 300 euro). De schade is op 3 november aangegeven (dossiernummer SCH-2026-08812), ruim voor de uiterste datum van 9 november. De expertise is gepland op 12 november met Expertisebureau Voorbeeld BV; de geraamde schade is 2.400 euro.

## Veelgestelde vragen

**De eigenaar heeft een eigen verzekering. Moet ik dan iets doen?**
Schade die alleen het privatieve deel raakt, regelt de eigenaar vaak met zijn eigen verzekering. Raakt de schade gemene delen of komt ze uit een gemeen deel (zoals een leiding in de koker), dan doet de syndicus de aangifte op de polis van het gebouw. Twijfelt u, vraag het aan de makelaar.

**Waar staat de termijn van 8 dagen?**
In de polis. Vul de juiste termijn in op de verzekeringspolis; Odoo rekent vanaf de datum van het schadegeval.

**Kan ik de kosten van de herstelling verdelen over de eigenaars?**
Ja, een factuur met een schadedossier wordt verdeeld zoals elke andere factuur. De vergoeding van de verzekeraar boekt u op het moment dat ze binnenkomt.

> De termijnen voor aangifte en verjaring zijn nog niet juridisch nagekeken.
