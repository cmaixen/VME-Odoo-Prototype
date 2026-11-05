# AI-assistent voor mails (`ai/`)

Een los Python-script naast Odoo, geen Odoo-module: het praat met Odoo via de JSON-RPC-API en met Claude via de Anthropic API. Zo blijft de AI-laag los van de Odoo-versie (zie `docs/beslissingen.md`). Gebruik en installatie: `ai/README.md`.

## Flow

```
ai/inbox/*.eml|*.txt ──> mails.py ──> assistant.run() ──> classifier ──> odoo_api ──> mail.activity op vme.association
                                         ▲                    │
                     odoo_api.VmeDirectory.load()             └─ Claude (claude-opus-5-5) of MockClassifier
```

1. `mails.read_inbox()` leest elke `.eml` (standaard e-mailformaat) of `.txt` (optionele kopregels `Van:`, `Onderwerp:`, `Datum:`, `Message-ID:`, dan een lege regel en de tekst).
2. `VmeDirectory.load()` haalt in drie `search_read`-aanroepen alle VME's, kavels met hun huidige eigenaar (`vme.lot.current_owner_id`, berekend op vandaag) en de e-mailadressen van die eigenaars op. Over alle companies heen: de context krijgt `allowed_company_ids` = alle companies van de gebruiker, want elke VME is een eigen company.
3. Per mail bepaalt de classifier VME, kavel, eigenaar, onderwerp, dringendheid en zekerheid, met een samenvatting, een uitleg van de koppeling en een conceptantwoord.
4. `classifier.validate()` controleert de uitkomst tegen de directory: een onbekende VME-id of een kavel van een andere VME wordt weggegooid en de zekerheid gaat naar `low`. Het taalmodel kan dus nooit een activiteit op een record zetten dat het niet in de lijst kreeg.
5. `VmeDirectory.create_activity()` roept `activity_schedule` aan op `vme.association` met type "To-do" (`mail.mail_activity_data_todo`). De HTML-notitie bevat de gegevens, het conceptantwoord en de oorspronkelijke mail, allemaal ge-escapet.

Zonder VME maakt het script niets aan (een activiteit heeft een record nodig) en meldt het de mail als manueel te behandelen.

## Aanvragen met een vaste procedure (stap 19)

De classificatie heeft een veld `request_type` (`REQUEST_TYPES` in `classifier.py`, dezelfde codes als `vme.request.type`, of `none`). Is het niet `none`, dan maakt `run()` geen activiteit maar roept `VmeDirectory.create_request()` → `vme.request.create_from_intake` aan, met de bijlagen van de mail (base64) en het voorgestelde antwoord als notitie. Odoo herkent de aanvrager zelf aan het e-mailadres en start de procedure; zie [aanvragen.md](aanvragen.md). `load()` leest daarvoor ook de huurders van vandaag (`vme.lot.contact`, rol `tenant`) en zet ze per kavel onder `tenants`. Een mail met een aanvraag of een activiteit wordt bij een tweede run overgeslagen (`find_request` op `source_reference`).

## Nooit iets versturen

Het script heeft geen code om mails te versturen: het maakt alleen `mail.activity`-records. `activity_schedule` stuurt ook geen mail naar de eigenaar; hoogstens krijgt de toegewezen medewerker de gewone Odoo-melding van een nieuwe activiteit. Wie later "Bericht verzenden" gebruikt, doet dat bewust zelf.

## Classifiers

- **`ClaudeClassifier`**: één `client.beta.messages.create`-aanroep per mail.
  - Model `claude-opus-5-5`, `output_config.effort = "medium"` (de standaard op dit model; expliciet gezet).
  - Gestructureerde uitvoer via `output_config.format` met het JSON-schema `RESULT_SCHEMA`: het antwoord is gegarandeerd geldige JSON met de juiste velden en enums.
  - De systeemprompt bevat de instructies plus de volledige directory als JSON, met `cache_control`: voor alle mails van één run is dat dezelfde prefix, dus vanaf de tweede mail wordt ze uit de cache gelezen. De mail zelf is het enige gebruikersbericht.
  - Server-side fallback (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`): als een veiligheidsfilter weigert, probeert de API zelf een geschikt ander model. Weigert ook dat, dan is `stop_reason == "refusal"` en meldt het script de mail als manueel te behandelen.
  - Promptinjectie: de prompt zegt dat de mail gegevens zijn en geen opdracht. De echte bescherming is dat de uitkomst alleen een concept is dat een mens nakijkt, en dat `validate()` alleen id's uit de directory toelaat.
- **`MockClassifier`**: regels zonder taalmodel, voor demo's en tests zonder API-sleutel. Afzenderadres van een gekende eigenaar → die kavel (de kavel die in de tekst genoemd wordt, anders de eerste); anders gebouwnaam plus kavelnummer in de tekst. Onderwerp via sleutelwoorden, antwoord uit vaste sjablonen.

## Dubbel verwerken vermijden

De `Message-ID` van de mail (zonder `<>`, die in HTML ge-escapet worden) of anders de bestandsnaam staat in de notitie. Voor elke mail zoekt het script een `mail.activity` op `vme.association` waarvan de notitie die referentie bevat; is er een, dan slaat het de mail over. `--force` schakelt dat uit. Een activiteit die als gedaan gemarkeerd is, bestaat niet meer als `mail.activity` (ze wordt een bericht in de chatter), dus na "gedaan" zou een nieuwe run de mail opnieuw voorstellen: verwerkte mails horen dan uit de inbox weg. Voor een echte mailbox komt daar later een eigen register.

## Wat er in de Odoo-module nodig was

`vme.association` erft nu van `mail.thread` en `mail.activity.mixin`, het formulier heeft een `<chatter/>`, en `mail` staat expliciet in `depends` (zat er al onrechtstreeks via `account`). Zonder die mixin kan een VME geen activiteiten dragen. Verder raakt het script de module niet aan.

## Valkuilen

- Odoo 19 kondigt aan dat `/jsonrpc` en `/xmlrpc` verdwijnen in Odoo 20 ten voordele van `/json/2` met API-sleutels. Voor het prototype volstaat `/jsonrpc`; bij een overstap moet alleen `OdooClient` herschreven worden.
- `activity_schedule` geeft een recordset terug en geen id; het script zoekt de nieuwe activiteit daarna op via VME en titel, zodat het niet afhangt van hoe Odoo een recordset over JSON-RPC doorgeeft.
- `anthropic` 2.x gebruikt `httpx2` in plaats van `httpx`; de test met de echte SDK en een nagebootste HTTP-laag gebruikt daarom `httpx2.MockTransport`.
- Python 3.10 of nieuwer is nodig (`int | None` in de dataclass, en de SDK).

## Testen

```bash
cd ai && .venv/bin/pytest -q
```

De tests draaien zonder API-sleutel en zonder Odoo:

- de acht mails in `ai/inbox/` worden gelezen (ook de PDF-bijlagen) en door de mock aan de juiste VME, kavel, onderwerp en soort aanvraag gekoppeld, ook een huurder via zijn adres;
- `run()` maakt voor de drie aanvragen een aanvraag in plaats van een activiteit; `VmeDirectory` leest de huurders en geeft de bijlagen door aan `create_from_intake`;
- `validate()` gooit onbekende of niet-passende id's weg;
- `ClaudeClassifier` met een nagebootste client (vorm van het verzoek, validatie, weigering) en met de echte SDK achter een nagebootste HTTP-laag (de SDK aanvaardt `fallbacks`, `betas` en `output_config`);
- `run()` met een nagebootste Odoo: één activiteit per mail, vervaldatum per dringendheid, overslaan bij een tweede run, niets schrijven bij `--dry-run` of zonder VME, HTML ge-escapet;
- `OdooClient` met een nagebootste JSON-RPC-server (login, `execute_kw`, foutmeldingen).

Live testen tegen een Odoo met demodata: `python assistant.py --mock --dry-run`, dan `python assistant.py --mock`, en de VME's openen in Odoo. Met een API-sleutel in `ai/.env` hetzelfde zonder `--mock`.

## Uitbreidingspunten

- Echte mailbox (IMAP of Odoo's eigen inkomende mail) in plaats van `ai/inbox/`, met een register van verwerkte mails.
- Meer context per mail voor betere antwoorden: openstaand saldo van de eigenaar, geplande AV (stap 6c), lopende schadedossiers (stap 13).
- Koppeling met een schadedossier bij een lek (stap 13 in `PROMPTS.md`).
- Frans: de prompt laten antwoorden in de taal van de mail.
