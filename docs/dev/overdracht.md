# Overdracht aan een nieuwe syndicus

De vertrekkende syndicus draagt binnen dertig dagen na het einde van zijn mandaat het volledige beheersdossier over aan zijn opvolger (`# LEGAL-CHECK: art. 3.89 §5, 6° BW`). De knop **Overdracht aan nieuwe syndicus** op de VME maakt daarvoor één zip die de medewerker downloadt. Er vertrekt niets.

Code: `addons/vme_belgie/wizard/vme_handover_wizard.py`, scherm `wizard/vme_handover_wizard_views.xml`, rapporten `report/vme_handover_reports.xml`, tests `tests/test_handover.py`. Gebruikersuitleg: [kennisbank](../kb/overdracht-syndicus.md).

## Werking

`vme.handover.wizard` is een transient model (geen eigen spoor nodig: de zip blijft als bijlage op de VME). Velden: VME, overdrachtsdatum (standaard vandaag), nieuwe syndicus (partner, optioneel), jaar van jaarafrekening en balans (standaard het jaar van de laatste geboekte regel tot de overdrachtsdatum) en opmerkingen. `deadline` = overdrachtsdatum + `HANDOVER_DAYS` (30).

1. `_handover_data()` leest alles één keer, als `sudo()` na `check_access("read")` op de VME, zoals de andere rapporten. Het geeft een dict met de CSV-tabellen (`tables`), de records voor de rapporten en een lijst `warnings`.
2. `_build_package()` controleert eerst `check_not_auditor()`, schrijft de tabellen met `_csv()`, rendert de PDF's (`_report_files()`), voegt de documenten toe en rendert als laatste het overdrachtsdocument. Dat krijgt de lijst van bestanden en de aandachtspunten via de context (`handover_files`, `handover_warnings`).
3. `action_build_package()` bewaart de zip als `ir.attachment` op de VME, zet een interne notitie (`mail.mt_note`) met de bijlage in de chatter en geeft een `ir.actions.act_url` naar `/web/content/<id>?download=true` met `target: "self"` terug: de browser downloadt en blijft op de pagina. Niet `target: "download"`: dat opent een pop-up, en de browser blokkeert die na een verzoek van enkele seconden (de PDF's renderen).

De knop zit in de header van het VME-formulier (`action_open_handover`), verborgen voor `group_vme_auditor`; de methode zelf weigert de commissaris ook.

## Inhoud van de zip

```
vme.csv kavels.csv eigenaars.csv eigendommen.csv sleutels.csv leveranciers.csv
openingsbalans.csv werken.csv procedures.csv mandaten.csv
rapporten/Overdrachtsdocument.pdf
rapporten/Jaarafrekening <jaar>.pdf                    (alleen als er afrekeningen zijn)
rapporten/Balans en resultatenrekening <jaar>.pdf      (alleen als er boekingen zijn)
rapporten/Openstaande saldi eigenaars.pdf
rapporten/Reservekapitaal.pdf
archief/<map>/[<kavel>/]<bestand>                      (vme.document)
archief/Bijlagen VME/<bestand>                         (ir.attachment op de VME, behalve zips)
```

De CSV-bestanden volgen exact het formaat van [migratie.md](migratie.md): de kolommen komen uit `TABLES` van `vme_migration.py`, `;` als scheidingsteken, UTF-8 met BOM, datums `dd/mm/jjjj`, bedragen met komma en zonder duizendtal. De import leest de zip zonder omzetting; de PDF's in `rapporten/` en `archief/` gaan daar naar het archief van de nieuwe VME.

### Van het model naar de tabellen

| Tabel | Bron |
| --- | --- |
| `vme` | de VME; IBAN's alleen als ze geldig zijn; `overstapdatum` = overdrachtsdatum |
| `kavels` | `vme.lot` op volgorde; type via de omgekeerde `LOT_TYPES` |
| `eigenaars` | partners met een eigendom op een kavel, plus partners met een vorderingssaldo die geen leverancier zijn (een erfgenaam zonder kavel) |
| `eigendommen` | alle `vme.ownership`, ook afgelopen |
| `sleutels` | alle `vme.key` met hun lijnen; een dubbele naam krijgt " (2)" |
| `leveranciers` | partners met een geboekte leveranciersfactuur, een actieve verdeelregel, een lopend contract of een schuldsaldo, behalve eigenaars; sleutel = die van de eerste verdeelregel met sleutel |
| `openingsbalans` | `_opening_rows()`, zie hieronder |
| `werken` | werkdossiers die niet afgesloten of geannuleerd zijn, met als bedrag wat nog te factureren is (opdracht of budget min gefactureerd); een dossier zonder restbedrag komt alleen op het overdrachtsdocument |
| `procedures` | de `<li>` (of anders de alinea's) van "Lopende gerechtelijke procedures", plus elke invordering met status Doorgestuurd |
| `mandaten` | `vme.mandate` die op de overdrachtsdatum lopen |

**Codes.** Eigenaars en leveranciers krijgen hun `ref` als die uniek is in de lijst, anders `E001`… of `L001`… op alfabetische volgorde. Zo blijven de codes uit een vorige overstap behouden en geeft dezelfde VME altijd dezelfde codes.

### Openingsbalans

`_opening_rows()` groepeert alle geboekte regels tot en met de overdrachtsdatum per rekening en partner (`_read_group`) en zet elk saldo om:

| Saldo op | Soort | Teken |
| --- | --- | --- |
| standaardrekening van het bankdagboek van de rekening werkkapitaal / reservekapitaal | `bank_werkkapitaal` / `bank_reservekapitaal` | saldo |
| 100100 / 100200 | `fonds_werkkapitaal` / `fonds_reservekapitaal` | −saldo |
| vordering of schuld van een eigenaar | `eigenaar` met code | saldo |
| vordering of schuld van een leverancier | `leverancier` met code | −saldo |
| andere rekening van 6 cijfers, niet in klasse 4/5 behalve 490–493 en 499 | `rekening` met de code | saldo |
| al de rest (derde bankrekening, betalingen die nog niet op een uittreksel staan zoals 550002 Openstaande ontvangsten, btw, vordering van een partner die eigenaar noch leverancier is) | `rekening` 499000, één rij per rekening (per partner alleen bij vorderingen en schulden), omschrijving "Saldo <code> <naam>" | saldo, plus één waarschuwing per rij |

Rijen met dezelfde soort, code en omschrijving worden opgeteld. Omdat elke geboekte boeking in evenwicht is, is de som van alle rijen 0 en aanvaardt de proefrun de balans. Een eigenaar met vorderingen en schulden krijgt één rij met zijn nettosaldo.

Valkuil: de import zoekt een `rekening` op code in de nieuwe company. Rekeningen uit het Belgische rekeningstelsel bestaan daar; een rekening die iemand in de oude VME met de hand aanmaakte, niet. Die import faalt dan met "Rekening … bestaat niet". Zet zo'n rekening in de toekomst ook op de wachtrekening als ze geen `ir.model.data` van het rekeningstelsel heeft.

In de demodata komen zo de geregistreerde betalingen die nog niet met een bankuittreksel afgepunt zijn (550002) op de wachtrekening. De proefrun van de drie demo-VME's geeft geen fouten.

## Rapporten

Drie nieuwe QWeb-rapporten op `vme.handover.wizard`, zonder printmenu: `report_handover_form`, `report_handover_arrears` (`_arrears_data()`) en `report_handover_reserve` (`_reserve_data()`). De jaarafrekening en de balans komen uit de bestaande wizards (`vme.annual.statement.wizard`, `vme.financial.statements.wizard`), met hun eigen toegangscontrole en taal.

- **Openstaande saldi**: per eigenaar het saldo op de overdrachtsdatum (gelijk aan de openingsbalans) en de facturen van vóór die datum die vandaag nog open zijn, met het invorderingsdossier. Een saldo "op datum" per factuur rekenen we niet; bij een datum in het verleden zegt het rapport dat.
- **Reservekapitaal** (`# LEGAL-CHECK: art. 3.86 §3 BW`): stand op 1 januari en op de overdrachtsdatum (`_get_fund_balance`), saldo van de bankrekening, de bewegingen op 100200 in dat jaar en wat lopende werken op het reservekapitaal nog vastleggen.

In tests rendert Odoo een rapport als HTML in plaats van PDF (`_render_qweb_pdf` zonder `force_report_rendering`). De bestanden heten dan toch `.pdf`; de proefrun van de roundtrip geeft er een waarschuwing "Is geen PDF" voor.

## Tests

`tests/test_handover.py` leest Residentie Esdoorn in met de echte import (`demo_data/migratie/residentie-esdoorn`) en voegt een kost met een schuld aan de glazenwasser, een werkdossier, een polis met schadegeval, een contract, een voorzitter, een procedure en een basisakte toe.

- **Inhoud**: alle CSV's, de rapporten en het archief zitten in de zip; het overdrachtsdocument noemt rekening, werken, schadegeval, procedure, contract, polis en mandaat; de zip staat als interne notitie op de VME en er komt geen `mail.mail` bij.
- **Openingsbalans**: de bedragen per soort, de stand van het reservekapitaal (24.600, waarvan 15.000 vastgelegd) en de openstaande saldi per eigenaar, de erfgenaam zonder kavel als eigenaar, de kost op een rekening van klasse 6; vóór de overstapdatum is de balans leeg.
- **Roundtrip**: export, de oude VME krijgt een andere naam, KBO en IBAN's, de zip gaat ongewijzigd door proefrun (0 fouten) en import, en de export van de nieuwe VME is tabel per tabel gelijk aan de eerste (behalve `vme.csv`). Het saldo per rekening is in beide VME's gelijk op de overdrachtsdatum.
- **Wachtrekening**: een btw-saldo komt op 499000 met een waarschuwing.
- **bin_size**: met `bin_size=True` in de context (zoals de webclient na de knop leest) zitten de documenten toch met hun inhoud in het pakket. Zonder `with_context(bin_size=False)` in `_documents()` gaf `datas` de grootte ("12 Kb") en faalde de base64-decodering; alleen in de browser te zien, niet in een gewone test.
- **Commissaris**: `_build_package()` geeft een `AccessError`.

## Uitbreidingen

- Een spoor per overdracht (wie, wanneer, aan wie, ondertekend op) als gewoon model, als de pilootsyndicus dat vraagt; nu volstaat de notitie met de zip in de chatter.
- Een eigen tabel `contracten.csv` en `polissen.csv` in het importformaat, zodat ook die terug inlezen; nu staan ze alleen op het overdrachtsdocument en als document in het archief.
