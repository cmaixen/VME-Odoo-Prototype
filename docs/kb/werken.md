# Hoe volg ik werken op, van offertes tot oplevering?

Heeft de algemene vergadering werken beslist, bijvoorbeeld een nieuw dak, dan volgt u die op in een **werkdossier**. Het dossier hangt aan de beslissing van de AV en neemt het budget en de verdeelsleutel daaruit over. U verzamelt er de offertes, vergelijkt ze, gunt de werken, volgt de uitvoering en de oplevering op, en ziet welke facturen al binnen zijn. Odoo maakt bij elke stap een taak; er wordt niets automatisch verstuurd.

## Stappen

### 1. Het dossier starten

1. Open de beslissing van de AV: **VME > Algemene vergaderingen > Register van beslissingen**, en open het agendapunt.
2. Vul onder **Werken** de **geraamde kostprijs** in (en eventueel een andere **sleutel**, bv. de liftsleutel voor liftwerken).
3. Klik op **Werkdossier aanmaken**. U kunt ook starten via **VME > Werken en schade > Werkdossiers > Nieuw** en daar de beslissing kiezen.
4. Kies de **financiering**:
   - **Reservekapitaal**: de facturen worden uit het reservekapitaal betaald. Ze komen niet in de afrekening van het werkkapitaal.
   - **Werkkapitaal**: de facturen worden verdeeld en afgerekend zoals elke andere kost.
5. Beschrijf de werken op het tabblad **Beschrijving** en bewaar.

Bij financiering uit het reservekapitaal ziet u meteen hoeveel er in het reservekapitaal zit, hoeveel al vastligt voor andere gegunde werken, en wat nog beschikbaar is. Is dat te weinig, dan krijgt u een oranje melding met het tekort.

### 2. Offertes vragen en vergelijken

1. Klik op **Offertes opvragen**. Odoo maakt een taak met de datum waartegen de offertes binnen moeten zijn. De aanvragen zelf stuurt u naar de aannemers.
2. Vul per offerte op het tabblad **Offertes** de aannemer, de datum, het bedrag (met btw) en de duur in. Hang de PDF eraan.
3. Odoo toont het verschil met het budget en zet de goedkoopste offerte in het vet.
4. Hebt u twee tot vier offertes als PDF, klik dan op **Offertes vergelijken**: de AI zet ze per post naast elkaar, met de pagina van elke waarde, als bijlage voor de AV. Zie [Offertes voor werken vergelijken met de AI](offertes-vergelijken.md).

**Hoeveel offertes?** De AV legt een bedrag vast waarboven meerdere offertes verplicht zijn. U vindt het op de VME, tabblad **Werken en verzekeringen**: **Offertes verplicht vanaf** en **Minimum aantal offertes** (standaard 5.000 euro en 3 offertes). Zolang er te weinig offertes zijn, ziet u een melding en kunt u niet gunnen.

### 3. Gunnen

1. Klik bij de gekozen offerte op **Gunnen** (het vinkje).
2. De andere offertes krijgen de status **Niet gekozen**.
3. Odoo maakt een taak om de opdrachtbevestiging op te maken en de andere aannemers te verwittigen. Die brieven verstuurt u zelf.
4. Is er een geplande start, dan komt er ook een taak op die dag.

### 4. Uitvoering en facturen

1. Vul op het tabblad **Uitvoering en oplevering** de geplande start en het geplande einde in.
2. Klik op **Werken gestart** zodra de aannemer begint.
3. Facturen van de aannemer komen vanzelf bij het dossier zolang de werken gegund of bezig zijn. Een Peppol-factuur die u opent, krijgt het werkdossier en de verdeelsleutel van de werken al ingevuld. Om zelf een factuur in te geven, klikt u op de knop **Facturen** van het dossier en dan **Nieuw**.
4. Bij **Bevestigen** wordt de factuur verdeeld over de eigenaars. Bij financiering uit het reservekapitaal boekt Odoo er ook meteen een boeking "Aanwending reservekapitaal" bij.
5. Het dossier toont hoeveel al gefactureerd is en wat nog moet komen.

### 5. Oplevering

1. **Voorlopige oplevering**: vul de datum in en klik op **Voorlopig opgeleverd**. Noteer de opmerkingen. Vanaf dan gelden de werken als uitgevoerd: ze staan niet meer in de inlichtingen aan de notaris bij een verkoop. Odoo toont tot wanneer de tienjarige aansprakelijkheid van de aannemer loopt, en maakt een taak voor de definitieve oplevering een jaar later.
2. **Definitieve oplevering**: kijk na of de opmerkingen opgelost zijn en klik op **Definitief opgeleverd**.

## Voorbeeld uit de demodata

In **Residentie Linde** besliste de AV van 10 maart 2026 (beslissing 2026/06) het platte dak te renoveren, geraamd op 38.000 euro uit het reservekapitaal. Het werkdossier **Renovatie plat dak blok A** heeft drie offertes:

| Aannemer | Bedrag | Verschil met budget |
| --- | --- | --- |
| Dakrenovatie Fictief NV | 36.450 euro | −1.550 euro |
| Dakwerken Voorbeeld BV | 39.220 euro | +1.220 euro |
| Bouwbedrijf Voorbeeld NV | 41.980 euro | +3.980 euro |

De werken zijn op 2 juni 2026 gegund aan Dakrenovatie Fictief NV en starten op 16 november 2026. Het reservekapitaal van de VME is veel kleiner dan het opdrachtbedrag, dus het dossier toont een oranje melding met het tekort.

Wilt u een factuur laten binnenkomen, importeer dan in de company Residentie Linde het bestand `voorschot_dakwerken_residentie_linde_2026-11.xml` (een voorschot van 30%, 10.935 euro) via **Facturatie > Leveranciers > Facturen > Upload**. De factuur hangt meteen aan het werkdossier en heeft de algemene sleutel. Na **Bevestigen** is ze verdeeld over 12 eigenaars (Eigenaar Linde A4 draagt 787,32 euro) en ten laste van het reservekapitaal geboekt. In de jaarafrekening staat ze bij het reservekapitaal, onder "Werken betaald uit het reservekapitaal".

## Veelgestelde vragen

**Waarom kan ik niet gunnen?**
Het bedrag van de werken ligt boven de drempel van de AV en er zijn nog te weinig offertes. Ook als het budget laag is maar de offerte hoger uitvalt dan de drempel, zijn meerdere offertes nodig.

**Ik klik op Facturen en krijg de melding "Kies rechtsboven in Odoo ook de VME".**
De facturen staan in de boekhouding van de VME. Zet de VME aan in de keuzelijst rechtsboven in Odoo en probeer opnieuw.

**Een factuur van de aannemer hoort niet bij de werken (bv. een klein herstel).**
Maak het veld **Werkdossier** op de factuur leeg voor u ze bevestigt. Dan wordt ze verdeeld en afgerekend zoals een gewone kost.

**Het reservekapitaal volstaat niet. Wat nu?**
Vraag een bijzondere bijdrage aan het reservekapitaal op, of leg de AV voor om (een deel van) de werken uit het werkkapitaal te betalen. Odoo blokkeert niets: het tekort is een waarschuwing.

**Wat gebeurt er als ik een factuur terugzet naar concept?**
De boeking op het reservekapitaal wordt teruggedraaid. Bij het opnieuw bevestigen komt ze er opnieuw.

**Moeten eigenaars hun aandeel in werken uit het reservekapitaal nog betalen?**
Nee. Hun aandeel staat ter informatie op de jaarafrekening, maar het wordt betaald met het reservekapitaal dat zij eerder opbouwden. Het saldo van het werkkapitaal verandert niet.

> De regels rond het aantal offertes en het gebruik van het reservekapitaal zijn nog niet juridisch nagekeken.
