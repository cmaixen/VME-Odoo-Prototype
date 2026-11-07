# De fiches 281.50 van een VME maken (Belcotax-on-web)

Een VME die erelonen, commissies of gelijkaardige vergoedingen betaalt aan zelfstandigen of bedrijven, moet die elk jaar melden aan de FOD Financiën op een **fiche 281.50**. Denk aan een commissaris van de rekeningen die geen mede-eigenaar is en die een factuur stuurt, een consultant, een architect of een expert.

Het platform zoekt de betalingen voor u bij elkaar, toont per verkrijger wat er op de fiche komt en waarschuwt als er gegevens ontbreken. Na uw controle downloadt u een bestand dat u **zelf** oplaadt in Belcotax-on-web. Het platform dient niets in.

> De wettelijke regels (wie, welke bedragen, de drempel en de termijn) zijn nog niet juridisch nagekeken. Het bestand volgt de technische voorschriften die de FOD Financiën publiceert, maar doe vóór de eerste echte aangifte een proefupload in Belcotax-on-web.

## Hoe duid ik aan welke leveranciers op een fiche komen?

1. Open de leverancier (via **Facturatie > Leveranciers** of de leverancierskaart).
2. Ga naar het tabblad **Fiche 281.50**.
3. Vink **281.50-plichtig** aan.
4. Kies de **soort vergoeding**: commissies en makelaarslonen, erelonen of vacatiegelden, voordelen van alle aard, of kosten voor rekening van de verkrijger.
5. Vul het **beroep** in (bv. "Accountant"). Voor een persoon vult u ook het **rijksregisternummer** in.
6. Kijk na dat het **adres** volledig is. Het platform haalt het ondernemingsnummer uit het veld KBO of uit het btw-nummer. Dat geldt voor een bedrijf, maar ook voor een zelfstandige met een vrij beroep (bv. een accountant of architect): die heeft naast zijn rijksregisternummer een ondernemingsnummer, en dat moet op de fiche.

Dat doet u één keer per leverancier: het geldt in alle VME's.

## Hoe maak ik het overzicht van een jaar?

1. Ga naar **VME > Fiches 281.50** en klik op **Nieuw**.
2. Kies de **VME** en het **inkomstenjaar** (standaard vorig jaar).
3. Bewaar. Het platform telt per 281.50-plichtige leverancier op wat de VME in dat jaar **betaald** heeft op geboekte facturen. Een creditnota die terugbetaald is, gaat ervan af.
4. Kijk elke regel na:
   - Een **grijze** regel staat onder de drempel van 250 euro per jaar: daarvoor is geen fiche nodig en ze komt niet in het bestand.
   - Een **oranje** regel heeft een waarschuwing, bv. "Adres onvolledig" of "Rijksregisternummer ontbreekt". Vul de gegevens aan op de leverancier en klik **Opnieuw berekenen**, of verbeter ze rechtstreeks in de regel.
5. Klopt alles, klik dan op **Nagekeken**. Uw naam en de datum worden bewaard.
6. Klik op **Bestand voor Belcotax downloaden** en laad het bestand op in Belcotax-on-web.
7. Klik daarna op **Opgeladen in Belcotax**. Zo ziet u in de lijst welke VME's nog moeten.

Bovenaan ziet u ook **Indienen uiterlijk**: de termijn die het platform aanhoudt (29 juni van het jaar erna, zoals in de brochure van de FOD Financiën). De FOD bevestigt die elk jaar; kijk ze na in Belcotax-on-web.

Een oranje melding bovenaan het overzicht wijst op ontbrekende gegevens van de VME zelf of van wie het bestand oplaadt: het ondernemingsnummer of adres van de VME, of het e-mailadres en telefoonnummer van het kantoor. Vul ze aan bij de instellingen van de company of van uw gebruiker.

## Welk bestand krijg ik?

Bij **Formaat** ziet u welk bestand het platform maakt. Dat hangt af van het inkomstenjaar:

- **Tot en met inkomsten 2025**: een XML-bestand voor de huidige Belcotax-on-web. Het kantoor van de syndicus staat erin als afzender, de VME als schuldenaar.
- **Vanaf inkomsten 2026**: een bestand in het nieuwe formaat van de vernieuwde Belcotax-on-web, die vanaf februari 2027 werkt. Het oude XML-formaat wordt daar niet meer aanvaard. Belcotax stuurt de ontvangstmelding naar uw e-mailadres.

## Voorbeeld uit de demo

Na **Demohistoriek 2026 laden** staat er per demogebouw een overzicht 2026:

| VME | Verkrijger | Bedrag | Wat valt op |
| --- | --- | --- | --- |
| Hof ter Beuken | Commissaris Voorbeeld Beuken (accountant) | 650,00 | Volledig, klaar om na te kijken |
| Residentie Linde | Advies Voorbeeld BV (ingenieur-adviseur) | 1.800,00 | Bedrijf: het ondernemingsnummer komt uit het btw-nummer |
| Kaaihuis | Expert Voorbeeld Kaaihuis | 420,00 | Waarschuwing: adres, rijksregisternummer en beroep ontbreken |

Alle namen en nummers zijn verzonnen.

## Veelgestelde vragen

**Telt de factuurdatum of de betaaldatum?**
De betaaldatum. Een factuur van december 2026 die in januari 2027 betaald wordt, komt op de fiche van 2027.

**Is het bedrag met of zonder btw?**
Met btw: de meeste VME's kunnen de btw niet aftrekken, dus dat is wat ze betaald hebben. Dat is een keuze van het prototype die nog nagekeken moet worden.

**Kan ik een overzicht maken als er gegevens ontbreken?**
Ja. Ontbrekende gegevens zijn een waarschuwing, geen blokkering. Belcotax-on-web weigert wel een fiche zonder identificatie, dus vul ze best eerst aan.

**Er kwam nog een betaling bij nadat ik "Nagekeken" klikte.**
Klik **Opnieuw berekenen**. Het overzicht gaat terug naar "Na te kijken" en u kijkt het opnieuw na.

**Ik heb het bestand van 2026 al opgeladen en moet iets verbeteren.**
Verbeter, bereken opnieuw, kijk na en laad het nieuwe bestand op. Elke fiche heeft een vaste sleutel per VME, jaar en verkrijger: in de vernieuwde Belcotax-on-web vervangt de nieuwe fiche dan de oude. Voor de jaren tot 2025 maakt u een verbetering rechtstreeks in Belcotax-on-web.

**Waarom staat het rijksregisternummer niet in het bestand?**
Het platform neemt alleen een nummer op als het controlegetal klopt: Belcotax-on-web weigert het hele bestand bij één fout nummer. De regel toont dan een waarschuwing. Vanaf 1 januari 2028 is het rijksregisternummer verplicht voor elke persoon op een fiche.

**Moet de syndicus zelf ook op een fiche?**
Dat beslist u: vink de syndicus aan als 281.50-plichtig als dat voor uw kantoor geldt. Het platform kiest niet zelf wie op een fiche komt.

**Kan de commissaris van de rekeningen het overzicht zien?**
Ja, alleen lezen, en alleen voor zijn eigen VME.
