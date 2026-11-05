# Odoo-methodes die we overschrijven

We blijven zo dicht mogelijk bij standaard Odoo: elke override roept eerst `super()` aan en voegt alleen iets toe. Wie Odoo upgradet, kijkt deze lijst na.

| Methode | Bestand | Wat we toevoegen | Waarom |
| --- | --- | --- | --- |
| `account.move._post(soft)` | `models/account_move.py` | Na `super()`: `_vme_auto_distribute()` op geboekte leveranciersfacturen en -creditnota's met een VME | Een factuur met verdeelregel moet zonder klikken verdeeld zijn. Fouten worden chatterberichten: het boeken mag nooit blokkeren op eigendomsgegevens. De verdeling loopt in een savepoint, zodat een mislukte verdeling niets half achterlaat. |
| `account.move._compute_partner_bank_id()` | `models/account_move.py` | Voor facturen met een `vme_fund`: de bankrekening van dat fonds van de VME | Odoo kiest standaard de eerste rekening van de company. Een provisie moet op de rekening van haar fonds komen (`# LEGAL-CHECK: art. 3.89 §5 BW`). De VME wordt op company gezocht, omdat `vme_association_id` bij `create` nog niet berekend is. Extra `@api.depends` op `vme_fund` en `vme_association_id`. |
| `account.move._extend_with_attachments(files_data, new)` | `models/account_move.py` | Leest `InvoicePeriod/StartDate` en `EndDate` uit het UBL-bestand en zet de kostperiode | Odoo negeert de factuurperiode van een Peppol-factuur; wij hebben ze nodig voor de pro-rataverdeling bij een verkoop. Dit is het haakje dat Odoo 19 gebruikt voor zowel **Upload** als `journal._create_document_from_attachment`. |
| `account.move.line._compute_account_id()` | `models/account_move.py` | Voor regels zonder product: de rekening uit de verdeelregel, als die er een heeft | Facturen zonder product (de meeste Peppol-facturen) krijgen anders de standaardrekening van het dagboek. |
| `account.move._get_invoice_reference_be_invoice()` | `models/account_move.py` | Voor facturen van een VME: de gestructureerde mededeling uit het factuurnummer (`1`/`2` + jaar + volgnummer) in plaats van uit het database-id | De medewerker leest het factuurnummer in de mededeling, en de vaste demobankafschriften passen bij elke opnieuw opgebouwde demo (stap 12). Valt terug op `super()` voor andere companies of een onverwachte naam. |
| `account.move._post(soft)` (tweede override) | `models/vme_works.py` | Na `super()`: `_vme_book_reserve_use()` voor geboekte facturen van werken uit het reservekapitaal | Diverse boeking debet 100200, credit de kostenrekeningen, zodat het reservekapitaal de werken draagt (stap 14). Gemaakt met `clean_context`, anders erft ze `default_vme_works_id` van het factuurformulier. |
| `account.move.button_draft()` | `models/vme_works.py` | Keert de boeking op het reservekapitaal om en maakt `vme_reserve_move_id` leeg | Een factuur terugzetten naar concept mag het reservekapitaal niet verminderd laten. |
| `account.move.line._compute_vme_key_id()` (override) | `models/vme_works.py` | Extra `@api.depends("move_id.vme_works_id")`: regels van een werkfactuur krijgen de sleutel van het werkdossier, tenzij met de hand een andere sleutel gekozen is | De verdeelregel van een aannemer (als die er is) mag de sleutel van de werken niet overschrijven. |
| `account.chart.template._post_load_data(template_code, company, template_data)` | `models/account_chart_template.py` | Alleen voor companies van een VME: standaardrekening 611000 op het aankoopdagboek, en de rekeningen 100100 Werkkapitaal en 100200 Reservekapitaal | Het Belgische PCMN laat het aankoopdagboek zonder standaardrekening en kent geen fondsrekeningen voor een VME. Dit haakje loopt nadat het rekeningstelsel van een nieuwe company geladen is; dat gebeurt pas bij de commit, dus op dat moment bestaat de VME al. |
| `base._get_view()` en `base._get_view_cache_key()` | `models/vme_council.py` | Voor de commissaris: `create`, `edit` en `delete` op `0` in list-, form- en kanbanweergaven (niet voor `res.users` en wizards); de cachesleutel krijgt een element erbij | De commissaris mag alleen lezen; zonder deze knoppen botst hij niet op toegangsfouten. De record rules blijven de echte bescherming (stap 16). |
| `vme.association.create()` (tweede override) | `models/vme_council.py` | Na `super()`: `_vme_sync_auditor_access()` voor commissarissen van de nieuwe company | De eerste override geeft alle interne gebruikers toegang tot een nieuwe VME; een commissaris mag alleen zijn eigen VME's zien. |

## Andere uitbreidingspunten

| Punt | Bestand | Uitleg |
| --- | --- | --- |
| `vme.association.create()` | `models/vme_association.py` | Maakt de company met `chart_template: "be_comp"` en geeft alle interne gebruikers toegang. Geen `required=True` op `company_id`: dan eist de webclient het veld al voor `create()` het kan invullen; een SQL-check vervangt dat. |
| `vme.key.write()` / `vme.key.line.write()` / `unlink()` | `models/vme_key.py` | De som van een sleutel wordt gecontroleerd na alle regelcommando's van een formulier (context `vme_skip_line_check`), maar ook als iemand een regel los bewerkt of verwijdert. |
| `account.move.line._compute_vme_key_id()` | `models/account_move.py` | Nieuw opgeslagen compute (`readonly=False`) op `move_id.partner_id`, `move_id.company_id`, `display_type`: vult een lege sleutel vanuit de verdeelregel. |
| `account.move._compute_vme_association_id()` | `models/account_move.py` | Opgeslagen compute op `company_id`, met `sudo` en `active_test=False`, zodat ook gearchiveerde VME's en companies buiten de selectie gevonden worden. |
| Serveracties `action_load_demo_data`, `action_load_demo_history` | `data/demo_actions.xml` | Alleen voor `base.group_system`; roepen `_load_demo_data()` en `_load_demo_history()` aan. |
| `account.bank.statement.line` (nieuwe velden en methodes) | `models/account_bank_statement_line.py` | Koppelt bankregels zelf: vervangt de regel op de wachtrekening door tegenregels en lettert af met `reconcile()`. Gebruikt Odoo's `_seek_for_lines()`, `action_undo_reconciliation()` en `_find_or_create_bank_account()`. Zie [bankafschriften.md](bankafschriften.md). |
| Toegangsrecht op `account.bank.statement.line` voor `account.group_account_invoice` | `security/ir.model.access.csv` | Lezen en schrijven (niet aanmaken of verwijderen): in Community kan anders alleen de verborgen groep `group_account_basic` bankregels wijzigen. |
| `res.partner._can_be_edited_by_current_customer()` | `models/vme_portal.py` | `False` voor een portaalgebruiker die eigenaar is: Odoo's eigen adresformulieren in het portaal mogen het register niet rechtstreeks wijzigen (stap 15). |
| `CustomerPortal.account()`, `my_addresses()`, `_prepare_home_portal_values()` | `controllers/portal.py` | Eigenaars gaan van `/my/account` en `/my/addresses` naar `/my/vme/address`; teller `vme_count` en `vme_owner` voor de tegels op `/my`. |
| Template `portal.portal_my_home` | `views/portal_templates.xml` | Tegel "Mijn mede-eigendom"; Odoo's tegel "Je facturen" verborgen voor eigenaars (provisies staan in de VME-company, die lijst bleef leeg). |
| Record rules voor `group_vme_auditor` | `security/vme_council_security.xml` | Per VME-model een leesregel op `company_ids` en een regel die schrijven, aanmaken en verwijderen weigert; een leesregel op `res.partner`. Gelden alleen voor de commissaris. Zie [raad-commissaris.md](raad-commissaris.md). |
| `check_not_auditor(env)` | `models/vme_access.py` | Bovenaan knoppen die met `sudo()` schrijven (invordering, bankregels): record rules gelden niet voor wat `sudo()` doet. |
| Serveracties `action_help_*` | `data/help_menu.xml` | Geven een `ir.actions.act_url` terug naar `vme_belgie.help_url` + artikel. |

| `account.move._vme_auto_distribute()` | `models/vme_request.py` | Slaat facturen met `vme_request_id` over | De factuur van de slotenmaker voor een privé-aanvraag wordt aan één eigenaar aangerekend, niet verdeeld (stap 19). |
| Domein in `vme.association._get_annual_statement()` | `models/vme_annual_statement.py` | `("vme_request_id", "=", False)` op de leveranciersfacturen | Een privé-kost hoort niet in de kosten van de jaarafrekening en ook niet bij de niet-verdeelde facturen. |
| `vme.sale.file.action_deed_done()` | `models/vme_sale_file.py` | Draagt de sleutels van de verkoper over aan de koper | Het sleutelregister volgt de eigendom (stap 19). |

## Wat we bewust niet overschrijven

- **Bevestigen van bankrekeningen** (`res.partner.bank.allow_out_payment`, `_user_can_trust`). Odoo laat dat alleen toe voor een mens met de juiste rechten; we tonen een waarschuwing en de wizard weigert, maar we zetten het nooit zelf aan vanuit code die als systeemgebruiker draait.
- **Gestructureerde mededeling: wel het formaat, niet het model.** Het Belgische referentiemodel van het verkoopdagboek (`l10n_be`) blijft aan; alleen de cijfers komen sinds stap 12 uit het factuurnummer (zie hierboven).
- **Peppol-import zelf.** We gebruiken de gewone upload van Odoo en lezen alleen de periode extra.
