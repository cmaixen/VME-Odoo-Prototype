# Het kantoor van de syndicus: ereloon, prestaties en mandaat

Code: `models/vme_syndic.py`, wizard `wizard/vme_fee_invoice_wizard.py`, views `views/vme_syndic_views.xml`,
rapport `report/vme_syndic_reports.xml`, data `data/syndic_data.xml` (documentmap, cron), record rules
`security/vme_syndic_security.xml`, tests `tests/test_syndic.py`, `test_demo_syndic` in `test_demo_data.py` en
`test_syndic_fee_bills_stay_drafts` in `test_annual_statement.py` (`vme_slow`). Demo: `demo_data/vme_demo_syndic.py`.

Niet te verwarren met `vme_rentmeester`: het ereloon voor verhuurders hoort daar en raakt deze modellen niet.

## Het kantoor

`res.company.is_syndic_office` markeert de company van het syndicuskantoor. Het kantoor heeft het gewone
Belgische rekeningstelsel (`_load_vme_chart`, zoals elke VME) en is btw-plichtig. Ereloonfacturen zijn
klantfacturen (`out_invoice`) in die company, met klant = `vme.association.partner_id`.

## Datamodel

| Model | Inhoud |
| --- | --- |
| `vme.management.agreement` | Beheerovereenkomst: VME, `syndic_company_id`, begin/einde, `fee_basis` (`lot`/`vme`), `fee_amount` per maand zonder btw, `billing_period` (`month`/`quarter`), `indexation` (`none`/`cpi`/`percent`), `index_base_month`, `index_base_value`, `index_percent`, `index_rates`, `rate_ids`. Geen overlap per VME (constraint). |
| `vme.service.rate` | Prijslijst per overeenkomst, één regel per `service_type`. `create` van de overeenkomst vult `DEFAULT_RATES`. |
| `vme.service.line` | Prestatie: VME, overeenkomst (compute op datum), soort, datum, aantal, `price_unit` (compute uit prijslijst × indexfactor, aanpasbaar), bron (`res_model`, `res_id`, `source_name`), `recharge_partner_id`, `no_charge`, `invoice_line_id`, `state` (compute: `invoiced` als de factuurlijn bestaat en niet geannuleerd is). Unieke index op (bron, soort). |
| `vme.consumer.price.index` | Consumptieprijsindex per maand (aparte tabel: de rentmeester gebruikt de gezondheidsindex, en `vme_belgie` hangt niet af van `vme_rentmeester`). Gedeeld door alle VME's: medewerkers lezen, alleen de beheerder (`base.group_system`) wijzigt. |
| `vme.syndic.mandate` | Mandaat: VME, syndicus (partner), begin, einde (standaard +3 jaar −1 dag), `appointment_item_id`, `previous_mandate_id`, opgeslagen `renewal_assembly_year` en `renewal_period_start`, niet-opgeslagen `renewal_state`/`renewal_text`/`renewal_item_id`/`posting_state` (met `search`), `posting_deadline`, `posted_date`, `posting_document_id`. Bewust niet `vme.mandate`: dat is de raad en de commissaris (stap 16). |
| `account.move` | `vme_fee_agreement_id`, `vme_fee_bill_id` (op de klantfactuur), `vme_fee_invoice_id` (op de leveranciersfactuur). |
| `account.move.line` | `vme_service_line_id`. |
| `vme.association` | `management_agreement_ids`, `syndic_mandate_ids`, `service_line_ids`, computes `current_agreement_id`, `current_syndic_mandate_id`, `syndic_renewal_state/text`; `_get_management_agreement_on(day)` en `_get_syndic_mandate_on(day)`. |

## Indexering

`_fee_factor(day)`: `years = relativedelta(day, date_start).years`. Vóór de eerste verjaardag of zonder indexering 1.
Percentage: `(1 + p/100) ** years`. Consumptieprijsindex: index van de maand vóór de laatste verjaardag gedeeld
door `index_base_value`; ontbreekt het cijfer, dan een `UserError` met de maand. `_unit_fee(month)` rondt af op de cent.

`_fixed_fee_lines(start, end)` loopt per maand en groepeert opeenvolgende maanden met dezelfde prijs tot één lijn
(`quantity` = eenheden × maanden). Een verjaardag midden in een kwartaal geeft zo twee lijnen.

Een ontbrekend indexcijfer mag de bron van een prestatie (aangifte, afgifte, AV) nooit blokkeren:
`_compute_price_unit` vangt de `UserError` op en zet 0; de factuurwizard vraagt dan om het cijfer.

## Prestaties uit de bronnen

`vme.service.line._register_from_source(source, service_type, day, name, recharge_partner=None)` maakt een
regel als de VME op die dag een overeenkomst heeft, en zet een bericht in de chatter van de bron. Bestaat er al
een regel voor (bron, soort), dan geeft ze die terug. Heet bewust niet `_register`: dat is een klasse-attribuut van
`BaseModel` (de registry gebruikt het), en een methode met die naam wordt een `bool`.

| Bron | Overschreven methode | Soort |
| --- | --- | --- |
| `vme.sale.file` | `_answer("first")` | `sale_file`, met de verkoper als `recharge_partner_id` (`LEGAL-CHECK` art. 3.94 §1 BW) |
| `vme.damage.claim` | `action_declare` | `damage_claim` |
| `vme.assembly` | `action_mark_held` | `extra_meeting` bij `second_session`, anders `extraordinary_assembly` voor een buitengewone AV |
| `vme.registered.mail` | `action_deposit`, `action_send_electronic` | `registered_mail` |

De overschrijvingen staan onderaan `vme_syndic.py`; het bestand wordt als laatste geladen (`models/__init__.py`).

## Ereloonfactuur

- `agreement._billing_periods(date_from, date_to)` geeft de volledige maanden of kalenderkwartalen binnen de periode.
- `agreement._create_fee_invoice(start, end)`: weigert bij een overlappende niet-geannuleerde ereloonfactuur,
  maakt een concept-`out_invoice` in het kantoor met de vaste lijnen en alle prestaties `to_invoice` met datum ≤ einde,
  rekening `a7001` (700100) en btw `attn_VAT-OUT-21-S` via `account.chart.template.ref()`. De kostperiode staat in
  `vme_period_start/end` (velden van stap 4 die ook op klantfacturen bestaan).
- `vme.fee.invoice.wizard` doet dat voor alle (gekozen) VME's, slaat al gefactureerde periodes over en opent de lijst
  van de concepten. Standaardperiode: het vorige kwartaal (`previous_quarter`).
- `account.move._post` (overschrijving in `vme_syndic.py`): een bevestigde ereloonfactuur roept
  `_vme_prepare_fee_bill()` op. Die maakt (of herschrijft, als ze nog concept is) een `in_invoice` in de company van
  de VME met dezelfde lijnen, btw `attn_VAT-IN-V82-21-S`, rekening en sleutel uit de verdeelregel van het kantoor.
  Is de leveranciersfactuur al bevestigd, dan alleen een bericht. De leveranciersfactuur blijft altijd concept: de
  bestaande `_vme_auto_distribute` verdeelt ze pas als een mens ze bevestigt.
- `agreement._ensure_fee_rule()` (bij `create` en vóór elke leveranciersfactuur): verdeelregel kantoor → eerste
  algemene sleutel, rekening `a61329` (613290 "Andere erelonen"). Bij een nieuwe VME bestaat het rekeningstelsel pas
  na de commit; daarom zet de tweede aanroep de rekening alsnog.

## Mandaat en herbenoeming

- `LEGAL-CHECK` art. 3.89 §1 BW: `_check_duration` (einde ≤ begin + 3 jaar − 1 dag, geen overlap per VME).
- `renewal_assembly_year`: het laatste jaar waarvan de AV-periode (`vme.association._get_assembly_period`) binnen het
  mandaat begint.
- `renewal_state`: `renewed` (er is een mandaat met dit als vorige), `expired`, `decided` (agendapunt aangenomen),
  `urgent` (≤ 2 maanden vóór de periode), `plan` (≤ 6 maanden), anders `ok`.
- `vme.assembly.create` (overschrijving): een nieuwe gewone AV van het herbenoemingsjaar krijgt meteen het agendapunt
  `RENEWAL_ITEM_TITLE` (absolute meerderheid, `LEGAL-CHECK`). `action_add_renewal_item` doet hetzelfde voor een AV die
  al bestaat. De AV-planner maakt AV's met `create`, dus ook daar komt het punt vanzelf.
- `action_renew` maakt het volgende mandaat (begin = einde + 1 dag) en weigert als het agendapunt bestaat maar niet
  aangenomen is.
- Cron `ir_cron_syndic_mandate` (dagelijks): `_cron_schedule_mandate_activities` maakt één taak per mandaat voor de
  herbenoeming en voor een ontbrekende aanplakking (zelfde `summary` = geen dubbele taak).
- Aanplakking (`LEGAL-CHECK` art. 3.89 §2 BW): rapport `report_syndic_posting`; `action_make_posting` bewaart de PDF als
  `vme.document` in de map `folder_syndic` (zichtbaar in het portaal); `posting_deadline` = begin + 8 dagen.

### Voor de jaarcyclus

De jaarcyclus leest het mandaat via `vme.association._get_syndic_mandate_on(day)` en de velden
`renewal_assembly_year`, `renewal_period_start` en `renewal_state` op `vme.syndic.mandate`; het agendapunt herkent
hij aan `vme_belgie.models.vme_syndic.RENEWAL_ITEM_TITLE`.

## Toegang

ACL voor `base.group_user`, zoals de andere VME-modellen. De commissaris (`group_vme_auditor`) leest overeenkomsten,
prijslijst, prestaties en mandaten van zijn eigen VME's en wijzigt niets (`vme_syndic_security.xml`, zelfde patroon als
stap 16). Het menu **VME > Syndicus** is er alleen voor `account.group_account_invoice`.

## Demo

`_load_demo_syndic` (in `_load_demo_data`, vóór de AV's, de verkoop en de werken, zodat die hun prestaties registreren):
kantoor "Syndicus Voorbeeld BV", fictieve consumptieprijsindex (december 2023 – oktober 2026), drie overeenkomsten,
drie mandaten (Linde: herbenoeming 2027 te plannen; Kaaihuis: aanplakking te laat), twee handmatige prestaties.
`_load_demo_syndic_history` (na de demohistoriek): ereloonfacturen van het derde kwartaal 2026, bevestigd in het kantoor.
De leveranciersfacturen in de VME's blijven concept: de kosten en de jaarafrekening van het demojaar veranderen niet
(`test_syndic_fee_bills_stay_drafts` en de bestaande `vme_slow`-tests).

## Valkuilen

- **`account.account.code` is per company.** Lees de code van een rekening van een andere company met
  `account.with_company(company).code`, anders is ze `False`.
- **`_register` is van Odoo.** Zie hierboven.
- **Prijs zonder indexcijfer.** Zie "Indexering".

## Open punten

- Doorrekenen van de kosten van het verkoopdossier aan de verkoper (nu alleen `recharge_partner_id`).
- Garages aan een ander tarief dan appartementen (nu telt elke kavel even zwaar).
- Btw-regime van het kantoor (nu altijd 21%) en de niet-aftrekbare btw van de VME (stap 26).
