# AI-assistent voor mails van eigenaars

Leest de mails in `inbox/`, koppelt elke mail aan de juiste VME en kavel in Odoo, bepaalt het onderwerp en zet een voorgesteld antwoord in het Nederlands als taak (activiteit) op de VME. **Er wordt nooit iets automatisch verstuurd**: een medewerker kijkt het voorstel na en verstuurt het zelf.

Hoe medewerkers de voorstellen behandelen: `docs/kb/ai-voorstellen-mails.md`. Architectuur: `docs/dev/ai-assistent.md`.

## Installatie

Python 3.10 of nieuwer.

```bash
cd ai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # en vul in
```

`.env` staat in `.gitignore`. Zet er nooit een echte sleutel in een ander bestand.

| Variabele | Betekenis |
| --- | --- |
| `ANTHROPIC_API_KEY` | API-sleutel voor Claude. Niet nodig met `--mock`. |
| `ODOO_URL`, `ODOO_DB` | Odoo en database, standaard `http://localhost:8069` en `vme_demo`. |
| `ODOO_USER`, `ODOO_PASSWORD` | Gebruiker die alle VME-companies ziet; wachtwoord of API-sleutel. |
| `ODOO_ACTIVITY_USER_ID` | Optioneel: wie de taken krijgt (standaard de gebruiker hierboven). |

Odoo heeft de module `vme_belgie` met demodata nodig (zie `CLAUDE.md`).

## Gebruik

```bash
.venv/bin/python assistant.py --mock --dry-run   # zonder taalmodel, niets schrijven: toont de voorstellen
.venv/bin/python assistant.py --mock             # zonder taalmodel, zet taken in Odoo
.venv/bin/python assistant.py                    # met Claude (claude-opus-5-5), zet taken in Odoo
```

| Optie | Effect |
| --- | --- |
| `--mock` | Regels in plaats van een taalmodel: koppelt op afzenderadres, gebouwnaam en kavelnummer, kiest het onderwerp op sleutelwoorden en gebruikt vaste antwoordsjablonen. |
| `--dry-run` | Toont koppeling en antwoord, schrijft niets naar Odoo. |
| `--force` | Maakt ook een taak voor mails die er al een hebben. |
| `--inbox MAP` | Andere map met mails. |

Een mail die al een taak heeft (herkend aan de `Message-ID`, of de bestandsnaam), wordt overgeslagen. Een mail die bij geen enkele VME past, krijgt geen taak; het script meldt dat ze met de hand behandeld moet worden.

## Mails in `inbox/`

Eén bestand per mail: een `.eml` (standaard e-mailformaat) of een `.txt` met optionele kopregels en dan, na een lege regel, de tekst:

```
Van: Eigenaar Beuken B23 <eigenaar.beuken.b23@example.com>
Onderwerp: Wanneer is de volgende algemene vergadering?
Datum: 2026-11-05 08:20
Message-ID: <av-b23-20261105@example.com>

Beste, ...
```

De acht mails zijn verzonnen en gebruiken de namen en adressen van de demodata (`@example.com`): een lek (Residentie Linde A4), een vraag over de afrekening (Hof ter Beuken B7), een verkoop en verhuis (Kaaihuis K4), een klacht over de lift (Residentie Linde A11, vanaf een onbekend privéadres), een vraag over de volgende AV (Hof ter Beuken B23), en drie aanvragen voor een badge of sleutel: van de eigenaar van Linde A4, van de huurder van Linde A6 zonder bewijs, en van de huurder van Beuken B12 met de toestemming van de eigenaar en het huurcontract als PDF-bijlage. Die drie worden geen taak maar een aanvraag in **VME > Aanvragen** (zie `docs/kb/aanvragen-sleutels-badges.md`).

## Tests

```bash
.venv/bin/pytest -q
```

Geen API-sleutel en geen Odoo nodig: het taalmodel en de Odoo-API worden nagebootst.

## Leveranciersfacturen per mail aanleveren (stap 7b)

`facturen_mailgate.py` levert de `.eml`-bestanden in `facturen_inbox/` aan Odoo zoals een inkomende mailserver dat doet (via `mail.thread.message_process`). Elke VME heeft een adres `facturen-<naam>@syndicus.example.com` op haar aankoopdagboek; Odoo maakt van elke mail een conceptfactuur in die VME en leest de UBL-bijlage in.

```bash
.venv/bin/python facturen_mailgate.py --dry-run   # toont per mail het adres en de bijlagen
.venv/bin/python facturen_mailgate.py             # levert aan en toont de conceptfacturen
```

De drie mails komen van de fictieve energieleverancier uit de demodata, met de UBL-facturen uit `addons/vme_belgie/demo_data/facturen/` als bijlage. Een tweede run maakt geen nieuwe facturen: Odoo herkent de Message-ID. Uitleg voor medewerkers: `docs/kb/facturen-per-mail.md`; architectuur: `docs/dev/facturen-per-mail.md`.
