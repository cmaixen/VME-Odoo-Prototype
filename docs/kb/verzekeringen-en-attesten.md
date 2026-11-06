# De brandverzekering en de verplichte attesten van een gebouw opvolgen

Elk gebouw heeft een brandverzekering die elk jaar op de vervaldag verlengt, en een reeks verplichte attesten: het asbestattest van de gemene delen, het postinterventiedossier, het EPC van de gemeenschappelijke delen en de keuring van de elektrische installatie. Vervalt een polis zonder dat iemand het merkt, of ontbreekt een attest bij een verkoop, dan staat de syndicus zwak. Het platform houdt dit per gebouw bij, maakt op tijd een taak en toont een signaal op de gebouwkaart.

Er wordt nooit iets verstuurd: een taak of signaal is een herinnering voor u. De verzekeraar contacteren, een attest bestellen of de polis opzeggen doet u zelf.

## Hoe zie ik hoe een gebouw ervoor staat?

1. Open de VME en ga naar het tabblad **Verzekering en attesten**.
2. Bovenaan staan de polissen, met de verzekeraar, de **vervaldag**, de dag waarop u uiterlijk kunt **opzeggen**, de **verzekerde waarde** en het aantal schadegevallen.
3. Daaronder staan de attesten die voor dit gebouw verplicht zijn, met hun toestand:
   - **In orde** (geen kleur)
   - **Vervalt binnenkort** (oranje): nog minder dan 90 dagen geldig
   - **Vervallen** of **Ontbreekt** (rood)
   - **Bouwjaar ontbreekt** (oranje): vul het bouwjaar in, dan weet het platform welke attesten nodig zijn
4. Hetzelfde blok staat op de **gebouwkaart**.

Welke attesten verplicht zijn, hangt af van het **bouwjaar** en het **gewest** (afgeleid uit de postcode). Beide staan bij de adresgegevens van de VME:
- asbestattest gemene delen: Vlaamse gebouwen van vóór 2001
- postinterventiedossier: gebouwen van 2001 of later
- EPC gemeenschappelijke delen: Vlaamse appartementsgebouwen
- elektrische keuring: elk gebouw; die komt uit de installatie "Elektrische installatie gemene delen" (zie [Keuringen en liften](keuringen.md))

**Voorbeeld in de demo:** Hof ter Beuken (bouwjaar 1978) heeft een EPC en een geldige elektrische keuring, maar **geen asbestattest**: de lijn staat in het rood en het gebouw krijgt het signaal *Verplicht attest ontbreekt*.

## Hoe voeg ik een attest toe?

1. Open de VME, tabblad **Verzekering en attesten**.
2. Klik op **Asbestattest toevoegen**, **EPC gemene delen toevoegen** of **Postinterventiedossier toevoegen**.
3. Kies het bestand en vul de datum van het attest in. **Geldig tot** wordt ingevuld (tien jaar voor asbest en EPC, onbeperkt voor het postinterventiedossier); pas het aan als het attest iets anders vermeldt.
4. Sla op. Het attest staat in de map *Attesten (asbest, EPC)* of *Postinterventiedossier* bij de documenten van de VME, het signaal verdwijnt en de open taak wordt afgevinkt.

U kunt een bestaand document ook zelf als attest markeren: open het onder **Documenten** en kies de soort bij **Attest**.

## Hoe volg ik de brandverzekering op?

1. Open **VME > Werken en schade > Verzekeringspolissen**, of de polis vanuit de VME.
2. Vul de **vervaldag** (einde van de lopende periode), de **verzekerde waarde**, de basis van die waarde en de jaarpremie in.
3. Het platform berekent **Opzeggen uiterlijk**: drie maanden vóór de vervaldag.
4. Vier maanden vóór de vervaldag krijgt de verantwoordelijke een taak *Verzekering nakijken*, met als deadline de opzegdatum. Kijk dan de verzekerde waarde, de premie en de dekking na.
5. Blijft de polis lopen? Klik op **Verlengd**: de vervaldag schuift een jaar op, de taak wordt afgevinkt en er komt een bericht in de historiek. Er gaat niets naar de verzekeraar.
6. Met de knop **Schadegevallen** ziet u alle schadedossiers onder deze polis (zie [Schadegevallen](schadegevallen.md)).

**Voorbeeld in de demo:** de brandverzekering van Kaaihuis vervalt op 1 december 2026. De lijn staat in het oranje, de taak staat klaar en de gebouwkaart toont het signaal *Brandverzekering vervalt of ontbreekt*.

## Wat ziet de notaris bij een verkoop?

In de inlichtingen aan de notaris (zie [Verkoop van een kavel](verkoop-notaris.md)) staan twee extra delen:
- **9. Verplichte attesten van de gemene delen**: elk attest met datum en geldigheid; een ontbrekend attest staat er uitdrukkelijk als *Ontbreekt*.
- **10. Brandverzekering van het gebouw**: verzekeraar, polisnummer, vervaldag en verzekerde waarde.

## Krijg ik een herinnering?

Ja. Elke nacht:
- krijgt een polis die binnen 120 dagen vervalt één taak per vervaldag
- krijgt de VME één taak per attest dat ontbreekt, vervallen is of binnen 90 dagen vervalt (de elektrische keuring heeft haar taak al bij de installatie)

## Veelgestelde vragen

**Het gebouw ligt in Brussel of Wallonië.** Het prototype volgt voor asbest en EPC alleen de Vlaamse regels; in Brussel en Wallonië vraagt het die attesten niet. Het postinterventiedossier en de elektrische keuring gelden overal.

**Kloppen de regels?** Het zijn de regels zoals we ze nu begrijpen, nog niet juridisch nagekeken. Vooral de uiterste datum voor het asbestattest van de gemene delen (31 december 2026) en het minimum aantal appartementen voor het EPC moeten nog bevestigd worden.

**Waarom staat de elektrische keuring niet bij de documenten?** Ze is al een installatie met keuringsverslagen. Het platform leest de laatste keuring daar, zodat u ze maar op één plaats ingeeft.

**Een gebouw heeft twee brandverzekeringen (bv. bij een overstap).** Het signaal verschijnt pas als alle lopende brandverzekeringen van het gebouw vervallen. Archiveer de oude polis na de overstap.
