# Hoe verdeel ik verwarming of water op verbruik?

Sommige kosten verdeel je niet alleen volgens de quotiteiten, maar ook volgens wat elke kavel echt verbruikt: de verwarming met kostenverdelers op de radiatoren, het water met een teller per appartement. Het platform doet dat met een sleutel **Op verbruik**: een **vast deel** van de factuur volgens de quotiteiten van de sleutel, en een **variabel deel** volgens het verbruik in de kostperiode van de factuur. Hoeveel procent vast is, kies je per sleutel en dus per VME, zoals het reglement van mede-eigendom het voorschrijft.

## Stappen

### 1. De sleutel op verbruik instellen

1. Ga naar **VME > Verdeelsleutels** en open de sleutel (of maak er een, zie [Verdeelsleutels en quotiteiten](verdeelsleutels.md)).
2. Kies als **Soort** "Op verbruik". Er verschijnt een blok **Verdeling op verbruik**.
3. Kies bij **Tellers** welke tellers het verbruik geven: Verwarming (kostenverdeler), Water of Elektriciteit.
4. Vul het **Vast deel (%)** in, bijvoorbeeld 30. Het **Variabel deel** (70) rekent het platform zelf uit.
5. Vul de quotiteiten in voor het vaste deel en sla op.

### 2. De meterstanden inlezen

Het meteropnamebedrijf bezorgt de meterstanden meestal als CSV-bestand.

1. Ga naar **VME > Verbruik > Meterstanden inlezen**.
2. Kies de **VME** en het **Bestand**.
3. Klik op **Controleren**. Het platform leest het bestand, maar slaat nog niets op. Je ziet hoeveel meterstanden en tellers erin staan, de opnamedatums en een lijst met fouten en waarschuwingen.
4. Zijn er fouten (rood), verbeter dan het bestand, kies het opnieuw en klik weer op **Controleren**.
5. Geen fouten meer: klik op **Importeren**. Je krijgt de lijst van de ingelezen meterstanden.

Een teller die het platform nog niet kent, wordt bij het importeren aangemaakt bij de kavel uit het bestand (dat staat als waarschuwing in de controle). Meterstanden die al ingelezen waren, worden overgeslagen; je kan hetzelfde bestand dus gerust een tweede keer kiezen.

Het bestand heeft deze kolommen, gescheiden door een puntkomma:

| kavel | teller | soort | datum | stand | coefficient | plaats |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | KV-B1-1 | verwarming | 31/10/2026 | 1883 | 1,2 | Woonkamer |

De **coëfficiënt** is die van de radiator (bij een kostenverdeler) en mag leeg blijven: dan is ze 1. **Plaats** is ook niet verplicht.

Je kan meterstanden ook met de hand ingeven: open de kavel, tabblad **Tellers**, kies de teller en voeg een regel toe in **Meterstanden**. Of gebruik **VME > Verbruik > Meterstanden**.

### 3. De factuur verdelen

Geef de factuur in zoals elke andere (zie [Een leveranciersfactuur verdelen](factuur-verdelen.md)) en vul de **Kostperiode** juist in: het verbruik wordt gemeten van het begin tot het einde van die periode. Kies de sleutel op verbruik, of laat de verdeelregel van de leverancier dat doen, en klik op **Bevestigen**.

In de verdeling zie je per eigenaar het **Verbruik** en het bedrag. Via de kolomkeuze (rechts in de kolomtitels) toon je ook **Vast deel** en **Variabel deel**. Op de jaarafrekening staat onder de sleutel het verbruik van de eigenaar, met het vaste en het variabele deel.

## Voorbeeld uit de demo

**Hof ter Beuken** heeft de sleutel **Verwarming op verbruik**: 30% vast volgens de verwarmingsquotiteiten, 70% volgens de kostenverdelers. Elk appartement heeft twee kostenverdelers (woonkamer, coëfficiënt 1,2, en slaapkamer, coëfficiënt 0,8). De demohistoriek leest de opnames van 31/12/2025, 31/03, 30/06 en 30/09/2026 in en verdeelt de drie gasfacturen van **Gasleverancier Voorbeeld NV** daarmee.

Probeer het zelf:

1. Lees het bestand `hof_ter_beuken_2026-10-31.csv` in (te vinden in de map `demo_data/meterstanden` van de module, of vraag het aan de beheerder): 48 meterstanden van 31 oktober.
2. Kies rechtsboven het bedrijf **Hof ter Beuken** en maak een factuur van **Gasleverancier Voorbeeld NV**, kostperiode 01/10/2026 tot 31/10/2026, bijvoorbeeld 4.000 euro.
3. Bevestig. De verwarmingssleutel komt uit de verdeelregel, en de factuur wordt verdeeld over 23 eigenaars, elk volgens het verbruik van oktober.

## Veelgestelde vragen

**Ik krijg "Ontbrekende meterstand vóór of na ...".**
Voor een teller ontbreekt een opname: het platform heeft een meterstand nodig op of vóór het begin van de kostperiode én op of na het einde. Lees de ontbrekende meterstanden in en klik opnieuw op **Verdeel over eigenaars**. Gebeurde dit bij het bevestigen, dan is de factuur wel geboekt en staat de reden in het logboek.

**Ik krijg "Geen teller ... voor kavel ...".**
Een kavel staat in de sleutel, maar heeft geen teller van die soort. Voeg de teller toe (of haal de kavel uit de sleutel als hij echt niet meedoet).

**De opname valt niet op het begin of einde van de kostperiode.**
Dat is normaal. Tussen twee opnames rekent het platform het verbruik gelijk per dag uit. Een opname op 31/12 en een factuur van 1/1 tot 31/3 sluiten perfect aan; een opname op 15/01 geeft een schatting voor de eerste twee weken.

**Een kavel wordt verkocht midden in de periode.**
Laat bij voorkeur een tussenopname doen op de dag van de akte en geef die in met de datum van de dag vóór de akte: dan krijgen verkoper en koper elk hun eigen verbruik. Zonder tussenopname wordt het verbruik tussen de twee opnames gelijk per dag verdeeld. Het vaste deel wordt altijd per dag verdeeld.

**Een stand is lager dan de vorige.**
Dat weigert het platform: een meterstand gaat nooit naar beneden. Is de teller vervangen, maak dan een nieuwe teller aan en archiveer de oude pas als alle facturen over de oude periode verdeeld zijn.

**Kan ik alles vast of alles op verbruik verdelen?**
Ja: 100% vast verdeelt alleen op quotiteiten (dan zijn geen meterstanden nodig), 0% vast verdeelt alles op verbruik.

**Waar komt de 30% vandaan?**
Uit het reglement van mede-eigendom of een beslissing van de algemene vergadering. Elk gebouw kan een ander percentage hebben; het platform neemt het percentage van de sleutel.
