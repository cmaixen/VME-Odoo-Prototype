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
10. [De balans en resultatenrekening van een VME maken](balans-en-resultatenrekening.md)
11. [Invordering van achterstallen: herinneringen, interest en doorsturen](invordering.md)
11b. [Het boekjaar afsluiten: afrekening boeken, overdracht en vergrendeling](boekjaar-afsluiten.md)

### Gebouw en installaties

12. [Keuringen en liften opvolgen](keuringen.md)
13. [Werken opvolgen, van offertes tot oplevering](werken.md)
14. [Een schadegeval behandelen met de verzekering](schadegevallen.md)
15. [De brandverzekering en de verplichte attesten van een gebouw opvolgen](verzekeringen-en-attesten.md)
16. [Offertes voor werken vergelijken met de AI](offertes-vergelijken.md)

### Algemene vergaderingen

17. [Algemene vergaderingen plannen in blokken](av-planner.md)
18. [De algemene vergadering: oproeping, stemming en notulen](algemene-vergadering.md)
19. [Een hybride of online algemene vergadering houden](digitale-av.md)

### Post en mails

20. [Leveranciersfacturen per e-mail ontvangen](facturen-per-mail.md)
21. [Een antwoord behandelen dat de AI-assistent voorstelt](ai-voorstellen-mails.md)
22. [Bankafschriften inlezen en betalingen koppelen](bankafschriften.md)

### Overstappen

23. [Een VME overnemen uit een ander syndicuspakket](migratie.md)

### Documenten en eigenaars

24. [Documenten van een VME en van een kavel bewaren](documenten.md)
25. [Het eigenaarsportaal: toegang, wat de eigenaar ziet, adreswijzigingen](eigenaarsportaal.md)
26. [De raad van mede-eigendom en de commissaris van de rekeningen](raad-en-commissaris.md)

### Overzichten

27. [De gebouwkaart, de budgetopvolging en de portefeuille](gebouwkaart.md)
28. [Het jaar van een VME opvolgen: de jaarcyclus](jaarcyclus.md)
29. [Een gebouw overnemen met de basisakte en de notulen (AI)](overname-basisakte-ai.md)

### Documenten en eigenaars


### Overzichten


### Post en mails


### Overstappen


### Algemene vergaderingen


### Post en mails


### Overstappen

30. [Contracten en personeel opvolgen](contracten.md)

### Algemene vergaderingen


### Post en mails


### Bewoners

31. [Aanvragen van bewoners: sleutels, badges en andere vaste procedures](aanvragen-sleutels-badges.md)
32. [Aanvragen en bevragingen in het eigenaarsportaal](portaal-aanvragen-bevragingen.md)

### Overstappen

33. [Leveranciers betalen en provisies domiciliëren](betalingen.md)

### Overstappen

34. [PDF-facturen en documenten laten lezen door de AI-assistent](pdf-facturen-ai.md)

### Overstappen

35. [Communicatie met eigenaars: mededelingen, bevragingen en aangetekende brieven](communicatie.md)

### Overstappen


### Overstappen


### Overstappen


### Overstappen


### Rentmeester

36. [Een verhuurd appartement beheren: huurcontract, huurfacturen, indexering en afrekening aan de huurder](rentmeester.md)
37. [De huur doorstorten aan de verhuurder: ereloon, kosten, afrekening en betaalbatch](doorstorting-verhuurder.md)

### Gebruikers

38. [Medewerkers toegang geven tot alle of enkele VME's](toegang-medewerkers.md)

### De website

39. [De website en inloggen voor medewerkers en eigenaars](website-en-inloggen.md)

### Het kantoor van de syndicus

40. [Uw ereloon, extra prestaties en uw mandaat als syndicus](ereloon-en-mandaat.md)

### Taal

41. [Documenten in het Frans sturen](documenten-in-het-frans.md)

### De dag van de medewerker

42. [Mijn werk vandaag: alles wat vandaag moet, over al uw VME's](mijn-werk-vandaag.md)

### Outlook

43. [Mails in Outlook koppelen aan de VME en de kavel](outlook-invoegtoepassing.md)

### Gebruikers


### De website


### Het kantoor van de syndicus


### Taal


## Zo is het platform opgebouwd

- **Eén VME = één bedrijf in Odoo.** Elke VME heeft haar eigen boekhouding, eigen rekeningnummers en eigen facturen. Rechtsboven in Odoo kies je in welke VME je werkt wanneer je facturen ingeeft. De schermen in de app **VME** (kavels, sleutels, provisieoproepen, jaarafrekening) tonen altijd alle VME's samen waartoe je toegang hebt.
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

De drie gebouwen worden beheerd door het fictieve kantoor **Syndicus Voorbeeld BV**, met een beheerovereenkomst en een mandaat per gebouw; zie [ereloon en mandaat](ereloon-en-mandaat.md).

Bij de demo horen ook drie verhuurde appartementen (Linde A2, Linde A7 en Beuken B23), beheerd door het fictieve kantoor **Rentmeester Voorbeeld BV**; zie [rentmeester](rentmeester.md).

Een beheerder laadt de demo via **VME > Configuratie > Demodata laden** en daarna **Demohistoriek 2026 laden** (provisieoproepen, betalingen, leveranciersfacturen en invorderingen van een volledig jaar). De schermafbeeldingen in deze kennisbank komen uit die demo.
