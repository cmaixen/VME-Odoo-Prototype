# De fiches 281.50 van een VME maken (Belcotax-on-web)

Een VME die erelonen, commissies of gelijkaardige vergoedingen betaalt aan zelfstandigen of bedrijven, moet die elk jaar melden aan de FOD Financiën op een **fiche 281.50**. Denk aan een commissaris van de rekeningen die geen mede-eigenaar is en die een factuur stuurt, een consultant, een architect of een expert.

Het platform zoekt de betalingen voor u bij elkaar, toont per verkrijger wat er op de fiche komt en waarschuwt als er gegevens ontbreken. Na uw controle downloadt u een bestand dat u **zelf** oplaadt in Belcotax-on-web. Het platform dient niets in.

> De wettelijke regels (wie, welke bedragen, de drempel en de termijn) en het bestandsformaat zijn nog niet juridisch nagekeken. Kijk vóór de eerste echte aangifte het formaat na met een proefupload in Belcotax-on-web.

## Hoe duid ik aan welke leveranciers op een fiche komen?

1. Open de leverancier (via **Facturatie > Leveranciers** of de leverancierskaart).
2. Ga naar het tabblad **Fiche 281.50**.
3. Vink **281.50-plichtig** aan.
4. Kies de **soort vergoeding**: commissies en makelaarslonen, erelonen of vacatiegelden, voordelen van alle aard, of kosten voor rekening van de verkrijger.
5. Vul het **beroep** in (bv. "Accountant"). Voor een persoon vult u ook het **rijksregisternummer** in.
6. Kijk na dat het **adres** volledig is. Voor een bedrijf haalt het platform het ondernemingsnummer uit het veld KBO of uit het btw-nummer.

Dat doet u één keer per leverancier: het geldt in alle VME's.

## Hoe maak ik het overzicht van een jaar?

1. Ga naar **VME > Fiches 281.50** en klik op **Nieuw**.
2. Kies de **VME** en het **inkomstenjaar** (standaard vorig jaar).
3. Bewaar. Het platform telt per 281.50-plichtige leverancier op wat de VME in dat jaar **betaald** heeft op geboekte facturen. Een creditnota die terugbetaald is, gaat ervan af.
4. Kijk elke regel na:
   - Een **grijze** regel staat onder de drempel van 250 euro per jaar: daarvoor is geen fiche nodig en ze komt niet in het bestand.
   - Een **oranje** regel heeft een waarschuwing, bv. "Adres onvolledig" of "Rijksregisternummer ontbreekt". Vul de gegevens aan op de leverancier en klik **Opnieuw berekenen**, of verbeter ze rechtstreeks in de regel.
5. Klopt alles, klik dan op **Nagekeken**. Uw naam en de datum worden bewaard.
6. Klik op **XML voor Belcotax downloaden** en laad het bestand op in Belcotax-on-web.
7. Klik daarna op **Opgeladen in Belcotax**. Zo ziet u in de lijst welke VME's nog moeten.

Bovenaan ziet u ook **Indienen uiterlijk**: de termijn die het platform aanhoudt (30 juni van het jaar erna). De FOD Financiën legt die elk jaar vast; kijk ze na in Belcotax-on-web.

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

**Moet de syndicus zelf ook op een fiche?**
Dat beslist u: vink de syndicus aan als 281.50-plichtig als dat voor uw kantoor geldt. Het platform kiest niet zelf wie op een fiche komt.

**Kan de commissaris van de rekeningen het overzicht zien?**
Ja, alleen lezen, en alleen voor zijn eigen VME.
