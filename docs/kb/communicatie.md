# Communicatie met eigenaars en huurders

In **VME > Communicatie** stuurt u een mededeling of een bevraging naar alle eigenaars van een VME, naar de eigenaars van één blok of van enkele kavels. U kiest hoe: volgens de voorkeur van elke eigenaar (e-mail of brief), als brief per post, aangetekend, per sms of als pushbericht. Alles wat u verstuurt, komt in het **communicatielog** van de eigenaar, samen met de oproepingen voor de algemene vergadering en de herinneringen van de invordering.

Odoo verstuurt nooit zelf iets. Elke verzending is eerst een concept. Pas als u op **Bevestigen en versturen** klikt, vertrekken de e-mails en worden de brieven klaargezet.

## Hoe stuur ik een mededeling aan één blok?

Voorbeeld uit de demo: een waterafsluiting in blok A van Residentie Linde.

1. Open **VME > Communicatie > Verzendingen** en klik op **Nieuw**.
2. Kies de **VME**: Residentie Linde.
3. Kies een **Sjabloon**, bv. **Waterafsluiting**. Onderwerp, tekst en kanaal worden ingevuld. Vul de puntjes in de tekst aan (dag en uur).
4. Kies bij **Ontvangers** "Eigenaars van een blok" en vul bij **Blok** `A` in.
5. **Eigenaar op**: de eigenaars op die datum krijgen de mededeling. Laat dit op vandaag, tenzij u een verkoop wilt afwachten.
6. Klik op **Ontvangers ophalen**. Op het tabblad **Ontvangers en antwoorden** ziet u per eigenaar de kavels en het kanaal. Een eigenaar met een appartement en een garage krijgt één bericht.
7. Kijk de tekst per ontvanger na (open een lijn of klik op het printericoontje).
8. Klik op **Bevestigen en versturen**.

Wat er dan gebeurt:

- **E-mail**: de e-mail gaat naar de uitgaande post van Odoo en vertrekt binnen enkele minuten.
- **Brief per post**: Odoo maakt één PDF met alle brieven (veld **Brieven voor de post**). Druk die af en post ze.
- **Aangetekend**: elke brief komt als PDF in het **Verzendregister aangetekend** (zie verder).
- **Sms en push**: de korte tekst gaat naar de sms- of pushdienst. In het prototype is dat een simulatie: er vertrekt niets, maar u ziet een referentie in het log.

## Welk kanaal krijgt een eigenaar?

| U kiest | De eigenaar krijgt |
| --- | --- |
| Volgens voorkeur | Een e-mail, of een brief als de eigenaar **Papier** vroeg of geen e-mailadres heeft |
| Brief per post | Altijd een brief |
| Aangetekend | Altijd een aangetekende brief |
| Sms | Een sms als er een telefoonnummer is, anders volgens voorkeur |
| Pushbericht | Een pushbericht als de eigenaar de app gebruikt, anders volgens voorkeur |

De voorkeur stelt u in op de fiche van de eigenaar (**Contacten**), veld **Voorkeur communicatie**. In de demo vroegen de eigenaars van Linde A4 en A9 en Beuken B12 papier.

## Welke plaatshouders kan ik gebruiken?

Schrijf deze woorden met accolades in onderwerp of tekst; ze worden per ontvanger ingevuld:

| Plaatshouder | Wordt |
| --- | --- |
| `{eigenaar}` | Naam van de ontvanger |
| `{kavels}` | Zijn kavels in deze VME, bv. "A1, G1" |
| `{vme}` | Naam van de VME |
| `{adres_vme}` | Adres van het gebouw |
| `{datum}` | De datum bij **Eigenaar op** |

## Hoe houd ik een bevraging?

Voorbeeld: "Interesse in een laadpaal?" in Residentie Linde.

1. Open **VME > Communicatie > Bevragingen** en klik op **Nieuw**.
2. Kies de VME en het sjabloon **Bevraging laadpalen**. De vraag en de mogelijke antwoorden ("Ja, binnen het jaar", "Ja, later", "Nee") staan op het tabblad **Bevraging**. Vul eventueel **Antwoorden tegen** in.
3. Kies de ontvangers en klik op **Bevestigen en versturen**. De vraag en de antwoorden staan onderaan elke e-mail of brief.
4. Komt er een antwoord binnen (per e-mail, telefoon of brief), open dan de bevraging en kies op het tabblad **Ontvangers en antwoorden** bij die eigenaar het **Antwoord**. Een opmerking kan erbij.
5. Op het tabblad **Bevraging** ziet u per antwoord hoeveel eigenaars het kozen.

## Hoe werkt aangetekend versturen?

Elke aangetekende brief komt in **VME > Communicatie > Verzendregister aangetekend**, met een volgnummer (bv. AT/2026/0001), het adres op dat moment en de PDF.

1. Open het register en filter op **Af te geven**.
2. Druk de PDF af (knop **PDF**), geef de brieven af bij de post en noteer het **Zendingsnummer** van het afgiftebewijs.
3. Klik op **Afgegeven bij de post** (in de lijst kan dat per lijn).
4. Komt het ontvangstbewijs terug, klik dan op **Ontvangen**. Werd de brief niet afgehaald, klik op **Niet afgehaald**.

Met **Elektronisch aangetekend versturen** gaat de brief naar een dienst voor elektronisch aangetekende zendingen. In het prototype is dat een simulatie; **Status ophalen** zet ze op ontvangen.

## Krijgt een nieuwe eigenaar automatisch een welkomstbrief?

Bijna. Als u in een verkoopdossier op **Akte verleden** klikt, zet Odoo een **concept-welkomstbrief** klaar voor de koper, met de kavels van de verkoop en de datum van de akte. Er wordt niets verstuurd.

1. Klik in het verkoopdossier op de knop **Welkomstbrief** (verschijnt na de akte).
2. Kijk de tekst na, vul eventueel aan en klik op **Bevestigen en versturen**.

Voorbeeld uit de demo: de lopende verkoop van A3 en G3 in Residentie Linde (vul de datum van de akte in en klik op **Akte verleden**).

## Waar zie ik alles wat een eigenaar kreeg?

- Op de fiche van de eigenaar (**Contacten**) staat de knop **Communicatie VME**: alle verzendingen, per VME.
- **VME > Communicatie > Communicatielog** toont alles van alle eigenaars, met filters op kanaal en status.

In het log staan ook:

- de **oproepingen voor de algemene vergadering**: als concept zodra ze gemaakt zijn, als verstuurd zodra u ze verstuurt. Zonder schriftelijk akkoord van de eigenaar voor e-mail gaan ze aangetekend en komen ze in het verzendregister;
- de **herinneringen van de invordering**. Een **ingebrekestelling** gaat altijd aangetekend: ze komt in het verzendregister, ook als u ze per e-mail verstuurt. In de herinnering staat daarvoor de knop **Aangetekend versturen**.

## Veelgestelde vragen

**Wordt er iets verstuurd als ik op "Ontvangers ophalen" klik?**
Nee. Pas **Bevestigen en versturen** verstuurt. Tot dan kunt u alles aanpassen of de verzending annuleren.

**Een eigenaar verkocht zijn appartement vorige week. Krijgt hij de mededeling nog?**
Nee, de mededeling gaat naar wie op de datum bij **Eigenaar op** eigenaar is. Wilt u de vorige eigenaar toch bereiken, kies dan "Gekozen personen".

**Kan ik de huurders verwittigen?**
De keuze "Huurders" bestaat al, maar huurders worden pas in een volgende versie per kavel bijgehouden. Tot dan vindt Odoo geen huurders. Vraag in de tekst aan de eigenaars om het door te geven, zoals in het sjabloon **Waterafsluiting**.

**Is een elektronisch aangetekende zending even geldig als een papieren?**
Dat laten we nog juridisch nakijken, vooral voor een ingebrekestelling en voor de oproeping tot de algemene vergadering. Gebruik voorlopig de papieren aangetekende zending voor die brieven.

**Mag ik een oproeping voor de AV per e-mail sturen?**
Alleen aan eigenaars die daar uitdrukkelijk en schriftelijk mee akkoord gingen; anders aangetekend. Dit wordt nog juridisch nagekeken.

**Kan ik een sjabloon aanpassen of toevoegen?**
Een beheerder kan dat in **VME > Configuratie > Communicatiesjablonen**.
