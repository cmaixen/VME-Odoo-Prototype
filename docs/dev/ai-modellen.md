# Welk taalmodel per AI-taak

Elke AI-taak in `ai/` gebruikt het goedkoopste Claude-model dat op de demodocumenten even goed deed als Claude Opus 5.5. De keuze staat in `MODELS` in `ai/classifier.py`; `model_for(task)` geeft het model van een taak.

| Taak | Script | Model | Waarom |
| --- | --- | --- | --- |
| Mails van eigenaars koppelen en een antwoord voorstellen | `assistant.py` | Claude Sonnet 5.5 | Haiku koos voor 2 van de 8 demomails het verkeerde onderwerp (een vraag over de afrekening werd "Andere vraag", een sleutelaanvraag "Algemene vergadering"). Sonnet koppelde alles zoals Opus, met even goede antwoorden. |
| PDF-facturen lezen | `pdf_facturen.py` | Claude Haiku 5.5 | Zelfde velden als Opus. Odoo controleert daarna elk veld (leverancier, IBAN tegen de bevestigde rekening, totalen). |
| Documenten klasseren | `documenten.py` | Claude Haiku 5.5 | Zelfde soort en VME als Opus voor de drie demodocumenten. |
| Offertes vergelijken | `offertes.py` | Claude Sonnet 5.5 | De bedragen en posten waren bij alle drie gelijk, maar de samenvatting van Haiku bevatte een verwarrende zin. Die samenvatting gaat bij de oproeping van de AV. |
| Basisakte en notulen lezen | `overname.py` | Claude Sonnet 5.5 | Op de slechte scan vlagde Haiku het onleesbare aandeel van A2, maar niet de "1O5" van B3. Sonnet vlagde beide, zoals Opus. |

Prijzen per miljoen tokens (in/uit, november 2026): Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0,10/$0,50. Sonnet halveert dus de kost van de mails, de offertes en de overname. Haiku maakt facturen en documenten ongeveer veertig keer goedkoper.

## Een ander model proberen

Met `VME_AI_MODEL` in `ai/.env` (of in de omgeving) gebruiken alle taken hetzelfde model, bijvoorbeeld om opnieuw te vergelijken:

```bash
VME_AI_MODEL=claude-haiku-5-5 .venv/bin/python assistant.py --dry-run
VME_AI_MODEL=claude-opus-5-5 .venv/bin/python overname.py --json --bestand PAD.pdf
```

De vergelijking hierboven is zo gemaakt: elk script met `--dry-run` of `--bestand`, met de drie modellen, op de demomails in `ai/inbox/`, de PDF's in `addons/vme_belgie/demo_data/facturen_pdf/` en `offertes/`, en de documenten van Residentie Wilg. Er werd niets naar Odoo geschreven.

## Valkuilen

- Haiku heeft geen terugval aan de kant van de API als een veiligheidsfilter weigert. `fallback_options(model)` stuurt de parameter `fallbacks` daarom alleen naar Sonnet en Opus. Een weigering bij Haiku wordt een `RefusalError`, zoals bij de andere modellen zonder geslaagde terugval.
- Acht mails en drie offertes zijn een kleine proefset. Komt er een pilootsyndicus met echte mails, vergelijk dan opnieuw op een grotere set voor je een model goedkoper zet.
- De mock en de offline-modus gebruiken geen model. Hun uitvoer zegt welk model het niet was.
