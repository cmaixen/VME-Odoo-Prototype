# Aanvragen van bewoners (stap 19)

Code: `models/vme_request.py` (aanvraag, type, checklist, `account.move.vme_request_id`), `models/vme_lot_contact.py` (huurders en bewoners, sleutelregister, slotenmaker op de VME), `data/request_data.xml` (nummering en de acht types), `report/vme_request_reports.xml` (bestelbon), `views/vme_request_views.xml`, demo `demo_data/vme_demo_requests.py`, tests `tests/test_requests.py`. In `ai/`: `REQUEST_TYPES` in `classifier.py`, `create_request` in `odoo_api.py`.

## Datamodel

| Model | Wat |
| --- | --- |
| `vme.request.type` | Eén record per procedure (`code`, uniek): `key`, `badge_lost`, `move`, `new_tenant`, `works_permission`, `damage`, `document`, `nuisance`. `needs_verification` (alleen `key` staat aan), `checklist` (tekst, één stap per regel), `description`. Data met `noupdate`, dus aanpasbaar per kantoor. |
| `vme.request` | Aanvraag met `mail.thread` en activiteiten. VME, kavel, type, `channel` (`mail`, `portal`, `manual`), `source_reference` (Message-ID), `requester_id`, `requester_role` (`owner`, `tenant`, `unknown`; opgeslagen compute, aanpasbaar), `owner_id` (eigenaar op `request_date`), `state`, checklist `check_ids`. Bewijs: drie booleans `proof_*`, `proof_attachment_ids`, `proof_requested_date`, `proof_reminder_date`. Sleutel: `key_kind`, `quantity`, `unit_price`, `amount`, `order_*`, `key_numbers`, `invoice_id`. Andere procedures: `blocked_key_ids`, `planned_date`, `tenant_partner_id`, `decision_route`, `assembly_item_id`. |
| `vme.request.check` | Stap van de checklist, gekopieerd uit het type bij `create`. |
| `vme.lot.contact` | Contact per kavel met `role` (`tenant`, `occupant`, `contact`) en `date_start`/`date_end`. Stap 25 (huurcontracten) koppelt een contract aan een contact met rol `tenant`. |
| `vme.lot.key` | Sleutelregister: kavel, `kind` (veiligheidssleutel inkom, sleutel garagepoort, afstandsbediening, badge), `number`, `issue_date`, `partner_id` ("in handen van"), `state` (`active`, `blocked`, `returned`), `request_id`. |
| `vme.association` | `locksmith_partner_id` (leveranciersrol, zoals de onderhoudsfirma bij een installatie), `key_certificate_ref`, `key_certificate_file`. |
| `vme.lot` | `contact_ids`, `key_register_ids`, `request_ids`, `_get_tenants_on(date)`. |
| `account.move` | `vme_request_id`. |

Statussen: `new` → `waiting_proof` → `in_progress` → `ordered` (alleen `key`) → `done`, of `refused`/`cancelled`. Een type zonder verificatie gaat bij `create` meteen naar `in_progress`.

## Intake: één ingang voor mail, portaal en manueel

`vme.request.create_from_intake(association_id, request_type, email, name, lot_id, subject, body, channel, reference, summary, proposed_reply, attachments)` is publiek (geen `_`), zodat de AI-assistent het via JSON-RPC kan aanroepen. Het portaal (stap 15) gebruikt dezelfde methode met `channel="portal"`.

1. Bestaat er al een aanvraag met dezelfde `reference`, dan geeft het die id terug.
2. `_identify_in(vme, email, lot)` vergelijkt het genormaliseerde adres (`email_normalize`) eerst met de eigenaars op vandaag, dan met de huurders op vandaag. Met een kavel kijkt het alleen naar die kavel: de eigenaar van A2 die een badge voor A1 vraagt, is "onbekend". Zonder kavel neemt het de kavel van die eigenaar of huurder.
3. Een onbekend adres wordt een nieuwe `res.partner` (naam uit de mail).
4. Bij `key` raadt `KEY_KIND_WORDS` de soort uit onderwerp en tekst; standaard de veiligheidssleutel van de inkom.
5. De aanvraag wordt aangemaakt met context `vme_request_defer_start`, de mail komt met bijlagen als notitie in de chatter (de bijlagen ook in `proof_attachment_ids`), het voorgestelde antwoord van de AI als tweede notitie, en pas dan start `_start_procedure()`. Zo leest de chatter in de juiste volgorde.

Een manuele aanvraag start de procedure in `create()`; de rol komt dan uit het e-mailadres van de gekozen aanvrager.

## Verificatie en berichten

`REQUIRED_PROOFS` per rol: eigenaar niets, huurder toestemming van de eigenaar en huurcontract, onbekend een eigendomsbewijs. `needs_verification` is `type.needs_verification and role != "owner"`.

Er vertrekt nooit iets vanzelf. Elke uitgaande mail loopt via `_post_to()`, dat `message_post` met `partner_ids` en subtype `mail.mt_comment` doet, en wordt alleen vanuit een knop aangeroepen:

| Knop | Methode | Daarna |
| --- | --- | --- |
| Bewijs opvragen | `action_send_proof_request` | `proof_requested_date`, To-do "Herinnering" op +7 dagen (`PROOF_REMINDER_DAYS`) |
| Herinnering versturen | `action_send_proof_reminder` | `proof_reminder_date`, To-do "Bewijs opvolgen of aanvraag weigeren" op +7 dagen |
| Bewijs goedkeuren | `action_verify` | `UserError` zolang een vereist bewijs niet aangevinkt is; anders `_mark_verified()` |
| Bestelling versturen | `action_send_order` | Bestelbon en eventueel een kopie van het sleutelcertificaat als bijlage; status `ordered`, To-do levering op +14 dagen |

`reminder_due` (niet opgeslagen) en de filter "Herinnering nodig" zijn waar als het bewijs 7 dagen geleden gevraagd werd zonder herinnering. Er is geen cron: de To-do met vervaldatum is de herinnering voor de medewerker.

De concepten staan als bewerkbare velden op de aanvraag (`proof_mail_body`, `order_mail_subject`, `order_mail_body`), in het tabblad Berichten.

## Bestelling bij de slotenmaker en de open beslissing

`_mark_verified()` roept bij `key` `_prepare_order()` aan: de PDF `vme_belgie.action_report_request_order` wordt een bijlage op de aanvraag (`order_attachment_id`) en de conceptmail wordt ingevuld. Zonder slotenmaker op de VME komt er een To-do "Slotenmaker instellen" en de knop **Bestelling opnieuw opmaken**.

Daarna blijft de bestelling een concept met een To-do "Bestelling slotenmaker nakijken en versturen"; alleen **Bestelling versturen** (`action_send_order`) stuurt ze. Er is bewust geen haak of instelling om dat te automatiseren: een mens beslist altijd (harde regel in `CLAUDE.md`). Ook aanvragen uit het portaal (stap 27) eindigen in een taak of concept voor een medewerker. `test_order_never_leaves_by_itself` en de portaaltests bewaken dit.

## Levering en privé-aanrekening

`action_register_delivery()` controleert dat er evenveel nummers als stuks zijn, maakt per nummer een `vme.lot.key` op naam van de aanvrager en roept `_create_private_invoice()` aan.

De privé-aanrekening is een gewone verkoopfactuur (`out_invoice`) in de company van de VME:

- aan `owner_id`, de eigenaar van de kavel op de datum van de aanvraag, ook als een huurder de aanvraag deed;
- één regel op rekening **416100 Door te rekenen privékosten** (`PRIVATE_CHARGE_ACCOUNT`, type `asset_current`), zonder btw: de prijs is inclusief btw, want voor een VME is de btw een kost;
- `vme_fund = "working"`, dus betaalbaar op de rekening van het werkkapitaal en met de gestructureerde mededeling uit het factuurnummer;
- `vme_request_id` gezet en meteen geboekt.

Waarom 416100 en geen opbrengstrekening: de leveranciersfactuur van de slotenmaker hoort op dezelfde rekening. Dan is 416100 na beide facturen nul en komt de kost nooit in de kosten van de VME, dus ook nooit in de verdeling over de eigenaars. De rekening bestaat niet in het Belgische PCMN van Odoo en wordt de eerste keer aangemaakt (`_private_charge_account(company)`).

De leveranciersfactuur van de slotenmaker koppelt de medewerker aan de aanvraag met het veld **Aanvraag** op de factuur. Een factuur met `vme_request_id`:

- wordt niet automatisch verdeeld (`account.move._vme_auto_distribute` filtert ze weg);
- telt niet mee in de jaarafrekening (domein in `_get_annual_statement`), dus ook niet als "niet verdeelde factuur".

De medewerker moet de regel van die factuur zelf op 416100 zetten; een verdeelregel voor de slotenmaker zou anders 611000 of de rekening van de regel kiezen. Een onbetaalde privé-factuur komt vanzelf in de invordering (stap 10), want die kijkt naar alle open debiteurenlijnen.

## Andere procedures

| Type | Methode | Wat |
| --- | --- | --- |
| `badge_lost` | `action_block_keys` | Zet de gekozen registerlijnen op `blocked` met datum en chatterbericht. |
| `new_tenant` | `action_register_tenant` | Maakt een `vme.lot.contact` met rol `tenant` vanaf `planned_date`. `# LEGAL-CHECK: art. 3.93 BW` (reglement van orde voor huurders). |
| `works_permission` | `action_add_to_assembly` | Agendapunt op de eerstvolgende AV in status `draft`, `proposed` of `confirmed`, met meerderheid `WORKS_PERMISSION_MAJORITY` (twee derde, `# LEGAL-CHECK: art. 3.88 §1, 1°, b) BW`). |
| `damage` | `_forward_damage` | Koppelplaats voor stap 14, zie hieronder. |
| `move`, `document`, `nuisance` | | Alleen de checklist en **Afgehandeld**. |

## Koppelplaatsen voor andere stappen

- **Portaal (stap 27):** `res.partner._vme_portal_create_request` roept `create_from_intake(..., channel="portal", requester_id=partner.id, user_id=admin)` aan, als sudo. De herkenning en de procedure zijn dezelfde als per mail; `requester_id` zet de ingelogde partner als aanvrager en `user_id` houdt de verantwoordelijke (en dus de taken) bij een medewerker, want onder sudo is `env.user` de portaalgebruiker. Status (`portal_state`), berichten (`_portal_messages`) en bewijs opladen (`_portal_add_proof`) staan in `models/vme_portal_requests.py`; zie [portaal.md](portaal.md#aanvragen-en-bevragingen-stap-27). Geen `portal.mixin`: dat zou toegangstokens en de chatter van Odoo openen, terwijl we interne notities juist verborgen willen houden.
- **Schadedossiers (stap 14):** `_forward_damage()` kijkt of het model `vme.damage.claim` bestaat en een methode `_create_from_request(request)` heeft. Zo ja, dan maakt die het dossier en komt er een link in de chatter; zo nee, dan krijgt de medewerker een To-do. Stap 14 hoeft dus alleen die methode toe te voegen. Bij het samenvoegen: stap 14 stuurt lekmails mogelijk zelf naar een schadedossier; kies dan één route (voorkeur: de AI maakt een aanvraag `damage`, de aanvraag maakt het dossier).
- **Huurcontracten (stap 25):** een contract verwijst naar een `vme.lot.contact` met rol `tenant`, of maakt er een bij de start van de huur. De verificatie leest alleen `vme.lot.contact`, dus een contract hoeft niets aan de aanvragen te veranderen.
- **Raad van mede-eigendom (stap 16):** `decision_route = "council"` is nu alleen informatief; een vraag om advies aan de raad kan daar later een record maken.

## AI-assistent

`classifier.RESULT_SCHEMA` heeft een veld `request_type` (een code uit `REQUEST_TYPES` of `none`). De prompt beschrijft de acht soorten; `validate()` zet een onbekende code op `none`. De mock herkent de soort met woordgroepen (`MOCK_REQUEST_WORDS`, elke groep moet voorkomen) en herkent huurders aan hun adres.

`VmeDirectory.load()` leest ook de huurders van vandaag (`vme.lot.contact` met rol `tenant`) en zet ze per kavel onder `tenants`, zodat het taalmodel en de mock een huurder aan zijn kavel koppelen. `mails.py` leest de bijlagen van een `.eml`. Is `request_type` niet `none`, dan roept `assistant.run()` `directory.create_request()` aan in plaats van een activiteit te maken; het voorgestelde antwoord gaat mee als notitie. Een mail die al een aanvraag of een activiteit heeft, wordt overgeslagen.

## Demo

`_load_demo_requests()` (aangeroepen vanuit `_load_demo_data`): Slotenmaker Voorbeeld BV als slotenmaker van de drie VME's, een fictief certificaatnummer per VME, huurders op Linde A6, Beuken B12 en Kaaihuis K2, en een register (Linde: veiligheidssleutel en badge per appartement, afstandsbediening per garage; Beuken: badge per appartement; Kaaihuis: veiligheidssleutel per appartement). De drie mails `ai/inbox/06` tot `08` geven de drie demo-aanvragen: eigenaar Linde A4, huurder Linde A6 zonder bewijs, huurder Beuken B12 met toestemming en huurcontract als PDF-bijlage.

## Tests

`tests/test_requests.py` (19 tests, freezegun op 5 november 2026): verificatie van eigenaar, eigenaar van een andere kavel, huurder zonder en met toestemming, onbekende; manuele aanvraag; dezelfde mail één keer; bewijsvraag en herinnering na 7 dagen; bestelling met één klik en de haak voor automatisch versturen; geen slotenmaker; levering met register en privé-factuur (bedrag, rekening, partner, fonds, geen btw); leveranciersfactuur niet verdeeld en niet in de jaarafrekening; badge blokkeren; huurder registreren; agendapunt op de AV; schade; register in het verkoopdossier en overdracht bij de akte. In `ai/tests`: de drie nieuwe mails, bijlagen lezen, de soorten van de mock, `validate()`, `run()` met aanvragen, en `VmeDirectory` met huurders en `create_request`.

## Valkuilen

- De code van een rekening hangt in Odoo 19 af van de company: lees `account_id.with_company(company).code`, anders is ze `False`.
- `env.get(model)` bestaat niet op een Odoo-environment; gebruik `model in env`.
- Odoo verwerkt de bijlage van `message_post(attachment_ids=...)` alleen als ze al aan het record hangt of nog nergens aan hangt; daarom wordt de kopie van het sleutelcertificaat eerst gekopieerd naar de aanvraag.
