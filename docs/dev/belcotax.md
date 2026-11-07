# Fiches 281.50 en Belcotax-XML

Per VME en inkomstenjaar een overzicht van wat de VME betaalde aan 281.50-plichtige leveranciers, nagekeken door een medewerker, met een XML-bestand dat de medewerker zelf oplaadt in Belcotax-on-web. Odoo Community heeft hier niets voor (`l10n_be_reports` met de 281.50 is Enterprise); dit is eigen code.

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `models/vme_belcotax.py` | Velden op `res.partner`, `vme.belcotax.statement`, `vme.belcotax.line`, drempel en termijn |
| `models/belcotax_xml.py` | XML-bouwer zonder Odoo, controle van ondernemings- en rijksregisternummer |
| `views/vme_belcotax_views.xml` | Tabblad "Fiche 281.50" op de partner, lijst en formulier, menu **VME > Fiches 281.50** |
| `security/vme_belcotax_security.xml` | Company-regels en regels van de commissaris voor beide modellen |
| `demo_data/vme_demo_belcotax.py` | Drie fictieve verkrijgers in 2026, aan het einde van de demohistoriek |
| `tests/test_belcotax.py` | Selectie, totalen, drempel, waarschuwingen, XML en werkwijze |

## Datamodel

- `res.partner`: `vme_belcotax_liable` (281.50-plichtig), `vme_belcotax_category` (commission, fees, benefits, expenses), `vme_belcotax_profession`, `vme_national_number` (groep `account.group_account_invoice`). De partner is gedeeld tussen VME's, dus de vlag geldt overal.
- `vme.belcotax.statement`: één per VME en jaar (constraint), `state` draft → checked → filed, `checked_by_id`/`checked_date`, `filed_date`, `xml_file` (attachment). `deadline` is opgeslagen, `threshold` niet.
- `vme.belcotax.line`: momentopname van de verkrijger (naam, adres, land, rechtspersoon, rijksregister- of ondernemingsnummer, beroep), een bedrag per categorie, `amount_total` en `below_threshold` (opgeslagen), `warning` (opgeslagen tekst), `bill_ids`.

De regels zijn een kopie op het moment van berekenen, zodat een nagekeken overzicht niet verandert als iemand later de partner aanpast. **Opnieuw berekenen** wist de regels, zet het overzicht terug op "Na te kijken" en wist het bestand.

## Berekening

`_paid_by_partner()` zoekt de geboekte `in_invoice` en `in_refund` in de company van de VME waarvan de commerciële partner 281.50-plichtig is. Per factuur neemt het de `account.partial.reconcile` van de lijnen op de rekening te betalen (`matched_debit_ids | matched_credit_ids`) met `max_date` in het jaar. Een factuur telt positief, een creditnota negatief; een creditnota die met een factuur verrekend is, telt zo netto juist (de factuur ziet het deel, de creditnota trekt het af). Het bedrag is in de munt van de company en met btw.

Het hele bedrag gaat naar de categorie van de leverancier; een medewerker kan het in de regel over categorieën spreiden. `below_threshold` is `amount_total <= 250`. Het formulier telt alleen regels boven de drempel in `fiche_count`, `total_amount` en `warning_count`.

Waarschuwingen (nooit blokkerend): adres onvolledig, ondernemingsnummer ontbreekt of foute controlegetal (alleen Belgische of lege landcode), rijksregisternummer ontbreekt of foute controlegetal (ook de variant met prefix 2 voor geboren vanaf 2000), beroep ontbreekt.

## XML

`build_belcotax_xml(year, debtor, fiches)` maakt `Verzendingen/Verzending` met de v0…-velden van de VME, één `Aangifte` met `Opgaven/Opgave32550` en per verkrijger een `Fiche28150`, plus de sluitrecords r8… en r9… met aantallen en controletotalen. Bedragen in eurocent, datums dd-mm-jjjj.

**Te valideren.** De tags zijn gereconstrueerd uit de publieke Belcotax-on-web-brochure; we hebben geen XSD van de FOD in de repository. Vóór echt gebruik: vergelijken met de brochure van het inkomstenjaar, de controletotalen en het aantal records nakijken, en een proefupload doen. Haal je de XSD binnen, valideer dan zoals `sepa_xml.py` dat doet met de XSD's in `data/sepa/`.

## Niets vertrekt vanzelf

Er is geen koppeling met Belcotax-on-web en geen cron. Downloaden kan pas na **Nagekeken**; **Opgeladen in Belcotax** is een vinkje dat de medewerker zelf zet na de upload. Alle knoppen roepen `check_not_auditor` aan.

## LEGAL-CHECK

- Art. 57, 1° WIB 92: welke vergoedingen (de vier categorieën) en "betaald of toegekend" (wij nemen betaald).
- Art. 30 KB/WIB 92, gewijzigd door het KB van april 2022 (circulaire 2022/C/96): drempel 250 euro per verkrijger per jaar.
- Termijn: jaarlijks door de FOD vastgelegd, wij nemen 30 juni van het jaar erna.
- Art. 30bis van de RSZ-wet en art. 403 WIB 92 (inhoudingsplicht bij aannemers) staan in de opdracht vermeld, maar gaan over iets anders dan de fiche 281.50; ze zijn hier niet gebouwd. Een jurist kijkt best na of er een verband is.

## Testen

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie --test-enable --test-tags /vme_belgie:TestBelcotax --stop-after-init
```

De demohistoriek voegt in Residentie Linde een factuur toe (advies, 1.800 euro): de trage test `TestAnnualStatementDemo.test_all_costs_distributed` telt daarom acht facturen.
