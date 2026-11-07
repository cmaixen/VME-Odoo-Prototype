# Algemene vergaderingen plannen

Elke VME houdt minstens één keer per jaar een gewone algemene vergadering (AV), binnen een vaste periode van 15 dagen uit het reglement van mede-eigendom. Met de **AV-planner** legt u een heel seizoen AV's in uw beschikbare avonden ("blokken"), zonder dat een zaal of een medewerker twee keer geboekt wordt.

## Hoe stel ik de periode van de AV in?

1. Open **VME > VME's** en kies de VME.
2. Vul onder **Algemene vergadering** in vanaf welke dag en maand de periode loopt, bijvoorbeeld "vanaf 4 maart". Odoo toont meteen de volledige periode van 15 dagen: *4 maart tot 18 maart*.
3. Controleer de **oproepingstermijn**. Die staat standaard op 15 dagen (de wettelijke termijn). Bepaalt het reglement van mede-eigendom een langere termijn, vul die dan in.

**Voorbeeld in de demo:** Residentie Linde vergadert tussen 4 en 18 maart, Kaaihuis tussen 10 en 24 maart, Hof ter Beuken tussen 12 en 26 april.

## Hoe geef ik mijn beschikbare avonden in?

1. Open **VME > Algemene vergaderingen > Vergaderzalen** en voeg uw zalen toe (naam, adres, aantal plaatsen).
2. Open **VME > Algemene vergaderingen > Blokken** en klik op **Nieuw**.
3. Vul in:
   - **Datum** en **beginuur**,
   - **Duur per AV** (standaard 2 uur),
   - **Max. AV's in dit blok**: hoeveel vergaderingen na elkaar op die avond kunnen (bv. 2: om 18:30 en om 20:30),
   - **Waar**: een zaal of online,
   - **Medewerker**: wie de vergaderingen leidt.
4. Odoo weigert een blok als dezelfde zaal of dezelfde medewerker op dat uur al in een ander blok staat.

Per medewerker kunt u ook vastleggen hoeveel AV's hij of zij op één avond mag leiden (standaard 2). Dat staat op de gebruiker, bij **Max. AV's per avond**.

**Voorbeeld in de demo:** vier blokken in het voorjaar van 2027, onder meer woensdag 17 maart in de vergaderzaal van het kantoor (plaats voor één AV) en dinsdag 23 maart online (plaats voor twee AV's).

## Hoe laat ik de planner een voorstel maken?

1. Open **VME > Algemene vergaderingen > AV-planner**.
2. Kies het jaar. Laat **VME's** leeg om alle VME's met een AV-periode te plannen.
3. Klik op **Indeling voorstellen**.

De planner maakt voor elke VME de gewone AV van dat jaar aan (als die nog niet bestaat) en zet ze in een vrij blok binnen haar periode. Hij houdt rekening met:

- de periode van 15 dagen van elke VME,
- de plaats in elk blok,
- het maximum aantal AV's per medewerker per avond,
- de oproepingstermijn: een blok wordt alleen gekozen als de oproeping nog op tijd kan vertrekken.

Strijden twee VME's om dezelfde avond, dan krijgt de VME waarvan de periode het eerst afloopt voorrang. Zo raakt de andere VME toch nog in een later blok.

**Voorbeeld in de demo:** zowel Residentie Linde als Kaaihuis past op 17 maart, maar dat blok heeft maar plaats voor één AV. Linde krijgt 17 maart, want haar periode loopt al op 18 maart af; Kaaihuis gaat naar 23 maart.

Vindt de planner geen vrij blok, dan blijft de AV op **Te plannen** staan met een bericht in de historiek. Voeg een blok toe en start de planner opnieuw.

## Hoe bevestig of wijzig ik een voorstel?

1. Open **VME > Algemene vergaderingen > AV's**. U ziet per VME de periode, het voorgestelde tijdstip, de medewerker, de uiterste datum voor de oproeping en de status.
2. Akkoord? Open de AV en klik op **Bevestigen**, of selecteer meerdere AV's in de lijst en klik op **Bevestigen**. Odoo zet de afspraak dan in de agenda van de medewerker (knop **Agenda** op de AV).
3. Iets anders? Kies in de AV een ander **blok** en sla op. Een bevestigde AV die u verplaatst, verhuist ook in de agenda.
4. **Opnieuw plannen** haalt de AV uit haar blok en verwijdert de afspraak; de planner kan ze dan opnieuw indelen.
5. Na het versturen van de oproeping klikt u op **Oproeping verstuurd**; na de vergadering op **Gehouden**.

Start u de planner opnieuw, dan blijven bevestigde AV's staan. Voorstellen die u nog niet bevestigde, worden opnieuw ingedeeld (tenzij u dat vinkje uitzet).

## Wat betekenen de waarschuwingen?

In de lijst staan AV's in het oranje of rood als er iets dreigt mis te lopen. Met de filter **Dreigt te laat** ziet u ze allemaal samen.

| Waarschuwing | Betekenis |
| --- | --- |
| Dringend plannen | De AV heeft nog geen datum, en binnen 30 dagen is het te laat om nog binnen de periode op te roepen. |
| Niet meer haalbaar | De AV heeft nog geen datum en de oproeping kan niet meer op tijd vertrekken voor een vergadering binnen de periode. |
| De oproeping zou te laat vertrekken | De datum staat vast, maar de uiterste dag voor de oproeping is voorbij en er is nog geen oproeping verstuurd. |
| De oproeping vertrok te laat | De oproeping werd na de uiterste dag verstuurd. |
| Oproeping(en) vertrokken na … | Elke eigenaar moet op tijd opgeroepen worden. De eerste oproepingen vertrokken op tijd, maar die van de genoemde eigenaars niet. |
| Oproeping(en) nog niet verstuurd | De uiterste dag is voorbij en de genoemde eigenaars kregen nog geen oproeping. |
| De AV valt buiten de periode | U koos met de hand een blok buiten de periode van 15 dagen. |

## Veelgestelde vragen

**Kan ik een AV plannen buiten de periode?**
Ja, als u met de hand een ander blok kiest. Odoo waarschuwt dan, maar houdt u niet tegen: soms is het niet anders.

**Kan een blok vol raken?**
Ja. Een blok heeft een maximum aantal AV's. Kiest u met de hand een vol blok, dan weigert Odoo het opslaan.

**Krijgen de eigenaars een uitnodiging in hun agenda?**
Nee. De afspraak staat alleen in de agenda van de medewerker. De oproeping aan de eigenaars komt in een volgende stap.

**Waarom koos de planner niet het eerste blok in de periode?**
Omdat dat blok al vol was, de medewerker die avond al zijn maximum had, of de oproeping voor dat blok niet meer op tijd kon vertrekken.
