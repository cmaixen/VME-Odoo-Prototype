# Hoe stort ik de huur door aan de verhuurder?

Als rentmeester int het kantoor de huur en de lasten van de huurders op zijn **derdenrekening**. Dat geld is van de verhuurder. Elke maand maak je per verhuurder een **doorstorting**:

> ontvangen huur en lasten − kosten die het kantoor voor hem betaalde − ereloon van de rentmeester (met btw) = door te storten

Bij elke doorstorting horen een **afrekening als PDF** voor de verhuurder, een **ereloonfactuur** en een **overschrijving** in een SEPA-betaalbatch. Odoo verstuurt en betaalt niets zelf: jij bevestigt, keurt goed en laadt het betaalbestand zelf op in de bank.

> Kies rechtsboven in Odoo het bedrijf van het rentmeesterkantoor (in de demo **Rentmeester Voorbeeld BV**), anders zie je de facturen en betaalbatches niet.

## Eenmalig: het kantoor en de beheermandaten

1. **Rentmeester > Configuratie > Kantoor en derdenrekening**: open het kantoor en kies bij **Derdenrekening** de rekening waarop de huurders betalen. Van die rekening vertrekken de doorstortingen.
2. **Rentmeester > Configuratie > Beheermandaten > Nieuw**, per verhuurder:
   - de **verhuurder** en zijn **rekening**;
   - het **ereloon**: een **percentage van de ontvangen huur** (vink **Ook op de lasten** aan als het percentage ook op de lasten geldt) of een **vast bedrag per maand**;
   - de **btw** op het ereloon: standaard 21 %. De rentmeester is btw-plichtig; de huur zelf niet.
3. Bevestig de rekening van de verhuurder en de derdenrekening: open de rekening en zet **Betalen** aan. Alleen een gebruiker met dat recht kan dat. Zolang een rekening niet bevestigd is, komt de doorstorting niet in een betaalbatch; het mandaat en de doorstorting tonen dan een waarschuwing.

De huurcontracten van de verhuurder krijgen het mandaat vanzelf; je ziet het in het contract bij **Beheermandaat**.

## Een kost betalen voor de verhuurder

Betaalt het kantoor een factuur voor de verhuurder (bijvoorbeeld een loodgieter in zijn appartement), geef die dan in als leveranciersfactuur in het bedrijf van het kantoor en kies bij **Huurcontract (kost voor de verhuurder)** het contract. Odoo zet de factuurregels op de rekening van de verhuurder. De volgende doorstorting trekt de kost af.

## Elke maand: de doorstortingen

1. **Rentmeester > Doorstortingen > Doorstortingen maken**: kies de maand (standaard de vorige) en klik op **Doorstortingen maken**. Odoo maakt per verhuurder een concept met:
   - de **huur en lasten** die tot het einde van die maand **ontvangen** zijn en nog niet doorgestort werden. Een huurder die nog niet betaald heeft, staat er niet in; een gedeeltelijke betaling telt voor het betaalde deel;
   - de **kosten** die het kantoor voor de verhuurder betaalde;
   - het **ereloon** per mandaat, met de btw.
2. Open een doorstorting en kijk de regels na. **Afrekening (PDF)** toont de afrekening zoals de verhuurder ze krijgt (met "CONCEPT" zolang ze niet bevestigd is).
3. Klik op **Bevestigen**. Odoo boekt de ereloonfactuur, het doorstortingsstuk en de verrekening van het ereloon met de huur. Er wordt niets verstuurd.
4. Klik op **Goedkeuren voor betaling**.
5. Selecteer in de lijst de goedgekeurde doorstortingen en klik op **Betaalbatch maken**, of doe het in de doorstorting zelf. Je krijgt een betaalbatch in concept.
6. In de betaalbatch: **SEPA-bestand maken**, **Bestand downloaden**, laad het op in de bankapplicatie van het kantoor en onderteken daar. Klik daarna op **Opgeladen in de bank**. Dat is dezelfde betaalbatch als voor de VME's (zie [betalingen](betalingen.md)).
7. Stuur de afrekening (PDF) en de ereloonfactuur zelf naar de verhuurder.

In de kolom **Betaling** van de lijst zie je waar elke doorstorting staat: goed te keuren, klaar voor betaalbatch, in betaalbatch, verstuurd, doorgestort.

## Voorbeeld uit de demo

Verhuurder van *Linde A2* (mandaat 7 % op de huur): in september betaalde het kantoor 242 euro voor een herstelling van de boiler. De doorstorting van september trekt die af. De doorstortingen van januari tot september zijn doorgestort; die van oktober staan klaar als concept. *Linde A7* betaalde de huur van oktober niet: die zit dus niet in de doorstorting van oktober en komt mee zodra ze betaald is. Voor *Beuken B23* rekent het kantoor een vast ereloon van 65 euro per maand.

## Veelgestelde vragen

**Het saldo is negatief. Wat nu?**
Dan zijn de kosten en het ereloon hoger dan wat er binnenkwam. Bevestigen kan niet; klik op **Overdragen**. De volgende doorstorting neemt alles mee, ook een vast ereloon voor de overgeslagen maand.

**Ik heb een doorstorting overgedragen en wil ze toch maken.**
Open ze en klik op **Terug naar concept**; Odoo rekent ze opnieuw uit.

**Waarom staat de doorstorting niet in de betaalbatch?**
Kijk op het tabblad **Niet opgenomen** van de betaalbatch. Meestal is de rekening van de verhuurder of de derdenrekening nog niet bevestigd, of is de doorstorting nog niet goedgekeurd.

**Wordt het ereloon twee keer aangerekend als ik een maand overdraag?**
Nee. Het ereloon wordt pas geboekt bij het bevestigen, en een bevestigde doorstorting neemt nooit iets mee dat al in een eerdere bevestigde doorstorting zat.

**Moet de verhuurder het ereloon nog betalen?**
Nee. Het ereloon wordt verrekend met de huur: de ereloonfactuur staat meteen als betaald en de verhuurder krijgt het saldo.

**Bij Bevestigen krijg ik een melding dat de rekening van het bedrijf niet vertrouwd is.**
Odoo boekt de ereloonfactuur pas als de eigen rekening van het kantoor bevestigd is. Laat iemand met dat recht de rekening bevestigen (schakelaar **Betalen**) en bevestig opnieuw.

**Kan ik een bevestigde doorstorting nog wijzigen?**
Nee. Is er iets mis, maak dan een creditnota op de ereloonfactuur en vraag de boekhouder om het doorstortingsstuk te corrigeren.
