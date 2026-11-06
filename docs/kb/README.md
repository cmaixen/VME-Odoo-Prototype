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
7. [Verwarming of water op verbruik: tellers en meterstanden](verbruik-en-meterstanden.md)

### Geld opvragen en afrekenen

8. [Budget en provisieoproepen, met de 5%-regel voor het reservefonds](budget-en-provisieoproepen.md)
9. [De jaarafrekening lezen en afdrukken](jaarafrekening.md)
10. [Invordering van achterstallen: herinneringen, interest en doorsturen](invordering.md)

### Gebouw en installaties

11. [Keuringen en liften opvolgen](keuringen.md)
12. [Werken opvolgen, van offertes tot oplevering](werken.md)
13. [Een schadegeval behandelen met de verzekering](schadegevallen.md)

### Algemene vergaderingen

14. [Algemene vergaderingen plannen in blokken](av-planner.md)
15. [De algemene vergadering: oproeping, stemming en notulen](algemene-vergadering.md)
16. [Een hybride of online algemene vergadering houden](digitale-av.md)

### Post en mails

17. [Leveranciersfacturen per e-mail ontvangen](facturen-per-mail.md)
18. [Een antwoord behandelen dat de AI-assistent voorstelt](ai-voorstellen-mails.md)
19. [Bankafschriften inlezen en betalingen koppelen](bankafschriften.md)

### Overstappen

20. [Een VME overnemen uit een ander syndicuspakket](migratie.md)

### Documenten en eigenaars

21. [Documenten van een VME en van een kavel bewaren](documenten.md)
22. [Het eigenaarsportaal: toegang, wat de eigenaar ziet, adreswijzigingen](eigenaarsportaal.md)
23. [De raad van mede-eigendom en de commissaris van de rekeningen](raad-en-commissaris.md)

### Overzichten

24. [De gebouwkaart, de budgetopvolging en de portefeuille](gebouwkaart.md)
31. [Het jaar van een VME opvolgen: de jaarcyclus](jaarcyclus.md)

### Post en mails


### Overstappen


### Algemene vergaderingen


### Post en mails


### Overstappen

25. [Contracten en personeel opvolgen](contracten.md)

### Algemene vergaderingen


### Post en mails


### Bewoners

26. [Aanvragen van bewoners: sleutels, badges en andere vaste procedures](aanvragen-sleutels-badges.md)

### Overstappen

27. [Leveranciers betalen en provisies domiciliëren](betalingen.md)

### Overstappen

28. [PDF-facturen en documenten laten lezen door de AI-assistent](pdf-facturen-ai.md)

### Overstappen

29. [Communicatie met eigenaars: mededelingen, bevragingen en aangetekende brieven](communicatie.md)

### Overstappen


### Rentmeester

30. [Een verhuurd appartement beheren: huurcontract, huurfacturen, indexering en afrekening aan de huurder](rentmeester.md)

## Zo is het platform opgebouwd

- **Eén VME = één bedrijf in Odoo.** Elke VME heeft haar eigen boekhouding, eigen rekeningnummers en eigen facturen. Rechtsboven in Odoo kies je in welke VME je werkt wanneer je facturen ingeeft. De schermen in de app **VME** (kavels, sleutels, provisieoproepen, jaarafrekening) tonen altijd alle VME's samen.
- **Werkkapitaal en reservekapitaal staan apart.** Elk fonds heeft een eigen bankrekening, en elke eigenaar krijgt per fonds een eigen provisiefactuur.
- **Kosten volgen de eigenaar op de dag zelf.** Wordt een kavel verkocht, dan verdeelt het platform elke kost over verkoper en koper volgens het aantal dagen dat elk eigenaar was.

## De demo

De demo bevat drie verzonnen gebouwen:

| VME | Kavels | Verdeelsleutels | Bijzonder |
| --- | --- | --- | --- |
| Residentie Linde | 12 appartementen (A1–A12) en 8 garages (G1–G8) | Algemene sleutel, liftsleutel | A5 en G5 zijn op 1 juli 2026 verkocht; A3 en G3 zijn in verkoop (vraag van de notaris) |
| Hof ter Beuken | 24 appartementen (B1–B24) | Algemene sleutel, verwarming op verbruik (30% vast) | Eén eigenaar heeft B23 en B24; kostenverdelers op elke radiator; het reservefonds zit onder de 5% |
| Hof ter Beuken | 24 appartementen (B1–B24) | Algemene sleutel, verwarmingssleutel | Eén eigenaar heeft B23 en B24; het reservefonds zit onder de 5%; een conciërge via een sociaal secretariaat |
| Kaaihuis | 6 appartementen (K1–K6) | Algemene sleutel | Klein gebouw zonder lift |
| Residentie Linde | 12 appartementen (A1–A12) en 8 garages (G1–G8) | Algemene sleutel, liftsleutel | A5 en G5 zijn op 1 juli 2026 verkocht; A3 en G3 zijn in verkoop (vraag van de notaris); A6 is verhuurd |
| Hof ter Beuken | 24 appartementen (B1–B24) | Algemene sleutel, verwarmingssleutel | Eén eigenaar heeft B23 en B24; het reservefonds zit onder de 5%; B12 is verhuurd |
| Kaaihuis | 6 appartementen (K1–K6) | Algemene sleutel | Klein gebouw zonder lift; K2 is verhuurd |

Elk gebouw heeft een sleutelregister en dezelfde verzonnen slotenmaker (Slotenmaker Voorbeeld BV).

Bij de demo horen ook drie verhuurde appartementen (Linde A2, Linde A7 en Beuken B23), beheerd door het fictieve kantoor **Rentmeester Voorbeeld BV**; zie [rentmeester](rentmeester.md).

Een beheerder laadt de demo via **VME > Configuratie > Demodata laden** en daarna **Demohistoriek 2026 laden** (provisieoproepen, betalingen, leveranciersfacturen en invorderingen van een volledig jaar). De schermafbeeldingen in deze kennisbank komen uit die demo.
