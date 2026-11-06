# Hoe lees ik bankafschriften in en koppel ik de betalingen?

De bank levert elke dag (of elke week) een bestand met de bewegingen op de rekeningen van een VME. Leest u dat bestand in, dan zoekt het platform voor elke betaling de provisie of de leveranciersfactuur waarbij ze hoort, en zet die factuur op betaald. Wat het niet zeker weet, komt in een lijst met een voorstel; u beslist zelf.

Het platform leest twee formaten:

- **CODA** (`.cod`), het Belgische formaat dat elke bank in België levert. Vraag het aan bij uw bank als "CODA-bestanden" voor de rekeningen van de VME.
- **CAMT.053** (`.xml`), het Europese formaat. Gebruik het als de bank geen CODA levert.

Elk fonds heeft een eigen rekening: werkkapitaal en reservekapitaal. U moet niet kiezen voor welke VME of welk fonds een bestand is: het rekeningnummer in het bestand bepaalt dat. Eén bestand mag de afschriften van meerdere rekeningen bevatten.

## Stappen

1. Download het CODA- of CAMT-bestand uit het internetbankieren van de syndicus.
2. Ga naar **VME > Bank > Bankafschriften inlezen**.
3. Kies het bestand en klik op **Inlezen**.
4. U ziet meteen de ingelezen bewegingen, gegroepeerd per soort koppeling:
   - **Automatisch gekoppeld**: de betaling had de juiste gestructureerde mededeling, of een leveranciersbetaling paste op een geboekte factuur. De factuur staat op betaald.
   - **Voorstel**: het platform denkt te weten bij welke factuur de betaling hoort. De kolom **Voorstel** toont de factuur, de kolom **Toelichting** waarom.
   - **Te koppelen**: er is geen voorstel.
5. Klik bij een voorstel op **Koppelen** als het klopt. Klopt het niet, open de beweging, pas in het blok **Voorstel** de facturen aan (verwijderen of **Regel toevoegen**) en klik op **Koppelen**.
6. Een betaling zonder factuur (bijvoorbeeld een dubbele betaling of een voorschot) boekt u met **Boeken op eigenaar of leverancier** als tegoed van die eigenaar. Vul eerst de eigenaar in als die leeg is.

Leest u hetzelfde bestand per ongeluk twee keer in, dan gebeurt er niets: het platform herkent afschriften die het al kent.

Rechtsboven in Odoo kiest u welke VME's u ziet. Zet alle VME's aan om de bewegingen van alle gebouwen samen te zien.

## De lijst "Op te volgen betalingen"

**VME > Bank > Op te volgen betalingen** toont alles waar nog iemand naar moet kijken:

| Uitzondering | Wat er aan de hand is | Wat u doet |
| --- | --- | --- |
| Geen mededeling | De eigenaar schreef iets vrij in de mededeling, of niets. | Kijk het voorstel na en klik op **Koppelen**. |
| Foute mededeling | De gestructureerde mededeling bestaat niet of heeft een tikfout. | Idem. |
| Al betaald | De factuur in de mededeling was al betaald: wellicht een dubbele betaling. | **Boeken op eigenaar of leverancier** (tegoed), of terugbetalen. |
| Rekening van het andere fonds | Een provisie reservekapitaal werd op de rekening werkkapitaal betaald, of omgekeerd. | **Koppelen**, en daarna het bedrag overschrijven naar de juiste rekening. |
| Te weinig betaald | De betaling is gekoppeld, maar er blijft een deel open. | Het openstaande deel komt in de volgende herinnering. |
| Te veel betaald | De factuur is betaald; het verschil staat als tegoed op de eigenaar. | Niets, of terugbetalen. |
| Onbekende betaling | Geen eigenaar en geen factuur gevonden. | Zoek uit van wie ze komt, vul de eigenaar in en koppel of boek. |

Ook een betaling die **te laat** binnenkwam, staat in deze lijst (kolom **Dagen te laat**), al is ze gekoppeld. Zo ziet u wie een herinnering kreeg of interesten verschuldigd kan zijn.

Een gekoppelde betaling verdwijnt uit de lijst, tenzij er iets op te volgen blijft. Alle bewegingen ziet u in **VME > Bank > Alle bankbewegingen**.

## Hoe vindt het platform een voorstel?

1. **De eigenaar**: aan het rekeningnummer waarvan betaald werd (het platform onthoudt dat na een eerste manuele koppeling), aan de naam van de betaler, of aan een kavel in de mededeling (bijvoorbeeld "A3").
2. **De factuur**: een openstaande provisie van die eigenaar met precies hetzelfde bedrag, op het fonds van de rekening. Zijn er meerdere, dan stelt het de oudste voor. Is de betaler onbekend, dan stelt het een factuur alleen voor als er maar één openstaande provisie met dat bedrag is.
3. **Leveranciers**: een betaling naar een leverancier wordt gekoppeld als het factuurnummer van de leverancier in de mededeling staat en het bedrag klopt. Klopt het bedrag niet, dan wordt het een voorstel.

Er wordt nooit iets verstuurd en geen betaling uitgevoerd: het platform koppelt alleen wat al op de rekening staat.

## Voorbeeld uit de demo

Na **VME > Configuratie > Demobankafschriften inlezen** (na de demodata en de demohistoriek) staan er afschriften van 5 november 2026 voor de drie gebouwen:

| VME | Beweging | Resultaat |
| --- | --- | --- |
| Residentie Linde | Liftonderhoud en schoonmaak betaald (ELEVATOR-20260915, CLEANING-20260930) | Automatisch gekoppeld aan de leveranciersfacturen |
| Residentie Linde | A3 betaalt oproep 4 werkkapitaal op 5 november | Automatisch gekoppeld, **1 dag te laat** |
| Residentie Linde | "Familie Voorbeeld" stort 43,20 € op de reserverekening met "reservefonds A3 oproep 4" | **Voorstel**: provisie reservekapitaal van A3 (kavel A3 in de mededeling, zelfde bedrag) |
| Hof ter Beuken | B7 betaalt 840,00 € met een tikfout in de mededeling | **Voorstel**: de oudste open provisie van 840,00 € (oproep 3) |
| Hof ter Beuken | B7 betaalt 200,00 € voor oproep 4 (840,00 € gevraagd) | Gekoppeld, **te weinig betaald**: 640,00 € blijft open |
| Hof ter Beuken | B7 betaalt de provisie reservekapitaal van oproep 3 op de rekening werkkapitaal | **Voorstel**, rekening van het andere fonds |
| Hof ter Beuken | B7 betaalt oproep 4 reservekapitaal op tijd | Automatisch gekoppeld |
| Hof ter Beuken | Gasfactuur derde kwartaal betaald | Automatisch gekoppeld |
| Kaaihuis | K2 betaalt oproep 4 een tweede keer | **Te koppelen**, al betaald |
| Kaaihuis (reserve, als CAMT.053) | "J. Voorbeeld" stort 250,00 € als "voorschot" | **Te koppelen**, onbekende betaling |

## Veelgestelde vragen

**Waarom kreeg mijn eigenaar een "gestructureerde mededeling"?**
Elke provisiefactuur heeft een mededeling als `+++120/2600/07589+++`. Daarin zit het factuurnummer (hier F/2026/00075). Gebruikt de eigenaar die mededeling, dan koppelt het platform de betaling zonder dat iemand ernaar moet kijken.

**Een eigenaar betaalt twee provisies in één keer. Wat nu?**
Is het bedrag gelijk aan alles wat hij nog open heeft, dan stelt het platform alle open provisies samen voor. Anders past u het voorstel aan en voegt u de facturen toe die hij wil betalen; het bedrag wordt over de oudste eerst verdeeld.

**Ik heb verkeerd gekoppeld.**
Open de beweging en klik op **Koppeling ongedaan maken**. De factuur staat weer open en het platform zoekt opnieuw een voorstel.

**Moet ik de bankkosten ook koppelen?**
In het prototype nog niet: zulke bewegingen blijven in **Te koppelen**. Een boekhouder boekt ze voorlopig in de boekhouding.

**Kan de bank de bestanden automatisch sturen?**
Ja, via een "CODA-dienst" van de bank of een tussenpartij. Het prototype leest de bestanden alleen in als u ze opent; automatisch ophalen komt later.
