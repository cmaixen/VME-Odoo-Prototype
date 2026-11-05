# Prompts voor Claude Code, in volgorde

Plak telkens één prompt in Claude Code. Ga pas naar de volgende als de vorige werkt en je ze in de browser getest hebt.

## 1. Omgeving en lege module

> Lees CLAUDE.md. Start de Docker-omgeving, maak een database `vme_demo` aan en maak een lege module `vme_belgie` in `addons/` die afhangt van `account`. Installeer ze en controleer in de logs dat er geen fouten zijn. Leg uit hoe ik de database in de browser open.

## 2. Datamodel

> Maak in `vme_belgie` de modellen uit CLAUDE.md: `vme.association` (gekoppeld aan een company, met KBO-nummer, adres en bankrekeningen voor werk- en reservekapitaal), `vme.lot`, `vme.key` met `vme.key.line` (quotiteit per kavel) en `vme.ownership` (eigenaar, kavel, begin- en einddatum). Voeg menu's, lijst- en formulierweergaven toe in het Nederlands. Controleer dat de som van de quotiteiten per sleutel klopt met het totaal (bijvoorbeeld 1.000). Gebruik plan mode.

## 3. Fictieve demodata

> Maak demodata met drie fictieve VME's: "Residentie Linde" (12 appartementen, 8 garages, lift), "Hof ter Beuken" (24 appartementen, centrale verwarming) en "Kaaihuis" (6 appartementen, geen lift). Elk met een algemene sleutel en waar nodig een lift- of verwarmingssleutel, en verzonnen eigenaars. In één VME is een kavel midden in het jaar verkocht.

## 4. Kostenverdeling

> Voeg op leveranciersfacturen een veld toe voor de VME en per factuurlijn een verdeelsleutel. Maak een knop "Verdeel over eigenaars" die per eigenaar het aandeel berekent volgens de quotiteiten, rekening houdend met eigendomsdatums (pro rata bij verkoop). Toon het resultaat in een overzicht per eigenaar. Schrijf unittests voor de verdeling, inclusief de verkoop midden in het jaar.

## 4b. Verdeelregels en automatisch afboeken

> Bouw verder op de kostenverdeling uit stap 4. Voeg per VME "verdeelregels" toe: een leverancier (en optioneel een kostenrekening) met een vaste verdeelsleutel, bijvoorbeeld "Energieleverancier → algemene sleutel" in Residentie Linde. Als een leveranciersfactuur binnenkomt in de company van een VME, vul dan de VME en per lijn de sleutel automatisch in volgens de regel, en verdeel de factuur automatisch over de eigenaars bij het boeken. Lijnen zonder passende regel blijven open voor een medewerker. Maak drie fictieve elektriciteitsfacturen als Peppol-UBL-bestanden (BIS Billing 3.0) in `addons/vme_belgie/demo_data/facturen/`, van een verzonnen leverancier met een fictief btw-nummer, en importeer ze in de demo via de gewone upload van leveranciersfacturen; echte Peppol-registratie kan niet met fictieve VME's. Voeg de verdeelregels toe aan de demodata. Schrijf unittests: een factuur met regel wordt zonder klikken verdeeld, een factuur zonder regel niet, en de verkoop midden in het jaar wordt ook hier pro rata verdeeld. Gebruik plan mode.

## 5. Provisieoproepen

> Maak een wizard "Provisieoproep" die voor een of meer VME's tegelijk per eigenaar een factuur maakt voor werkkapitaal en reservekapitaal, op basis van het jaarbudget en de algemene sleutel, met een Belgische gestructureerde mededeling. Voeg de 5%-regel voor het reservefonds toe als waarschuwing, met een `# LEGAL-CHECK:`-commentaar.

## 6. Jaarafrekening

> Maak een PDF-rapport "Jaarafrekening" per eigenaar: werkelijke kosten per sleutel, aandeel van de eigenaar, betaalde provisies en het saldo. Gebruik de demodata en controleer de cijfers met een unittest.

## 6b. Keuringen en onderhoudsagenda

> Voeg per VME een register van installaties toe (lift, brandblussers en brandhaspels, elektrische installatie van de gemene delen, centrale verwarmingsketel, rookluiken, …) met per installatie het keuringsorganisme of de onderhoudsfirma, de laatste keuring, de keuringsfrequentie en de volgende vervaldatum. Zet de wettelijke standaardfrequenties per soort installatie in de code, elk met een `# LEGAL-CHECK:`-commentaar en de bron, en laat een medewerker ze per installatie aanpassen. Maak een overzicht over alle VME's heen: vervallen, vervalt binnen 30, 60 of 90 dagen, met kleuren, filters per VME en per soort, en een kalenderweergave. Maak automatisch een taak (activiteit) voor de verantwoordelijke medewerker zodra een keuring binnen 60 dagen vervalt, en nooit twee keer voor dezelfde vervaldatum. Koppel een geboekte leveranciersfactuur van het keuringsorganisme aan de installatie, zodat de laatste keuring en de volgende vervaldatum vanzelf worden bijgewerkt (bouw daarvoor verder op de verdeelregels uit stap 4b). Liften krijgen een eigen, volledige opvolging: per lift in welke VME en welk gebouw ze staat, de onderhoudsfirma en het onderhoudscontract, de erkende dienst voor technische controle (EDTC) die de preventieve inspecties doet, de datum van de laatste en volgende preventieve inspectie (`# LEGAL-CHECK:` frequentie volgens het KB van 9 maart 2003 betreffende de beveiliging van liften), de datum van de laatste risicoanalyse en wanneer de volgende nodig is (`# LEGAL-CHECK:` idem), en of er een herkeuring nodig is na werken of na een negatief verslag. Laat per inspectieverslag het verslag (PDF) opladen en de opmerkingen als aparte opvolgpunten invoeren, elk met ernst, termijn, verantwoordelijke (onderhoudsfirma of syndicus) en status (open, gepland, opgelost, herkeurd); toon per lift en over alle VME's heen welke opmerkingen nog open staan en welke over hun termijn zijn. Voeg fictieve installaties toe aan de demodata, met minstens één vervallen keuring en één die binnenkort vervalt, en voor de lift van Residentie Linde een inspectieverslag met twee open opmerkingen en een risicoanalyse die binnenkort vervalt. Schrijf unittests voor de vervaldatums, het aanmaken van taken, de opvolging van opmerkingen en de koppeling met facturen. Gebruik plan mode.

## 6c. Algemene vergaderingen plannen in blokken

> Voeg per VME de periode van 15 dagen toe waarin de gewone algemene vergadering volgens het reglement van mede-eigendom moet plaatsvinden (`# LEGAL-CHECK: art. 3.87 §2 BW`). Bouw een planner voor de syndicus over alle VME's heen: welke AV's moeten in de komende maanden plaatsvinden, welke zijn al gepland, en welke dreigen hun periode te missen. Laat de syndicus beschikbare blokken ingeven (datum, uur, zaal of online, maximaal aantal vergaderingen per avond en per medewerker) en stel een indeling voor die elke AV binnen haar periode plant, zonder dubbele boekingen van zaal of medewerker; de syndicus bevestigt of past aan. Gebruik de Odoo-module `calendar` (Community) voor de afspraken en een eigen model voor de AV met VME, periode, blok, status en de wettelijke oproepingstermijn (`# LEGAL-CHECK:` met bron), en waarschuw als de oproeping te laat zou vertrekken. Voeg AV-periodes en een paar vrije blokken toe aan de demodata, zodat de planner minstens één conflict moet oplossen. Schrijf unittests voor de indeling en de waarschuwingen. Gebruik plan mode.

## 7. AI-assistent voor mails

> Bouw in `ai/` een Python-script volgens de architectuur in CLAUDE.md. Maak eerst vijf fictieve mails van eigenaars in `ai/inbox/` (een lek, een vraag over de afrekening, een verhuis, een klacht over de lift, een vraag over de volgende AV). Het script koppelt elke mail aan de juiste VME en kavel, bepaalt het onderwerp, stelt een antwoord voor en zet dat als activiteit op de VME in Odoo. Er wordt niets automatisch verstuurd. Lees de API-sleutel uit `ai/.env`.

## 7b. Leveranciersfacturen per e-mail

> Geef elke VME een eigen e-mailadres voor leveranciersfacturen via een alias op het aankoopdagboek van haar company, zodat een mail met een factuur als bijlage een conceptfactuur in de juiste VME wordt. Als de bijlage een UBL-bestand is, worden de lijnen ingelezen en passen de verdeelregels uit stap 4b. Gebruik in het prototype geen echte mailbox: maak drie fictieve `.eml`-bestanden in `ai/facturen_inbox/` en lever ze aan Odoo zoals een inkomende mailserver dat zou doen. Leg in `docs/beslissingen.md` vast wat er nodig is voor een echte mailbox (inkomende mailserver, domein, SPF/DKIM). Gebruik plan mode.

## 8. Demoscenario

> Schrijf in `docs/demo.md` een demoscenario van 10 minuten voor een syndicus: van een elektriciteitsfactuur die binnenkomt en automatisch verdeeld wordt, via een factuur die een medewerker zelf verdeelt, tot de jaarafrekening; van het keuringsoverzicht met een vervallen keuring tot de taak voor de medewerker; van de AV-planner die een seizoen AV's in blokken legt; en van een mail van een eigenaar tot een voorgesteld antwoord. Controleer dat elke stap werkt op een verse database met de demodata.

## 8b. Kennisbank en ontwikkelaarsdocumentatie (inhaalstap)

> Lees CLAUDE.md (werkwijze over documentatie) en schrijf de documentatie voor alles wat al gebouwd is. In `docs/kb/` een kennisbank voor syndici en medewerkers, in eenvoudig Nederlands: een startpagina met inhoudstafel, en per functie een artikel (VME aanmaken en bankrekeningen bevestigen, kavels en eigendom, verdeelsleutels, een factuur verdelen, verdeelregels en Peppol-facturen, budget en provisieoproepen met de 5%-regel, de jaarafrekening lezen en afdrukken), elk met stappen in Odoo, een voorbeeld uit de demodata, schermafbeeldingen uit de browser en veelgestelde vragen. In `docs/dev/` de interne documentatie: architectuur (één module op Odoo 19 Community, één company per VME), het datamodel met een diagram, de rekenregels (verdeling, afronding, provisies, afrekening), de Odoo-methodes die we overschrijven en waarom, de valkuilen die we tegenkwamen (automatisch installeren van modules, bevestigde bankrekeningen, multi-company, tijdelijke records in formulieren, trage tests), hoe je de omgeving, tests en demo opbouwt, en een lijst van alle `LEGAL-CHECK`-punten die een script automatisch uit de code haalt. Maak de kennisbank ook bereikbaar vanuit Odoo: een menu "Help" in de app VME dat naar de juiste artikels linkt. Controleer elke stap van de kennisbank in de browser op een verse demo.

---

# Fase 2: de rest van het werk van een syndicus

Na de demo (stap 8) dekken de stappen hieronder de taken af die een syndicus nog buiten het prototype doet. Ze staan in volgorde van hoeveel tijd ze een syndicus kosten. Elke wettelijke regel krijgt een `# LEGAL-CHECK:` met de bron, en alle data blijft fictief.

## 9. Inlichtingen aan de notaris bij verkoop

> Bouw een dossier "Verkoop kavel" per kavel: de notaris vraagt inlichtingen op, de syndicus antwoordt binnen de wettelijke termijnen (`# LEGAL-CHECK: art. 3.94 BW`, eerste en tweede vraag van de notaris). Stel het antwoord automatisch samen uit de bestaande gegevens: aandeel van de kavel in het werk- en reservekapitaal, openstaande provisies en achterstallen van de verkoper, door de AV beslste maar nog niet uitgevoerde werken en hun kostprijs, lopende gerechtelijke procedures, en de laatste notulen. Maak er een PDF van in de huisstijl van de VME, toon de termijn als vervaldatum met een taak voor de medewerker, en zet bij de akte de eigendom automatisch over naar de koper op de juiste datum (zodat kostenverdeling en provisies vanzelf volgen). Voeg in de demodata een lopende verkoop toe in Hof ter Beuken. Schrijf unittests voor de bedragen in het antwoord en de eigendomsoverdracht. Gebruik plan mode.

## 10. Invordering van achterstallen

> Bouw een invorderingsflow voor openstaande provisies en afrekeningen, over alle VME's heen: een overzicht van achterstallen per eigenaar en per VME met ouderdom (30/60/90 dagen), en drie niveaus (vriendelijke herinnering, aanmaning, ingebrekestelling) met Nederlandse sjablonen, de gestructureerde mededeling en het openstaande saldo. Bereken nalatigheidsinteresten en een forfaitaire schadevergoeding volgens het reglement van mede-eigendom (instelbaar per VME, `# LEGAL-CHECK:` voor de wettelijke grenzen) en boek ze op de eigenaar. Niets wordt automatisch verstuurd: de medewerker keurt per niveau goed, en een dossier kan doorgestuurd worden naar een advocaat of deurwaarder met een PDF-overzicht. Gebruik de achterstallen uit de demohistoriek (A3, B7). Schrijf unittests voor de ouderdom, de niveaus en de interesten. Gebruik plan mode.

## 11. Algemene vergadering: oproeping, stemming en notulen

> Bouw verder op de AV-planner uit stap 6c. Maak per AV een agenda met punten (elk met de vereiste meerderheid: volstrekte meerderheid, 2/3, 4/5 of eenparigheid, `# LEGAL-CHECK: art. 3.88 BW`), en verstuur de oproeping binnen de wettelijke termijn (`# LEGAL-CHECK: art. 3.87 BW`) als concept per eigenaar, met de agenda, de jaarafrekening en een volmachtformulier. Registreer op de vergadering de aanwezigen en volmachten (met de wettelijke grens op het aantal volmachten per mandataris), controleer het quorum op quotiteiten en aantal eigenaars, en laat per punt stemmen in quotiteiten met automatische uitkomst. Genereer de notulen als PDF, houd het register van beslissingen bij, en maak voor elke beslissing een opvolgtaak (bv. "offertes vragen voor dakwerken"). Gebruik een fictieve AV van Residentie Linde in de demodata. Schrijf unittests voor quorum, meerderheden en volmachtgrenzen. Gebruik plan mode.

## 12. Bankafschriften inlezen en betalingen koppelen

> Lees bankafschriften in (CODA, het Belgische formaat, en als alternatief CAMT.053) per VME en per fondsrekening, en koppel betalingen automatisch aan provisies en afrekeningen via de gestructureerde mededeling; betalingen zonder of met foute mededeling komen in een lijst om manueel te koppelen, met een voorstel op basis van bedrag en eigenaar. Leveranciersbetalingen worden aan de geboekte facturen gekoppeld. Maak fictieve CODA-bestanden voor de drie demo-VME's met een paar bewuste uitzonderingen (te laat, te weinig, foute mededeling). Gebruik wat Odoo Community al kan; zeg duidelijk wat een Enterprise-module of een externe bibliotheek zou vragen. Schrijf unittests voor de automatische en de voorgestelde koppelingen. Gebruik plan mode.

## 13. Migratie uit een ander syndicuspakket

> Bouw een importmodule om een bestaande portefeuille over te nemen uit een ander syndicuspakket (bijvoorbeeld Dobby), op basis van CSV- of Excel-exports. Ken je het exportformaat van het bronpakket niet, ontwerp dan een eigen, gedocumenteerd importformaat en maak een omzetter per bronpakket later. Importeer per VME: VME-gegevens, kavels, eigenaars met eigendomsdatums, sleutels met quotiteiten, leveranciers, en de openingsbalans op de overstapdatum (stand werk- en reservekapitaal, bank, openstaande saldi per eigenaar en per leverancier) als één openingsboeking; oudere jaren worden alleen als PDF-archief bewaard. Maak eerst een proefrun met een rapport van fouten en waarschuwingen (sleutels die niet optellen, eigenaars zonder kavel, ontbrekende bankrekeningen) zonder iets te schrijven, en daarna pas de echte import. Maak fictieve exportbestanden voor één VME met bewuste fouten. Leg in `docs/beslissingen.md` vast hoe de overstap verloopt (overstapdatum, parallel draaien van één VME gedurende een kwartaal, verwerkersovereenkomst voor echte gegevens). Schrijf unittests voor de proefrun en de openingsbalans. Gebruik plan mode.

## 14. Werken, offertes en schadegevallen

> Bouw een dossier per werk: beschrijving, beslissing van de AV (koppeling met stap 11), budget en financiering (werkkapitaal of reservekapitaal), offertes van meerdere aannemers met vergelijking (`# LEGAL-CHECK:` minimum aantal offertes boven het bedrag dat de AV vastlegde), gunning, opvolging van de uitvoering, oplevering en de facturen met hun verdeling. Bouw daarnaast een schadedossier per schadegeval: melding (bv. vanuit een mail van een eigenaar uit stap 7), betrokken kavels, verzekeringspolis, aangifte bij de verzekeraar, expertise, herstelling en uitbetaling, met termijnen en taken. Voeg een dakwerken-dossier en een waterschade toe aan de demodata. Schrijf unittests voor de financiering uit het reservekapitaal en de statussen. Gebruik plan mode.

## 15. Documenten en eigenaarsportaal

> Bouw per VME een documentenbeheer met vaste mappen (basisakte en reglement van mede-eigendom, notulen, jaarafrekeningen, verzekeringspolissen, keuringsverslagen, postinterventiedossier, contracten) en per kavel (eigendomsdocumenten, briefwisseling). Gebruik de portaalfunctie van Odoo Community zodat elke eigenaar na inloggen alleen zijn VME en zijn eigen kavels ziet: documenten, zijn afrekeningen en provisies met betaalstatus, en de agenda van de volgende AV (`# LEGAL-CHECK:` welke documenten de syndicus digitaal toegankelijk moet maken). Houd het register van eigenaars en hun contactgegevens actueel en laat eigenaars hun adres zelf wijzigen, met goedkeuring door de syndicus. Schrijf unittests voor de toegangsrechten (een eigenaar ziet nooit gegevens van een andere VME of kavel). Gebruik plan mode.

## 16. Raad van mede-eigendom en commissaris van de rekeningen

> Voeg per VME de leden van de raad van mede-eigendom en de commissaris van de rekeningen toe (`# LEGAL-CHECK: art. 3.90 en 3.91 BW`), met een portaaltoegang voor de commissaris om de boekhouding, facturen en bankafschriften van zijn VME in te kijken zonder iets te kunnen wijzigen, en een sjabloon voor zijn verslag aan de AV. Geef de raad een overzicht van de lopende dossiers (werken, schade, invordering). Schrijf unittests voor de leesrechten. Gebruik plan mode.

## 17. Verbruik en meterstanden

> Werk de sleutels "op verbruik" uit: per kavel tellers (water, verwarming via kostenverdelers, elektriciteit gemene delen) met meterstanden per periode, import van een CSV van een meteropnamebedrijf, en het verdelen van een factuur volgens het werkelijke verbruik in de kostperiode (met een vast deel volgens quotiteiten en een variabel deel volgens verbruik, instelbaar per VME). Maak fictieve meterstanden voor de verwarming van Hof ter Beuken. Schrijf unittests voor de verdeling vast/variabel en ontbrekende meterstanden. Gebruik plan mode.

## 18. Personeel en contracten

> Voeg per VME een overzicht van de lopende contracten toe (onderhoud, schoonmaak, verzekering, energie, lift, conciërge) met looptijd, opzegtermijn en jaarlijkse evaluatie (`# LEGAL-CHECK:` evaluatieplicht van de syndicus), met een taak vóór elke opzegtermijn. Voor een VME met eigen personeel (conciërge) volstaat in het prototype het boeken van de loonkosten uit een extern sociaal secretariaat via de verdeelregels. Schrijf unittests voor de opzegtermijnen. Gebruik plan mode.

## 19. Aanvragen van bewoners: sleutels, badges en andere vaste procedures

> Bouw een intake voor aanvragen van eigenaars en huurders (via mail uit stap 7, het portaal uit stap 15 of manueel) met per aanvraagtype een vaste procedure. Eerste type: **een extra sleutel of badge** (veiligheidssleutel van de inkom, garagepoort, afstandsbediening). De aanvrager wordt herkend aan zijn e-mailadres. Een gekende eigenaar van de kavel is meteen geverifieerd. Een huurder of onbekende moet bewijs leveren: een eigendomsbewijs, of voor een huurder de schriftelijke toestemming van de eigenaar en het huurcontract. De aanvraag vraagt dat bewijs automatisch op en wacht erop, met een herinnering na 7 dagen. Na verificatie gaat de bestelling naar de slotenmaker van de VME (vastgelegd in een leveranciersrol per VME, zoals bij de keuringen). Met het sleutelcertificaat erbij; de syndicus is de enige die veiligheidssleutels mag bestellen. De kost wordt privé aangerekend aan de eigenaar van de kavel, niet verdeeld over de VME. Houd per kavel een register bij van de uitgereikte sleutels en badges (nummer, datum, aan wie), en toon dat register bij de akte in het verkoopdossier van stap 9. Andere aanvraagtypes met dezelfde motor, elk met een eigen checklist:
> - verlies of diefstal van een badge (badge blokkeren)
> - verhuis (lift reserveren, liftbescherming, borg, naambordje en brievenbus aanpassen)
> - een nieuwe huurder melden (contactgegevens, reglement van orde bezorgen; `# LEGAL-CHECK: art. 3.93 BW`)
> - toestemming voor werken aan een privatief die gemene delen raken (buitenunit airco, ramen, zonnepanelen, laadpaal), met advies van de raad of een punt op de volgende AV
> - een defect of schade (doorsturen naar het schadedossier van stap 14)
> - een document opvragen (notulen, reglement)
> - een klacht over overlast
>
> **Beslissing vooraf:** de regel "er wordt nooit automatisch iets verstuurd" staat in CLAUDE.md. Leg in `docs/beslissingen.md` vast of de bestelling aan de slotenmaker na verificatie automatisch mag vertrekken (per VME aan te zetten) of als concept klaarstaat voor één klik. Schrijf unittests voor de verificatie (eigenaar, huurder met en zonder toestemming, onbekende), de privé-aanrekening en het sleutelregister. Gebruik plan mode.

## 20. Betalingsverkeer: leveranciers betalen en provisies domiciliëren

> Bouw de uitgaande kant van het betalingsverkeer per VME en per fondsrekening:
> - **Betaalvoorstel:** te betalen leveranciersfacturen volgens vervaldag. Een factuur moet eerst goedgekeurd zijn door een medewerker en, boven een bedrag dat per VME instelbaar is, ook door een tweede persoon (bv. een lid van de raad uit stap 16).
> - **Betaalbatch** als SEPA-bestand (pain.001) om in de bank op te laden, met de betalingen in Odoo als "verstuurd" tot het bankafschrift uit stap 12 ze bevestigt.
> - **Domiciliëringen voor provisies:** SEPA-mandaten per eigenaar en een incassobestand (pain.008) per provisieoproep. Een mislukte incasso komt terug via het bankafschrift en gaat naar de invordering van stap 10.
>
> Gebruik wat Odoo Community kan (`account_batch_payment` en `account_sepa` zijn Enterprise) en schrijf de XML zelf, gevalideerd tegen het XSD-schema. Een rechtstreekse bankkoppeling (Swan, Ponto, Isabel) valt buiten het prototype: beschrijf in `docs/beslissingen.md` wat die zou vragen. Er wordt nooit automatisch iets naar een bank gestuurd. Schrijf unittests voor de goedkeuringsregel, het SEPA-bestand en de terugkoppeling via het afschrift. Gebruik plan mode.

## 21. PDF-facturen en documenten lezen met AI

> Veel leveranciers sturen nog een PDF zonder UBL. Breid de facturen per mail uit stap 7b uit: komt er een PDF zonder UBL binnen, dan leest een taalmodel (zoals in `ai/`) leverancier, btw-nummer, factuurnummer, datums, kostperiode, bedragen en IBAN. Het vult de conceptfactuur in, met per veld de zekerheid. De verdeelregels doen daarna hun werk. Een nieuwe leverancier of een ander IBAN dan het gekende is altijd een waarschuwing, nooit automatisch aanvaard (fraude met valse IBAN's). Gebruik dezelfde aanpak om binnenkomende documenten automatisch in de juiste map van stap 15 te zetten (keuringsverslag, polis, offerte). Werkt zonder API-sleutel met een mock, zoals stap 7. Maak fictieve PDF-facturen voor de demo. Schrijf unittests voor de veldcontrole en de IBAN-waarschuwing. Gebruik plan mode.

## 22. Gebouwkaart, budgetopvolging en portefeuille

> Maak per VME een gebouwkaart: één scherm met de kerngegevens, de stand van werk- en reservekapitaal (met het verloop over de jaren), het budget tegenover het werkelijke per rekening en per sleutel tot vandaag, de achterstallen, de lopende dossiers (werken, schade, verkoop, invordering), de keuringen die vervallen, en de contracten met een opzegtermijn. Maak daarnaast een portefeuilleoverzicht voor de syndicus: alle VME's in één lijst met signalen (reservefonds onder 5%, achterstallen boven een drempel, AV buiten de periode, vervallen keuring). Maak ook een leverancierskaart met contracten, keuringen, lopende werken, facturen en betaaltermijn. Gebruik standaard Odoo-views (list, kanban, graph, pivot) en geen Enterprise-dashboards. Schrijf unittests voor de budgetopvolging. Gebruik plan mode.

## 23. Centrale communicatie met eigenaars en huurders

> Bouw verzendingen per VME of per selectie (alle eigenaars, een blok, de huurders): e-mail, brief als PDF voor de post, en aangetekend. Het aangetekende stuk wordt in het prototype als PDF met een verzendregister aangemaakt. Beschrijf hoe een koppeling met een dienst voor elektronisch aangetekend verzenden zou werken (`# LEGAL-CHECK:` geldigheid van elektronisch aangetekend bij invordering en oproeping). Sms en pushberichten krijgen een provider-interface met een mock. Voorzie sjablonen (welkomstbrief voor een nieuwe eigenaar na de akte uit stap 9, mededeling werken, waterafsluiting) en bevragingen met antwoorden per eigenaar (bv. "interesse in laadpalen?"). Houd per eigenaar een communicatielog bij met alle verzendingen. Elke verzending is eerst een concept dat een medewerker bevestigt. Schrijf unittests voor de selectie van ontvangers (eigenaar op datum, huurders, voorkeur papier of e-mail). Gebruik plan mode.

## 24. Digitale en hybride algemene vergadering

> Breid stap 11 uit:
> - **Online deelnemen:** een link per AV, en de aanwezigheid via het portaal van stap 15.
> - **Elektronisch stemmen tijdens de vergadering:** per agendapunt opent de syndicus de stemming, en eigenaars stemmen in het portaal met hun quotiteiten.
> - **Schriftelijke stemming vooraf**, waar de wet dat toelaat (`# LEGAL-CHECK: art. 3.87 BW` over schriftelijke besluitvorming en deelname op afstand).
> - **Elektronisch ondertekenen van de notulen** door voorzitter, secretaris en aanwezigen. Odoo Sign is Enterprise, dus bouw een eenvoudige ondertekening via het portaal met een auditspoor: wie, wanneer, IP en hash van de PDF.
>
> Schrijf unittests voor de stemrechten online (geen dubbele stem met volmacht, sluiten van de stemming) en voor het auditspoor. Gebruik plan mode.

## 25. Rentmeester: huurcontracten, indexering en afrekening aan huurders

> Voeg het beheer voor eigenaars die verhuren toe (de rol rentmeester), los van de VME-boekhouding:
> - **Huurcontract:** pand of kavel, verhuurder, huurders, begin, duur, huur en lasten, huurwaarborg, gewest (de huurwetgeving verschilt per gewest).
> - **Maandelijkse huurfacturen.**
> - **Jaarlijkse indexering** volgens de gezondheidsindex, met de formule en uitzonderingen per gewest en de indexatiebrief als concept (`# LEGAL-CHECK:` indexeringsregels per gewest, bv. de beperking volgens het EPC). Neem de indexcijfers op als tabel die een beheerder bijwerkt.
> - **Afrekening van lasten aan de huurder:** uit de jaarafrekening van de eigenaar (stap 6) het deel dat de huurder draagt, per rubriek instelbaar (bv. schoonmaak en lift wel, groot onderhoud niet).
> - **Opzeggingen en einde huur**, met een taak vóór de termijn.
>
> Fictieve demo: twee verhuurde appartementen in Residentie Linde en één in Hof ter Beuken. Een bpost-koppeling voor brieven valt buiten het prototype (zie stap 23). Schrijf unittests voor de indexering per gewest en de afrekening aan de huurder. Gebruik plan mode.

