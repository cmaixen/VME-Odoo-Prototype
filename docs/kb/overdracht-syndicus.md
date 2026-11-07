# Hoe draag ik een VME over aan een nieuwe syndicus?

Kiest de algemene vergadering een andere syndicus, dan moet je als vertrekkende syndicus het volledige dossier van het gebouw overdragen: de boekhouding, de bankrekeningen, de lopende werken en schadedossiers, de procedures, de contracten en het archief. De wet geeft je daarvoor dertig dagen na het einde van je mandaat.

Het platform maakt dat pakket in één keer: een zip-bestand dat je downloadt en zelf aan de nieuwe syndicus bezorgt. Er wordt niets verstuurd.

## Wat zit er in het pakket?

| Map | Inhoud |
| --- | --- |
| (bovenaan) | De gegevens van de VME als CSV-bestanden: kavels, eigenaars en eigendommen, verdeelsleutels, leveranciers, lopende werken, procedures, mandaten en de **openingsbalans** op de overdrachtsdatum. Het zijn dezelfde bestanden als die van [Een VME overnemen uit een ander syndicuspakket](migratie.md). Werkt de nieuwe syndicus ook met dit platform, dan leest die het pakket in één keer in. |
| `rapporten` | Het **overdrachtsdocument** om samen te tekenen, de laatste **jaarafrekening**, de **balans en resultatenrekening**, de **openstaande saldi per eigenaar** en de **stand van het reservekapitaal**. |
| `archief` | Alle documenten van de VME, per map: basisakte, notulen, verzekeringspolissen, attesten, keuringsverslagen, contracten. Ook de bijlagen bij de VME, zoals de jaarafrekeningen uit een vorig pakket. |

Het overdrachtsdocument somt op wat je overdraagt:

- de twee bankrekeningen met hun saldo en de stand van het werk- en reservekapitaal;
- de lopende werken, met status, aannemer en wat al gefactureerd is;
- de open schadedossiers, met verzekeraar en dossiernummer;
- de gerechtelijke procedures en de invorderingen die bij een advocaat liggen;
- de lopende contracten en verzekeringspolissen, met hun einddatum en opzegtermijn;
- de mandaten in de raad van mede-eigendom en van de commissaris;
- de lijst van alle bestanden in het pakket, je opmerkingen en een vak om te tekenen voor overdracht en voor ontvangst.

## Stappen

1. Open de VME via **VME > VME's**.
2. Klik bovenaan op **Overdracht aan nieuwe syndicus**.
3. Vul in:
   - **Nieuwe syndicus**: wie het pakket krijgt. Is er nog geen opvolger, dan is dat de voorzitter van de laatste algemene vergadering.
   - **Overdrachtsdatum**: de laatste dag van je mandaat. Alle saldi en de openingsbalans staan op die datum. Het venster toont meteen tegen wanneer je moet overdragen (dertig dagen later).
   - **Jaar jaarafrekening en balans**: staat standaard op het laatste jaar met boekingen.
   - **Opmerkingen**: wat je nog op het overdrachtsdocument wilt zetten, bijvoorbeeld welke sleutels je apart overhandigt.
4. Kijk de samenvatting na. Een geel vak meldt wat de nieuwe syndicus na de overstap zelf moet rechtzetten, bijvoorbeeld een saldo dat op de wachtrekening komt.
5. Klik op **Pakket maken (zip)**. Het bestand wordt gedownload.
6. Het pakket staat ook als bijlage in de chatter van de VME, met een interne notitie wie het wanneer maakte.
7. Bezorg het pakket zelf aan de nieuwe syndicus, bijvoorbeeld via een beveiligde link, en laat het overdrachtsdocument tekenen voor ontvangst.

## Voorbeeld uit de demodata

Laad Residentie Esdoorn in via **VME > Configuratie > Overstap uit ander pakket** met de voorbeeldbestanden uit `demo_data/migratie/residentie-esdoorn` (zie [migratie](migratie.md)). Maak daarna het overdrachtspakket met overdrachtsdatum 31/03/2027. Het pakket bevat dan de tien kavels, de eigenaars met hun saldo (ook de erfgenaam zonder kavel), de twee sleutels, de drie leveranciers en een openingsbalans met 8.432,15 euro op de rekening werkkapitaal en 24.600,00 euro reservekapitaal.

Wil je zien dat het pakket echt terug inleest: hernoem de oude VME en zet er andere rekeningnummers op (anders zegt de proefrun terecht dat die al bestaan), en laad de zip op in een nieuwe overstap. De proefrun vindt geen fouten.

## Veelgestelde vragen

**Wordt het pakket naar de nieuwe syndicus gemaild?**
Nee. Het platform maakt alleen de zip. Jij beslist hoe en wanneer je ze bezorgt.

**De nieuwe syndicus gebruikt een ander pakket. Heeft die er iets aan?**
Ja. De CSV-bestanden zijn gewone tabellen die elk pakket of Excel kan openen, en het formaat is beschreven. De rapporten en het archief zijn PDF's.

**Waarom staat er een saldo op de wachtrekening (499000)?**
De openingsbalans kent bankrekeningen, fondsen, eigenaars, leveranciers en gewone rekeningen. Een saldo dat daar niet in past, bijvoorbeeld op een derde bankrekening of op een btw-rekening, komt op de wachtrekening met de oorspronkelijke rekening in de omschrijving. De samenvatting en het overdrachtsdocument melden het, zodat de nieuwe syndicus het juist kan boeken.

**Kan ik een overdrachtsdatum in het verleden kiezen?**
Ja. De saldi en de openingsbalans staan dan op die datum. Bij de openstaande saldi per eigenaar staan de facturen van vóór die datum die vandaag nog openstaan.

**Zijn de oude boekjaren in detail mee?**
Nee, net als bij een overstap: de nieuwe syndicus start met één openingsboeking. Het detail zit in de jaarafrekening, de balans en de documenten in het archief.

**Kan de commissaris van de rekeningen een pakket maken?**
Nee. De commissaris kan alles inkijken, maar ziet de knop niet.
