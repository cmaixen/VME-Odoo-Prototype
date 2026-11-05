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
| [legal-checks.md](legal-checks.md) | Alle `LEGAL-CHECK`-punten uit de code (gegenereerd) |

Documentatie hoort bij elke stap, in hetzelfde commit als de code (zie `CLAUDE.md`). Na een wijziging aan een `# LEGAL-CHECK:`-commentaar draai je:

```bash
python3 tools/legal_checks.py
```
