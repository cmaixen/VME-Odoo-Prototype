# Hoe beheer ik een verhuurd appartement als rentmeester?

Een eigenaar die zijn appartement verhuurt, kan het beheer van die huur aan het kantoor geven: de rol **rentmeester**. Dat staat los van de VME. De huur is van de verhuurder, niet van de vereniging van mede-eigenaars; daarom werk je in een aparte app, **Rentmeester**, en komen huurfacturen in de boekhouding van het rentmeesterkantoor, niet in die van de VME.

Wat de app doet:

- het **huurcontract** bijhouden: pand, verhuurder, huurders, duur, huur, lasten, waarborg en gewest;
- elke maand de **huurfacturen** klaarzetten;
- jaarlijks de **indexering** berekenen volgens de gezondheidsindex, met de **indexatiebrief** als concept;
- de **lasten afrekenen** met de huurder, vertrekkend van de jaarafrekening van de VME aan de eigenaar;
- **opzeggingen en einde huur** opvolgen, met een taak vóór elke termijn;
- elke maand de huur **doorstorten aan de verhuurder**, min het ereloon en de kosten: zie [de huur doorstorten](doorstorting-verhuurder.md).

Er wordt nooit iets automatisch verstuurd: brieven en facturen zijn concepten die je zelf nakijkt en verstuurt.

> Werk je in de facturen van de rentmeester, kies dan rechtsboven in Odoo het bedrijf van het rentmeesterkantoor (in de demo **Rentmeester Voorbeeld BV**). Anders zie je de huurfacturen niet in de lijsten. De contracten, indexeringen en afrekeningen zie je altijd.

## Een huurcontract invoeren

1. Open **Rentmeester > Huurcontracten** en klik op **Nieuw**.
2. Vul het **pand** in: kies de kavels (bijvoorbeeld het appartement en de garage). VME, adres en **gewest** komen vanzelf mee; voor een huis buiten een VME tik je het adres en kies je het gewest.
3. Kies de **verhuurder** en de **huurders**. De eerste huurder krijgt de facturen. Bij **Beheerder** staat wie de taken krijgt (opzegtermijn, indexering, einde huur); standaard bent u dat zelf. Is er geen beheerder, dan gaan ze naar de dossierbeheerder van de VME.
4. Vul de **datum van ondertekening**, de **ingangsdatum** en de **duur** in. Een contract van hoogstens drie jaar is kortlopend; de einddatum en de uiterste opzegdatum rekent Odoo uit.
5. Vul de **basishuur** per maand in (zonder lasten), de **lasten** per maand en of het een provisie (jaarlijks afgerekend) of een forfait is.
6. Vul de **huurwaarborg** in. Is hij hoger dan wat in het gewest mag, dan verschijnt een waarschuwing.
7. Kies het **EPC-label**. Dat telt voor de indexering (zie verder).
8. Kijk op het tabblad **Lasten per rubriek** welk deel van elke soort kost de huurder draagt. Standaard: schoonmaak, lift, verwarming en elektriciteit en water van de gemene delen volledig; verzekering, grote werken en het beheer door de syndicus niet.
9. Klik op **Contract activeren**.

Op de kavel in de app **VME** zie je daarna de huidige huurders en het huurcontract.

## Huurfacturen

Elke nacht zet Odoo voor elk lopend contract de factuur van de maand klaar als **concept**: de huur en de lasten, op naam van de huurder, met de vermelding dat het kantoor ze int in naam van de verhuurder. Begint of eindigt de huur in de loop van de maand, dan rekent Odoo per dag.

Wil je zelf facturen maken (bijvoorbeeld voor de volgende maand), gebruik dan **Rentmeester > Huurfacturen > Huurfacturen maken**: kies de maand, eventueel enkele contracten, en of je ze meteen wilt boeken. Een contract dat al een factuur heeft voor die maand, wordt overgeslagen.

## De jaarlijkse indexering

Op de verjaardag van het contract mag de huur aangepast worden aan de gezondheidsindex:

> nieuwe huur = basishuur × nieuw indexcijfer / aanvangsindex

- De **aanvangsindex** is de gezondheidsindex van de maand vóór de maand waarin het contract ondertekend is.
- Het **nieuwe indexcijfer** is dat van de maand vóór de verjaardag.
- Een **mondeling** contract of een contract dat indexering **uitsluit**, wordt niet geïndexeerd.

**De indexstop van 2022-2023.** Tijdens de energiecrisis mocht een woning met een slecht EPC-label een jaar lang niet of maar half geïndexeerd worden. Die gemiste indexering wordt nooit ingehaald: Odoo rekent daarvoor een **correctiefactor** uit die bij elke latere indexering blijft gelden. De regels verschillen per gewest:

| Gewest | Verjaardagen tijdens de stop | Volledig | Half | Niet |
| --- | --- | --- | --- | --- |
| Vlaanderen | 1 oktober 2022 – 30 september 2023 | A+ tot C | D | E, F of geen EPC |
| Brussel | 14 oktober 2022 – 13 oktober 2023 | A tot D | E | F, G of geen EPB |
| Wallonië | 1 november 2022 – 31 oktober 2023 | A tot C | D en E | F, G of geen PEB |

**Hoe je indexeert.** Ongeveer zes weken voor de verjaardag zet Odoo een indexering klaar met een taak "Indexatiebrief nakijken en versturen", zodra het indexcijfer van de maand ervoor in de tabel staat. Je kunt ook zelf op **Indexering berekenen** klikken in het contract.

1. Open de indexering. Je ziet de berekening: basishuur, aanvangsindex, nieuw indexcijfer, eventueel de correctiefactor, en de nieuwe huur.
2. Klik op **Indexatiebrief (PDF)** en kijk de brief na. Zolang de indexering een concept is, staat er "CONCEPT" op.
3. Verstuur de brief zelf naar de huurder.
4. Klik op **Bevestigen**. Vanaf de datum in **Nieuwe huur vanaf** gebruiken de huurfacturen de nieuwe huur; huurfacturen die nog in concept stonden, worden opnieuw gemaakt.

Vraag je de indexering laat, dan geldt ze hoogstens **drie maanden** terug vóór de datum van de brief. Odoo zet de datum "Nieuwe huur vanaf" daar zelf op.

**De indexcijfers bijwerken.** Statbel publiceert elke maand de gezondheidsindex. Een beheerder vult hem in onder **Rentmeester > Configuratie > Gezondheidsindex** (basis 2013 = 100).

## De lasten afrekenen met de huurder

Betaalt de huurder elke maand een provisie voor de lasten, dan reken je die eens per jaar af. Het vertrekpunt is de **jaarafrekening van de VME aan de verhuurder**: het platform neemt elke leveranciersfactuur daaruit, het deel van de verhuurder voor de verhuurde kavels, en dan:

1. alleen de dagen van de kostperiode dat de huur liep;
2. maal het percentage van de rubriek in het contract (schoonmaak 100%, verzekering 0%, enzovoort).

De som is wat de huurder draagt. Daar gaan de gefactureerde provisies lasten van het jaar af; het verschil is bij te betalen of terug te krijgen. Reservekapitaal komt nooit bij de huurder terecht.

1. Open het contract en klik op **Afrekening lasten**.
2. Kies het jaar en klik op **Berekenen**.
3. Kijk de regels na: per factuur de rubriek, het deel van de verhuurder, het deel tijdens de huur, het percentage en het bedrag voor de huurder.
4. Klik op **Afrekening (PDF)** voor de afrekening voor de huurder.
5. Klik op **Conceptfactuur maken**. Odoo maakt een factuur (of een creditnota als de huurder geld terugkrijgt) als concept; jij boekt en verstuurt ze.

Een forfait wordt nooit afgerekend.

**In welke rubriek komt een kost?** Eerst kijkt Odoo naar de leverancier (zo staat de schoonmaakfirma bij de rubriek schoonmaak), dan naar de soort sleutel (liftsleutel, verwarmingssleutel), dan naar de kostenrekening (612 is elektriciteit en water, 614 verzekering). Je past de rubrieken aan onder **Rentmeester > Configuratie > Rubrieken van lasten**. Een kost die nergens past, blijft voor de verhuurder.

## Opzeggen en einde van de huur

- Het contract toont de **uiterste opzegdatum**: voor een kortlopend contract drie maanden vóór het einde (anders wordt het een contract van negen jaar), voor een contract van negen jaar zes maanden voor de verhuurder en drie voor de huurder. Dertig dagen vooraf krijg je een taak.
- Zegt iemand op, vul dan **Opzeg gegeven op**, **Opzeg door** en de **opzegtermijn** in en klik op **Opzeg registreren**. De termijn begint de eerste dag van de maand na de opzeg; Odoo rekent het einde uit en zet een taak voor de plaatsbeschrijving en de huurwaarborg. Na het einde komen er geen huurfacturen meer.
- Klik op **Huur beëindigen** als de huurder vertrokken is.

## Voorbeeld uit de demo

Na **Demodata laden** en **Demohistoriek 2026 laden** beheert **Rentmeester Voorbeeld BV** drie verhuurde appartementen:

| Contract | Huur | Bijzonder |
| --- | --- | --- |
| Residentie Linde A2 en garage G2 | sinds 1 november 2021, negen jaar | EPC-label E: geen indexering in november 2022, daarna een correctiefactor. De indexatiebrief voor 1 november 2026 staat klaar als concept. |
| Residentie Linde A7 | sinds 1 maart 2024, drie jaar | Kortlopend: wie wil stoppen, moet uiterlijk op 30 november 2026 opzeggen. Er staat een taak. De huur van oktober is niet betaald. |
| Hof ter Beuken B23 | sinds 1 september 2019, negen jaar | EPC-label D: in september 2023 maar half geïndexeerd. Verwarming via de verwarmingssleutel. |

De huur van januari tot oktober 2026 is gefactureerd en (op één maand na) betaald. Bereken voor het contract van **Linde A2** de afrekening 2026: de huurder draagt schoonmaak, lift en elektriciteit, niet de brandverzekering.

## Veelgestelde vragen

**Waarom staan de huurfacturen niet in de boekhouding van de VME?**
Omdat de huur van de verhuurder is. De VME rekent haar kosten af met de eigenaar; de eigenaar rekent een deel door aan zijn huurder. Het rentmeesterkantoor int de huur voor rekening van de verhuurder. In de boekhouding van het kantoor staat elke verhuurder apart (als analytische rekening).

**De nieuwe indexcijfers staan er nog niet in. Wat nu?**
Dan kan Odoo de indexering nog niet berekenen en probeert het de volgende dag opnieuw. Vul het cijfer in onder **Configuratie > Gezondheidsindex** of klik later op **Indexering berekenen**.

**Kan ik de rubrieken per contract anders zetten?**
Ja. In het tabblad **Lasten per rubriek** van het contract pas je het percentage aan, bijvoorbeeld 50% voor de schoonmaak als dat zo in het contract staat.

**De jaarafrekening van de VME is nog niet af. Kan ik toch afrekenen?**
Ja, maar de afrekening toont dan een waarschuwing en is voorlopig. Klik later op **Herberekenen**, zolang je nog geen factuur gemaakt hebt.

**Worden de brieven met de post verstuurd?**
Nee. Een koppeling met bpost valt buiten het prototype; je drukt de PDF af of verstuurt hem zelf per e-mail.

> De huurregels in dit artikel zijn nog niet juridisch nagekeken. Kijk bij twijfel de regels van het gewest na.
