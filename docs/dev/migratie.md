# Overstap uit een ander syndicuspakket (stap 13)

Een syndicus die overstapt, brengt een hele portefeuille mee. We kennen het exportformaat van de bronpakketten (Dobby en andere) nog niet. Daarom leest de import een **eigen, gedocumenteerd formaat**: CSV-bestanden of één Excel-bestand. Voor elk bronpakket komt later een omzetter naar dit formaat.

Code: `addons/vme_belgie/models/vme_migration.py`, scherm `views/vme_migration_views.xml`, tests `tests/test_migration.py`, voorbeeldbestanden `demo_data/migratie/`.

Een overname met de basisakte en de notulen in plaats van (of naast) een export: [overname-ai.md](overname-ai.md). Die levert de tabellen `vme`, `kavels`, `sleutels`, `werken`, `procedures` en `mandaten` als voorstel, via het haakje `_apply_proposal`.

## Werking

`vme.migration` is een gewoon (niet-transient) model, zodat elke overstap een spoor nalaat: de bestanden, het rapport, de nieuwe VME en de openingsboeking. Menu: **VME > Configuratie > Overstap uit ander pakket**, alleen voor beheerders (`base.group_system`).

1. **Bestanden opladen** in `attachment_ids` (widget `many2many_binary`, meerdere bestanden tegelijk).
2. **Proefrun** (`action_dry_run`): `_check()` leest de bestanden (`_read_files`), zet ze om (`_convert_files`) en controleert alles in `_Checker`. Die klasse leest de database (bestaande VME's, KBO-nummers, IBAN's, leveranciers op btw-nummer), maar **schrijft niets**. Het rapport komt in `report_html`, met `error_count` en `warning_count`. Status: `checked`.
3. **Importeren** (`action_import`): de knop verschijnt alleen na een proefrun zonder fouten. De import controleert opnieuw. Zijn er fouten (bijvoorbeeld omdat iemand intussen een VME met dezelfde naam aanmaakte), dan werkt hij alleen het rapport bij. Anders maakt `_import()` alles aan in één transactie. Faalt er iets, dan rolt het hele verzoek terug. Status: `done`.

Nieuwe bestanden opladen zet de status terug op `draft` (`write`). Een geïmporteerde overstap kan niet opnieuw.

## Formaat

Eén import is één VME. Toegestaan zijn:

- losse `.csv`-bestanden met de namen hieronder;
- een `.zip` met die bestanden (submappen mogen);
- één `.xlsx` met tabbladen met dezelfde namen (zonder `.csv`).

Elke `.pdf` en alles in een map `archief/` gaat naar het archief.

- **Scheidingsteken**: `;` of `,`, bepaald uit de kopregel.
- **Codering**: UTF-8 (met of zonder BOM), anders cp1252 (Excel onder Windows).
- **Datums**: `dd/mm/jjjj`, `jjjj-mm-dd`, `dd-mm-jjjj` of `dd.mm.jjjj`. In Excel ook een echte datumcel.
- **Bedragen en quotiteiten**: `1.234,56`, `1,234.56` of `1234.56`. In Excel ook een getalcel.
- **Kopregels**: kleine letters, in de volgorde naar keuze. Onbekende kolommen worden genegeerd.

Vetgedrukte kolommen zijn verplicht.

| Bestand | Kolommen | Opmerkingen |
| --- | --- | --- |
| `vme.csv` | **naam**, **kbo**, straat, postcode, gemeente, iban_werkkapitaal, iban_reservekapitaal, **overstapdatum** | Precies één rij. In Excel het KBO-nummer als tekst opmaken, anders vallen de voorloopnullen weg. |
| `kavels.csv` | **kavel**, type, verdieping | type: appartement (standaard), garage, berging, handelsruimte, andere |
| `eigenaars.csv` | **code**, **naam**, email, telefoon, straat, postcode, gemeente | `code` is de code uit het oude pakket; ze komt in `res.partner.ref` |
| `eigendommen.csv` | **kavel**, **eigenaar**, **begindatum**, einddatum | eigenaar = code; einddatum leeg zolang de eigendom loopt |
| `sleutels.csv` | **sleutel**, **soort**, **totaal**, **kavel**, **quotiteit**, meerderheid | Lang formaat: één rij per sleutel en kavel. soort: algemeen, lift, verwarming, verbruik, andere. meerderheid: voor een sleutel die de AV besliste, letterlijk uit de notulen; minder dan 4/5 geeft een waarschuwing |
| `leveranciers.csv` | **code**, **naam**, btw, email, iban, sleutel | Optioneel bestand. sleutel = naam uit `sleutels.csv` en maakt een verdeelregel |
| `openingsbalans.csv` | **soort**, code, **bedrag**, omschrijving | Zie hieronder |
| `werken.csv` | **omschrijving**, **bedrag**, financiering, sleutel, datum_av | Optioneel. Beslist maar nog niet uitgevoerd; wordt een werkdossier in voorbereiding. financiering: werkkapitaal of reservekapitaal (standaard) |
| `procedures.csv` | **omschrijving**, tegenpartij, stand | Optioneel. Lopende procedures; worden een taak op de VME en komen in "Gerechtelijke procedures" |
| `mandaten.csv` | **rol**, **naam**, **begindatum**, einddatum | Optioneel. rol: voorzitter, lid, commissaris. Een raadslid moet eigenaar zijn op de begindatum (naam zoals in `eigenaars.csv`) |

### Openingsbalans

De openingsbalans wordt één geboekte boeking (`entry`) in het eerste algemene dagboek (`type = general`) van de VME, op de overstapdatum, met als referentie "Openingsbalans overstap dd/mm/jjjj".

| soort | code | Rekening | Positief bedrag |
| --- | --- | --- | --- |
| `bank_werkkapitaal` | – | `default_account_id` van het bankdagboek WK | debet |
| `bank_reservekapitaal` | – | idem dagboek RK | debet |
| `fonds_werkkapitaal` | – | 100100 | credit |
| `fonds_reservekapitaal` | – | 100200 | credit |
| `eigenaar` | eigenaarscode | vordering van de partner in die company (400000), met partner | debet (eigenaar is schuldig); negatief = vooruitbetaald |
| `leverancier` | leverancierscode | schuld van de partner (440000), met partner | credit (VME is schuldig) |
| `rekening` | rekeningnummer (6 cijfers) | die rekening | debet |

Debet min credit moet 0 zijn, anders geeft de proefrun een fout met het verschil. Bij `rekening` zijn klasse 4 en 5 verboden, behalve 490–493 en 499 (overlopende rekeningen en wachtrekening). Bank, eigenaars en leveranciers hebben elk hun eigen soort. Zo blijven de eigenaarssaldi openstaande posten die je later met een betaling kunt afpunten.

De bankdagboeken komen uit `vme.association._ensure_fund_bank_journals()`. Dat vraagt beide rekeningen. Is er een banksaldo maar ontbreekt een van de twee IBAN's, dan geeft de proefrun een fout.

## Controles

**Fouten** blokkeren de import:

- bestand of verplichte kolom ontbreekt;
- tabel dubbel;
- `vme.csv` heeft niet precies één rij.
- VME-naam bestaat al (`=ilike`, ook gearchiveerd).
- KBO-nummer ongeldig (modulo 97) of al in gebruik.
- IBAN ongeldig (`base_iban.validate_iban`), zelfde IBAN voor beide fondsen, of IBAN al gekend bij een partner.
- Kavel of eigenaar dubbel.
- Type of soort onbekend.
- Eigendom of sleutelregel met een onbekende kavel of eigenaar.
- Einddatum vóór begindatum, of overlappende eigendommen op één kavel.
- Een sleutel die niet optelt tot haar totaal (zelfde precisie als `vme.key`, 2 decimalen), een totaal van 0, of een sleutel met verschillende totalen of soorten.
- Geen sleutel met soort algemeen.
- Ongeldig btw-nummer van een leverancier, of een onbekende sleutel bij een leverancier.
- In de openingsbalans: een onbekende soort of code, een banksaldo zonder beide IBAN's, of een balans die niet in evenwicht is.
- Ongeldige datum, bedrag of e-mailadres.

**Waarschuwingen** blokkeren niet:

- eigenaar zonder kavel;
- kavel zonder eigenaar op de overstapdatum;
- kavel in geen enkele sleutel of niet in de algemene;
- meer dan één algemene sleutel;
- ontbrekende bankrekening zonder saldo;
- eigenaar zonder e-mailadres;
- leverancier zonder btw-nummer;
- geen `leveranciers.csv`;
- lege openingsbalans;
- onbekend bestand of tabel;
- een bestand in `archief/` dat geen PDF is.

**Info**: een leverancier die al bestaat (zelfde btw-nummer, zonder `parent_id`), wordt hergebruikt in plaats van dubbel aangemaakt.

## Import in detail

`_import(plan)` werkt op het "plan" dat de controle opbouwt (opgeschoonde waarden), nooit opnieuw op de ruwe bestanden.

1. `vme.association.create()` maakt de company. Daarna laadt `_load_vme_chart(company.id)` meteen het rekeningstelsel. Normaal gebeurt dat in een precommit-haakje (zie [valkuilen](valkuilen.md#multi-company)), maar de openingsboeking heeft de rekeningen nu al nodig. De functie is idempotent, dus het haakje doet daarna niets meer.
2. De bankrekeningen van de VME worden bevestigd als de gebruiker dat mag (`_user_can_trust()`, zoals in de demodata). Anders toont het VME-formulier de gekende waarschuwing.
3. Daarna volgen kavels, eigenaars (`res.partner` met `ref`), eigendommen, sleutels met regels, leveranciers (hergebruikt of nieuw, met hun bankrekening) en een `vme.distribution.rule` per leverancier met een sleutel.
4. De openingsboeking wordt aangemaakt en geboekt.
5. De PDF's komen als bijlagen op de VME, met een bericht in de chatter. Een tweede bericht verwijst naar de overstap.

## Uitbreidingspunt: omzetter per bronpakket

Voeg aan `source_format` een waarde toe, bijvoorbeeld `("dobby", "Dobby")`, en schrijf `_convert_dobby(self, tables)`. Die krijgt de ingelezen tabellen, in de vorm `{naam: {"source", "columns", "rows"}}` met de bestandsnamen van het bronpakket. Hij geeft dezelfde structuur terug met onze tabel- en kolomnamen. Proefrun, controles en import blijven ongewijzigd. Onbekende tabelnamen geven nu een waarschuwing; een omzetter mag zijn eigen namen dus pas in `_convert_*` omzetten. Laat `_read_file` die tabellen daarom toe, bijvoorbeeld door de controle op `TABLES` in `_add_table` alleen voor `standard` te doen.

## Wat niet meekomt

- **Oudere boekjaren en hun detail**: alleen het saldo op de overstapdatum, plus de PDF's. Openstaande facturen per eigenaar worden één saldo per eigenaar. Wil je per factuur kunnen afpunten, voeg dan meerdere `eigenaar`-rijen toe met elk een eigen omschrijving.
- Budgetten, provisieoproepen, installaties, AV's en verdeelregels zonder sleutel. Die maak je na de overstap in het platform zelf.
- Meer dan één VME per import. Voor 200 VME's is dat 200 zips; een batch-scherm is pas zinvol als de eerste omzetter bestaat.

## Voorbeeldbestanden

`demo_data/migratie/residentie-esdoorn-met-fouten/` en `demo_data/migratie/residentie-esdoorn/` beschrijven dezelfde fictieve VME, met 10 kavels (A1–A8, G1–G2), 10 eigenaars, een algemene sleutel en een liftsleutel, 3 leveranciers en een overstapdatum op 1/1/2027. De versie met fouten heeft:

| Bewuste fout | Gevolg |
| --- | --- |
| Liftsleutel: A8 heeft 175 in plaats van 185 (som 990) | fout |
| `eigendommen.csv`: kavel A12 in plaats van A8 | fout, plus de waarschuwing "A8 heeft geen eigenaar" en "Eigenaar Esdoorn A8 heeft geen kavel" |
| `iban_reservekapitaal` leeg, terwijl er een reservesaldo is | fout op beide bankregels, plus de waarschuwing "geen bankrekening" |

In beide versies zitten ook drie bedoelde waarschuwingen: de erfgenaam E09 heeft een saldo maar geen kavel, de glazenwasser heeft geen btw-nummer en E07 heeft geen e-mailadres. Leverancier L01 heeft het btw-nummer van de energieleverancier uit de demodata en wordt dus hergebruikt.

## Tests

`tests/test_migration.py`:

- **Parsing**: datums, bedragen, `,` als scheidingsteken en cp1252.
- **Proefrun op de foutenversie**: de verwachte fouten en waarschuwingen. Een telling vóór en na bewijst dat er geen VME, company, partner, bankrekening, kavel, sleutel, boeking of bijlage bijkomt.
- **Proefrun op de verbeterde versie**: geen fouten.
- **Import weigert bij fouten.**
- **Afzonderlijke foutgevallen**: ontbrekend bestand of kolom, balans niet in evenwicht, onbekende codes in de openingsbalans, overlappende eigendom, bestaande VME, ongeldig KBO-, IBAN- en btw-nummer.
- **Volledige import**: VME, rekeningstelsel, bankrekeningen, eigendommen met verkoop, sleutels, hergebruikte leverancier en verdeelregels, de geboekte openingsboeking met saldi per rekening, eigenaar en leverancier, een openstaand saldo dat afpuntbaar is, archief-PDF's, en geen tweede import.
- **Zip met een Excel-bestand**, met echte datum- en getalcellen.

Rekeningcodes hangen in Odoo 19 af van de company: lees ze in tests met `with_company(vme.company_id)`.
