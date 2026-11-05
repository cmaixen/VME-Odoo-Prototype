# Ontwikkelaarsdocumentatie

Interne documentatie voor wie aan de module `vme_belgie` werkt. De gebruikersdocumentatie staat in [`docs/kb/`](../kb/README.md), de ontwerpkeuzes in twee zinnen per keuze in [`docs/beslissingen.md`](../beslissingen.md).

| Document | Inhoud |
| --- | --- |
| [architectuur.md](architectuur.md) | Eén module op Odoo 19 Community, één company per VME, mappen en bestanden |
| [datamodel.md](datamodel.md) | Modellen, velden en relaties, met een diagram |
| [rekenregels.md](rekenregels.md) | Verdeling van kosten, afronding, provisies, jaarafrekening, 5%-regel |
| [odoo-uitbreidingen.md](odoo-uitbreidingen.md) | Welke Odoo-methodes we overschrijven en waarom |
| [valkuilen.md](valkuilen.md) | Wat misliep en hoe we het oplosten, plus bekende problemen |
| [omgeving-tests-demo.md](omgeving-tests-demo.md) | Docker, tests, demodata, een tweede demo naast de eerste, schermafbeeldingen |
| [keuringen.md](keuringen.md) | Installaties, keuringsverslagen, opmerkingen, cron en factuurkoppeling (stap 6b) |
| [av-planner.md](av-planner.md) | AV-periodes, blokken en de planner (stap 6c) |
| [algemene-vergadering.md](algemene-vergadering.md) | Agenda, oproeping, quorum, stemming en notulen (stap 11) |
| [werken-schade.md](werken-schade.md) | Werkdossiers, offertes, financiering uit het reservekapitaal, schadedossiers en polissen (stap 14) |
| [verkoop-notaris.md](verkoop-notaris.md) | Verkoopdossier, antwoord aan de notaris en overdracht bij de akte (stap 9) |
| [invordering.md](invordering.md) | Achterstallen, ouderdom, herinneringen in drie niveaus, interest en schadevergoeding, doorsturen (stap 10) |
| [bankafschriften.md](bankafschriften.md) | CODA en CAMT.053 inlezen, betalingen koppelen, wat Community niet kan (stap 12) |
| [facturen-per-mail.md](facturen-per-mail.md) | Mailalias per VME op het aankoopdagboek (stap 7b) |
| [ai-assistent.md](ai-assistent.md) | Het losse script in `ai/` voor mails van eigenaars (stap 7) |
| [migratie.md](migratie.md) | Overstap uit een ander pakket: importformaat, proefrun, openingsboeking, omzetters (stap 13) |
| [legal-checks.md](legal-checks.md) | Alle `LEGAL-CHECK`-punten uit de code (gegenereerd) |

Documentatie hoort bij elke stap, in hetzelfde commit als de code (zie `CLAUDE.md`). Na een wijziging aan een `# LEGAL-CHECK:`-commentaar draai je:

```bash
python3 tools/legal_checks.py
```
