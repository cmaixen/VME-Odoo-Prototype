# De algemene vergadering: oproeping, stemming en notulen

Zodra een AV bevestigd is in de AV-planner (zie [Algemene vergaderingen plannen](av-planner.md)), bereidt u in dezelfde AV de agenda en de oproepingen voor. Op de vergadering zelf registreert u wie er is, laat u stemmen en drukt u de notulen af. Odoo rekent het quorum en de uitslag van elke stemming zelf uit.

## Hoe stel ik de agenda op?

1. Open **VME > Algemene vergaderingen > AV's** en kies de AV.
2. Op het tabblad **Agenda** staan al de vaste punten van een gewone AV: opening en quorum, verslag van de syndicus, goedkeuring van de jaarrekening, kwijting, budget en de benoeming van de commissaris van de rekeningen.
3. Voeg punten toe met **Regel toevoegen** en kies per punt de **vereiste meerderheid**:
   - **Volstrekte meerderheid**: meer dan de helft van de uitgebrachte stemmen (de meeste beslissingen),
   - **Twee derde**: bv. werken aan de gemene delen,
   - **Vier vijfde**: bv. een wijziging van de statuten over het gebruik van de gemene delen,
   - **Eenparigheid**: alle stemmen van alle eigenaars, ook wie niet aanwezig is,
   - **Geen stemming**: punten ter informatie, zoals het verslag van de syndicus.
4. Sleep de punten in de juiste volgorde.

## Hoe maak ik de oproepingen?

1. Klik in de bevestigde AV op **Oproepingen aanmaken**.
2. Odoo maakt per eigenaar een oproeping **als concept**, met in bijlage:
   - de oproeping met datum, uur, plaats en agenda, en het aantal stemmen van de eigenaar,
   - een volmachtformulier met de agendapunten,
   - de jaarafrekening van het vorige jaar van die eigenaar (als die er is).
3. Odoo meldt tot wanneer u de oproeping moet versturen. Is die datum al voorbij, dan krijgt u een waarschuwing.
4. Kijk bij elke oproeping naar **Verzending**. De wet vraagt een aangetekende brief, tenzij de eigenaar schriftelijk akkoord gaf voor e-mail. Dat akkoord vult u in op de contactpersoon, veld **Akkoord oproeping per e-mail** (met de datum).
   - **E-mail**: klik op **Versturen**. Er opent een e-mail met de bijlagen; kijk die na en verstuur ze zelf.
   - **Aangetekend**: klik op **Aangetekend versturen**. De oproeping komt in het **Verzendregister aangetekend**. Druk de oproeping en de jaarafrekening af, geef de brief af bij de post en klik daar op **Afgegeven**. Pas dan telt de oproeping als vertrokken voor de termijn van 15 dagen.

Er wordt nooit iets automatisch verstuurd. De eerste verstuurde oproeping vult op de AV de datum **Oproeping verstuurd op** in.

**Voorbeeld in de demo:** plan de AV 2027 van Residentie Linde, bevestig ze en klik op **Oproepingen aanmaken**: twaalf concepten, één per eigenaar. Kavel A5 gaat naar de nieuwe eigenaar, omdat de verkoop van juli 2026 al gebeurd is.

## Hoe registreer ik de aanwezigen en volmachten?

1. Klik op de dag van de vergadering op **Aanwezigheidslijst**. Odoo zet alle eigenaars op de lijst, met hun kavels en hun quotiteiten in de algemene sleutel.
2. Zet op het tabblad **Aanwezigheid** per eigenaar **Aanwezig**, **Volmacht** (met de naam van de volmachthouder) of laat **Afwezig** staan.
3. Bovenaan ziet u meteen het **quorum**: hoeveel eigenaars en quotiteiten aanwezig of vertegenwoordigd zijn, en of de vergadering geldig kan beslissen.
4. Vul de voorzitter en de secretaris in.

Het quorum is bereikt als meer dan de helft van de eigenaars aanwezig of vertegenwoordigd is én zij samen minstens de helft van de quotiteiten hebben, of als de aanwezigen samen meer dan drie vierde van de quotiteiten hebben. Is het quorum niet bereikt, dan roept u een tweede vergadering samen; vink daar **Tweede vergadering** aan, dan geldt geen quorum.

Een volmachthouder mag hoogstens drie volmachten hebben. Meer mag alleen als hij met zijn eigen stemmen en die van zijn volmachten samen niet meer dan 10% van alle stemmen heeft. Odoo weigert een volmacht die die grens overschrijdt.

## Hoe laat ik stemmen?

1. Klik op **Stemlijsten aanmaken**: elk agendapunt met een stemming krijgt een lijn per aanwezige of vertegenwoordigde eigenaar, standaard **Voor**.
2. Klik bij een agendapunt op **Stemmen** en zet bij wie tegen stemt of zich onthoudt de juiste stem. Met **Iedereen voor** zet u alles terug op voor.
3. De uitslag verschijnt meteen: **Aangenomen**, **Verworpen** of **Geen quorum**.
4. Vul de tekst van de beslissing in, en bij een beslissing die werk vraagt een **opvolgtaak** (bv. "Drie offertes vragen voor de dakwerken") met wie het opvolgt en tegen wanneer.

Odoo telt in quotiteiten. Onthoudingen tellen niet mee als uitgebrachte stem. Een eigenaar kan nooit meer stemmen uitbrengen dan alle andere aanwezigen samen.

## Hoe sluit ik de vergadering af?

1. Klik op **Gehouden**. Dat lukt pas als over elk punt gestemd is.
2. Odoo nummert de beslissingen (bv. 2026/06) en zet ze in het **Register van beslissingen** (**VME > Algemene vergaderingen > Register van beslissingen**), over alle VME's heen.
3. Voor elke aangenomen beslissing met een opvolgtaak maakt Odoo een taak voor de medewerker.
4. Klik op **Notulen (PDF)** voor de notulen: aanwezigheid, quorum, per punt de stemmen en de uitslag, de beslissingen en plaats voor de handtekeningen.

**Voorbeeld in de demo:** de AV 2026 van Residentie Linde (10 maart 2026) is al gehouden. 10 van de 12 eigenaars waren aanwezig of vertegenwoordigd (858 van 1000 quotiteiten). De dakwerken (twee derde) zijn aangenomen met een opvolgtaak "Drie offertes vragen voor de dakwerken"; de statutenwijziging over de tuin (vier vijfde) is verworpen.

## Veelgestelde vragen

**Waarom kan ik een oproeping niet per e-mail versturen?**
De eigenaar gaf geen schriftelijk akkoord voor e-mail, of heeft geen e-mailadres. Zonder dat akkoord gaat de oproeping aangetekend. Krijgt u het akkoord, vul dan de datum in op de contactpersoon: de oproepingen in concept gaan dan per e-mail.

**Telt een onthouding als tegenstem?**
Nee. Onthoudingen tellen niet mee bij het berekenen van de meerderheid.

**Waarom staat een punt op "Geen quorum"?**
Omdat er te weinig eigenaars of quotiteiten aanwezig zijn. Beslissingen van die vergadering zijn niet geldig; roep een tweede vergadering samen.

**Kan de volmachthouder iemand zijn die geen eigenaar is?**
Ja. Kies gewoon de persoon als volmachthouder; zijn volmachten tellen mee voor de grens van drie volmachten of 10%.

**Wat als een eigenaar meerdere kavels heeft?**
Hij staat één keer op de lijst, met de som van de quotiteiten van al zijn kavels.
