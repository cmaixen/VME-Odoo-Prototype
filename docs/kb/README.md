# Kennisbank VME-platform

Deze kennisbank is voor syndici en hun medewerkers. Elk artikel legt één taak uit: wat je doet, waar je klikt, een voorbeeld uit de demo en de vragen die we het vaakst krijgen.

Je opent de kennisbank ook vanuit Odoo: in de app **VME** staat bovenaan het menu **Help**, met een link naar elk artikel.

> Dit is een prototype. Alle gebouwen, eigenaars, rekeningnummers en bedragen in de voorbeelden zijn verzonnen. De Belgische regels in het platform zijn nog niet juridisch nagekeken.

## Inhoud

### Het gebouw opzetten

1. [Een VME aanmaken en de bankrekeningen bevestigen](vme-aanmaken.md)
2. [Kavels en eigenaars, ook bij een verkoop](kavels-en-eigendom.md)
3. [Verdeelsleutels en quotiteiten](verdeelsleutels.md)
4. [Verkoop van een kavel: inlichtingen aan de notaris](verkoop-notaris.md)

### Kosten verdelen

5. [Een leveranciersfactuur verdelen over de eigenaars](factuur-verdelen.md)
6. [Verdeelregels en Peppol-facturen: automatisch verdelen](verdeelregels-en-peppol.md)

### Geld opvragen en afrekenen

7. [Budget en provisieoproepen, met de 5%-regel voor het reservefonds](budget-en-provisieoproepen.md)
8. [De jaarafrekening lezen en afdrukken](jaarafrekening.md)
9. [Invordering van achterstallen: herinneringen, interest en doorsturen](invordering.md)

### Gebouw en installaties

10. [Keuringen en liften opvolgen](keuringen.md)
11. [Werken opvolgen, van offertes tot oplevering](werken.md)
12. [Een schadegeval behandelen met de verzekering](schadegevallen.md)

### Algemene vergaderingen

13. [Algemene vergaderingen plannen in blokken](av-planner.md)
14. [De algemene vergadering: oproeping, stemming en notulen](algemene-vergadering.md)

### Post en mails

15. [Leveranciersfacturen per e-mail ontvangen](facturen-per-mail.md)
16. [Een antwoord behandelen dat de AI-assistent voorstelt](ai-voorstellen-mails.md)
17. [Bankafschriften inlezen en betalingen koppelen](bankafschriften.md)

### Overstappen

18. [Een VME overnemen uit een ander syndicuspakket](migratie.md)

## Zo is het platform opgebouwd

- **Eén VME = één bedrijf in Odoo.** Elke VME heeft haar eigen boekhouding, eigen rekeningnummers en eigen facturen. Rechtsboven in Odoo kies je in welke VME je werkt wanneer je facturen ingeeft. De schermen in de app **VME** (kavels, sleutels, provisieoproepen, jaarafrekening) tonen altijd alle VME's samen.
- **Werkkapitaal en reservekapitaal staan apart.** Elk fonds heeft een eigen bankrekening, en elke eigenaar krijgt per fonds een eigen provisiefactuur.
- **Kosten volgen de eigenaar op de dag zelf.** Wordt een kavel verkocht, dan verdeelt het platform elke kost over verkoper en koper volgens het aantal dagen dat elk eigenaar was.

## De demo

De demo bevat drie verzonnen gebouwen:

| VME | Kavels | Verdeelsleutels | Bijzonder |
| --- | --- | --- | --- |
| Residentie Linde | 12 appartementen (A1–A12) en 8 garages (G1–G8) | Algemene sleutel, liftsleutel | A5 en G5 zijn op 1 juli 2026 verkocht; A3 en G3 zijn in verkoop (vraag van de notaris) |
| Hof ter Beuken | 24 appartementen (B1–B24) | Algemene sleutel, verwarmingssleutel | Eén eigenaar heeft B23 en B24; het reservefonds zit onder de 5% |
| Kaaihuis | 6 appartementen (K1–K6) | Algemene sleutel | Klein gebouw zonder lift |

Een beheerder laadt de demo via **VME > Configuratie > Demodata laden** en daarna **Demohistoriek 2026 laden** (provisieoproepen, betalingen, leveranciersfacturen en invorderingen van een volledig jaar). De schermafbeeldingen in deze kennisbank komen uit die demo.
