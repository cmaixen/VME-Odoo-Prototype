# Ontwikkelaarsdocumentatie

Interne documentatie voor wie aan de module `vme_belgie` werkt. De gebruikersdocumentatie staat in [`docs/kb/`](../kb/README.md), de ontwerpkeuzes in twee zinnen per keuze in [`docs/beslissingen.md`](../beslissingen.md).

| Document | Inhoud |
| --- | --- |
| [architectuur.md](architectuur.md) | Eén module op Odoo 19 Community, één company per VME, mappen en bestanden |
| [datamodel.md](datamodel.md) | Modellen, velden en relaties, met een diagram |
| [rekenregels.md](rekenregels.md) | Verdeling van kosten, afronding, provisies, jaarafrekening, 5%-regel |
| [odoo-uitbreidingen.md](odoo-uitbreidingen.md) | Welke Odoo-methodes we overschrijven en waarom |
| [valkuilen.md](valkuilen.md) | Wat misliep en hoe we het oplosten, plus bekende problemen |
| [vertaling.md](vertaling.md) | Franse vertaling: `fr.po`, woordenlijst, rapporten in de taal van de ontvanger, nieuwe termen bijwerken |
| [omgeving-tests-demo.md](omgeving-tests-demo.md) | Docker, tests, demodata, een tweede demo naast de eerste, schermafbeeldingen |
| [keuringen.md](keuringen.md) | Installaties, keuringsverslagen, opmerkingen, cron en factuurkoppeling (stap 6b) |
| [av-planner.md](av-planner.md) | AV-periodes, blokken en de planner (stap 6c) |
| [algemene-vergadering.md](algemene-vergadering.md) | Agenda, oproeping, quorum, stemming en notulen (stap 11) |
| [digitale-av.md](digitale-av.md) | Buitengewone AV, online deelname, elektronisch en schriftelijk stemmen, ondertekening van de notulen met auditspoor (stap 24) |
| [werken-schade.md](werken-schade.md) | Werkdossiers, offertes, financiering uit het reservekapitaal, schadedossiers en polissen (stap 14) |
| [verkoop-notaris.md](verkoop-notaris.md) | Verkoopdossier, antwoord aan de notaris en overdracht bij de akte (stap 9) |
| [invordering.md](invordering.md) | Achterstallen, ouderdom, herinneringen in drie niveaus, interest en schadevergoeding, doorsturen (stap 10) |
| [bankafschriften.md](bankafschriften.md) | CODA en CAMT.053 inlezen, betalingen koppelen, wat Community niet kan (stap 12) |
| [betalingsverkeer.md](betalingsverkeer.md) | Goedkeuren vóór betaling, SEPA-overschrijvingen en -domiciliëringen, terugkoppeling via het afschrift (stap 20) |
| [communicatie.md](communicatie.md) | Verzendingen, selectie van ontvangers, communicatielog, verzendregister aangetekend, providers voor sms, push en elektronisch aangetekend, koppelplaats voor huurders (stap 23) |
| [facturen-per-mail.md](facturen-per-mail.md) | Mailalias per VME op het aankoopdagboek (stap 7b) |
| [pdf-ai-lezen.md](pdf-ai-lezen.md) | PDF-facturen zonder UBL en documenten lezen met AI, veld- en IBAN-controle, haakje voor de mappen van stap 15 (stap 21) |
| [offertes-vergelijken.md](offertes-vergelijken.md) | Offertes voor werken vergelijken met AI: tabel per post met bronpagina, deterministische controles, goedkeuring en PDF bij de oproeping van de AV |
| [ai-assistent.md](ai-assistent.md) | Het losse script in `ai/` voor mails van eigenaars (stap 7) |
| [portaal.md](portaal.md) | Documenten in vaste mappen, eigenaarsportaal, zichtbaarheidsregels, adreswijzigingen (stap 15); aanvragen en bevragingen in het portaal, ook voor huurders (stap 27) |
| [raad-commissaris.md](raad-commissaris.md) | Mandaten, leesrechten van de commissaris met record rules, overzicht voor de raad, verslagsjabloon (stap 16) |
| [verbruik.md](verbruik.md) | Tellers, meterstanden, CSV-import en verdeling vast/variabel op verbruik (stap 17) |
| [contracten.md](contracten.md) | Contracten, opzegtermijnen, jaarlijkse evaluatie, conciërge via het sociaal secretariaat (stap 18) |
| [aanvragen.md](aanvragen.md) | Aanvragen van bewoners: intake, verificatie, bestelling, sleutelregister, privé-aanrekening en koppelplaatsen (stap 19) |
| [gebouwkaart.md](gebouwkaart.md) | Gebouwkaart, budget per rekening en sleutel, budgetopvolging, kapitalen, signalen, portefeuille, leverancierskaart (stap 22) |
| [financiele-rapporten.md](financiele-rapporten.md) | Balans en resultatenrekening per VME volgens het minimumrekeningstelsel (KB 12 juli 2012), koppeling van de rekeningen, niet-aftrekbare btw (stap 26) |
| [jaarcyclus.md](jaarcyclus.md) | Jaarkalender per VME met vaste stappen en termijnen, cron die concepten en taken klaarzet, signaal in de portefeuille, haken voor afsluiting en mandaat van de syndicus (stap 28) |
| [werkbak.md](werkbak.md) | Mijn werk vandaag: dossierbeheerder per VME, transient lijst per medewerker uit taken, signalen en concepten, urgentie, ontdubbeling en bronnen (stap 29) |
| [migratie.md](migratie.md) | Overstap uit een ander pakket: importformaat, proefrun, openingsboeking, omzetters (stap 13) |
| [rentmeester.md](rentmeester.md) | Module `vme_rentmeester`: huurcontracten, huurfacturen, indexering met de indexstop per gewest, afrekening aan huurders (stap 25), doorstorting aan verhuurders en ereloon (stap 25b) |
| [syndicus.md](syndicus.md) | Het kantoor van de syndicus: beheerovereenkomst, indexering, prestaties uit de bronnen, ereloonfactuur en leveranciersfactuur in de VME, mandaat, herbenoeming en aanplakking |
| [rentmeester.md](rentmeester.md) | Module `vme_rentmeester`: huurcontracten, huurfacturen, indexering met de indexstop per gewest, afrekening aan huurders (stap 25) |
| [toegangsrechten.md](toegangsrechten.md) | Rollen, record rules per company, regels van de commissaris, sudo-knoppen, bevindingen van de review en wat een nieuw model nodig heeft |
| [website.md](website.md) | Module `vme_website`: productwebsite, knop Inloggen met landing per type gebruiker, demo-aanvraag als lead zonder mail (stap 27) |
| [code-review.md](code-review.md) | Code review van main (november 2026): bevindingen op ernst, wat hersteld is en wat als voorstel openstaat |
| [schaal.md](schaal.md) | Schaaldatabase met 200 fictieve VME's, meetscript, metingen vóór en na, portefeuille in één keer lezen, provisieoproepen op de achtergrond (stap 27) |
| [verzekeringen-attesten.md](verzekeringen-attesten.md) | Brandverzekering (vervaldag, opzegtermijn, verzekerde waarde, schadegevallen) en verplichte attesten per gebouw op `vme.document` en `vme.installation`, signalen, taken en notaris |
| [legal-checks.md](legal-checks.md) | Alle `LEGAL-CHECK`-punten uit de code (gegenereerd) |

Documentatie hoort bij elke stap, in hetzelfde commit als de code (zie `CLAUDE.md`). Na een wijziging aan een `# LEGAL-CHECK:`-commentaar draai je:

```bash
python3 tools/legal_checks.py
```
