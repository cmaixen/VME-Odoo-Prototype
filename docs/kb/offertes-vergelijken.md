# Hoe vergelijk ik offertes voor werken met de AI?

Voor grotere werken vraagt u meerdere offertes, en de algemene vergadering kiest. Offertes van aannemers zien er telkens anders uit: de ene rekent de stelling mee, de andere niet; de ene rekent 6% btw, de andere 21%. De AI leest twee tot vier offertes voor u en zet de verschillen naast elkaar in één tabel, met bij elke waarde de pagina in de offerte waar ze staat. U kijkt de tabel na, past ze aan waar nodig en keurt ze goed. Daarna gaat ze als PDF mee met de oproeping van de AV.

De AI maakt alleen een **concept**. Ze geeft geen advies over welke aannemer beter is en verstuurt niets: u beslist wat in de vergelijking staat, en de AV kiest de aannemer.

## Stappen

### 1. De offertes opladen

1. Open het werkdossier: **VME > Werken en schade > Werkdossiers**.
2. Vul op het tabblad **Offertes** per offerte de aannemer, de datum en het bedrag in, en hang in de kolom **Offerte (PDF)** de PDF van de aannemer eraan.
3. U hebt twee tot vier offertes met een PDF nodig.

### 2. De vergelijking vragen

1. Klik bovenaan op **Offertes vergelijken**.
2. Odoo opent de vergelijking met de status **Wacht op AI**. De kolommen staan in de volgorde waarin de offertes binnenkwamen.
3. De AI leest de offertes. Op dit moment start een collega met toegang tot de server dat lezen (zie de vraag hieronder); daarna staat er een concept klaar en krijgt de verantwoordelijke van het werkdossier de taak **Offertevergelijking nakijken**.

### 3. Nakijken en aanpassen

Open de vergelijking via de knop **Vergelijking** op het werkdossier of via **VME > Werken en schade > Offertevergelijkingen**.

- Het tabblad **Vergelijking** toont de **samenvatting** en de **tabel**: per post (werfinrichting, stelling, voegwerk …) en per voorwaarde (prijs, btw-tarief, uitvoeringstermijn, geldigheid, betalingsvoorwaarden, waarborg, verzekering, voorbehouden) wat elke offerte zegt.
- Achter elke waarde staat **(p. 2)**: de pagina in de offerte. Klik erop en de PDF opent op die pagina. Kijk zo elke waarde na.
- **Rood** betekent dat iets ontbreekt in een offerte terwijl een andere het wel meerekent. **Geel** betekent nakijken, bijvoorbeeld een ander btw-tarief of een voorbehoud.
- Bovenaan staan de **aandachtspunten** die Odoo zelf berekent: een verschillend btw-tarief, een totaal dat niet klopt met het bedrag zonder btw plus btw, een bedrag in het werkdossier dat niet overeenkomt met de offerte, een post die ontbreekt, een waarde zonder pagina, of een samenvatting die naar een aanbeveling klinkt.
- Klopt iets niet, pas het dan aan op het tabblad **Aanpassen**: elke rij heeft per offerte een waarde, een paginanummer en een status. Bedragen en btw-tarief van elke offerte past u aan op het tabblad **Offertes**.
- Pas de **samenvatting** aan. Ze moet feitelijk en neutraal blijven: wat verschilt, niet wie de beste is.

### 4. Goedkeuren en meesturen met de oproeping

1. Kies in **Voor de AV** de algemene vergadering waarop de werken voorgelegd worden.
2. Klik op **PDF bekijken** om het resultaat te zien. Zolang de vergelijking niet goedgekeurd is, staat er **CONCEPT** bovenaan.
3. Klik op **Goedkeuren**. Odoo maakt de PDF, zet ze bij het werkdossier (in het berichtenoverzicht) en sluit de taak af. Er wordt niets verstuurd.
4. Maakt u daarna de oproepingen voor die AV (**Oproepingen aanmaken**), dan zit de vergelijking bij de bijlagen van elke oproeping. U verstuurt de oproepingen zelf, zoals altijd.

Wilt u na het goedkeuren nog iets wijzigen, klik dan op **Terug naar concept**, pas aan en keur opnieuw goed.

## Voorbeeld uit de demodata

In **Residentie Linde** staat het werkdossier **Gevelrenovatie voor- en achtergevel** (budget 50.000 euro) met drie offertes als PDF:

| Aannemer | Totaal incl. btw | Opvallend |
| --- | --- | --- |
| Gevelwerken Fictief BV | 48.548,00 euro | volledig, 6% btw |
| Renovatiebedrijf Voorbeeld NV | 36.941,00 euro | stelling niet inbegrepen, geen verzekering alle bouwplaatsrisico's, prijsherziening na 31/12/2026 |
| Bouwonderneming Denkbeeld BV | 53.240,00 euro | 21% btw in plaats van 6%, geen waterafstotende behandeling |

Klik op **Offertes vergelijken** en laat de AI lezen. De vergelijking toont onder meer:

- de rij **Stelling** in het rood bij Renovatiebedrijf Voorbeeld NV, met de tekst uit de offerte ("te plaatsen door een derde in opdracht van de VME", p. 2);
- het btw-tarief van 21% in het geel, met het aandachtspunt dat het tarief verschilt;
- het aandachtspunt dat in het werkdossier 44.000 euro staat voor Bouwonderneming Denkbeeld BV, terwijl de offerte 53.240 euro incl. btw vermeldt (het bedrag werd zonder btw ingevuld). Verbeter het bedrag op het werkdossier en het punt verdwijnt.

## Veelgestelde vragen

**Wie start het lezen door de AI?**
In het prototype draait de AI als een apart programma naast Odoo. Een collega met toegang start het met `python offertes.py` in de map `ai`. Zonder sleutel voor het taalmodel draait het in een testmodus die alleen de demo-offertes kan lezen.

**Mag ik de vergelijking zo doorsturen naar de eigenaars?**
Pas na uw controle en goedkeuring, en alleen als bijlage bij de oproeping die u zelf verstuurt. De AI kan zich vergissen; de paginanummers zijn er om dat snel na te kijken. Onderaan de PDF staat dat de tekst van de offerte zelf geldt.

**Waarom geeft de vergelijking geen advies?**
De algemene vergadering kiest de aannemer. Een vergelijking die een aannemer aanbeveelt, kan de keuze sturen. Daarom somt ze alleen de feitelijke verschillen op. Schrijft u zelf een advies, zet het dan in de oproeping of de toelichting bij het agendapunt, niet in de vergelijking.

**Een offerte rekent 21% btw, de andere 6%. Wie heeft gelijk?**
Voor renovatie van een woning die minstens tien jaar oud is, geldt onder voorwaarden 6%. Odoo markeert het verschil, maar beslist niet. Vraag de aannemer om uitleg of een aangepaste offerte.

**Ik heb vijf offertes.**
De vergelijking neemt er hoogstens vier. Hang alleen aan de vier offertes die u wilt vergelijken een PDF, of maak twee vergelijkingen.

**De AI las een bedrag verkeerd.**
Pas het aan op het tabblad **Aanpassen** (de tekst in de tabel) en op het tabblad **Offertes** (het bedrag waarmee Odoo rekent). De aandachtspunten worden meteen opnieuw berekend.

**Ik klik op Opnieuw laten lezen. Wat gebeurt er met mijn aanpassingen?**
Die gaan verloren: de AI maakt een nieuwe tabel en samenvatting. Gebruik het alleen als u een andere PDF hebt opgeladen.
