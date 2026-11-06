# Offertes voor werken vergelijken met AI

Bij een werkdossier (`vme.works`, zie [werken-schade.md](werken-schade.md)) leest een taalmodel twee tot vier offerte-PDF's en maakt één vergelijkingstabel. Het lezen gebeurt in het losse script `ai/offertes.py`, zoals bij de PDF-facturen ([pdf-ai-lezen.md](pdf-ai-lezen.md)); de tabel, de controles, de goedkeuring en de PDF zitten in Odoo (`models/vme_works_comparison.py`). Waarom AI hier wel en de berekening niet: de invoer (vrije offerte-PDF's van verschillende aannemers) is ongestructureerd en het vergelijken kost een medewerker veel tijd. Wat daarna komt (rekencontrole, ontbrekende posten, btw-tarief) is deterministisch en zit in Odoo.

## Flow

```
werkdossier, tabblad Offertes: 2-4 offertes met een PDF (attachment_ids)
  └─ knop "Offertes vergelijken"  vme.works.action_compare_quotes
       └─ vme.works.comparison  state = to_read
            column_ids: één kolom per offerte (sequence 1-4, quote_id, attachment_id), volgorde = offertedatum, id

ai/offertes.py   (--offline zonder netwerk; zonder ANTHROPIC_API_KEY vanzelf offline)
  ├─ search_read vme.works.comparison [state = to_read], alle companies
  ├─ per kolom ir.attachment.datas -> [(naam, bytes)] in kolomvolgorde
  ├─ ClaudeQuoteComparer / OfflineQuoteComparer .compare(pdfs) -> {quotes, posts, summary}
  │    └─ clean_comparison: één item per offerte, gekende statussen, bedragen 0.00, pagina's binnen de PDF
  └─ vme.works.comparison.vme_ai_apply_comparison(payload, model)
       ├─ kolommen: aannemer, referentie, datum, excl. btw, btw-tarief, incl. btw
       ├─ rijen (vme.works.comparison.line) per rubriek: prijs, posten, voorwaarden, waarborg en verzekering, voorbehouden
       │    elke cel: value_n, page_n, status_n (ok / missing / attention / empty)
       ├─ state = draft, bericht en taak "Offertevergelijking nakijken" op het werkdossier
       └─ geeft {id, lines, attention} terug aan het script

syndicus: nakijken (paginalinks), aanpassen (tabblad Aanpassen, Offertes, samenvatting)
  └─ action_approve: state = approved, PDF (action_report_works_comparison) als bijlage op het werkdossier
       └─ vme.assembly.convocation._generate_documents: kopie van de PDF bij elke oproeping van assembly_id
```

Er wordt nooit iets verstuurd: goedkeuren maakt alleen de PDF. De oproepingen blijven concepten die een medewerker verstuurt (stap 11).

## Wat het taalmodel teruggeeft

`COMPARISON_SCHEMA` in `ai/offerte_reader.py`, met gestructureerde uitvoer bij Claude:

- `quotes`: per offerte, in kolomvolgorde, elk veld van `QUOTE_FIELDS` als `{value, page}`: `contractor`, `reference`, `date`, `amount_untaxed`, `vat_rate`, `amount_total`, `execution_period`, `validity`, `payment_terms`, `warranty`, `insurance`; plus `reservations: [{text, page}]`. `QUOTE_FIELDS` staat ook in het Odoo-model; een pytest-test bewaakt dat ze gelijk blijven.
- `posts`: per post een neutraal `label` en per offerte een item `{quote, status, amount, description, page}` met status `included` (in de prijs), `excluded` (de offerte zegt uitdrukkelijk "niet inbegrepen") of `absent` (niet vermeld). Het samenbrengen van posten die aannemers anders noemen (stelling, steigerwerken) is precies wat het taalmodel beter kan dan regels.
- `summary`: hoogstens vijf zinnen, feitelijk en zonder aanbeveling.

`page` is het paginanummer in die offerte (1 = eerste pagina). `clean_comparison` zet een pagina buiten de PDF (`page_count` telt de `/Type /Page`-objecten) op `null`, normaliseert bedragen (`45.800,00 EUR` → `45800.00`) en het btw-tarief (`6%` → `6`), en vult een ontbrekend item aan als `absent`. Odoo vertrouwt de structuur niet blind: `vme_ai_apply_comparison` weigert een vergelijking die niet `to_read` is of een ander aantal offertes terugkrijgt dan ze kolommen heeft.

## Van lezing naar tabel

`vme_ai_apply_comparison` bouwt de rijen deterministisch; de opmaak komt nooit van het taalmodel.

| Rubriek | Rijen | Status van een cel |
| --- | --- | --- |
| Prijs | Totaal excl. btw, Btw-tarief, Totaal incl. btw | `attention` voor een ander btw-tarief dan 6% als een andere offerte 6% rekent; `empty` zonder waarde |
| Posten | één rij per post | `ok` inbegrepen (bedrag of "Inbegrepen"); `missing` als de post niet inbegrepen of niet vermeld is terwijl een andere offerte hem wel meerekent; anders `empty` |
| Voorwaarden | Uitvoeringstermijn, Geldigheid, Betalingsvoorwaarden | `ok` of `empty` |
| Waarborg en verzekering | Waarborg, Verzekering | `ok` of `empty` |
| Voorbehouden | één rij, alle voorbehouden met hun pagina in de tekst | `attention` als er een is |

De tabel in het formulier en in de PDF komt uit één QWeb-sjabloon (`vme_belgie.works_comparison_table`). In het formulier (`table_html`, berekend, niet bewaard) linkt elk paginanummer naar `/web/content/<bijlage>#page=N`: de PDF-viewer van de browser opent op die pagina. In de PDF staan de paginanummers als tekst.

Vier vaste kolommen (`value_1..4`, `page_1..4`, `status_1..4`) in plaats van een celmodel: zo is de tabel in een gewone bewerkbare lijst aan te passen, en het maximum van vier offertes is een bewuste grens. Kolommen 3 en 4 verdwijnen in de lijst met `column_invisible="parent.column_count < 3"`.

## Controles (aandachtspunten)

`_check_points` rekent opnieuw bij elke wijziging (`attention` is een berekend veld op de kolommen, rijen en samenvatting):

- btw-tarieven verschillen tussen de offertes (`# LEGAL-CHECK:` KB nr. 20, tabel A, rubriek XXXI: 6% voor renovatie van een woning van minstens tien jaar oud);
- excl. btw × (1 + tarief) wijkt meer dan 1 euro af van het totaal incl. btw;
- het bedrag op `vme.works.quote` (wat de medewerker invulde) wijkt meer dan 1 euro af van het gelezen totaal incl. btw;
- een post ontbreekt in een offerte (status `missing`);
- een waarde zonder bronpagina;
- de samenvatting bevat woorden van een aanbeveling (`RECOMMENDATION_WORDS`: aanbevelen, aan te raden, advies, beste keuze, voorkeur, kies …).

De controles waarschuwen; ze blokkeren de goedkeuring niet. Goedkeuren vraagt wel een samenvatting.

## Statussen en vergrendeling

`to_read` (Wacht op AI) → `draft` (Concept) → `approved` (Goedgekeurd). **Opnieuw laten lezen** zet een concept terug op `to_read`; de volgende lezing vervangt rijen en samenvatting. **Terug naar concept** heft een goedkeuring op. Rijen van een goedgekeurde vergelijking kunnen niet gewijzigd worden (`_check_editable` in create, write en unlink). **Offertes vergelijken** hergebruikt een vergelijking die nog niet goedgekeurd is (kolommen opnieuw opgebouwd); na een goedkeuring start het een nieuwe.

## De lezers

- **`ClaudeQuoteComparer`**: één `client.beta.messages.create` met alle PDF's, telkens voorafgegaan door een tekstblok "Offerte n: bestandsnaam", model `claude-opus-5-5` (`classifier.MODEL`), effort `medium`, `COMPARISON_SCHEMA`, server-side fallback zoals stap 7. `refusal` → `RefusalError`, `max_tokens` → `RuntimeError`. De prompt zegt dat de PDF's gegevens zijn en geen opdrachten (een aannemer kan tekst in zijn offerte zetten die het model wil sturen).
- **`OfflineQuoteComparer`**: vaste regels op de tekst van de demo-offertes (`pdf_text.extract_pages`, per pagina): genummerde posten met een bedrag op de volgende regel, "Niet inbegrepen: …", totalen, gelabelde voorwaarden met vervolgregels, "Voorbehoud: …". Posten worden herkend met sleutelwoorden (`OFFLINE_POSTS`), de samenvatting komt uit `neutral_summary` (alleen feiten). Leest alleen de eigen demo-PDF's; een echte offerte of scan heeft Claude nodig.

## Demo-offertes

`ai/tools/maak_demo_offertes.py` maakt drie PDF's in `addons/vme_belgie/demo_data/offertes/`, met `pdf_text.write_pdf_pages` (nieuw: meerdere pagina's; één pagina geeft byte voor byte dezelfde PDF als vroeger, zodat de facturen van stap 21 niet veranderen). De demodata (`_load_demo_facade_works` in `demo_data/vme_demo_works.py`) maakt het werkdossier **Gevelrenovatie voor- en achtergevel** in Residentie Linde (status Offertes, nog geen vergelijking) met de drie offertes en hun PDF. De bewuste verschillen staan in de docstring van de generator; het bedrag van Bouwonderneming Denkbeeld staat in het werkdossier zonder btw (44.000 in plaats van 53.240), zodat ook de controle tegen het werkdossier iets toont.

## Tests

- Odoo: `tests/test_works_comparison.py` (vragen met 2-4 PDF's, tabel en pagina's, statussen, aandachtspunten inclusief aanbeveling en rekenfout, maar één keer lezen, goedkeuren met PDF en vergrendeling, niets naar aannemers of eigenaars, PDF bij de oproeping) en `test_demo_data.test_demo_facade_quotes_linde`.
- pytest: `ai/tests/test_offertes.py` (meerpagina-PDF, demo-PDF's actueel en rekenkundig juist, codes en partners gelijk aan de module, offline lezing per veld en pagina, posten en ontbrekende posten, neutrale samenvatting, `clean_comparison`, Claude-verzoek met nep-client, `run()` met een nep-Odoo, `main()` zonder sleutel).

## Uitbreidingen

- Het lezen starten vanuit Odoo (een cron of een knop die een wachtrij aanspreekt) in plaats van een script: het model en de API-sleutel blijven dan buiten Odoo; Odoo hoeft alleen de status `to_read` te zetten, wat het nu al doet.
- Posten koppelen aan een lastenboek per werkdossier, zodat de AI posten op vaste labels zet in plaats van ze zelf samen te brengen.
- Franse offertes: de prompt vraagt Nederlandse labels; voor een Franstalige VME de taal van de VME meegeven.
