# Bankafschriften en het koppelen van betalingen (stap 12)

CODA- en CAMT.053-bestanden worden ingelezen als gewone Odoo-rekeninguittreksels (`account.bank.statement` met `account.bank.statement.line`) in het bankdagboek van de fondsrekening. Daarna koppelt `vme_belgie` elke beweging automatisch of met een voorstel aan provisies en leveranciersfacturen.

## Wat Odoo 19 Community kan, en wat niet

| Onderdeel | Community | Enterprise / extern | Wat wij doen |
| --- | --- | --- | --- |
| Rekeninguittreksel en bankregels als boekingen | Ja (`account.bank.statement(.line)`): elke regel is een `account.move` met een liquiditeitsregel en een regel op de wachtrekening (suspense) | | Gebruiken we zoals het is |
| Gestructureerde mededeling op klantfacturen | Ja (`l10n_be`: referentiemodel "be" op het verkoopdagboek) | | Overschreven: uit het factuurnummer (zie hieronder) |
| CODA inlezen | Nee | Enterprise `l10n_be_coda` (+ `account_bank_statement_import`); extern bv. de OCA-module `account_statement_import_be_coda` met de bibliotheek `pycoda` | Eigen parser `models/bank_formats.py` |
| CAMT.053 inlezen | Nee | Enterprise `account_bank_statement_import_camt`; OCA `account_statement_import_camt` | Eigen parser in `bank_formats.py` |
| Afletterscherm (bank reconciliation widget), afletterregels (`account.reconcile.model`) | Alleen het model, geen scherm; schrijven op bankregels vraagt de verborgen groep `account.group_account_basic` | Enterprise `account_accountant` | Eigen koppellogica, lijst en knoppen |
| Automatisch ophalen bij de bank | Nee | Enterprise `account_online_synchronization` (Ponto e.d.), of een CODA-dienst van de bank | Niet in het prototype |

In de container van Odoo 19 Community bestaan geen modules `account_bank_statement_import*`, `l10n_be_coda` of `account_accountant`, en geen `pycoda` (nagekeken met `ls /usr/lib/python3/dist-packages/odoo/addons`). We kopieerden niets uit Enterprise of OCA: de parsers zijn geschreven vanuit de publieke specificaties (CODA 2.6 van Febelfin, camt.053.001.02 van ISO 20022).

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `models/bank_formats.py` | Zuivere Python zonder Odoo: `parse_coda`, `write_coda` (voor tests en demo), `parse_camt053`, `parse_statement_file` (kiest het formaat), en de gestructureerde mededeling (`make_structured`, `find_structured`, controle modulo 97) |
| `models/account_bank_statement_line.py` | Uitbreiding van `account.bank.statement.line`: velden, automatische koppeling, voorstellen, afletteren, knoppen |
| `wizard/vme_bank_import_wizard.py` | `vme.bank.import.wizard`: bestand → een uittreksel per rekening in het juiste dagboek → `_vme_match()` |
| `views/vme_bank_views.xml` | Lijst, formulier en zoekscherm voor bankregels, de wizard, menu **VME > Bank** en de demo-actie |
| `demo_data/vme_demo_bank.py`, `demo_data/bankafschriften/` | Fictieve CODA- en CAMT-bestanden van 5 november 2026 en `_load_demo_bank_statements()` |
| `tools/make_demo_bank_files.py` | Maakt die demobestanden opnieuw (zelfde bedragen, mededelingen uit de factuurnummers) |

## Flow

```
CODA/CAMT-bestand
  └─ parse_statement_file()           -> [Statement(account_number, balances, transactions)]
  └─ per Statement:
       _journal_for_account(IBAN)     -> bankdagboek WK of RK van de VME (maakt het aan als het nog niet bestaat)
       al ingelezen? (dagboek + vme_import_key "CODA:044:2026-11-05", of de oude naam) -> overslaan
       account.bank.statement.create  -> regels op de wachtrekening van het dagboek
  └─ lines._vme_match()  (als superuser)
       ontvangst (> 0)  -> _vme_match_receipt()
            geldige mededeling + open klantfactuur van die company
                 fonds van de factuur ≠ fonds van de rekening -> voorstel, uitzondering wrong_fund
                 anders                                       -> _vme_reconcile(state="auto")
            ongeldig / onbekend / al betaald / geen          -> uitzondering + _vme_suggest_receipt()
       uitgave (< 0)    -> _vme_match_supplier_payment()
            mededeling = payment_reference of bevat `ref` van een open leveranciersfactuur,
            of tegenpartij (IBAN of naam) = leverancier; precies één factuur met dat bedrag -> auto
            anders -> voorstel
```

Sinds stap 20 kijkt `_vme_match()` eerst of de beweging een betaling of inning uit een eigen SEPA-batch is (op EndToEndId, of op bedrag en mededeling); zie [betalingsverkeer.md](betalingsverkeer.md#terugkoppeling-via-het-afschrift).

### Afletteren zonder Enterprise

`_vme_reconcile(moves, state)` doet wat het Enterprise-afletterscherm doet, op de boeking van de bankregel zelf:

1. `_seek_for_lines()` geeft de liquiditeitsregel en de regel op de wachtrekening.
2. De regel op de wachtrekening wordt vervangen door een tegenregel per open debiteuren- of crediteurenregel van de facturen (oudste vervaldatum eerst, tot het bedrag op is), via `move.with_context(skip_readonly_check=True, force_delete=True).write({"line_ids": ...})`.
3. Elke tegenregel wordt met `reconcile()` afgeletterd met haar factuurregel. De factuur wordt `paid` of `partial`.
4. Een rest blijft op de wachtrekening, of gaat bij een te hoge betaling (of **Boeken op eigenaar of leverancier**) naar de debiteuren-/crediteurenrekening van de partner als tegoed.
5. `vme_exception` (underpaid/overpaid) en `vme_days_late` (datum van de bankregel min de vroegste vervaldatum) worden gezet.

Ongedaan maken gebruikt Odoo's eigen `action_undo_reconciliation()`, die de twee standaardregels terugzet.

### Velden op `account.bank.statement.line`

| Veld | Uitleg |
| --- | --- |
| `vme_bank_fund` | `working`/`reserve`: welke fondsrekening (bankrekening van het dagboek = rekening van de VME). Opgeslagen. |
| `vme_match_state` | `auto`, `manual`, `suggested`, `todo` |
| `vme_exception` | `no_reference`, `wrong_reference`, `already_paid`, `wrong_fund`, `underpaid`, `overpaid`, `unknown` |
| `vme_days_late` | Dagen na de vervaldatum, alleen voor ontvangsten |
| `vme_match_note` | Toelichting voor de medewerker (Nederlands) |
| `vme_structured_reference` | De gevonden mededeling, genormaliseerd |
| `vme_candidate_move_ids` | Het voorstel; de medewerker mag het aanpassen voor hij op **Koppelen** klikt |
| `vme_matched_move_ids` | Berekend: de facturen waarmee de regel afgeletterd is |
| `vme_follow_up` | Opgeslagen: nog te koppelen, of gekoppeld met te laat / te weinig / te veel / ander fonds |

`vme_association_id` komt via `_inherits` van `account.move` (de boeking van de bankregel), dus niet opnieuw gedefinieerd. Kies daarom geen veldnamen die al op `account.move` bestaan (zoals `vme_fund`): die zouden het geërfde veld verbergen.

### Voorstellen

`_vme_identify_partners()` zoekt de eigenaar in deze volgorde: de partner op de regel, het rekeningnummer van de tegenpartij (`res.partner.bank`), de naam van de tegenpartij gelijk aan een eigenaar van de VME, een kavelnaam als los woord in de mededeling (eigenaar op de datum van de betaling). Daarna `_vme_suggest_receipt()`:

- eigenaar bekend: één open provisie (op het fonds van de rekening) met exact het bedrag → die (de oudste bij meerdere); de som van al zijn open provisies → allemaal; anders al zijn open provisies, met de opmerking dat het bedrag afwijkt;
- eigenaar onbekend: alleen een voorstel als precies één open provisie van de VME dat bedrag heeft.

Na een manuele koppeling bewaart `_vme_learn_bank_account()` het rekeningnummer van de tegenpartij op de eigenaar (`_find_or_create_bank_account`, zoals Odoo's eigen afletterscherm), zodat de volgende betaling op rekeningnummer herkend wordt.

## Gestructureerde mededeling uit het factuurnummer

`l10n_be` maakt de mededeling standaard uit het database-id van de factuur. Voor facturen van een VME overschrijft `account.move._get_invoice_reference_be_invoice()` dat: `1` (factuur) of `2` (creditnota) + jaar + volgnummer uit de naam. `F/2026/00075` wordt `+++120/2600/07589+++`. Zo leest een medewerker het factuurnummer in de mededeling, en krijgt dezelfde demo altijd dezelfde mededelingen, wat de vaste demobestanden mogelijk maakt. De matching zoekt op `sanitize_payment_reference` (alleen cijfers en letters) binnen de company van de bankrekening; dezelfde mededeling in een andere VME stoort dus niet.

Facturen die vóór deze versie geboekt zijn, houden hun oude mededeling. Een bestaande demodatabase moet je opnieuw opbouwen om de demobankafschriften te laten passen.

## Rechten

In Community mogen alleen leden van de verborgen groep `account.group_account_basic` bankregels wijzigen; gewone facturatiegebruikers (`group_account_invoice`) mogen ze alleen lezen. De module geeft `group_account_invoice` schrijfrecht (geen aanmaken of verwijderen) op `account.bank.statement.line` (`security/ir.model.access.csv`). De knoppen controleren `check_access("write")` en werken daarna als superuser, omdat ze boekingen in de company van de VME schrijven, los van de bedrijvenkiezer. Het menu **Bank** is alleen zichtbaar voor `group_account_invoice`.

## Demo

`VME > Configuratie > Demobankafschriften inlezen` (of `env['vme.association']._load_demo_bank_statements()` in de shell, als admin) leest vier bestanden in, na de demodata en de demohistoriek:

| Bestand | Rekeningen | Bewust |
| --- | --- | --- |
| `residentie_linde_2026-11-05.cod` | WK en RK | Twee leveranciersbetalingen; A3 één dag te laat; reserve A3 zonder mededeling, betaald door "Familie Voorbeeld" |
| `hof_ter_beuken_2026-11-05.cod` | WK en RK | B7: tikfout in de mededeling, te weinig, reserveprovisie op de werkrekening, één correcte betaling; gasfactuur |
| `kaaihuis_2026-11-05.cod` | WK | Schoonmaakfactuur; dubbele betaling van K2 |
| `kaaihuis_reservekapitaal_2026-11-05.xml` | RK (CAMT.053) | Onbekende betaler zonder mededeling |

Resultaat: 7 automatisch (1 te laat, 1 te weinig), 3 voorstellen, 2 te koppelen. De trage test `TestAnnualStatementDemo.test_demo_bank_statements` (tag `vme_slow`) controleert dat de bestanden nog passen bij de demohistoriek. Verandert de historiek (meer eigenaars, andere volgorde), pas dan `tools/make_demo_bank_files.py` aan en draai het opnieuw:

```bash
python3 tools/make_demo_bank_files.py
```

De beginsaldi in de bestanden zijn de provisies die in 2026 op die rekening binnenkwamen; de leveranciersfacturen uit de historiek zijn in Odoo nog niet betaald.

## Testen

- `tests/test_bank_statements.py`, `TestBankFormats`: mededeling en modulo 97, CODA heen en terug (128 tekens per record), saldo dat niet klopt, CAMT.053 (het demobestand), onbekend formaat.
- `TestBankMatching`: mededeling uit het factuurnummer; een bestand met twee rekeningen gaat naar twee dagboeken en tweemaal inlezen maakt niets; onbekende rekening geweigerd; automatisch; te laat; te weinig (gedeeltelijk); te veel (tegoed); foute mededeling → voorstel op naam en bedrag, manueel koppelen, rekeningnummer onthouden; voorstel op kavel in de mededeling; geen voorstel bij twee provisies van hetzelfde bedrag; ander fonds; dubbele betaling en boeken op de eigenaar; leveranciersbetaling op referentie; leveranciersbetaling met ander bedrag is een voorstel; ongedaan maken; een facturatiegebruiker kan koppelen.

## Valkuilen

- **Partner wijzigen na het afletteren wist de koppeling.** `account.bank.statement.line._synchronize_to_moves()` schrijft bij een gewijzigde `partner_id` de standaardregels opnieuw en verwijdert alle andere regels. Zet de partner dus altijd vóór `_vme_reconcile()`.
- **Bedrijvenkiezer.** Bankregels vallen onder de multi-company-regels van Odoo: de lijst toont alleen de geselecteerde VME's.
- **Uitgelogd in een tweede demo.** Bij de browsercontrole op `localhost:8270` (naast de demo op `localhost:8069`) werden we herhaaldelijk uitgelogd; vermoedelijk delen beide servers dezelfde sessiecookie voor `localhost`. Via `127.0.0.1:8270` en het gewone loginformulier bleef de sessie stabiel.
