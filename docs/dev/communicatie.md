# Centrale communicatie (stap 23)

Code: `models/vme_communication.py` (modellen en koppelingen met andere stappen), `models/communication_providers.py` (provider-interface met mocks), sjablonen, volgnummer en systeemparameters in `data/communication_data.xml`, de brief in `report/vme_communication_reports.xml`, views en menu's in `views/vme_communication_views.xml`, tests in `tests/test_communication.py`.

## Datamodel

```
vme.communication.template ──(kopie bij keuze)──> vme.communication ──< vme.communication.option
                                                       │
                                                       └──< vme.communication.log >── res.partner
                                                                 │        ▲
                                                                 │        └── ook: vme.assembly.convocation,
                                                                 │                 vme.collection.reminder (source_model/source_id)
                                                                 └──> vme.registered.mail ──> ir.attachment (PDF)
```

| Model | Rol |
| --- | --- |
| `vme.communication` | Verzending: VME, soort (`message`, `survey`), selectie (`audience`: `all_owners`, `block`, `lots`, `tenants`, `partners`), `reference_date` (eigenaar op), gevraagd kanaal (`preference`, `letter`, `registered`, `sms`, `push`), tekst met plaatshouders, korte tekst voor sms en push, vraag en antwoorden. Status `draft` → `sent` (of `cancel`). Erft `mail.thread`. `sale_file_id` voor de welkomstbrief. |
| `vme.communication.option` | Mogelijk antwoord op een bevraging, met `answer_count`. |
| `vme.communication.log` | Communicatielog: één lijn per ontvanger en per verzending, met het echte kanaal (`email`, `letter`, `registered`, `sms`, `push`), de gerenderde tekst, status en verzenddatum, en per kanaal de `mail_id`, de `provider_reference` of de `registered_mail_id`. Voor een bevraging ook `answer_option_id`, `answer_note`, `answer_date`. Lijnen van andere stappen hebben geen verzending maar `source_model`, `source_id` en `source_name`. |
| `vme.registered.mail` | Verzendregister aangetekend: volgnummer (`ir.sequence` `vme.registered.mail`, `AT/%(year)s/0001`), bestemmeling, adres als tekst op het moment van verzending, onderwerp, PDF, `provider` (`post` of `electronic`), zendingsnummer, status `prepared` → `deposited` → `delivered` of `returned`. |
| `vme.communication.template` | Sjabloon; `option_names` is één antwoord per regel. Vier sjablonen in `noupdate`-data: welkomstbrief, mededeling werken, waterafsluiting (sms), bevraging laadpalen. |
| `res.partner` (uitbreiding) | `vme_communication_preference` (`email`, `paper`), de loglijnen en een slimme knop. |
| `vme.lot` (uitbreiding) | `building_block` (Blok) en de koppelplaats `_get_tenants_on(date)`. |

## Selectie van ontvangers

`vme.communication._get_recipients()` geeft `[(partner, lots, role)]`, één item per persoon, in de volgorde van de kavels:

- `all_owners`, `block`, `lots`: per kavel `lot._get_owner_on(reference_date)`. Zo krijgt na een verkoop de koper het bericht en de verkoper niet. Iemand met een appartement en een garage krijgt één bericht met beide kavels. Het blok wordt vergeleken zonder hoofdletters en spaties.
- `partners`: de gekozen personen, met hun kavels op de datum (bij een welkomstbrief alleen de kavels van de verkoop). Wie geen kavel heeft, krijgt rol `other`.
- `tenants`: `lot._get_tenants_on(reference_date)` per kavel, rol `tenant`.

`_resolve_channel(partner)` bepaalt per persoon het kanaal:

| Gevraagd | Resultaat |
| --- | --- |
| `preference` | `email` als de voorkeur niet `paper` is en er een e-mailadres is, anders `letter` |
| `letter`, `registered` | altijd dat kanaal, de voorkeur speelt niet |
| `sms` | `sms` als `partner.phone` gevuld is, anders zoals `preference` |
| `push` | `push` als `PushProvider.can_reach(partner)`, anders zoals `preference` |

### Koppelplaats voor huurders (stappen 19 en 25)

Huurders bestaan nog niet. `vme.lot._get_tenants_on(date)` geeft voorlopig een lege `res.partner`-recordset terug. Het huurbeheer overschrijft die methode, bv.:

```python
class VmeLot(models.Model):
    _inherit = "vme.lot"

    def _get_tenants_on(self, date):
        leases = self.env["vme.lease"].search([
            ("lot_id", "in", self.ids), ("date_start", "<=", date),
            "|", ("date_end", "=", False), ("date_end", ">=", date),
        ])
        return leases.tenant_id
```

Meer is niet nodig: de selectie "Huurders", het log en de kanalen werken dan meteen. De test `test_tenants_come_from_the_hook` vervangt de methode met `patch.object` en laat zien wat er verwacht wordt. Wie later "eigenaars en huurders van blok A" wil, voegt een vinkje toe dat in `_get_recipients` ook de huurders van `_get_target_lots()` toevoegt.

## Van concept tot verstuurd

1. **Ontvangers ophalen** (`action_prepare_recipients`): verwijdert de conceptlijnen (`sudo`, want gebruikers mogen loglijnen niet verwijderen) en maakt ze opnieuw, met de tekst per ontvanger (`_render_logs`). Er wordt niets verstuurd en er komt geen `mail.mail`.
2. **Bevestigen en versturen** (`action_confirm`): haalt de ontvangers op als dat nog niet gebeurde, rendert de tekst opnieuw (de medewerker kan na het ophalen nog aan de tekst gewerkt hebben) en roept `log_ids._send()` op:
   - `email`: een `mail.mail` in de wachtrij van Odoo (`auto_delete=False`), van het e-mailadres van de company van de VME of anders van de gebruiker. De cron "Mail: Email Queue Manager" verstuurt ze.
   - `letter`: na de lus één PDF met alle brieven (`letter_attachment_id`).
   - `registered`: per lijn een PDF en een lijn in het register.
   - `sms`, `push`: via de provider; de referentie komt in het log.
3. De verzending gaat naar `sent` met een bericht in de chatter met het aantal per kanaal.

Plaatshouders (`{eigenaar}`, `{kavels}`, `{vme}`, `{adres_vme}`, `{datum}`) worden met `str.replace` ingevuld, met `markupsafe.escape` op de waarden. We gebruiken bewust geen `mail.template`: een medewerker zonder de groep "Mail Template Editor" mag geen dynamische inline templates renderen, en eenvoudige plaatshouders zijn voor een syndicus duidelijker dan `{{ object.partner_id.name }}`.

Een bevraging voegt onderaan de tekst de vraag, de antwoorden als lijst en de uiterste datum toe (`_survey_html`). Antwoorden worden in de lijst **Ontvangers en antwoorden** per eigenaar gekozen; `write` vult `answer_date` als die leeg is. Antwoorden via het portaal (stap 27) schrijven hetzelfde veld via `vme.communication.log._portal_answer`, met `answer_channel = portal`; een antwoord dat een medewerker ingeeft, krijgt `manual` (in `write`). `_render_logs` voegt voor ontvangers met een portaallogin een link `/my/vme/survey/<log_id>` toe aan de tekst.

## Provider-interface

`models/communication_providers.py` definieert drie abstracte klassen en hun mock:

| Soort | Interface | Mock |
| --- | --- | --- |
| `sms` | `send(number, text) -> reference` | logt, geeft `MOCK-SMS-...` |
| `push` | `can_reach(partner)`, `send(partner, title, text) -> reference` | bereikbaar als de partner een gebruiker heeft; geeft `MOCK-PUSH-...` |
| `registered` | `submit(registered_mail, pdf_content) -> reference`, `get_status(reference)` | geeft `MOCK-ERDS-...`, status altijd `delivered` |

`get_provider(env, kind)` leest de systeemparameter `vme_belgie.<kind>_provider` (standaard `mock`) en zoekt de klasse in `PROVIDERS`. Een echte provider is een subklasse die je in `PROVIDERS` registreert, met de sleutel in een systeemparameter of in de omgeving, nooit in de code.

### Een echte dienst voor elektronisch aangetekend verzenden

Zo zou een koppeling werken (niet gebouwd):

1. Een gekwalificeerde verlener van elektronische aangetekende bezorgdiensten (eIDAS, op de Belgische vertrouwenslijst) geeft een API-sleutel per syndicus. De VME is de afzender; de syndicus verstuurt namens haar.
2. `submit` stuurt de PDF met de identiteit van de bestemmeling (naam, e-mailadres, eventueel rijksregisternummer voor een identificatie met itsme of eID) en krijgt een zendingsnummer en een bewijs van verzending terug. Dat bewijs bewaren we als bijlage bij de registerlijn.
3. De bestemmeling krijgt een melding en moet zich identificeren om de zending te openen. De dienst geeft dan een bewijs van ontvangst; weigert of opent de bestemmeling niet binnen de termijn, een bewijs van niet-afhaling.
4. `get_status` (of een webhook van de dienst) zet de registerlijn op `delivered` of `returned` en bewaart het bewijs. Een cron zou dat dagelijks doen; in het prototype is het de knop **Status ophalen**.
5. Kan de bestemmeling niet elektronisch bereikt worden (geen e-mailadres, geen akkoord), dan blijft de papieren weg: afgeven bij de post, zendingsnummer en ontvangstbewijs met de hand.

`# LEGAL-CHECK:` (op het veld `provider` van `vme.registered.mail`): verordening (EU) 910/2014 art. 43-44 en art. XII.25 §3 WER. Na te kijken is of een elektronische aangetekende zending geldt voor een ingebrekestelling (art. 5.231 BW) en voor een oproeping tot de AV (art. 3.87 §3 BW), en of de bestemmeling daarvoor vooraf moet instemmen.

## Koppelingen met andere stappen

| Stap | Hoe | Wat we niet veranderen |
| --- | --- | --- |
| 9, verkoop | `vme.sale.file.action_deed_done` roept na `super()` `_create_welcome_letter` op: een conceptverzending (`audience = partners`, de koper, `reference_date` = aktedatum) uit het sjabloon `communication_template_welcome`, met de ontvangers al opgehaald. Bericht met link in de chatter van het dossier, knop **Welkomstbrief**. | De overdracht van de eigendom. |
| 10, invordering | `vme.collection.reminder.action_mark_sent` roept eerst `super()` op en maakt dan een loglijn. Niveau 3 (ingebrekestelling) krijgt kanaal `registered`, een PDF van het bestaande rapport `action_report_collection_reminder` en een registerlijn (`registered_mail_id`). Knop **Aangetekend versturen** (`action_send_registered`) in het formulier. | Niveaus, termijnen, kosten, het versturen per e-mail of per post. |
| 11, AV | `vme.assembly.convocation.create` maakt per oproeping een conceptlijn in het log (kanaal volgens voorkeur); `action_mark_sent` zet ze op verstuurd, met kanaal `email` als de context `mark_convocation_as_sent` (de composer) gezet is en anders `letter`. | De oproeping, de PDF's en de composer. |
| 15 en 27, portaal | Push via `PushProvider`; antwoorden op bevragingen via `_portal_answer` (stap 27, zie [portaal.md](portaal.md#aanvragen-en-bevragingen-stap-27)). | |
| 19 en 25, huurders | `vme.lot._get_tenants_on(date)` overschrijven. | |

## LEGAL-CHECK-punten

- `art. 3.87 §3 BW` (in `_resolve_channel`): oproeping per aangetekende brief, tenzij de eigenaar individueel, uitdrukkelijk en schriftelijk instemt met een ander middel. Het akkoord staat op de contactpersoon (`vme_convocation_consent_date`); de oproeping kiest daarmee `channel` `email` of `registered` (zie `docs/dev/algemene-vergadering.md`). Het akkoord geldt per persoon, niet per VME.
- `art. 5.231 BW` (in `VmeCollectionReminder.action_mark_sent`): de ingebrekestelling aangetekend.
- `eIDAS art. 43-44, art. XII.25 §3 WER` (veld `provider`): geldigheid van elektronisch aangetekend.

## Valkuilen

- Twee velden met hetzelfde label geven een waarschuwing bij het laden (`log_ids` en `audience` heetten allebei "Ontvangers"); het one2many-veld heet daarom "Ontvangerslijnen".
- `Html`-velden bewaren `Markup`. `render_placeholders` werkt op de string en geeft opnieuw `Markup` terug; daarom moeten de waarden zelf ge-escaped worden.
- Een PDF renderen kost ongeveer 2 seconden. Brieven per post worden in één PDF samen gerenderd; alleen aangetekende brieven krijgen elk een eigen PDF, omdat elke registerlijn haar eigen bewijs nodig heeft.
- Een welkomstbrief zonder `sale_file_id` zou alle kavels van de koper in de VME noemen, ook kavels die hij al had; daarom gebruikt `_get_recipients` bij een verkoop alleen de kavels van het dossier.

## Tests

`tests/test_communication.py` (20 tests): selectie van eigenaars, eigenaar op datum voor en na een verkoop, blok, kavels, gekozen personen, huurders via de koppelplaats, kanaal per voorkeur en terugval (papier, geen e-mailadres, sms zonder nummer, push zonder account), concept verstuurt niets, bevestigen per kanaal met log en register, elektronisch aangetekend via de mock, bevraging met antwoorden, welkomstbrief na de akte, ingebrekestelling in het register en oproepingen in het log.

## Uitbreidingen voor later

- Akkoord van de eigenaar voor oproepingen per e-mail (datum en bewijs) en de oproepingen van stap 11 als verzending laten lopen.
- Een echte sms-dienst en elektronisch aangetekend verzenden, met de bewijzen als bijlage.
- Huurders en eigenaars samen per blok.
- Bijlagen (plannen, offertes) bij een verzending en documenten delen via het portaal (stap 15).
