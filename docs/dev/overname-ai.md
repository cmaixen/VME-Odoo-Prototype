# Overname van een gebouw: basisakte en notulen lezen met AI

Neemt een syndicus een gebouw over van een collega, dan krijgt hij papier: de basisakte, de notulen van de laatste AV's en een lijst met eigenaars. Deze stap laat een taalmodel die documenten lezen en zet het resultaat als **voorstel** in de bestaande overstapflow ([migratie.md](migratie.md)). Een medewerker kijkt elke regel na naast het fragment uit het document; de gewone proefrun en import doen de rest.

Gebruikersuitleg: [`docs/kb/overname-basisakte-ai.md`](../kb/overname-basisakte-ai.md).

## Overzicht

```
Odoo: vme.migration                 ai/overname.py                         Odoo
document_ids (PDF's) ──► ai_state = to_read ──► search_read + PDF's ──► Claude of mock ──► vme_ai_apply_takeover
                                                                                                │
                      proefrun/import ◄── _apply_proposal ◄── aanvaarde regels ◄── vme.migration.proposal
```

| Onderdeel | Bestand |
| --- | --- |
| Lezer (Claude en mock), schema, prompt, opschonen | `ai/overname_reader.py` |
| Script: te lezen overstappen ophalen, lezen, naar Odoo | `ai/overname.py` |
| PDF's met meerdere bladzijden, tabelrijen en een "scan" | `ai/pdf_text.py` (`write_pages`, `extract_pages`) |
| Demodocumenten en de verwachte mock-lezing | `ai/tools/maak_demo_overname.py` → `addons/vme_belgie/demo_data/migratie/residentie-wilg-documenten/` |
| Voorstelregels, lezing toepassen, voorstel → tabellen | `addons/vme_belgie/models/vme_migration_ai.py` |
| Nieuwe tabellen werken, procedures, mandaten; import | `addons/vme_belgie/models/vme_migration.py` |
| Scherm | `views/vme_migration_views.xml` (tabbladen en formulier `vme_migration_proposal_view_form`) |
| Tests | `ai/tests/test_overname.py`, `addons/vme_belgie/tests/test_migration_ai.py` |

## Waarom het lezen buiten Odoo draait

Zoals bij de PDF-facturen ([pdf-ai-lezen.md](pdf-ai-lezen.md)): de API-sleutel blijft in `ai/.env`, Odoo hoeft geen HTTP-aanroepen naar een taalmodel te doen, en alle controles die de database nodig hebben (bestaande VME's, KBO, IBAN, eigendommen) blijven in Odoo. Het script stuurt alleen een lezing; Odoo bewaart ze als voorstelregels en schrijft verder niets.

## De lezing

Eén API-aanroep per document (`ClaudeTakeoverReader`, model `claude-sonnet-5-5` (`model_for("takeover")`, zie `ai-modellen.md`)). De PDF gaat als document-blok mee, dus een scan leest Claude zelf; er is geen OCR in het platform. Gestructureerde uitvoer met `TAKEOVER_SCHEMA`:

| Sectie | Velden |
| --- | --- |
| `document_kind`, `meeting_date`, `summary` | basisakte, notulen of ander; datum van de AV |
| `vme` | `field` (naam, kbo, straat, postcode, gemeente), `value` |
| `lots` | `name`, `lot_type` (apartment, garage, storage, commercial, other), `floor` |
| `keys` | `name`, `key_type` (general, elevator, heating, consumption, other), `total`, `majority`, `shares[]` met `lot` en `value` |
| `works` | `description`, `amount`, `financing` (working, reserve), `key` |
| `procedures` | `description`, `counterparty`, `status` |
| `mandates` | `role` (chair, member, auditor), `person`, `date_start`, `date_end` |

Elk item heeft ook `page`, `fragment` (letterlijk, hoogstens 300 tekens), `confidence` (high, medium, low) en `note`. De codes zijn die van de selecties in `vme.migration.proposal`; `test_same_codes_as_the_odoo_module` bewaakt dat.

De prompt vraagt om aandelen cijfer per cijfer te lezen, een onleesbaar aandeel als `null` of met `low` te geven en **nooit** een aandeel terug te rekenen uit het totaal: dat zou precies de controle op de som uitschakelen. De PDF is gegevens, geen opdracht (prompt-injectie).

`clean_takeover()` maakt van elk antwoord dezelfde vorm: alle secties aanwezig, onbekende codes weg of op een veilige standaard, en een ontbrekende waarde krijgt `confidence = "low"`. Odoo doet in `_reading_items()` dezelfde verdediging nog eens.

### Offline-modus (`--mock`)

`MockTakeoverReader` leest de tekst van de demodocumenten met reguliere expressies en geeft altijd hetzelfde resultaat. Tabellen staan in de demo-PDF's als één tekstobject per rij (`("row", y, size, bold, cells)` in `write_pages`); `extract_pages` geeft de cellen terug met tabs ertussen. Voor de scan leest de mock de onzichtbare OCR-laag (tekst in rendermodus `3 Tr` onder het beeld), zoals een kantoorscanner die maakt. Een cel als `1O5` wordt na correctie van typische OCR-fouten `105` met `low`; `1?0` blijft leeg met `low` en een uitleg in `note`.

`voorstel-mock.json` is de lezing van de mock voor de vier demodocumenten. De pytest-test controleert dat de mock ze nog zo leest; de Odoo-tests passen exact die lezing toe. Zo testen beide kanten hetzelfde voorstel zonder dat Odoo de lezer moet kennen.

## Het voorstel in Odoo

`vme.migration` krijgt:

- `document_ids` (eigen relatietabel `vme_migration_document_rel`, los van de exportbestanden);
- `ai_state`: `none`, `to_read` (zodra er documenten zijn, en opnieuw bij elke wijziging ervan), `read`;
- `proposal_ids` en per soort een One2many met een domein (`proposal_share_ids` enz.) voor de tabbladen.

`vme.migration.proposal` (één regel per gelezen waarde):

| Veld | Betekenis |
| --- | --- |
| `kind` | vme, lot, share, works, procedure, mandate |
| waardevelden | `vme_field`/`value`, `lot_name`/`lot_type`/`floor`, `key_name`/`key_type`/`key_total`/`majority`/`value` (aandeel), `description`/`amount`/`financing`, `counterparty`/`status_text`, `role`/`person`/`date`/`date_end` |
| `attachment_id`, `page`, `fragment`, `confidence`, `note` | de bron |
| `origin` | `ai` of `manual` (een regel die de medewerker toevoegt, geldt meteen als aanvaard) |
| `state` | `proposed`, `accepted`, `rejected` |
| `edited` | een mens paste een waarde van een AI-regel aan (`write`) |
| `uncertain` | AI-regel, niet aangepast, en lage zekerheid of geen waarde |

Waarden zijn tekst (`Char`), ook aandelen en bedragen: de bestaande controle zet ze om met `parse_amount` en geeft dezelfde foutmeldingen als bij een CSV.

`vme_ai_apply_takeover(readings, model)` verwijdert eerst alle AI-regels (ook aanvaarde) en maakt het nieuwe voorstel; handmatige regels blijven. Een onzekere sleutel (totaal met `low`) maakt al haar aandelen onzeker.

`action_accept_certain()` aanvaardt alle voorgestelde regels die niet onzeker zijn, met een bericht in de chatter. Onzekere regels moeten één voor één. `action_open_source()` opent `/web/content/<id>#page=<blz>`.

## Van voorstel naar import

`_check()` roept na `_convert_files` het haakje `_apply_proposal(tables, messages)` aan (leeg in `vme_migration.py`, ingevuld in `vme_migration_ai.py`). Dat:

1. geeft een **fout** zolang de documenten niet gelezen zijn of er regels in `proposed` staan;
2. geeft een **waarschuwing** voor elke onzekere regel die zonder verbetering aanvaard werd;
3. zet de aanvaarde regels om naar tabellen in het gewone formaat, met `_line` = het volgnummer van de regel en als bron "Voorstel uit de documenten":
   - `vme`: de waarden uit de documenten **vullen en overschrijven** een `vme.csv` (die levert wat niet in een akte staat: overstapdatum en rekeningen). Een ander gevuld veld geeft een waarschuwing.
   - `kavels` en `sleutels`: de basisakte is de juridische bron, dus de tabel uit het voorstel **vervangt** een geëxporteerde tabel. Elk verschil (kavel of aandeel ontbreekt, ander type of aandeel) wordt een waarschuwing, plus een info dat het bestand niet gebruikt wordt.
   - `werken`, `procedures`, `mandaten`: worden toegevoegd aan wat een export eventueel al had.

Daarna loopt de gewone `_Checker`. De som van de aandelen, kavels zonder eigenaar, eigenaars zonder kavel: alles werkt zoals bij een export.

### Nieuwe tabellen in het formaat

Ze kunnen ook als CSV komen; zie [migratie.md](migratie.md#formaat).

| Tabel | Controle | Import |
| --- | --- | --- |
| `werken` | bedrag > 0, financiering werkkapitaal of reservekapitaal, sleutel bestaat (anders waarschuwing: algemene sleutel) | `vme.works` in `draft` met `budget`, `key_id`, `financing` en een beschrijving met de datum van de AV |
| `procedures` | omschrijving verplicht | taak (`mail.mail_activity_data_todo`) op de VME voor de gebruiker die importeert, en een lijst in `vme.association.legal_proceedings` (gaat mee naar de notaris, zie [verkoop-notaris.md](verkoop-notaris.md)) |
| `mandaten` | rol voorzitter, lid of commissaris; een raadslid moet op de begindatum eigenaar zijn volgens `eigendommen`; één voorzitter tegelijk | `vme.mandate`; de persoon is de eigenaar met dezelfde naam, anders een nieuw contact (alleen voor de commissaris) |

`sleutels` heeft een optionele kolom `meerderheid`. Is die ingevuld en geen vier vijfde (`is_four_fifths`: 4/5 of meer, ≥ 80%, unaniem, eenparig), dan volgt een waarschuwing (`LEGAL-CHECK: art. 3.88 §1, 2°, a) BW`).

De documenten zelf gaan mee naar het archief van de VME (`plan["archive"]`).

## Een mens beslist

- De lezing maakt alleen `vme.migration.proposal`-regels. De test `test_reading_makes_a_proposal_and_nothing_else` telt VME's, partners, kavels, sleutels, werken, mandaten, activiteiten en boekingen vóór en na.
- Zolang één regel niet aanvaard of geweigerd is, blokkeert de proefrun de import.
- Er is geen instelling om automatisch te aanvaarden. "Zekere regels aanvaarden" is een knop met bevestiging en slaat onzekere regels over.

## Demo en tests

```bash
cd ai
.venv/bin/python tools/maak_demo_overname.py   # PDF's en voorstel-mock.json opnieuw maken (scan: Pillow nodig)
.venv/bin/python overname.py --mock --bestand ../addons/vme_belgie/demo_data/migratie/residentie-wilg-documenten/basisakte-scan.pdf
.venv/bin/python overname.py --mock            # alle overstappen met ai_state = to_read
.venv/bin/pytest -q tests/test_overname.py
```

Het beeld van de scan maakt Pillow met het lettertype Helvetica van macOS; op een andere machine verschilt het beeld licht. De test vergelijkt daarom voor de scan alleen de OCR-laag, voor de andere PDF's de bytes.

In Odoo: `tests/test_migration_ai.py` (lezing, onzekere aandelen en de som, import met werken, mandaten, procedures en archief, geweigerde regels, 4/5, raadslid zonder kavel, verschil met een export, `vme.csv` aanvullen).

## Valkuilen

- Twee `Many2many` naar `ir.attachment` op hetzelfde model hebben elk een eigen `relation` nodig, anders delen ze de standaardtabel.
- `vme.mandate` controleert bij het aanmaken dat een raadslid eigenaar is (`_check_council_owner`). De proefrun doet dezelfde controle op het plan, anders zou de import pas in de transactie falen.
- Lijsten in een formulier met veel kolommen duwen de knoppen per regel buiten beeld. Status en knoppen staan daarom vóór het fragment; bron, soort en totaal van de sleutel en de opmerking zijn optionele kolommen.

- Geen `null` in `TAKEOVER_SCHEMA` (ook niet in de keuzelijsten): zie de valkuil over unietypes in `pdf-ai-lezen.md`.

## Uitbreiden

- Een andere soort document (reglement van interne orde, verslag van de raad): voeg een `document_kind` en secties toe in `overname_reader.py` en een `kind` in `PROPOSAL_KINDS`, met een tabel in `TABLES` en een `_check_*` in `_Checker`.
- Echte akten zijn vaak 30 tot 80 bladzijden. Dan loont het om eerst de bladzijden met de splitsing te laten aanwijzen en alleen die te laten lezen, of de PDF per hoofdstuk te sturen.
