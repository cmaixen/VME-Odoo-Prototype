# PDF-facturen en documenten lezen met AI (stap 21)

Een leveranciersfactuur die als PDF zonder UBL binnenkomt, wordt gelezen door een taalmodel in het losse script `ai/pdf_facturen.py`; Odoo controleert elk veld en vult de conceptfactuur in. Dezelfde aanpak klasseert binnenkomende documenten (`ai/documenten.py`). Zie `docs/beslissingen.md` voor waarom het lezen buiten Odoo draait.

## Flow voor facturen

```
mail naar facturen-<vme>@... of Upload
  └─ account.move._extend_with_attachments (stap 7b, standaard Odoo)
       geen decoder (geen UBL/Factur-X in de PDF), geen lijnen
       └─ vme_belgie (account_move_ai.py): vme_ai_state = "to_read" + bericht in de chatter

ai/pdf_facturen.py   (of facturen_mailgate.py --lees-pdf)
  ├─ search_read account.move [vme_ai_state = to_read, state = draft], alle companies
  ├─ ir.attachment (PDF, bij voorkeur message_main_attachment_id) -> bytes
  ├─ ClaudeInvoiceReader / MockInvoiceReader -> {veld: {value, confidence}}
  └─ account.move.vme_ai_apply_reading(reading, model)
       ├─ _vme_ai_clean     alleen gekende velden, tekst of None, geldige zekerheid
       ├─ _vme_ai_fill      leverancier (btw-nummer), ref, datums, kostperiode, één lijn met btw-tarief
       │                     └─ verdeelregels: _compute_vme_key_id / _compute_account_id (stap 4b)
       ├─ _vme_ai_check     één vme.bill.ai.check per veld: ok / warning / danger + uitleg
       └─ bericht in de chatter; geeft een samenvatting terug aan het script
```

`vme_ai_apply_reading` weigert een factuur die niet `to_read` is of al lijnen heeft: een tweede run of een factuur die een medewerker al invulde, wordt nooit overschreven.

## Velden

`READING_FIELDS` in `models/account_move_ai.py` en in `ai/pdf_reader.py` (een pytest-test bewaakt dat ze gelijk blijven): `supplier_name`, `supplier_vat`, `customer_name`, `invoice_number`, `invoice_date`, `due_date`, `period_start`, `period_end`, `description`, `amount_untaxed`, `amount_tax`, `amount_total`, `currency`, `iban`. Elk veld heeft een waarde (tekst of `null`) en een zekerheid `high`/`medium`/`low`; de JSON-schema's dwingen dat af bij Claude.

Op `account.move`: `vme_ai_state`, `vme_ai_reading` (Json, de gelezen velden zoals ontvangen), `vme_ai_model`, `vme_ai_iban` (IBAN zoals gelezen), `vme_ai_check_ids`, `vme_ai_danger_count`/`vme_ai_warning_count` (berekend), `vme_ai_reviewed_by_id`/`vme_ai_reviewed_date`.

## Invullen

- **Leverancier** alleen op btw-nummer (genormaliseerd vergeleken met `res.partner.vat`, binnen de company of gedeeld). Staat er een btw-nummer op dat niemand heeft, dan wordt een partner die Odoo op het afzenderadres koos, weer leeggemaakt: het afzenderadres is makkelijk te vervalsen. Er wordt nooit een partner aangemaakt.
- **Btw**: één lijn met het bedrag excl. btw en de aankoopbelasting met het tarief `btw / excl. btw` (eerst de standaardaankoopbelasting van de company, anders de eerste passende). Geen passend tarief: één lijn met het totaal zonder btw, en een waarschuwing. De meeste VME's zijn niet btw-plichtig, zodat de btw toch kost is.
- **Vervaldatum** alleen als ze niet voor de factuurdatum ligt (dan zonder betalingstermijn); **kostperiode** alleen als begin en einde gelezen zijn en kloppen, anders de standaard (factuurdatum).

## Controles

| Veld | Waarschuwing (nakijken) | Gevaar |
| --- | --- | --- |
| elk verplicht veld | niet gelezen, of zekerheid laag | |
| btw-nummer | geen btw-nummer, partner op afzenderadres | controlegetal klopt niet; nieuwe leverancier |
| leverancier | naam verschilt van de gekende partner | geen leverancier gevonden |
| klant | niet gericht aan deze VME | |
| factuurnummer | zelfde nummer bij dezelfde leverancier (mogelijk dubbel) | |
| datums | geen datum, in de toekomst, vervaldag voor factuurdatum, halve of omgekeerde periode | |
| bedragen | excl. + btw ≠ totaal, totaal ≤ 0, geen btw-tarief, totaal in Odoo ≠ gelezen totaal | |
| munt | niet EUR | |
| IBAN | geen IBAN gelezen | ongeldig; onbekende leverancier; gekend maar niet bevestigd; ander dan de bevestigde rekening; leverancier zonder bevestigde rekening |

**IBAN** (`_vme_ai_check_iban`): alleen als het gelezen IBAN gelijk is aan een `res.partner.bank` van de (commerciële) leverancier mét `allow_out_payment` (in de interface "Vertrouwd"/"Betalen"), wordt het de `partner_bank_id`. In alle andere gevallen wordt `partner_bank_id` leeggemaakt, ook als de leverancier een andere bevestigde rekening heeft: wie betaalt, kiest bewust. Het gelezen IBAN blijft alleen in `vme_ai_iban` staan; er wordt nooit een `res.partner.bank` aangemaakt of bevestigd (bevestigen kan in Odoo alleen een gebruiker met de juiste rechten, nooit de systeemgebruiker).

**Boeken geblokkeerd**: `_post` weigert een AI-gelezen factuur met een gevaar zolang niemand op **Waarschuwingen nagekeken** klikte (`action_vme_ai_mark_reviewed`, met naam en tijd in de chatter). **Opnieuw controleren** (`action_vme_ai_recheck`) draait de controles opnieuw op de bewaarde lezing en de huidige factuur, bijvoorbeeld nadat de leverancier is aangemaakt of de nieuwe rekening bevestigd; het zet "nagekeken" terug uit.

## Lezers in `ai/pdf_reader.py`

- **`ClaudeInvoiceReader`**: één `client.beta.messages.create` per PDF, model `claude-haiku-5-5` (`model_for("invoice")`; documenten idem, zie `ai-modellen.md`), effort `medium`, de PDF als `document`-blok (base64) plus een korte instructie, gestructureerde uitvoer met `INVOICE_SCHEMA`; geen server-side fallback, want Haiku heeft er geen. `refusal` → `RefusalError`, het script meldt de factuur als manueel in te vullen.
- **`ClaudeDocumentClassifier`**: idem met `DOCUMENT_SCHEMA` (`association_id`, `document_type`, `confidence`, `summary`, `reason`); de systeemprompt bevat id, naam en adres van de VME's, met `cache_control`. `validate_document` gooit een onbekende VME-id weg.
- **Mocks**: `pdf_text.extract_text` haalt de tekst uit de eenvoudige demo-PDF's (Flate of ongecomprimeerd, `Tj`-operatoren) en reguliere expressies lezen de gelabelde regels ("Factuurnummer:", "Te betalen:", "IBAN ..."). Voor documenten sleutelwoorden plus naam of straat van het gebouw. Ze werken alleen op PDF's met tekst zoals de demobestanden; een scan leest de mock als "niets gevonden".

## Documenten en de plaats voor stap 15

`ai/documenten.py` leest `ai/documenten_inbox/*.pdf`, klasseert elk document en roept `vme.association.vme_receive_document(filename, datas_base64, document_type, confidence, reason, model)` aan (`models/vme_document_intake.py`):

1. bestaat er op die VME al een bijlage met dezelfde checksum, dan `{"duplicate": True}`;
2. anders een `ir.attachment` op `vme.association` met in `description` het soort en de zekerheid;
3. **`_vme_document_folder(attachment, document_type)`** → naam van de map, of `False`;
4. een bericht in de chatter van de VME met het document, het soort, de zekerheid en de plaats.

**Uitbreidingspunt voor stap 15 (documentbeheer).** Stap 15 overschrijft `_vme_document_folder` op `vme.association`: zoek de map van deze VME met code `DOCUMENT_TYPES[document_type][1]`, zet de bijlage erin (of maak er een document van in het model van stap 15) en geef de naam van de map terug. Meer is er niet nodig: het chatterbericht en het script tonen de map dan vanzelf.

| `document_type` | Label | Mapcode voor stap 15 |
| --- | --- | --- |
| `inspection_report` | Keuringsverslag | `inspection_reports` |
| `insurance_policy` | Verzekeringspolis | `insurance_policies` |
| `quote` | Offerte | geen map: hoort bij een werk (stap 14) |
| `minutes` | Notulen | `minutes` |
| `contract` | Contract | `contracts` |
| `deed` | Basisakte of reglement van mede-eigendom | `deed` |
| `annual_statement` | Jaarafrekening | `annual_statements` |
| `other` | Ander document | geen map |

De mapcodes zijn een voorstel; stap 15 mag ze aanpassen in `DOCUMENT_TYPES`, zolang de sleutels (de codes die het taalmodel teruggeeft) gelijk blijven aan `DOCUMENT_TYPES` in `ai/pdf_reader.py`. Documenten per kavel (eigendomsdocumenten, briefwisseling) classificeren we nog niet: daarvoor moet het model ook een kavel kiezen, zoals de mailassistent van stap 7.

## Demobestanden

`ai/tools/maak_demo_pdfs.py` maakt alle bestanden opnieuw (deterministisch; een pytest-test controleert dat de bestanden in git gelijk zijn aan wat het script maakt):

- `addons/vme_belgie/demo_data/facturen_pdf/`: drie PDF-facturen (lift Residentie Linde: alles in orde; energie Hof ter Beuken: ander IBAN; dakwerken Kaaihuis: nieuwe leverancier, 6% btw, geen kostperiode);
- `ai/facturen_pdf_inbox/`: dezelfde facturen als mail naar het factuuradres van de VME;
- `ai/documenten_inbox/`: keuringsverslag, brandpolis en offerte.

De demodata geeft de energie- en de liftleverancier een bevestigde rekening (`SUPPLIER_IBANS` in `demo_data/vme_demo_data.py`; die van de energieleverancier is ook het IBAN in haar UBL-facturen).

## Demo en testen

```bash
cd ai
.venv/bin/python facturen_mailgate.py --inbox facturen_pdf_inbox --lees-pdf --mock   # aanleveren en lezen
.venv/bin/python pdf_facturen.py --mock                                             # wat nog te lezen is
.venv/bin/python pdf_facturen.py --mock --bestand ../addons/vme_belgie/demo_data/facturen_pdf/dakgoot_kaaihuis_2026-10.pdf
.venv/bin/python documenten.py --mock
```

- Odoo: `addons/vme_belgie/tests/test_bill_ai_reading.py` — controlegetallen en parsers, invullen met sleutel/rekening/btw/IBAN en verdelen na boeken, één keer lezen, bedragen die niet kloppen, ongeldig btw-nummer, datums en lage zekerheid, andere klant en dubbel nummer, ander/onbevestigd/ongeldig IBAN (niets opgeslagen), nieuwe leverancier (niets aangemaakt, afzender genegeerd), boeken geblokkeerd tot nagekeken, opnieuw controleren na bevestigen, mail met PDF → `to_read`, documenten (één keer, soort onbekend → ander).
- Script: `ai/tests/test_pdf_reader.py` — tekstextractie, demobestanden actueel, zelfde codes als de module, mock op de drie facturen en documenten, Claude-verzoek (document-blok, schema, weigering, echte SDK achter een nagebootste HTTP-laag), `run()` met een nagebootste Odoo.

## Valkuilen

- `_extend_with_attachments` krijgt de bestanden als `files_data` met `import_file_type`; een PDF met ingebedde UBL (Factur-X) wordt door de standaarddecoder ingelezen en heeft dan lijnen, dus die wacht niet op de AI.
- Het IBAN in de waarschuwing toont Odoo met spaties (`acc_number`); vergelijken gebeurt op `sanitized_acc_number`.
- `allow_out_payment` kan in tests niet door de systeemgebruiker gezet worden: gebruik `with_user(base.user_admin)`.
- De mock is geen OCR: hij leest alleen de tekstlagen van de eigen demo-PDF's.
- Gestructureerde output van de API weigert een schema met meer dan 16 velden met een unietype (`["string", "null"]` of `anyOf`) en een `enum` met `null`. De schema's gebruiken daarom geen `null`: een lege tekst betekent "niet gevonden" en pagina 0 "onbekend"; het opschonen maakt er `None` van. `ai/tests/test_schemas.py` controleert die grenzen offline, want de gewone tests roepen de API niet aan.

## Naar productie

- Het script periodiek laten draaien (cron of systemd-timer) naast de mailserver, of Odoo na `to_read` een webhook laten sturen.
- Nakijken of de leverancier de PDF ook als UBL via Peppol kan sturen: dat is goedkoper en zekerder.
- Gegevensbescherming: de PDF gaat naar de API van Anthropic. Facturen van leveranciers bevatten zelden persoonsgegevens van eigenaars, documenten wel; dat hoort in de verwerkersovereenkomst.
