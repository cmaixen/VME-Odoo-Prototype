# Betalingsverkeer: goedkeuren, SEPA-bestanden en terugkoppeling (stap 20)

De uitgaande kant van het betalingsverkeer per VME en per fondsrekening: leveranciersfacturen goedkeuren, overschrijvingen (pain.001.001.09) en domiciliëringen (pain.008.001.08) als bestand, en de bevestiging of terugboeking via het rekeninguittreksel van stap 12. Er wordt nooit iets naar een bank gestuurd: de gebruiker downloadt het bestand en laadt het zelf op.

## Wat Odoo 19 Community kan, en wat niet

| Onderdeel | Community | Enterprise / extern | Wat wij doen |
| --- | --- | --- | --- |
| Betalingen (`account.payment`) | Ja, maar een geboekte betaling maakt de factuur meteen **Betaald**: de status `in_payment` bestaat alleen met `account_accountant` (`_get_invoice_in_payment_state()` geeft in Community `paid`) | Enterprise `account_accountant` | Geen `account.payment` bij het versturen: eigen batchregels met status *Verstuurd* |
| Batchbetalingen | Nee | Enterprise `account_batch_payment` | Eigen model `vme.payment.batch` |
| SEPA-overschrijving en -domiciliëring | Nee | Enterprise `account_sepa`, `account_sepa_direct_debit`; OCA `account_banking_sepa_*` | Eigen XML in `models/sepa_xml.py`, gevalideerd tegen de officiële XSD |
| Rekeningnummer bevestigen (`allow_out_payment`) | Ja, met een eigen recht en controle (`_user_can_trust()`) | | Gebruikt zoals het is, nooit omzeild |

We kopieerden niets uit Enterprise of OCA: de bestanden zijn geschreven vanuit de ISO 20022-berichtdefinities en de EPC-richtlijnen.

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `models/sepa_xml.py` | Zuivere Python met lxml: `build_credit_transfer`, `build_direct_debit`, `validate` (XSD), `creditor_identifier`, `iban_is_valid`, `sepa_text`/`sepa_id` (SEPA-tekenset) |
| `data/sepa/pain.001.001.09.xsd`, `pain.008.001.08.xsd` | De officiële schema's van iso20022.org, ongewijzigd (zie `data/sepa/README.md`) |
| `models/vme_payment.py` | Instellingen op `vme.association`, goedkeuring op `account.move`, `vme.sepa.mandate`, `vme.payment.batch(.line)`, knop **Domiciliëren** op `vme.provision.call` |
| `models/account_bank_statement_line.py` | `_vme_match_payment_batch()` en `_vme_return_direct_debit()`: terugkoppeling vóór de gewone koppeling van stap 12 |
| `models/bank_formats.py` | `Transaction.end_to_end_id` en `return_reason` uit CAMT.053, en `write_camt053()` voor tests en het demo-afschrift |
| `views/vme_payment_views.xml` | Menu **VME > Betalingen**, formulieren, tabblad **Betalingen** op de VME, knoppen op de factuur, nummering `BET/` en `DOM/` |
| `demo_data/vme_demo_payments.py` | `_load_demo_payments()` en `_load_demo_payment_statement()` |

## Goedkeuring

Velden op `account.move` (alleen `in_invoice` van een VME): `vme_approved_by_id`/`_date`, `vme_second_approved_by_id`/`_date`, en het opgeslagen, berekende `vme_approval_state` (`to_approve`, `first_approved`, `approved`).

- Tweede goedkeuring nodig als `amount_total >= vme.association.payment_approval_threshold` (btw inbegrepen; 0 = nooit).
- De tweede goedkeuring komt alleen van `payment_second_approver_id` (een `res.users` per VME) en nooit van wie de eerste gaf. Stap 16 (de raad van mede-eigendom) kan dat veld later vullen uit de leden van de raad; de regel zelf staat in `action_vme_approve()`.
- Na de eerste goedkeuring krijgt de tweede goedkeurder een to-do-activiteit; bij zijn goedkeuring wordt die afgevinkt.
- `button_draft()` wist de goedkeuring: een gewijzigde factuur moet opnieuw goedgekeurd worden.

## Betaalbatch

`vme.payment.batch`: `batch_type` (`transfer`/`direct_debit`), VME, `fund` (alleen overschrijvingen), `provision_call_id` (alleen domiciliëringen), `due_until`, `execution_date`, `state`:

```
draft (Concept) --SEPA-bestand maken--> generated (Bestand klaar) --Opgeladen in de bank--> sent (Verstuurd) --> done (Afgehandeld)
        \--Annuleren--> cancel           \--Terug naar concept--> draft
```

`vme.payment.batch.line`: een factuur, de begunstigde of eigenaar, de rekening, het mandaat, bedrag (`amount_residual` bij het voorstel), mededeling, `end_to_end_id` (`<batchnummer>-<volgnummer>`, gezet bij het maken van het bestand) en `state` (`draft`, `sent`, `paid`, `rejected`), plus de bankbeweging die bevestigt of terugboekt.

**Voorstel overschrijvingen** (`_transfer_proposal`): geboekte `in_invoice` van de company, `payment_state` `not_paid`/`partial`, vervaldag ≤ `due_until`, fonds van de factuur (`vme_fund`, leeg = werkkapitaal) = fonds van de batch, niet al in een actieve batch. Wat niet goedgekeurd is of geen bevestigde rekening heeft, komt met de reden in `proposal_note`.

**Voorstel domiciliëringen** (`_direct_debit_proposal`): open provisies van de oproep van eigenaars met een actief mandaat bij die VME.

**Bestand maken**: vlak vóór het bestand worden goedkeuring, `allow_out_payment` van de rekening van de VME en van elke leverancier, en de vooraankondiging (inningsdatum ≥ datum oproep + 14 dagen) opnieuw gecontroleerd. Daarna `validate()` tegen de XSD. Een domiciliëringsbestand krijgt één `PmtInf` per fondsrekening en per sequentietype (`FRST` bij de eerste inning op een mandaat, daarna `RCUR`; `first_collection_done` wordt gezet bij **Opgeladen in de bank**).

### Waarom geen `account.payment`

In Community maakt een geboekte betaling, afgeletterd met de factuur, die factuur meteen **Betaald**. Het afschrift zou dan nog alleen de rekening "uitstaande betalingen" afletteren. Stap 12 lettert bankregels rechtstreeks af met de facturen; door bij het versturen niets te boeken, blijft de factuur open tot de bank betaalt, en zie je *Verstuurd* op de batchregel en in het veld **Betaalopdracht** van de factuur. `_get_invoice_in_payment_state()` overschrijven kon niet: de demohistoriek en de tests registreren betalingen rechtstreeks op de bankdagboeken, die dan allemaal op `in_payment` zouden blijven staan.

## Terugkoppeling via het afschrift

`_vme_match()` (stap 12) roept per bankregel eerst `_vme_match_payment_batch()` op. `_vme_find_batch_line()` zoekt in de batchregels van de company (batch `generated`, `sent` of `done`):

1. op `vme_end_to_end_id` (uit `NtryDtls/TxDtls/Refs/EndToEndId` van CAMT.053, nieuw veld op de bankregel);
2. anders op bedrag en mededeling: de gestructureerde mededeling of de vrije mededeling van de batchregel in de mededeling van de bank (CODA heeft geen EndToEndId).

| Beweging | Batchregel | Gevolg |
| --- | --- | --- |
| Uitgaand | overschrijving `draft`/`sent` | `_vme_reconcile(factuur)`, regel `paid` |
| Inkomend | domiciliëring `draft`/`sent` | idem, `vme_days_late` = 0 (de syndicus koos de datum) |
| Uitgaand | domiciliëring `sent`/`paid` | `_vme_return_direct_debit()` |

Daarnaast markeert `_vme_reconcile()` een overschrijving als `paid` wanneer de gewone koppeling van stap 12 (referentie of leverancier) een factuur afletterde die in een actieve batch zit.

**Teruggekomen domiciliëring**: de afletterregel tussen de provisie en de tegenregel van de inning wordt verwijderd (`remove_move_reconcile()`), de terugboeking wordt met die tegenregel afgeletterd op de debiteurenrekening van de eigenaar. Beide bankregels zijn dan gekoppeld, de provisie staat weer open met haar eigen vervaldag, dus de SQL-view `vme.arrears` en de invordering (stap 10) zien ze vanzelf. De bankregel krijgt uitzondering `dd_returned` (staat in **Op te volgen betalingen**), de batchregel `rejected` met de reden (ISO-code, bv. `AM04`), en het invorderingsdossier van de eigenaar wordt aangemaakt of krijgt een notitie. Werd de inning zelf nog niet gekoppeld, dan blijft de terugboeking *Te koppelen* met een toelichting.

## Rechten

- Batches en batchregels: lezen voor `base.group_user`, schrijven voor `account.group_account_invoice`. Mandaten: `base.group_user` (geen verwijderen; intrekken).
- Goedkeuren: elke interne gebruiker met toegang tot de factuur; de tweede goedkeuring alleen de gebruiker op de VME.
- Rekeningnummers bevestigen blijft Odoo's eigen recht. De module zet `allow_out_payment` nergens, behalve in de demolader als de gebruiker het mag (`_user_can_trust()`), zoals de demodata van stap 3.

## Demo

Na de demodata en de demohistoriek (de demobankafschriften van stap 12 mogen ervoor of erna):

1. **VME > Configuratie > Demo betalingsverkeer laden** (`_load_demo_payments()`, als de ingelogde gebruiker): de gebruiker wordt tweede goedkeurder van de drie VME's, een demogebruiker "Medewerker Syndicus (demo)" keurt alle open leveranciersfacturen goed (9 van de 16 wachten daarna op de tweede goedkeuring), leveranciers krijgen bevestigde fictieve rekeningen (`fake_iban(2001..2004)`, dezelfde als in de demobankafschriften), vijf eigenaars krijgen een mandaat. De rekening van de energieleverancier uit de demodata blijft bewust onbevestigd.
2. Batches maken in het scherm.
3. **VME > Configuratie > Demo-afschrift voor betaalbatches** (`_load_demo_payment_statement()`): schrijft per fondsrekening een CAMT.053 met een beweging per regel van elke batch met een bestand (met EndToEndId), en laat de inning van **Eigenaar Beuken B7** twee dagen later terugkomen met `AM04`. Het beginsaldo is het eindsaldo van het laatste uittreksel van dat dagboek.

De trage test `TestAnnualStatementDemo.test_demo_payments` doorloopt dit scenario.

## Testen

`tests/test_payments.py`:

- `TestSepaXml`: pain.001 en pain.008 geldig tegen de XSD, gestructureerde mededeling als `SCOR`/`BBA`, FRST- en RCUR-blokken, een kapot bestand wordt door het schema geweigerd, ongeldige IBAN of ontbrekend mandaat, schuldeiseridentificatie (voorbeeld van de EPC), SEPA-tekenset, CAMT heen en terug met EndToEndId en terugboekreden.
- `TestPayments`: één goedkeuring onder het bedrag, tweede goedkeuring door de juiste en een andere persoon, bedrag 0 en ontbrekende goedkeurder, goedkeuring vervalt bij concept; voorstel (alleen goedgekeurd en vervallen, niet tweemaal), niet-bevestigde rekening (bij het voorstel en vlak voor het bestand); bevestiging via CAMT met EndToEndId en via CODA zonder; bestand maar één keer; domiciliëringsbestand per fonds met FRST; vooraankondiging; teruggekomen domiciliëring naar de invordering; mandaatregels.

## Valkuilen

- **Bedrijvenkiezer.** De demolader keurt goed als de demomedewerker; met de bedrijven die in de browser geselecteerd zijn (bv. "My Company", waar hij geen toegang toe heeft) gaf dat "Toegang tot ongeautoriseerde of ongeldige bedrijven". Zet `allowed_company_ids` expliciet bij `with_user()`.
- **Serveractie via een URL.** `/odoo/action-<xmlid>` van een serveractie voert ze niet uit in de browser; gebruik het menu.
- **Ruimte in de SEPA-tekenset.** Namen met accenten of `&` worden vereenvoudigd (`sepa_text`); identificaties (`MsgId`, `EndToEndId`, mandaat) mogen geen spaties of `//` bevatten (`sepa_id`).
