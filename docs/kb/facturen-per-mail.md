# Hoe ontvang ik leveranciersfacturen per e-mail?

Elke VME heeft een eigen e-mailadres voor leveranciersfacturen. Stuurt een leverancier een factuur als bijlage naar dat adres, dan staat ze vanzelf als **conceptfactuur** in de boekhouding van die VME. Is de bijlage een e-factuur (Peppol), dan zijn ook de leverancier, de bedragen, de kostperiode en de verdeelsleutel al ingevuld.

Er wordt niets automatisch geboekt of betaald: u kijkt de factuur na en bevestigt ze zelf.

## Waar vind ik het adres van een VME?

1. Ga naar **VME > VME's** en open de VME.
2. Bij **Gegevens** staat **E-mailadres voor facturen**, bijvoorbeeld `facturen-kaaihuis@syndicus.example.com`.
3. Klik op het kopieer-icoontje en geef het adres aan de leveranciers van dat gebouw.

Het adres volgt altijd hetzelfde patroon: `facturen-` gevolgd door de naam van de VME.

## Stappen om een binnengekomen factuur te behandelen

1. Kies bovenaan rechts de VME (het bedrijf) en ga naar **Facturatie > Leveranciers > Facturen**.
2. Nieuwe facturen per mail staan in **Concept**. Open de factuur.
3. Rechts ziet u de bijlage uit de mail; onderaan in de geschiedenis staat de mail zelf.
4. Kijk na: leverancier, factuurdatum, bedrag, **Kostperiode** en de **Verdeelsleutel** per lijn. Is er een verdeelregel voor deze leverancier, dan zijn sleutel en rekening al ingevuld.
5. Klik op **Bevestigen**. De factuur wordt geboekt en meteen over de eigenaars verdeeld.

Was de bijlage een gewone PDF en geen e-factuur, dan leest de AI-assistent de factuur en vult hij het concept in, met per veld een controle: zie [PDF-facturen en documenten laten lezen door de AI-assistent](pdf-facturen-ai.md).

## Voorbeeld uit de demodata

In de demo stuurt "Energieleverancier Voorbeeld NV" drie mails, één per gebouw, met de jaarafrekening elektriciteit als e-factuur:

| Aan | Wordt | Bedrag |
| --- | --- | --- |
| facturen-residentie-linde@syndicus.example.com | conceptfactuur EV-2026-110301 in Residentie Linde | 5.324,00 € |
| facturen-hof-ter-beuken@syndicus.example.com | conceptfactuur EV-2026-110302 in Hof ter Beuken | 6.231,50 € |
| facturen-kaaihuis@syndicus.example.com | conceptfactuur EV-2026-110303 in Kaaihuis | 1.500,40 € |

Elke factuur heeft als kostperiode 1 november 2025 tot 31 oktober 2026 en de algemene sleutel.

> Let op: deze drie elektriciteitsfacturen zitten ook al in de **demohistoriek 2026**. Lever ze alleen aan op een demo zonder historiek, anders worden ze dubbel geboekt. Voor een demo mét historiek staat in `ai/demo_inbox/` een aparte mail: de factuur van de liftinspectie van Residentie Linde (zie het [demoscenario](../demo.md)). Bij Residentie Linde wordt appartement A5 na het bevestigen pro rata verdeeld tussen de verkoper en de koper.

## Veelgestelde vragen

**Wat als een leverancier naar het verkeerde adres stuurt?**
Dan komt de factuur in de verkeerde VME terecht. Verwijder de conceptfactuur daar en vraag de leverancier om ze naar het juiste adres te sturen, of maak ze zelf aan in de juiste VME.

**Wat gebeurt er met een mail zonder bijlage?**
Er wordt geen factuur gemaakt. De afzender krijgt automatisch een antwoord dat er geen bijlage was (zodra de uitgaande mail ingesteld is).

**Wat als dezelfde mail twee keer binnenkomt?**
Odoo herkent de mail en maakt maar één factuur.

**Kan iedereen een factuur naar dat adres sturen?**
Ja, zoals bij een gewoon e-mailadres. Daarom wordt niets automatisch geboekt: elke factuur blijft een concept tot u ze nakijkt.

**Mogen meerdere facturen in één mail?**
Ja. Odoo maakt dan een conceptfactuur per factuur; een PDF en de e-factuur van dezelfde factuur blijven samen.

**Werkt dit al met onze echte mailbox?**
In het prototype nog niet: het adres op `syndicus.example.com` is verzonnen en de mails worden met een script aangeleverd. Voor de echte werking moet de beheerder een mailserver koppelen (zie de ontwerpbeslissingen).
