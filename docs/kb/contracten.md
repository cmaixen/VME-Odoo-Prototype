# Contracten en personeel opvolgen

Elke VME heeft lopende contracten: onderhoud van de lift of de verwarmingsketel, schoonmaak, de brandverzekering, energie en soms een conciërge. Het menu **VME > Contracten** toont ze voor al uw VME's samen. Bij elk contract ziet u tot wanneer het loopt, tot wanneer u nog kunt opzeggen, en wanneer de jaarlijkse evaluatie gepland is.

## Hoe zie ik welke contracten ik binnenkort moet opzeggen of verlengen?

1. Open **VME > Contracten > Lopende contracten**. U ziet de lopende contracten, gegroepeerd per VME.
2. De kolom **Opzeggen uiterlijk op** is de laatste dag waarop de opzeg bij de leverancier moet zijn. De kleur zegt hoe dringend het is:
   - **rood**: binnen 30 dagen
   - **oranje**: binnen 60 dagen
   - **blauw**: binnen 90 dagen
   - **groen**: ruim op tijd
3. Gebruik de filters *Opzeggen binnen 30 dagen* of *Opzeggen binnen 60 dagen*, of klik rechtsboven op het kalendericoon: elk contract staat dan op de dag van zijn opzegtermijn.

**Voorbeeld in de demo:** de schoonmaak van Residentie Linde en het aardgas van Hof ter Beuken moeten uiterlijk op 30 november 2026 opgezegd worden; de brandverzekering van Residentie Linde en de schoonmaak van Kaaihuis uiterlijk op 31 december 2026.

## Hoe voeg ik een contract toe?

1. Open de VME en ga naar het tabblad **Contracten**, of klik in **VME > Contracten** op **Nieuw**.
2. Vul de omschrijving, de soort, de leverancier en het contract- of polisnummer in.
3. Vul de looptijd in:
   - **Begindatum**
   - **Einde huidige periode**: de laatste dag van de lopende periode. Laat leeg voor een contract van onbepaalde duur zonder vaste vervaldag.
   - **Stilzwijgende verlenging**, en met hoeveel maanden het contract dan verlengd wordt (meestal 12)
   - **Opzegtermijn** in maanden. Odoo vult een standaard in volgens de soort (bv. 3 maanden voor een verzekering, 1 maand voor energie, 6 maanden voor een lift). Pas dit aan volgens uw contract.
4. Is het een onderhoudscontract voor een lift of een andere installatie met keuringsplicht? Kies dan ook de **installatie**. Het contract verschijnt dan bij die installatie onder **VME > Keuringen**.
5. Vul eventueel de geraamde jaarkost in.

Odoo berekent dan **Opzeggen uiterlijk op**. Een voorbeeld: een contract tot en met 31 maart 2027 met 3 maanden opzegtermijn moet uiterlijk op 31 december 2026 opgezegd worden.

## Krijg ik een herinnering vóór de opzegtermijn?

Ja. Elke nacht maakt Odoo een taak voor de verantwoordelijke medewerker zodra de opzegtermijn van een lopend contract binnen 60 dagen valt. De taak heeft als vervaldatum de laatste dag om op te zeggen. U ziet ze in het activiteitenicoon bovenaan en bij het contract. Per termijn komt er maar één taak.

Laat u de termijn voorbijgaan bij een contract met stilzwijgende verlenging, dan verlengt Odoo het contract op de einddatum met de afgesproken periode. U ziet dat in de historiek van het contract. Daarna komt er een taak voor de nieuwe termijn.

## Hoe registreer ik een opzeg?

1. Verstuur de opzeg zelf, op de manier die het contract voorschrijft (meestal een aangetekende brief). Odoo verstuurt niets.
2. Open het contract en klik op **Opzeg geregistreerd**.
3. Het contract krijgt de status *Opgezegd* en de datum van vandaag. Op de einddatum zet Odoo het op *Beëindigd*.

Was de opzegtermijn al voorbij, dan waarschuwt Odoo in de historiek: vraag de leverancier dan te bevestigen of het contract toch stopt.

## Hoe doe ik de jaarlijkse evaluatie?

De syndicus moet de contracten voor geregelde leveringen en diensten elk jaar evalueren en die evaluatie voorleggen aan de algemene vergadering.

1. Open het contract en ga naar het tabblad **Evaluaties**. Klik op **Regel toevoegen**.
2. Vul de datum, de beoordeling (*goed*, *voldoende* of *onvoldoende*) en uw voorstel in: verderzetten, heronderhandelen, nieuwe offertes vragen of opzeggen.
3. Kies de algemene vergadering waarop u de evaluatie voorlegt, en schrijf een korte toelichting.

De volgende evaluatie valt een jaar na de laatste. Odoo maakt 30 dagen vooraf een taak. Een contract dat nog nooit geëvalueerd is, krijgt meteen een taak.

Alle evaluaties samen ziet u in **VME > Contracten > Evaluaties**, per VME. Met de filter *Niet verderzetten* vindt u de contracten waarvoor u iets voorstelt.

**Voorbeeld in de demo:** de schoonmaak van Residentie Linde kreeg op de AV van 10 maart 2026 de beoordeling *voldoende*, met het voorstel om nieuwe offertes te vragen. De elektriciteit van Residentie Linde is nog nooit geëvalueerd.

## Hoe worden de facturen van een contract verdeeld?

Een contract verdeelt zelf geen kosten. De facturen van de leverancier worden verdeeld via zijn **verdeelregel** (zie [Verdeelregels en Peppol-facturen](verdeelregels-en-peppol.md)).

Op het contract, onder **Kosten verdelen**, ziet u welke verdeelregel, sleutel en kostenrekening er gelden. Staat er een waarschuwing, dan is er voor die leverancier nog geen verdeelregel: maak er een aan onder **VME > Configuratie > Verdeelregels**.

De knop **Dit jaar** bovenaan toont wat de leverancier sinds 1 januari gefactureerd heeft in die VME. Klik erop om de facturen te zien. Zo vergelijkt u bij de evaluatie de werkelijke kost met de geraamde jaarkost.

## Hoe boek ik de loonkosten van een conciërge?

Een VME met eigen personeel werkt met een sociaal secretariaat. Dat secretariaat stuurt elke maand een factuur met de loonkost: het brutoloon en de werkgeversbijdragen. Op loonkosten staat geen btw.

1. Maak een contract van de soort **Conciërge en personeel**, met het sociaal secretariaat als leverancier.
2. Maak een verdeelregel voor het sociaal secretariaat, met de sleutel waarover de conciërge verdeeld wordt (meestal de algemene sleutel) en de rekening *620300 Bezoldigingen arbeiders*.
3. Boek de maandfactuur als gewone leveranciersfactuur, of laad ze op als Peppol-bestand. Bij **Bevestigen** wordt ze automatisch verdeeld over de eigenaars.

De opzegtermijn van de arbeidsovereenkomst zelf berekent Odoo niet: die hangt af van de anciënniteit. Laat bij zo'n contract het einde van de periode leeg.

**Voorbeeld in de demo:** Hof ter Beuken heeft een conciërge via *Sociaal Secretariaat Voorbeeld vzw*. De loonkosten van januari tot september 2026 (3.250 euro per maand) zijn geboekt en verdeeld volgens de algemene sleutel. Het Peppol-bestand voor oktober staat klaar in `addons/vme_belgie/demo_data/facturen/loonkosten_concierge_hof_ter_beuken_2026-10.xml`. Laad het op in de VME Hof ter Beuken via **Facturatie > Leveranciers > Facturen > Upload** en klik op **Bevestigen**.

## Veelgestelde vragen

**Kloppen de standaard opzegtermijnen?** Het zijn standaardwaarden die nog juridisch nagekeken moeten worden. Wat in het contract staat, gaat voor: pas de opzegtermijn per contract aan.

**Waar staat het onderhoudscontract van de lift nu?** Bij **VME > Contracten**, met de lift als installatie. Op het scherm van de installatie ziet u het contract en de einddatum. Klik erop om het te openen.

**Kan Odoo de opzegbrief versturen?** Nee. Odoo herinnert u eraan en houdt bij dat u opgezegd hebt, maar het versturen doet u zelf.

**Het contract loopt niet stilzwijgend door.** Haal het vinkje *Stilzwijgende verlenging* weg. Op de einddatum zet Odoo het contract dan op *Beëindigd*. U krijgt wel nog een taak vóór de opzegtermijn, zodat u tijdig een nieuw contract of nieuwe offertes kunt regelen.
