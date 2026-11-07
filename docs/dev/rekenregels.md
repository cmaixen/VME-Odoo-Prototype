# Rekenregels

Alle verdelingen ronden af met dezelfde functie, zodat de som van de delen altijd exact het geheel is.

## Afronding: `largest_remainder`

`models/allocation_tools.py`:

```python
largest_remainder(total, weights, digits=0)
```

1. Reken het totaal om naar eenheden (`digits=2`: centen).
2. Geef elk deel het naar beneden afgeronde exacte aandeel.
3. Verdeel de overblijvende eenheden één voor één over de delen met de grootste rest.
4. Een negatief totaal (creditnota) wordt als absolute waarde verdeeld en krijgt daarna het minteken terug.

Voorbeeld: 1000 over drie gelijke gewichten geeft `[334, 333, 333]`. Gewichten die samen nul zijn, geven een `ValueError`.

Gebruikt voor: quotiteiten in de demodata (hele duizendsten), factuurbedragen over kavels en over eigenaars (centen), provisiebedragen over kavels (centen).

## Verdeling van een leveranciersfactuur

`account.move._vme_distribute()`, per factuur:

1. **Controle** (`_vme_check_distributable`): leveranciersfactuur of -creditnota, VME bekend, kostperiode ingevuld en niet omgekeerd, minstens één productregel, elke regel een sleutel van deze VME.
2. **Bedrag per regel**: `price_total` (inclusief btw, want btw is een kost voor een VME), omgerekend naar de munt van de company op de factuurdatum. Een creditnota krijgt een negatief bedrag.
3. **Over de kavels**: `largest_remainder(bedrag, quotiteiten, 2)` over de sleutelregels met een quotiteit verschillend van nul.
4. **Over de eigenaars per kavel**: `_vme_ownership_segments` knipt de kostperiode in stukken per eigenaar (`max(begin)` tot `min(einde)`) en telt de dagen, grenzen inbegrepen. Dekken de stukken niet elke dag van de periode, dan volgt een `UserError`. Het kavelbedrag wordt met `largest_remainder` over de dagen verdeeld (`# LEGAL-CHECK: art. 3.94 BW`).
5. **Opslaan**: bestaande `vme.cost.allocation`-rijen van deze factuur worden verwijderd en opnieuw gemaakt.

Gevolg: de som van alle rijen van een factuur is exact het factuurtotaal, en de som per kavel exact het kavelaandeel.

### Sleutel op verbruik

Voor een sleutel met `key_type = "consumption"` vervangen stap 3 en 4 door `_vme_consumption_rows` (details in [verbruik.md](verbruik.md)):

1. `largest_remainder(bedrag, [vast %, 100 − vast %], 2)`: vast en variabel deel.
2. Vast deel over de kavels volgens de quotiteiten, per kavel over de eigenaars volgens de dagen.
3. Variabel deel over de kavels volgens het verbruik in de kostperiode: (stand einde laatste dag − stand einde dag vóór de eerste dag) × coëfficiënt, opgeteld over de tellers van de gekozen soort. Een stand tussen twee opnames wordt lineair per dag geïnterpoleerd.
4. Per kavel het variabele deel over de eigenaars volgens hun verbruik binnen hun eigen eigendomsperiode (`# LEGAL-CHECK: art. 3.94 BW`): met een tussenopname bij de akte is dat het echte verbruik, anders pro rata per dag tussen de twee opnames.
5. Ontbreekt een opname vóór het begin of na het einde, of heeft een kavel geen teller, dan volgt een `UserError` met de lijst; er wordt niets verdeeld.

Voorbeeld (uit `test_consumption.py`): 1000 euro, 30% vast, A1 600/1000 en 100 eenheden, A2 400/1000 en 300 eenheden. Vast 300: 180 en 120. Variabel 700: 175 en 525. A1 betaalt 355, A2 645.

### Automatisch bij het boeken

`_post()` roept `_vme_auto_distribute()` aan voor geboekte leveranciersfacturen met een VME:

- Heeft een regel geen sleutel, dan komt er een bericht in de chatter en gebeurt er niets.
- Anders wordt verdeeld binnen een savepoint. Een `UserError` (bijvoorbeeld een kavel zonder eigenaar) wordt een chatterbericht; de factuur blijft geboekt.

### Kostperiode

- Standaard: begin en einde = factuurdatum (compute die alleen lege velden vult).
- UBL/Peppol: `InvoicePeriod/StartDate` en `EndDate` uit het XML-bestand (`_extend_with_attachments`).
- De kostperiode beïnvloedt alleen de verdeling tussen opeenvolgende eigenaars. Voor de jaarafrekening telt de factuurdatum.

## Verdeelregels

- `account.move.line._compute_vme_key_id`: hangt af van leverancier, company en `display_type`; vult alleen een lege sleutel, zodat een handmatige keuze blijft.
- `account.move.line._compute_account_id`: zet voor regels zonder product de rekening van de regel, als die er een heeft.
- De regel wordt gezocht op de company van de factuur en de leverancier of zijn commerciële partner.

## Provisieoproep

`vme.provision.call.wizard._create_call(vme, budget)`:

1. Controles: oproepnummer tussen 1 en `calls_per_year`, oproep nog niet gemaakt, een algemene sleutel met regels, rekeningstelsel met 100100/100200 en een verkoopdagboek, beide fondsrekeningen ingevuld én bevestigd.
2. Eigenaar per kavel: `lot._get_owner_on(invoice_date)`. Elke kavel moet op die datum een eigenaar hebben.
3. Per fonds: bedrag per oproep = jaarbedrag / `calls_per_year`, verdeeld over de kavels van de algemene sleutel met `largest_remainder(…, 2)`. Kavels met bedrag nul vallen weg.
4. Per fonds en per eigenaar één klantfactuur, zonder btw, met één regel per kavel op rekening 100100 of 100200, `partner_bank_id` = rekening van het fonds (`# LEGAL-CHECK: art. 3.89 §5 BW`).
5. De gestructureerde mededeling (`+++xxx/xxxx/xxxxx+++`) komt van Odoo zelf: het verkoopdagboek van het Belgische rekeningstelsel gebruikt het Belgische referentiemodel.
6. Met **Meteen boeken** boekt de wizard per VME in haar eigen company.

## 5%-regel voor het reservefonds

`vme.budget._compute_reserve_check` (`# LEGAL-CHECK: art. 3.86 §3 BW`):

- Lasten vorig jaar = som van `amount_total_signed` (inclusief btw) van geboekte leveranciersfacturen en -creditnota's van de company met factuurdatum in jaar − 1. Alleen de gewone lasten: facturen die uit het reservekapitaal betaald zijn (`vme_reserve_move_id`) en privékosten van een aanvraag (`vme_request_id`) tellen niet mee.
- Zijn die nul (nieuwe VME of demo zonder historiek), dan wordt het werkkapitaalbudget als schatting gebruikt en is `previous_year_charges_estimated` waar.
- Minimum = lasten × `RESERVE_MINIMUM_RATE` (0,05).
- Waarschuwing als de jaarbijdrage lager is en `reserve_exception_by_general_assembly` niet aanstaat. Het is een waarschuwing, geen blokkering.

## Jaarafrekening

`vme.association._get_annual_statement(year, partners=None)` (alles als `sudo`):

- **Kosten**: kostenverdelingen van geboekte leveranciersfacturen met factuurdatum in het jaar.
- **Provisies**: geboekte facturen van provisieoproepen met budgetjaar = het jaar van de afrekening (niet de factuurdatum); per fonds gefactureerd (`amount_total` min wat met een creditnota afgepunt is, `_credited_amount`), betaald (gefactureerd − `amount_residual`) en open. Een oproep die met een creditnota volledig tegengeboekt is (`payment_state = reversed`), telt niet mee: hij was nooit verschuldigd. Een gedeeltelijke creditnota verlaagt het gefactureerde bedrag, niet het betaalde.
- **Eigenaars**: iedereen met kosten of provisies in het jaar (of de opgegeven partners).
- **Saldo** = aandeel in de kosten − betaalde provisies werkkapitaal. Open provisies worden niet verrekend, reservekapitaal nooit.
- **Per sleutel**: totale kosten van de VME, de quotiteiten van de eigenaar (`"70 + 6"` voor twee kavels) en zijn aandeel.
- **Per factuur**: aandeel van de eigenaar, en `partial_days` als hij maar een deel van de kostperiode eigenaar was.
- **Controle**: `is_complete` als er geen geboekte factuur zonder verdeling is en de som van de verdeling gelijk is aan de som van de facturen.

Het rapport (`report/vme_annual_statement_report.xml`) toont per eigenaar kavels, kosten per sleutel, afrekening werkkapitaal, reservekapitaal en het detail per factuur.

## Balans en resultatenrekening

`vme.association._get_financial_statements(year)` (stap 26) rekent uit de geboekte regels van de VME, met het vorige jaar ernaast:

- **Balans per 31/12**: elke rekening in een rubriek van het KB; 48901 = saldo 100200, 48902 = saldo 100100 + het resultaat van alle jaren.
- **Kosten** per rubriek, bruto: de overboekingen van werken naar het reservekapitaal tellen niet mee. Met de niet-aftrekbare btw zijn ze gelijk aan de som van `price_total` van de leveranciersfacturen van het jaar (op boekingsdatum).
- **Opbrengsten**: 700/701 = de beweging op 100200/100100 in het jaar (zonder overboekingen voor werken), 75 en 76.
- **Over te dragen middelen** per fonds: beginstand + voorschotten + andere opbrengsten − kosten ten laste = eindstand, gelijk aan 48901/48902.

Details en de indeling van de rekeningen staan in [financiele-rapporten.md](financiele-rapporten.md).
