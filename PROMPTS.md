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

## 5. Provisieoproepen

> Maak een wizard "Provisieoproep" die voor een of meer VME's tegelijk per eigenaar een factuur maakt voor werkkapitaal en reservekapitaal, op basis van het jaarbudget en de algemene sleutel, met een Belgische gestructureerde mededeling. Voeg de 5%-regel voor het reservefonds toe als waarschuwing, met een `# LEGAL-CHECK:`-commentaar.

## 6. Jaarafrekening

> Maak een PDF-rapport "Jaarafrekening" per eigenaar: werkelijke kosten per sleutel, aandeel van de eigenaar, betaalde provisies en het saldo. Gebruik de demodata en controleer de cijfers met een unittest.

## 7. AI-assistent voor mails

> Bouw in `ai/` een Python-script volgens de architectuur in CLAUDE.md. Maak eerst vijf fictieve mails van eigenaars in `ai/inbox/` (een lek, een vraag over de afrekening, een verhuis, een klacht over de lift, een vraag over de volgende AV). Het script koppelt elke mail aan de juiste VME en kavel, bepaalt het onderwerp, stelt een antwoord voor en zet dat als activiteit op de VME in Odoo. Er wordt niets automatisch verstuurd. Lees de API-sleutel uit `ai/.env`.

## 8. Demoscenario

> Schrijf in `docs/demo.md` een demoscenario van 10 minuten voor een syndicus: van een binnenkomende factuur tot de jaarafrekening, en van een mail van een eigenaar tot een voorgesteld antwoord. Controleer dat elke stap werkt op een verse database met de demodata.
