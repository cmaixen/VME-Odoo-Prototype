# Verkoop en inlichtingen aan de notaris (stap 9)

Code: `models/vme_sale_file.py`, rapport `report/vme_sale_file_report.py` en `.xml`, views `views/vme_sale_file_views.xml`, tests `tests/test_sale_file.py` en `test_demo_sale_linde_a3` in `test_demo_data.py`. Demo: `_load_demo_sale` in `demo_data/vme_demo_data.py`.

## Datamodel

| Model | Wat erbij kwam |
| --- | --- |
| `vme.sale.file` (nieuw) | Verkoopdossier met `mail.thread` en `mail.activity.mixin`. VME, `lot_ids` (Many2many, zelfde VME), `seller_id` (compute uit de huidige eigenaar van de eerste kavel, opgeslagen en aanpasbaar), `buyer_id`, `notary_id`, `notary_reference`, `user_id`. Datums van de eerste en tweede vraag met opgeslagen termijnen, `deed_date`, `state`. |
| `vme.association` | `legal_proceedings` (Html), `sale_file_ids`. |
| `vme.lot` | Knop `action_start_sale`. |
| `vme.assembly.item` | `works_amount` (Monetary), `works_key_id` (optioneel; leeg = algemene sleutel), `works_done`. |

Statussen: `new` → `first_answered` → `second_received` → `second_answered` → `done`, of `cancelled`. `answer_deadline` is de termijn van de vraag die nog open staat (`new`: eerste, `second_received`: tweede); `deadline_state` en `deadline_text` zijn niet opgeslagen en bepalen de kleur in de lijst en de banner op het formulier (`WARNING_DAYS = 7`).

## Termijnen en taken

- `FIRST_ANSWER_DAYS = 15` en `SECOND_ANSWER_DAYS = 30`, met `LEGAL-CHECK` (art. 3.94 §1 en §2 BW).
- `create` maakt een To-do voor de eerste vraag. `write` herkent een nieuw ingevulde `second_request_date`, zet de status op `second_received` en maakt een To-do met de tweede termijn.
- `_answer(which)` rendert de PDF, post hem met bijlage in de chatter, sluit de To-do met dezelfde `summary` (`_activity_summary`) en zet datum en status. Er wordt niets verstuurd.

## Het antwoord: `_get_notary_information(on_date=None)`

Alles als `sudo`, zoals de jaarafrekening: de records van een VME zitten in haar eigen company. Het resultaat is een dict die zowel het PDF-rapport als het voorbeeld op het formulier (`information_html`, gerenderd met `ir.qweb` en de template `notary_information_body`) gebruiken.

| Sleutel | Bron |
| --- | --- |
| `keys` | Som van de quotiteiten van de verkochte kavels per sleutel. |
| `reserve_balance` | `-sum(balance)` van de geboekte lijnen op rekening 100200 tot `on_date`. De rekening zoeken we met `with_company(company)`: de code van een rekening hangt in Odoo 19 af van de company. |
| `reserve_share` | `reserve_balance` × quotiteit van de verkochte kavels in de algemene sleutel / totaal. |
| `statement` | `vme._get_annual_statement(jaar, partners=verkoper)`; het voorlopige saldo van het lopende jaar. |
| `arrears` | Geboekte provisiefacturen (`out_invoice` met `vme_provision_call_id`) van de verkoper met `amount_residual ≠ 0`. |
| `works` | Agendapunten met `outcome = adopted`, `works_amount > 0` en niet `works_done`; aandeel via `works_key_id` of de algemene sleutel. |
| `assemblies` | Gehouden AV's van de laatste drie jaar (`ASSEMBLY_YEARS`). |

Het rapportmodel `report.vme_belgie.report_notary_information` krijgt `data={"answer": "first"|"second"}`; zonder `data` (afdrukken vanuit het menu) kiest het de tweede vraag als die er is.

## De akte: `action_deed_done`

Voor elke kavel: de eigendom die vóór de aktedatum begon en erover loopt, moet van `seller_id` zijn (anders `UserError`). Die krijgt `date_end = deed_date - 1`; daarna een nieuwe `vme.ownership` voor de koper vanaf `deed_date`. De bestaande controle op overlappende eigendommen blijft gelden. Daarna volgen kostenverdeling, provisieoproepen en jaarafrekening de koper zonder extra code, want ze kijken allemaal naar `vme.ownership` op een datum.

## Tests

`TestSaleFile` (freezegun op 5 november 2026) bouwt een VME met A1 (500) en G1 (100) van de verkoper en A2 (400) van een andere eigenaar, twee provisieoproepen, betalingen en een gehouden AV met twee werken. Getest: termijnen en taken, de oranje en rode signalen, elke sectie van het antwoord (alleen eigen achterstallen, uitgevoerde werken vallen weg, eigen sleutel voor werken), het beantwoorden, het rapport, en de akte inclusief een provisieoproep 2027 die naar de koper gaat.

## Beperkingen

- Een kavel heeft in het prototype één eigenaar tegelijk (zie `vme.ownership._check_no_overlap`); mede-eigendom, vruchtgebruik en naakte eigendom ontbreken nog.
- Het antwoord rekent met vandaag; een antwoord "op de datum van de vraag" kan via `on_date`, maar zit niet in de schermen.
- Het werkkapitaal wordt niet tussen verkoper en koper verrekend: dat doet de jaarafrekening, per dag.
