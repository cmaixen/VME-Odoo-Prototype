# Functionele dekking

Vergelijking met de functies die een gangbaar Belgisch syndicus- en rentmeesterpakket aanbiedt (de functielijst van Dobby, november 2026). Per functie: wat het prototype al heeft, wat in een geplande stap zit, en wat nog ontbreekt. Stapnummers verwijzen naar `PROMPTS.md`.

Legende: ✅ gebouwd · 🔨 wordt nu gebouwd · 📋 gepland · ➖ bewust later

| Functie | Wat erbij hoort | Status | Waar |
| --- | --- | --- | --- |
| Aankoopfacturen verwerken | UBL en Peppol | ✅ | stap 4b, 7b |
| | Facturen per mail | ✅ | stap 7b |
| | OCR van PDF-facturen zonder UBL | 📋 | stap 21 |
| | Goedkeuren vóór betaling | 📋 | stap 20 |
| Boekhouding | Eén boekhouding per VME, Belgisch rekeningstelsel, boekingsregels (verdeelregels), opvragingen | ✅ | stap 1–6 |
| | Minimumrekeningstelsel VME (KB 12 juli 2012) nakijken | 📋 | LEGAL-CHECK |
| Betalingsverkeer | Bankafschriften inlezen (CODA/CAMT) en koppelen | ✅ | stap 12 |
| | Betaalbatches voor leveranciers (SEPA) | 📋 | stap 20 |
| | Domiciliëringen van provisies | 📋 | stap 20 |
| | Rechtstreekse bankkoppeling (bv. Swan, Ponto, Isabel) | ➖ | na het prototype, vraagt een contract met de bank of aggregator |
| Kapitaalbeheer | Werk- en reservekapitaal apart, 5%-regel | ✅ | stap 5 |
| | Stand en verloop per VME | 📋 | stap 22 |
| | Live inzicht voor eigenaars in het portaal | 🔨 | stap 15 |
| Budgetbeheer | Budget en provisieberekening | ✅ | stap 5 |
| | Budgetopvolging (budget tegenover werkelijk, per rekening en sleutel) | 📋 | stap 22 |
| Inlichtingen inzake verkoop | Notarismodule met termijnen | ✅ | stap 9 |
| | Kavelwissel bij de akte | ✅ | stap 9 |
| | Welkomstcommunicatie voor de nieuwe eigenaar | 📋 | stap 23 |
| Afrekeningen | Jaarafrekening per eigenaar | ✅ | stap 6 |
| | Commissaris van de rekeningen | 🔨 | stap 16 |
| | Afrekening van lasten aan huurders | ✅ | stap 25 |
| Rappelopvolging | Overzicht, rappels in niveaus, interest, doorsturen | ✅ | stap 10 |
| | Aangetekend versturen | 📋 | stap 23 |
| Indexatiebeheer | Huurindexering met uitzonderingen (gezondheidsindex, indexstop per gewest) | ✅ | stap 25 |
| | Indexatiebrieven | ✅ | stap 25 (de bpost-koppeling ➖) |
| Technisch beheer | Keuringen en liften | ✅ | stap 6b |
| | Contracten | 🔨 | stap 18 |
| | Technische documenten | 🔨 | stap 15 |
| | Sleutels, badges en codes | 📋 | stap 19 |
| Taakbeheer | Taken en activiteiten met termijnen (Odoo) | ✅ | |
| | Meldingen en workflows per aanvraagtype | 📋 | stap 19 |
| | Schadegevallen | 🔨 | stap 14 |
| Algemene vergadering | Planning in blokken | ✅ | stap 6c |
| | Agenda, oproeping, stemming, notulen en opvolging | ✅ | stap 11 |
| | Hybride en digitaal vergaderen, elektronisch stemmen en tekenen | 📋 | stap 24 |
| Gebouwbeheer en eigendomsbeheer | Gebouwen, kavels, quotiteiten, eigenaars | ✅ | stap 2 |
| | Gebouwkaart met de financiële toestand en een overzicht van de portefeuille | 📋 | stap 22 |
| Beheer mede-eigenaars en huurders | Eigenaars met historiek | ✅ | stap 2 |
| | Profiel in het portaal | 🔨 | stap 15 |
| | Huurders als volwaardige contacten per kavel | ✅ | stap 25 (aanvragen van huurders: stap 19) |
| Leveranciersbeheer | Leveranciers, verdeelregels, facturen | ✅ | stap 4b |
| | Leverancierskaart met contracten, keuringen, lopende werken en facturen | 📋 | stap 22 |
| Documentbeheer | Mappen per VME en kavel, delen of niet delen | 🔨 | stap 15 |
| | Automatisch ordenen met AI | 📋 | stap 21 |
| | Acties op meerdere documenten tegelijk | 🔨 | stap 15 |
| Huurcontractbeheer | Huurcontracten opmaken, huurders, waarborg, huur | ✅ | stap 25 |
| | Maandelijkse huurfacturen en opvolging van opzeg en einde huur | ✅ | stap 25 |
| | Doorstorting aan de verhuurder en ereloon van de rentmeester | 📋 | na stap 25 |
| Centraal communicatiebeheer | Brieven, e-mail, sms, aangetekend, push | 📋 | stap 23 |
| | Bevragingen | 📋 | stap 23 |
| | Updates en documenten delen | 📋 | stap 23 |
| Communicatie in twee richtingen | Mails van eigenaars gekoppeld met een voorgesteld antwoord (AI) | ✅ | stap 7 |
| | Meldingen via het portaal | 📋 | stap 15 en 19 |

## Waar het prototype verder gaat

- AI-assistent die mails van eigenaars aan VME en kavel koppelt en een antwoord voorstelt (stap 7).
- AV-planner die het hele AV-seizoen in blokken plant met de wettelijke periodes en oproepingstermijnen (stap 6c).
- Kosten per dag verdeeld bij een verkoop, met de kostperiode uit de Peppol-factuur (stap 4b).
- Alles op Odoo Community, zonder licentiekosten per gebruiker.
