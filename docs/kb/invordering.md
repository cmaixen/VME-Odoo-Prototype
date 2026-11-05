# Invordering van achterstallen

Betaalt een eigenaar een provisie of een afrekening niet op tijd, dan volgt u dat op in **VME > Invordering**. U ziet er alle achterstallen van alle VME's samen, per eigenaar en per VME, met hoe lang ze al openstaan. Odoo stelt telkens de volgende stap voor: een vriendelijke herinnering, een aanmaning en een ingebrekestelling. Daarna kunt u het dossier doorsturen naar een advocaat of deurwaarder.

Odoo verstuurt nooit zelf iets. Elke brief is eerst een concept dat u nakijkt en zelf verstuurt.

## Hoe zie ik welke eigenaars achterstallig zijn?

1. Open **VME > Invordering > Achterstallen**.
2. U ziet een tabel met per VME en per eigenaar het openstaande bedrag, verdeeld in kolommen:
   - **1-30 dagen**,
   - **31-60 dagen**,
   - **61-90 dagen**,
   - **Meer dan 90 dagen**.
3. Klik op de lijstweergave voor het detail per factuur: vervaldag, aantal dagen te laat, gestructureerde mededeling en fonds (werk- of reservekapitaal).
4. Met de filters toont u bv. alleen wat **meer dan 60 dagen** openstaat, of groepeert u per **eigenaar**.

Alleen bedragen waarvan de vervaldag voorbij is, komen in dit overzicht.

## Hoe maak ik de herinneringen?

1. Klik in **Achterstallen** of in **Dossiers** op **Invordering bijwerken**.
2. Odoo opent een **dossier** voor elke eigenaar met achterstallen, sluit dossiers die intussen volledig betaald zijn, en maakt per dossier het volgende niveau aan **als concept**.
3. U komt in **Herinneringen**, gegroepeerd per niveau. Kijk per niveau de concepten na.
4. Open een herinnering:
   - op het tabblad **Tekst** staat de brief: aanspreking, de lijst met openstaande bedragen, per bedrag de gestructureerde mededeling en het rekeningnummer, en het openstaande saldo. U kunt de tekst nog aanpassen;
   - met **Bijwerken** haalt u de bedragen opnieuw op als er intussen iets betaald is.
5. Versturen:
   - **Versturen** maakt de brief als PDF en opent een e-mail met die PDF in bijlage. Kijk de e-mail na en klik zelf op **Verzenden**;
   - per post: klik op **Afdrukken**, verstuur de brief en klik op **Per post verstuurd**. In de lijst kunt u meerdere herinneringen tegelijk selecteren en afdrukken of als verstuurd markeren;
   - wilt u een herinnering niet versturen, klik dan op **Annuleren**.

Elke nacht stelt Odoo ook zelf de nieuwe concepten voor. Versturen doet het nooit.

## Welke niveaus zijn er?

| Niveau | Wanneer | Toon |
| --- | --- | --- |
| **Vriendelijke herinnering** | Zodra een bedrag vervallen is (in te stellen per VME) | Kosteloos, "misschien is dit aan uw aandacht ontsnapt" |
| **Aanmaning** | Minstens 14 dagen na de vriendelijke herinnering | Dringend, kondigt interest en schadevergoeding aan |
| **Ingebrekestelling** | Minstens 14 dagen na de aanmaning | Formeel, kondigt overdracht aan advocaat of deurwaarder aan |

Odoo slaat geen niveau over en maakt maar één concept tegelijk per dossier. De sjablonen van de drie brieven past een beheerder aan via **Instellingen > Technisch > E-mail > E-mailsjablonen** (met de ontwikkelaarsmodus aan; zoek op "Invordering").

## Hoe reken ik interest en schadevergoeding aan?

1. Open het dossier en ga naar het tabblad **Interest en schadevergoeding**.
2. Onder **Nu aan te rekenen** ziet u de interest tot vandaag en de forfaitaire schadevergoeding.
3. Klik op **Kosten aanrekenen**. Odoo boekt een factuur op naam van de eigenaar, in de boekhouding van de VME, met:
   - per openstaande factuur een lijn nalatigheidsinterest (bedrag × interestvoet × dagen / 365),
   - eenmalig de forfaitaire schadevergoeding.
4. Die factuur komt meteen op de volgende herinnering. Een concept dat al klaarstaat, wordt automatisch bijgewerkt.

Rekent u later opnieuw aan, dan telt Odoo alleen de interest over de nieuwe dagen. De schadevergoeding wordt maar één keer per dossier aangerekend, en op aangerekende kosten loopt geen interest.

**Waar stel ik de regels in?** Op de VME, tabblad **Invordering**, volgens het reglement van mede-eigendom:

- **Eerste herinnering na (dagen)** na de vervaldag (standaard meteen),
- **Termijn tussen twee niveaus** (standaard 14 dagen),
- **Nalatigheidsinterest** in procent per jaar (standaard 8%),
- **Forfaitaire schadevergoeding** in procent van het saldo, met een minimum (standaard 10%, minimum 50 euro),
- **Eigenaars als consument behandelen** (standaard aan).

Staat **Eigenaars als consument behandelen** aan, dan houdt Odoo zich aan de regels voor consumentenschulden:

- de eerste herinnering is kosteloos, en kosten kunnen pas 14 dagen na die herinnering;
- de interest is hoogstens de wettelijke interestvoet plus 8 procentpunten (Odoo toont de **toegepaste interestvoet**);
- de schadevergoeding is hoogstens 20 euro (saldo tot 150 euro), 30 euro plus 10% boven 150 euro (tot 500 euro), of 65 euro plus 5% boven 500 euro, met een maximum van 2000 euro.

## Hoe stuur ik een dossier door naar een advocaat of deurwaarder?

1. Dat kan pas na een verstuurde ingebrekestelling. In de lijst **Dossiers** staat dan bij **Volgende stap** "Doorsturen naar advocaat of deurwaarder".
2. Open het dossier en kies de **Advocaat of deurwaarder**.
3. Klik op **Doorsturen**. Odoo maakt een PDF-overzicht van het dossier (eigenaar, kavels, openstaande facturen met mededeling, verstuurde herinneringen en aangerekende kosten) en opent een e-mail met die PDF.
4. Kijk de e-mail na en verstuur ze zelf. Het dossier krijgt dan de status **Doorgestuurd**.

Met **Overzicht (PDF)** drukt u hetzelfde overzicht af zonder door te sturen.

Is alles betaald, dan sluit **Invordering bijwerken** het dossier af. U kunt een dossier ook zelf **Afsluiten**, bv. na een afbetalingsplan, en later **Heropenen**.

## Voorbeeld in de demo

Na het laden van de demohistoriek 2026 zijn er twee dossiers:

- **Eigenaar Linde A3** (Residentie Linde) betaalde oproep 4 niet (vervallen op 4 november 2026). Er staat een vriendelijke herinnering klaar als concept.
- **Eigenaar Beuken B7** (Hof ter Beuken) betaalde oproep 3 en 4 niet. Voor oproep 3 kreeg hij al een vriendelijke herinnering (11 augustus) en een aanmaning (1 september). Er staat nu een ingebrekestelling klaar, en in het dossier staat de "Gerechtsdeurwaarder Voorbeeld" al ingevuld.

Probeer bij B7: **Kosten aanrekenen**, de ingebrekestelling **Bijwerken** en **Per post verstuurd**, en daarna **Doorsturen**.

## Veelgestelde vragen

**Waarom staat een eigenaar niet in de achterstallen, terwijl hij nog moet betalen?**
Alleen vervallen bedragen tellen. Een provisieoproep die pas volgende week vervalt, staat er nog niet in.

**Waarom stelt Odoo geen aanmaning voor?**
De termijn na de vorige herinnering loopt nog, of er staat al een concept klaar. Bij **Volgende stap** op het dossier staat waarom.

**Waarom kan ik nog geen kosten aanrekenen?**
Als de eigenaar als consument behandeld wordt, moet eerst een kosteloze herinnering verstuurd zijn en moeten daarna 14 dagen verstreken zijn. Het dossier zegt vanaf wanneer het kan.

**Wordt de herinnering automatisch gemaild?**
Nee. Odoo maakt alleen concepten. U verstuurt zelf, per e-mail of per post.

**De eigenaar heeft intussen betaald. Wat nu?**
Zodra de betaling in de boekhouding aan de factuur gekoppeld is, verdwijnt het bedrag uit de achterstallen. **Invordering bijwerken** annuleert dan een concept dat nog klaarstond en sluit het dossier af.
