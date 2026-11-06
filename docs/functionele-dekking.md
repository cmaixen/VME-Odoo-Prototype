# Functionele dekking

Vergelijking met de functies die een gangbaar Belgisch syndicus- en rentmeesterpakket aanbiedt (de functielijst van Dobby, november 2026). Per functie: wat het prototype al heeft, wat nu gebouwd wordt, en wat bewust later komt. Stapnummers verwijzen naar `PROMPTS.md`.

Legende: ✅ gebouwd · 🔨 wordt nu gebouwd · 📋 gepland · ➖ bewust later

| Functie | Wat erbij hoort | Status | Waar |
| --- | --- | --- | --- |
| Aankoopfacturen verwerken | UBL en Peppol, facturen per mail | ✅ | stap 4b, 7b |
| | PDF-facturen zonder UBL gelezen met AI, met waarschuwing bij een onbekend IBAN | ✅ | stap 21 |
| | Goedkeuren vóór betaling, met een tweede goedkeuring boven een drempel | ✅ | stap 20 |
| Boekhouding | Eén boekhouding per VME, Belgisch rekeningstelsel, boekingsregels (verdeelregels), opvragingen | ✅ | stap 1–6 |
| | Minimumrekeningstelsel VME (KB 12 juli 2012) nakijken | 📋 | LEGAL-CHECK |
| Betalingsverkeer | Bankafschriften inlezen (CODA/CAMT) en koppelen | ✅ | stap 12 |
| | Betaalbatches voor leveranciers (SEPA pain.001) | ✅ | stap 20 |
| | Domiciliëringen van provisies (SEPA pain.008) met mandaten en terugkoppeling | ✅ | stap 20 |
| | Rechtstreekse bankkoppeling (bv. Swan, Ponto, Isabel) | ➖ | na het prototype, vraagt een contract met de bank of aggregator |
| Kapitaalbeheer | Werk- en reservekapitaal apart, 5%-regel, werken uit het reservekapitaal | ✅ | stap 5, 14 |
| | Stand en verloop per VME | ✅ | stap 22 |
| | Live inzicht voor eigenaars in het portaal | ✅ | stap 15 (uitgebreid in stap 22) |
| Budgetbeheer | Budget en provisieberekening | ✅ | stap 5 |
| | Budgetopvolging (budget tegenover werkelijk, per rekening en sleutel) | ✅ | stap 22 |
| Inlichtingen inzake verkoop | Notarismodule met termijnen, kavelwissel bij de akte | ✅ | stap 9 |
| | Welkomstbrief voor de nieuwe eigenaar | ✅ | stap 23 |
| Afrekeningen | Jaarafrekening per eigenaar, ook op verbruik | ✅ | stap 6, 17 |
| | Commissaris van de rekeningen met leestoegang | ✅ | stap 16 |
| | Afrekening van lasten aan huurders | ✅ | stap 25 |
| Rappelopvolging | Overzicht, rappels in niveaus, interest, doorsturen | ✅ | stap 10 |
| | Aangetekend versturen (PDF met verzendregister) | ✅ | stap 23 |
| Indexatiebeheer | Huurindexering met uitzonderingen (gezondheidsindex, regels per gewest) | ✅ | stap 25 |
| | Indexatiebrieven | ✅ | stap 25 (de bpost-koppeling ➖) |
| Technisch beheer | Keuringen en liften | ✅ | stap 6b |
| | Contracten met opzegtermijnen | ✅ | stap 18 |
| | Technische documenten | ✅ | stap 15 |
| | Sleutels, badges en codes: register per kavel, bestelling bij de slotenmaker, blokkeren | ✅ | stap 19 |
| | Meterstanden en verbruik | ✅ | stap 17 |
| Taakbeheer | Taken en activiteiten met termijnen | ✅ | Odoo |
| | Meldingen en workflows per aanvraagtype, met verificatie van de aanvrager | ✅ | stap 19 |
| | Werken met offertes en schadegevallen met de verzekeraar | ✅ | stap 14 |
| Algemene vergadering | Planning in blokken | ✅ | stap 6c |
| | Agenda, oproeping, stemming, notulen en opvolging | ✅ | stap 11 |
| | Hybride en digitaal vergaderen, elektronisch stemmen en tekenen | 🔨 | stap 24 |
| Gebouwbeheer en eigendomsbeheer | Gebouwen, kavels, quotiteiten, eigenaars | ✅ | stap 2 |
| | Gebouwkaart met de financiële toestand en een overzicht van de portefeuille | ✅ | stap 22 |
| | Raad van mede-eigendom met overzicht van de lopende dossiers | ✅ | stap 16 |
| Beheer mede-eigenaars en huurders | Eigenaars met historiek en register | ✅ | stap 2, 15 |
| | Profiel in het portaal, adreswijziging met goedkeuring | ✅ | stap 15 |
| | Huurders als contacten per kavel, gekoppeld aan hun huurcontract | ✅ | stap 19, 25 |
| Leveranciersbeheer | Leveranciers, verdeelregels, facturen, contracten | ✅ | stap 4b, 18 |
| | Leverancierskaart met contracten, keuringen, lopende werken en facturen | ✅ | stap 22 |
| Documentbeheer | Mappen per VME en kavel, delen of niet delen, acties op meerdere documenten | ✅ | stap 15 |
| | Automatisch ordenen met AI | ✅ | stap 21 (soort en VME) met de mappen van stap 15 |
| Huurcontractbeheer | Huurcontracten, huurders, waarborg, maandelijkse huur, opzeg en einde huur | ✅ | stap 25 |
| | Doorstorting aan de verhuurder en ereloon van de rentmeester | 📋 | na stap 25 |
| Centraal communicatiebeheer | Brieven, e-mail en aangetekend per VME, blok of kavel, met voorkeur papier of e-mail | ✅ | stap 23 |
| | Sms, push en elektronisch aangetekend | ✅ | stap 23, provider-interface met een simulatie; een echte dienst ➖ vraagt een contract |
| | Sjablonen, updates, bevragingen met antwoorden, communicatielog per eigenaar | ✅ | stap 23 |
| | Huurders als ontvangers | ✅ | stap 23 met de huurders van stap 19 en 25 |
| Communicatie in twee richtingen | Mails van eigenaars gekoppeld met een voorgesteld antwoord (AI) | ✅ | stap 7 |
| | Aanvragen per mail als vaste procedure (AI) | ✅ | stap 19 |
| | Aanvragen en antwoorden op bevragingen via het portaal | 📋 | koppelplaatsen in stap 19 en 23 bestaan; aansluiten op het portaal van stap 15 |

## Waar het prototype verder gaat

- AI-assistent die mails van eigenaars aan VME en kavel koppelt en een antwoord voorstelt (stap 7).
- AV-planner die het hele AV-seizoen in blokken plant met de wettelijke periodes en oproepingstermijnen (stap 6c).
- Kosten per dag verdeeld bij een verkoop, met de kostperiode uit de Peppol-factuur (stap 4b).
- Een mail "ik wil een extra badge" wordt een aanvraag die de aanvrager herkent, het juiste bewijs opvraagt, de bestelling bij de slotenmaker klaarzet en de kost privé aanrekent; het sleutelregister volgt de eigendom tot in de akte (stap 19).
- Portefeuille met signalen over alle VME's (reservefonds onder 5%, achterstallen, AV buiten de periode, vervallen keuring), live berekend (stap 22).
- Alles op Odoo Community, zonder licentiekosten per gebruiker.
