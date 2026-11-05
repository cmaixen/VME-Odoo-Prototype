# Hoe laat ik PDF-facturen en documenten lezen door de AI-assistent?

Veel leveranciers sturen nog een gewone PDF en geen e-factuur. Komt zo'n PDF binnen op het factuuradres van een VME (of laadt u ze op), dan leest de AI-assistent de factuur en vult hij de **conceptfactuur** voor u in: leverancier, btw-nummer, factuurnummer, datums, kostperiode, bedragen en het rekeningnummer (IBAN). Per veld ziet u hoe zeker de assistent is en of de controle in orde is. De verdeelregels vullen daarna de verdeelsleutel en de rekening in, zoals bij een e-factuur.

Er wordt niets automatisch geboekt of betaald. Een **nieuwe leverancier** of een **ander rekeningnummer** dan het gekende is altijd een waarschuwing: zulke facturen kunt u pas bevestigen nadat u ze nagekeken hebt.

## Waarom zo voorzichtig met het rekeningnummer?

Een veelgebruikte fraude: iemand stuurt een factuur in naam van een gekende leverancier, met de melding "ons rekeningnummer is gewijzigd". Wie betaalt, betaalt aan de fraudeur. Daarom:

- gebruikt het platform alleen een rekeningnummer dat al bij de leverancier staat **en bevestigd is** (zie [een VME aanmaken en de bankrekeningen bevestigen](vme-aanmaken.md));
- slaat het een nieuw rekeningnummer van een factuur **nooit** op bij de leverancier;
- maakt het een nieuwe leverancier **nooit** zelf aan.

## Stappen voor een factuur

1. Kies bovenaan rechts de VME en ga naar **Facturatie > Leveranciers > Facturen**. Met de filter **Te lezen door AI** ziet u facturen die nog gelezen moeten worden, met **Gelezen door AI** de facturen die al ingevuld zijn.
2. Open de conceptfactuur. Rechts staat de PDF, bovenaan een gekleurde balk:
   - **blauw**: de factuur wacht nog op de assistent;
   - **geel**: ingevuld, met velden om na te kijken;
   - **rood**: ingevuld, maar met een **gevaar** (nieuwe leverancier of ander rekeningnummer).
3. Open het tabblad **AI-lezing**. Per veld ziet u de gelezen waarde, de **zekerheid** (hoog, gemiddeld, laag), de **controle** (in orde, nakijken, gevaar) en de uitleg.
4. Vergelijk wat geel of rood is met de PDF en verbeter het op de factuur zelf.
5. Bij een **gevaar**:
   - *Nieuwe leverancier*: zoek de onderneming op in de KBO, maak de leverancier aan (met btw-nummer) en kies hem op de factuur.
   - *Ander of onbevestigd rekeningnummer*: bel de leverancier op een nummer dat u al kende (niet het nummer op de factuur). Klopt het nieuwe rekeningnummer, voeg het dan toe bij de leverancier en laat het bevestigen.
   - Klik daarna op **Opnieuw controleren**. Is alles in orde, dan verdwijnt het gevaar.
   - Blijft er een gevaar dat u bewust aanvaardt (bijvoorbeeld een nieuwe leverancier die u gecontroleerd hebt), klik dan op **Waarschuwingen nagekeken**. Uw naam en het tijdstip komen in de geschiedenis.
6. Klik op **Bevestigen**. De factuur wordt geboekt en over de eigenaars verdeeld.

## Stappen voor een document

Keuringsverslagen, verzekeringspolissen en offertes kan de assistent ook herkennen. Hij bepaalt over welke VME het document gaat en wat voor document het is, en zet het bij die VME:

1. Ga naar **VME > VME's** en open de VME.
2. In de geschiedenis onderaan staat een bericht "Document ontvangen en geklasseerd", met het document als bijlage, het soort document en de zekerheid.
3. Klopt het soort of de VME niet, verwijder het bericht dan en zet het document zelf bij de juiste VME.

Het automatisch in de juiste **map** zetten komt er met het documentbeheer. Tot dan staan de documenten bij de bijlagen van de VME.

## Voorbeeld uit de demodata

In de demo komen drie PDF-facturen binnen:

| Factuur | VME | Wat de assistent zegt |
| --- | --- | --- |
| Liftonderhoud Voorbeeld BV, LO-2026-0412, 580,80 € | Residentie Linde | Alles in orde: gekende leverancier, bevestigd rekeningnummer, liftsleutel ingevuld |
| Energieleverancier Voorbeeld NV, EV-2026-110412, 375,10 € | Hof ter Beuken | **Gevaar**: "ons rekeningnummer is gewijzigd". Het IBAN op de factuur is niet de bevestigde rekening BE86 9990 0090 0150 |
| Dakwerken Voorbeeld BV, DW-26-077, 901,00 € (6% btw) | Kaaihuis | **Gevaar**: nieuwe leverancier, niet aangemaakt; geen verdeelsleutel tot u er een kiest |

En drie documenten: een keuringsverslag van de lift van Residentie Linde, een brandpolis van Hof ter Beuken en een offerte voor de gevel van het Kaaihuis.

## Veelgestelde vragen

**Moet ik de assistent zelf starten?**
In het prototype start de beheerder hem met een script, na het binnenhalen van de mails. In een echte installatie draait dat script elke paar minuten.

**Wat als de PDF een scan of foto is?**
Het taalmodel leest ook scans, maar de zekerheid is dan vaak lager. Velden met een lage zekerheid krijgen altijd "nakijken".

**Wat als de assistent een veld niet vindt?**
Dan blijft het leeg en staat er "Niet gelezen: vul zelf in vanuit de PDF". Hij verzint niets.

**Waarom staat er geen rekeningnummer op mijn factuur, terwijl het op de PDF staat?**
Omdat het niet overeenkomt met een bevestigde rekening van de leverancier. Bel de leverancier, voeg de rekening toe en laat ze bevestigen, en klik op **Opnieuw controleren**.

**Wordt er iets naar de leverancier gestuurd?**
Nee. De assistent leest alleen en vult een concept in.

**Waar gaat de PDF naartoe?**
Naar het taalmodel (Claude van Anthropic) om gelezen te worden. Zonder sleutel draait de demo met een eenvoudige nabootsing die alleen de demo-PDF's kan lezen.
