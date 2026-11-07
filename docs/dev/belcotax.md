# Fiches 281.50 en Belcotax-bestanden (XML en JSON Lines)

Per VME en inkomstenjaar een overzicht van wat de VME betaalde aan 281.50-plichtige leveranciers, nagekeken door een medewerker, met een bestand dat de medewerker zelf oplaadt in Belcotax-on-web: XML tot en met inkomsten 2025, JSON Lines vanaf inkomsten 2026. Odoo Community heeft hier niets voor (`l10n_be_reports` met de 281.50 is Enterprise); dit is eigen code.

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `models/vme_belcotax.py` | Velden op `res.partner`, `vme.belcotax.statement`, `vme.belcotax.line`, drempel en termijn |
| `models/belcotax_xml.py` | XML-bouwer zonder Odoo (tot inkomsten 2025), landcodes, controle van ondernemings- en rijksregisternummer, validatie tegen de XSD |
| `models/belcotax_jsonl.py` | JSON Lines-bouwer zonder Odoo (vanaf inkomsten 2026) en een kleine JSON Schema-validator |
| `data/belcotax/` | Officiële schema's van de FOD Financiën: `Belcotax-2025.xsd` en in `2026/` de JSON-schema's voor de 281.50 en de resources |
| `views/vme_belcotax_views.xml` | Tabblad "Fiche 281.50" op de partner, lijst en formulier, menu **VME > Fiches 281.50** |
| `security/vme_belcotax_security.xml` | Company-regels en regels van de commissaris voor beide modellen |
| `demo_data/vme_demo_belcotax.py` | Drie fictieve verkrijgers in 2026, aan het einde van de demohistoriek |
| `tests/test_belcotax.py` | Selectie, totalen, drempel, waarschuwingen, XML (2025) en JSON Lines (2026) tegen de officiële schema's, werkwijze |

## Datamodel

- `res.partner`: `vme_belcotax_liable` (281.50-plichtig), `vme_belcotax_category` (commission, fees, benefits, expenses), `vme_belcotax_profession`, `vme_national_number` (groep `account.group_account_invoice`). De partner is gedeeld tussen VME's, dus de vlag geldt overal.
- `vme.belcotax.statement`: één per VME en jaar (constraint), `state` draft → checked → filed, `checked_by_id`/`checked_date`, `filed_date`, `xml_file` (attachment). `deadline` en `threshold` zijn niet opgeslagen, zodat een gewijzigde termijn ook voor bestaande overzichten geldt.
- `vme.belcotax.line`: momentopname van de verkrijger (naam, adres, land, rechtspersoon, rijksregisternummer, ondernemingsnummer, btw-nummer, beroep), een bedrag per categorie, `amount_total` en `below_threshold` (opgeslagen), `warning` (opgeslagen tekst), `bill_ids`.

De regels zijn een kopie op het moment van berekenen, zodat een nagekeken overzicht niet verandert als iemand later de partner aanpast. **Opnieuw berekenen** wist de regels, zet het overzicht terug op "Na te kijken" en wist het bestand.

## Berekening

`_paid_by_partner()` zoekt de geboekte `in_invoice` en `in_refund` in de company van de VME waarvan de commerciële partner 281.50-plichtig is. Per factuur neemt het de `account.partial.reconcile` van de lijnen op de rekening te betalen (`matched_debit_ids | matched_credit_ids`) met `max_date` in het jaar. Een factuur telt positief, een creditnota negatief; een creditnota die met een factuur verrekend is, telt zo netto juist (de factuur ziet het deel, de creditnota trekt het af). Het bedrag is in de munt van de company en met btw.

Het hele bedrag gaat naar de categorie van de leverancier; een medewerker kan het in de regel over categorieën spreiden. `below_threshold` is `amount_total <= 250`. Het formulier telt alleen regels boven de drempel in `fiche_count`, `total_amount` en `warning_count`.

Het ondernemingsnummer komt uit `company_registry` of uit een Belgisch btw-nummer, ook voor een natuurlijke persoon (zelfstandige met een vrij beroep). Een buitenlands btw-nummer gaat apart mee in `vat`.

Waarschuwingen per regel (nooit blokkerend): adres onvolledig, land zonder RSZ-landcode in `RSZ_COUNTRY_CODES`, ondernemingsnummer ontbreekt of foute controlegetal (Belgisch bedrijf; buitenlands bedrijf zonder KBO- en btw-nummer), rijksregisternummer ontbreekt of foute controlegetal (ook de variant met prefix 2 voor geboren vanaf 2000), ondernemingsnummer van een persoon met fout controlegetal, beroep ontbreekt. `file_warning` op het overzicht meldt ontbrekende gegevens van de VME (KBO, adres), van de afzender (XML: telefoon, e-mail, KBO van het kantoor) of van de contactpersoon (JSON: e-mail).

Een nummer met een fout controlegetal gaat niet mee in het bestand: Belcotax-on-web weigert het hele bestand bij één fout nummer (en ook verzonnen nummers met een kloppend controlegetal, zoals die van de demo).

## Twee bestandsformaten

`uses_jsonl(year)` kiest: tot en met inkomsten 2025 XML, vanaf 2026 JSON Lines. De vernieuwde Belcotax-on-web (BOW 2.0, in productie vanaf februari 2027) aanvaardt de oude XML-structuur niet meer voor zendingen per bestand. `_belcotax_file()` bouwt het bestand, valideert het tegen de officiële schema's en geeft bij een fout een `UserError` met de eerste vijf meldingen (zoals `sepa_xml.py`).

### XML (tot inkomsten 2025)

`build_belcotax_xml(year, debtor, fiches, created, sender)` volgt de XSD "Belcotax 2025" (versie 2, 29.01.2026) en de brochure "Belcotax-on-web inkomsten 2025" (versie 3, 14.01.2026):

- `Verzending` (v0…): de **afzender** is wie inlogt in Belcotax-on-web, zijn KBO-nummer moet in 0.024. Dat is het kantoor van de syndicus (`current_agreement_id.syndic_company_id`, anders het eerste `is_syndic_office`), zonder kantoor de VME zelf. Telefoon, contactpersoon en e-mail zijn verplicht.
- `Aangifte` (a1…): de VME als schuldenaar; een naam langer dan 28 tekens loopt verder in `a1012_naamnl2`.
- `Fiche28150`: rechtspersoon → KBO in `f2011_nationaalnr` en `f50_2110_kbonbr` leeg; natuurlijke persoon → rijksregisternummer in 2.011 (niet verplicht) en KBO in 2.110. Landcode 0 voor België, anders de RSZ-code op vijf cijfers. `f50_2059_totaalcontrole` is de som van de zones 2.060 tot en met 2.088, dus 2.060 + 2.061 + 2.062 + 2.063 + 2.064. `f50_2065` blijft leeg: 2.064 is al het in het jaar betaalde bedrag, en 2.031 (nihil) is 1 als en alleen als 2.065 = 0.
- Sluitrecords: `r8010` = fiches + 2, `r8011` = som van de volgnummers 2.009, `r8012` = som van de 2.059; `r9010` = 3, `r9011` = fiches + 4, `r9012`/`r9013` = som van de r8011/r8012.
- Bedragen in eurocent, datum dd-mm-jjjj, lege facultatieve zones weggelaten, teksten afgekapt op de lengte uit de brochure (`LENGTHS`; de XSD heeft de lengtes uitgecommentarieerd en valideert ze dus niet).

### JSON Lines (vanaf inkomsten 2026)

`build_belcotax_jsonl(year, debtor, contact, fiches)` volgt de JSON-schema's "schemas preproduction BOW" (oktober 2026), de voorbeelden "ExamplesBelcotax2026" en de brochure "Pre-opening Belcotax-on-web" (versie 2, 03.11.2026). Eén JSON-object per regel:

1. contact (`urn:r:d:c:1`): de medewerker, met verplicht e-mailadres (gebruiker, anders het kantoor) en taal `nl`; telefoon alleen als `+32…`.
2. de VME als organisatie (`urn:r:d:o:1`) met `i.cbein` en adres.
3. per verkrijger een persoon (`urn:r:d:p:1`, `i.ssin` en `i.cbein`, de naam in `ln`) of organisatie (`i.cbein`, of `i.vat` voor een buitenlands bedrijf).
4. per verkrijger een fiche (`urn:f:d:2026:50:2`): `2010` volgnummer, de bedragen in euro in `2060`–`2063`, `2107` beroep, en de verwijzingen `b`, `c`, `d`. `2064` (totaal) is `readOnly`: Belcotax rekent het zelf.

Sleutels `k` zijn vast: `vme-28150-{jaar}-{company}-partner-{id}` voor een fiche, `vme-partner-{id}` voor een verkrijger. Een nieuwe zending met dezelfde sleutel vervangt de fiche in Belcotax, dus een verbeterd bestand opnieuw opladen werkt. De landcode is de RSZ-code op drie cijfers (België 150); zonder gekende landcode laat de bouwer het adres weg, want het schema vraagt dan een `l`.

De schema's van 2026 zijn pre-productie; de definitieve versie volgt eind 2026. Voor een later inkomstenjaar valideert `validate()` tegen de structuur van 2026 (met het eigen `$s`).

### Schema's en validatie

De bestanden in `data/belcotax/` zijn ongewijzigd overgenomen van https://financien.belgium.be/nl/E-services/Belcotaxonweb/technische-documentatie (november 2026): `161-xsd-2025-20260129.zip` en uit `161-schemas-preproduction-bow.zip` de schema's `fiche_2026_50_2_nl.json` en `resource_{contact,person,organisation}_nl.json`. Volgens https://fin.belgium.be/nl/gebruiksvoorwaarden is de informatie op die website vrij van rechten en onvoorwaardelijk herbruikbaar (gebaseerd op CC0); alleen multimedia vraagt toestemming. Bronvermelding wordt aangeraden, vandaar deze alinea.

De Odoo-image heeft geen `jsonschema`. `belcotax_jsonl.validate()` controleert daarom zelf de trefwoorden die deze schema's gebruiken (type, const, enum, oneOf, properties, additionalProperties, required, minimum, multipleOf, pattern, lengtes, items, minProperties, `$ref` naar `$defs`) en de unieke sleutel per zending. Alle 48 regels voor deze schema's in het officiële voorbeeldbestand `exampleBelcotax2026.jsonl` slagen. De zakelijke regels (bv. "rijksregisternummer of naam en adres") controleert Belcotax zelf na het opladen; het overzicht toont ze als waarschuwing.

Bij een nieuw inkomstenjaar: download de nieuwe XSD of JSON-schema's van dezelfde pagina, vervang ze in `data/belcotax/`, pas `SCHEMA_FILES` aan en draai de tests.

## Niets vertrekt vanzelf

Er is geen koppeling met Belcotax-on-web en geen cron. Downloaden kan pas na **Nagekeken**; **Opgeladen in Belcotax** is een vinkje dat de medewerker zelf zet na de upload. Alle knoppen roepen `check_not_auditor` aan.

## LEGAL-CHECK

- Art. 57, 1° WIB 92: welke vergoedingen (de vier categorieën) en "betaald of toegekend" (wij nemen betaald).
- Art. 30 KB/WIB 92, gewijzigd door het KB van april 2022 (circulaire 2022/C/96): drempel 250 euro per verkrijger per jaar.
- Termijn: 29 juni van het jaar erna volgens de brochure inkomsten 2025; de FOD bevestigt die elk jaar.
- Formaat: de brochures en schema's hierboven (codes, plaats van KBO- en rijksregisternummer, controletotalen, JSON Lines vanaf 2026, unieke sleutels).
- Art. 30bis van de RSZ-wet en art. 403 WIB 92 (inhoudingsplicht bij aannemers) staan in de opdracht vermeld, maar gaan over iets anders dan de fiche 281.50; ze zijn hier niet gebouwd. Een jurist kijkt best na of er een verband is.

## Testen

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie --test-enable --test-tags /vme_belgie:TestBelcotax --stop-after-init
```

De tests valideren offline: het XML-bestand van 2025 tegen de XSD, het JSON Lines-bestand van 2026 tegen de JSON-schema's, en een paar bewust foute regels die Belcotax zou weigeren.

De demohistoriek voegt in Residentie Linde een factuur toe (advies, 1.800 euro): de trage test `TestAnnualStatementDemo.test_all_costs_distributed` telt daarom acht facturen.

## Beveiliging

`state`, `checked_by_id`, `checked_date` en `filed_date` schrijven alleen de knoppen (als superuser). Een nagekeken of opgeladen overzicht en zijn lijnen wijzigen of verdwijnen pas na **Terug naar concept**; **Herberekenen** weigert een opgeladen overzicht. De facturen worden gezocht en de lijnen gemaakt met `with_company(company_id)`, want de record rule van `account.move` volgt de companies die in de schakelaar aan staan.
