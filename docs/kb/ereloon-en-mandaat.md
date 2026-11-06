# Uw ereloon, extra prestaties en uw mandaat als syndicus

Het platform beheert niet alleen de VME's, maar ook uw eigen kantoor: wat u per VME aanrekent (de beheerovereenkomst), de extra prestaties die u levert, de ereloonfacturen die u daarvoor maakt, en uw mandaat met de herbenoeming op de algemene vergadering.

Uw kantoor is in Odoo een eigen bedrijf, naast de bedrijven van de VME's. Daar staan uw ereloonfacturen: dat is uw omzet. In de VME komt dezelfde factuur binnen als een leveranciersfactuur, die over de eigenaars wordt verdeeld zoals elke andere kost.

Alles staat onder **VME > Syndicus**.

## Hoe leg ik een beheerovereenkomst vast?

1. Ga naar **VME > Syndicus > Beheerovereenkomsten** en klik op **Nieuw**.
2. Kies de **VME** en controleer het **kantoor syndicus** (uw eigen bedrijf, staat al ingevuld).
3. Vul de **begindatum** in. Een **einde** vult u pas in als de overeenkomst stopt.
4. **Vast ereloon**: kies **per kavel** of **per VME**, en vul het **bedrag per maand** zonder btw in. Kies of u **per maand** of **per kwartaal** factureert.
5. **Indexering**:
   - **Consumptieprijsindex**: op elke verjaardag van de begindatum wordt het bedrag aangepast met de index van de maand vóór die verjaardag, gedeeld door de basisindex (standaard de maand vóór het begin). Odoo vult de basisindex in uit de tabel onder **VME > Configuratie > Consumptieprijsindex**.
   - **Vast percentage per jaar**: bv. 2% per verstreken jaar.
   - **Geen indexering**.
   Met **Prijslijst mee indexeren** volgen ook de prijzen van de extra prestaties de index.
6. Op het tabblad **Prijslijst extra prestaties** staan vijf prestaties met een standaardprijs. Pas de prijzen aan zoals in uw overeenkomst.
7. Bewaar. Odoo maakt in de VME meteen een **verdeelregel** voor uw kantoor: uw facturen komen op de algemene sleutel en op de rekening "Andere erelonen".

Bovenaan ziet u het **ereloon per eenheid vandaag** en het **vaste ereloon per maand vandaag**, met de indexering erin.

## Welke extra prestaties registreert Odoo vanzelf?

Een prestatie is nog geen factuur: het is een regel die bij het volgende ereloon wordt aangerekend. Odoo maakt ze op het moment dat het werk gebeurt:

| Wat u doet | Prestatie |
| --- | --- |
| U maakt het eerste antwoord aan de notaris in een verkoopdossier | Verkoopdossier en inlichtingen notaris |
| U meldt een schadegeval aan bij de verzekeraar (**Aangegeven**) | Schadedossier |
| U zet een buitengewone AV op **Gehouden** | Buitengewone AV |
| U zet een tweede vergadering (na een eerste zonder quorum) op **Gehouden** | Bijkomende vergadering |
| U geeft een aangetekende brief af bij de post, of verstuurt hem elektronisch | Aangetekende zending |

In de chatter van het dossier ziet u dat de prestatie geregistreerd is. Elke bron geeft maar één prestatie, ook als u twee keer klikt. Een VME zonder beheerovereenkomst krijgt geen prestaties.

Een andere prestatie (bv. een extra vergadering met de raad) voegt u zelf toe via **VME > Syndicus > Prestaties > Nieuw**. Wilt u een prestatie niet aanrekenen, vink dan **Niet aanrekenen** aan.

Bij een verkoopdossier vult Odoo **Door te rekenen aan** in met de verkoper: de kosten van de inlichtingen aan de notaris zijn voor hem. Het doorrekenen aan de verkoper gebeurt nog niet vanzelf.

## Hoe maak ik de ereloonfacturen?

1. Ga naar **VME > Syndicus > Ereloonfacturen maken**. U kunt ook in de lijst van VME's of in de portefeuille enkele VME's aanvinken en via **Actie > Ereloonfacturen maken** werken.
2. De periode staat op het vorige kwartaal. Laat **VME's** leeg voor alle VME's met een overeenkomst.
3. Klik op **Conceptfacturen maken**. Per VME komt er één factuur per kwartaal, of één per maand als die VME per maand factureert. Elke factuur bevat:
   - het **vaste ereloon** (aantal kavels × geïndexeerde prijs × aantal maanden; valt de verjaardag midden in het kwartaal, dan staan er twee lijnen met elk hun prijs);
   - een lijn per **prestatie** die nog te factureren is tot het einde van de periode;
   - 21% btw.
4. Kijk elke factuur na en klik op **Bevestigen**. Odoo verstuurt niets.

Uw ereloonfacturen staan later onder **VME > Syndicus > Ereloonfacturen**. Zet dan rechtsboven in de bedrijvenkiezer ook uw kantoor aan: Odoo toont facturen alleen van de bedrijven die daar aangevinkt zijn.

Een periode die al gefactureerd is, wordt niet opnieuw gefactureerd. Annuleert u een ereloonfactuur, of verwijdert u een concept, dan staan de prestaties weer op **Te factureren**.

## Wat gebeurt er in de VME?

Bij het bevestigen van uw ereloonfactuur zet Odoo in de VME een **conceptleveranciersfactuur** klaar: dezelfde lijnen, uw kantoor als leverancier, het factuurnummer als referentie, de periode als kostperiode, en de sleutel en de rekening uit de verdeelregel. Met de knop **Factuur in de VME** opent u ze.

Een medewerker van de VME (of de raad, als die de facturen nakijkt) controleert die factuur en klikt op **Bevestigen**. Pas dan wordt ze verdeeld over de eigenaars en staat ze in de jaarafrekening, onder uw kantoor als leverancier.

## Hoe volg ik mijn mandaat op?

Uw mandaat staat onder **VME > Syndicus > Mandaten**, en op het tabblad **Syndicus** van de VME.

- Een mandaat duurt **hoogstens drie jaar**. Odoo vult het einde zelf in (begin + drie jaar) en weigert een langer mandaat. De AV kan het hernieuwen.
- **AV voor herbenoeming**: de laatste gewone AV die binnen het mandaat valt, volgens de AV-periode van de VME. Die AV moet over de herbenoeming beslissen.
- Het **signaal** wordt oranje (**Herbenoeming plannen**) vanaf zes maanden vóór die AV-periode, en rood (**Herbenoeming dringend**) vanaf twee maanden ervoor. Elke nacht maakt Odoo dan een taak "Herbenoeming syndicus voorbereiden".
- Wordt de gewone AV van dat jaar aangemaakt (ook door de AV-planner), dan staat het agendapunt **Herbenoeming van de syndicus en goedkeuring van de beheerovereenkomst** er meteen op. Bestaat de AV al, klik dan op **Agendapunt herbenoeming** op het mandaat.
- Is het agendapunt aangenomen, dan klikt u op **Hernieuwen**: Odoo maakt het volgende mandaat van drie jaar, dat aansluit op het vorige en gekoppeld is aan de beslissing.

## Hoe plak ik mijn aanstelling aan de ingang?

De wet vraagt dat een uittreksel van uw aanstelling binnen acht dagen na het begin van het mandaat zichtbaar aan de ingang van het gebouw hangt.

1. Open het mandaat en klik op **Aanplakbrief maken**. Odoo maakt een PDF met uw naam, adres, ondernemingsnummer, e-mail en telefoon, en de duur van het mandaat. U vindt hem bij de documenten van de VME, in de map **Syndicus**, en de eigenaars zien hem in het portaal.
2. Druk hem af en hang hem op.
3. Klik op **Aangeplakt**. Is de termijn van acht dagen voorbij zonder dat u dat deed, dan kleurt de aanplakking rood en krijgt u een taak.

## Voorbeeld uit de demo

Het fictieve kantoor **Syndicus Voorbeeld BV** beheert de drie demogebouwen:

- **Residentie Linde**: € 14 per kavel per maand, per kwartaal gefactureerd, geïndexeerd met de consumptieprijsindex sinds 1 januari 2024 (de demo-indexcijfers zijn verzonnen). Het mandaat loopt tot 11 maart 2027: de herbenoeming hoort op de AV van maart 2027, en het signaal staat op **Herbenoeming plannen**. Plan de AV's van 2027 met de AV-planner, en het agendapunt staat er vanzelf op. Het waterschadegeval van A4 werd aangegeven en staat als prestatie klaar voor het vierde kwartaal. Beantwoordt u in de demo de vraag van de notaris over A3, dan komt er een tweede prestatie bij.
- **Hof ter Beuken**: € 480 per maand voor het hele gebouw, maandelijks gefactureerd, 2% per jaar. In september was er een extra vergadering met de raad over de conciërge.
- **Kaaihuis**: € 18 per kavel per maand, zonder indexering. Het mandaat begon op 17 maart 2026, maar de aanstelling is nooit aangeplakt: de aanplakking staat in het rood.

Na **Demohistoriek 2026 laden** zijn de ereloonfacturen van het derde kwartaal bevestigd in het kantoor. In de drie VME's wachten de leveranciersfacturen nog als concept op goedkeuring: de kosten van het demojaar veranderen dus niet. Maak via **Ereloonfacturen maken** de facturen voor het vierde kwartaal zodra het kwartaal voorbij is (of kies zelf oktober als maand voor Hof ter Beuken).

## Veelgestelde vragen

**Telt een garage als een kavel voor het vaste ereloon?**
Ja, in het prototype telt elke kavel even zwaar. Rekent u garages aan een lager tarief aan, kies dan voorlopig **per VME** met het totaalbedrag.

**De factuur geeft een fout over de consumptieprijsindex.**
Het indexcijfer van de maand vóór de verjaardag ontbreekt. Vul het aan onder **VME > Configuratie > Consumptieprijsindex** en maak de factuur opnieuw.

**Kan ik een prestatie nog wijzigen?**
Zolang ze niet gefactureerd is, ja: prijs, aantal en omschrijving. Een gefactureerde prestatie kunt u niet meer wijzigen of verwijderen; annuleer dan eerst de ereloonfactuur.

**Ik heb de factuur in de VME al bevestigd en moet iets corrigeren.**
Maak in uw kantoor een creditnota en, in de VME, een creditnota op de leveranciersfactuur. Odoo past een bevestigde factuur in de VME nooit zelf aan.

**Wordt mijn factuur naar de VME gestuurd?**
Nee. Beide facturen staan in hetzelfde platform; niets vertrekt vanzelf. Wilt u de factuur ook als PDF aan de raad bezorgen, dan doet u dat zelf vanuit de factuur.

**Wat gebeurt er als het mandaat verloopt zonder herbenoeming?**
Het signaal wordt rood (**Verlopen**) en de VME heeft geen syndicus meer op die datum. Laat de AV zo snel mogelijk beslissen.
