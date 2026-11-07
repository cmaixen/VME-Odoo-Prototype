# Vertaling naar het Frans

Het prototype is in het Nederlands geschreven. De Franse vertaling (voor Brussel en Wallonië) staat in `addons/<module>/i18n/fr.po`, naast de sjabloon `addons/<module>/i18n/<module>.pot`.

## Waarom `fr.po` en geen `fr_BE.po`

Odoo laadt voor een taal eerst het bestand van de basistaal en daarna dat van de regio: voor `fr_BE` is dat `i18n/fr.po` en dan `i18n/fr_BE.po` (`odoo/tools/translate.py`, `get_po_paths`). Wij zetten alles in `fr.po`:

- het werkt voor `fr_BE` en ook als iemand "Français" (`fr_FR`) activeert, in plaats van dan terug te vallen op Nederlands;
- het is de gewoonte van Odoo zelf;
- het platform is alleen voor België, dus de Belgische termen in `fr.po` zijn geen nadeel.

Een `fr_BE.po` komt er pas als er een Frans-Franse variant nodig is; dan bevat het alleen de afwijkingen.

## Woordenlijst

Belgische juridische termen (Burgerlijk Wetboek, boek 3, titel 4, Franse versie). Gebruik ze overal, ook in de rapporten.

| Nederlands | Frans | Opmerking |
| --- | --- | --- |
| VME (vereniging van mede-eigenaars) | ACP (association des copropriétaires) | "l'ACP", "les ACP" |
| syndicus | syndic | |
| mede-eigenaar | copropriétaire | |
| eigenaar | propriétaire | |
| mede-eigendom | copropriété | |
| kavel | lot | |
| privatief / privatief deel | privatif / partie privative | |
| gemene delen | parties communes | |
| quotiteit | quote-part | in duizendsten: "quotes-parts (en millièmes)" |
| aandelen (van een kavel in een sleutel) | quotités / parts | |
| verdeelsleutel | clé de répartition | |
| provisie | provision | |
| provisieoproep | appel de fonds | |
| werkkapitaal | fonds de roulement | |
| reservekapitaal | fonds de réserve | |
| jaarafrekening | décompte annuel | |
| afrekening | décompte | |
| budget | budget | |
| algemene vergadering (AV) | assemblée générale (AG) | |
| gewone / buitengewone AV | AG ordinaire / AG extraordinaire | |
| oproeping (AV) | convocation | |
| notulen | procès-verbal | |
| agendapunt | point de l'ordre du jour | |
| volmacht | procuration | |
| quorum, meerderheid | quorum, majorité | |
| raad van mede-eigendom | conseil de copropriété | |
| commissaris van de rekeningen | commissaire aux comptes | |
| notaris | notaire | |
| inlichtingen aan de notaris | informations au notaire | art. 3.94 C. civ. |
| basisakte / reglement van mede-eigendom | acte de base / règlement de copropriété | |
| reglement van orde | règlement d'ordre intérieur | |
| KBO-nummer | numéro BCE | |
| BW (Burgerlijk Wetboek) | C. civ. (Code civil) | "art. 3.89 §5 BW" → "art. 3.89 §5 C. civ." |
| KB | AR (arrêté royal) | |
| leverancier | fournisseur | |
| leveranciersfactuur | facture fournisseur | |
| verdeling (van kosten) | répartition | |
| aanmaning, herinnering, ingebrekestelling | rappel, rappel, mise en demeure | |
| invordering | recouvrement | |
| nalatigheidsinterest | intérêts de retard | |
| gestructureerde mededeling | communication structurée | |
| domiciliëring | domiciliation | |
| verkoop / koper / verkoper | vente / acquéreur / vendeur | |
| akte | acte | |
| werken, schadegeval | travaux, sinistre | |
| keuring | contrôle / inspection | |
| conciërge | concierge | |
| huurder / verhuurder | locataire / bailleur | |
| rentmeester (rentmeesterij) | gestionnaire locatif (gestion locative) | |
| huurcontract | bail / contrat de bail | |
| indexering | indexation | |
| afrekening lasten | décompte des charges | |
| huurwaarborg | garantie locative | |
| eigenaarsportaal | portail des propriétaires | |
| medewerker (van de syndicus) | collaborateur | |
| verbruik, meter | consommation, compteur | |
| verwarming, lift | chauffage, ascenseur | |

Stijl: vouvoiement ("vous"), korte zinnen zoals in het Nederlands, Franse typografie zonder harde spatie-eisen (een gewone spatie vóór `:` en `%` is goed). Eigennamen van gebouwen en demo-eigenaars ("Residentie Linde", "Eigenaar A1") worden niet vertaald.

Een mens beslist altijd: er wordt nooit iets automatisch naar buiten verstuurd. Gebruik dus geen formulering die automatisch versturen belooft ("envoyé automatiquement", "envoi automatique"); "préparé", "proposé" of "à envoyer" wel.

## Documenten in de taal van de ontvanger

De interface volgt de taal van de gebruiker. Een document dat naar iemand gaat, volgt de taal van die persoon (`res.partner.lang`), zodat een Nederlandstalige medewerker een Franse jaarafrekening kan maken.

### Rapporten (QWeb)

Odoo vertaalt een template in de taal waarin het gecompileerd wordt. De inhoud van een `t-call` (de "body" die je aan `web.external_layout` meegeeft) hoort bij het aanroepende template en wordt dus in díe taal vertaald; een `t-lang` op `web.external_layout` helpt niet. Daarom heeft elk rapport twee templates, zoals Odoo's eigen `account.report_invoice`:

```xml
<template id="report_communication_letter">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="o">
            ...
            <t t-call="vme_belgie.report_communication_letter_document" t-lang="o.partner_id.lang"/>
        </t>
    </t>
</template>

<template id="report_communication_letter_document">
    <t t-call="web.external_layout">
        <div class="page">...</div>
    </t>
</template>
```

Variabelen die je in de lus zet (`vme`, `company`, `o`), zijn in het `_document`-template beschikbaar. Wie een nieuw rapport toevoegt, volgt dit patroon. De taal per rapport:

| Rapport | `t-lang` |
| --- | --- |
| Jaarafrekening | `o.lang` (de eigenaar) |
| Oproeping AV, herinnering, brief | `o.partner_id.lang` |
| Inlichtingen notaris | `o.notary_id.lang or company.partner_id.lang` |
| Bestelbon | `o.locksmith_id.lang or company.partner_id.lang` |
| Indexatiebrief, afrekening lasten | `o.tenant_id.lang` |
| Afrekening verhuurder (doorstorting) | `o.landlord_id.lang` |
| Notulen, verslag commissaris, lopende dossiers, invorderingsdossier, balans en resultatenrekening | `company.partner_id.lang` (de VME) |
| Aanplakking aanstelling syndicus | `mandate.company_id.partner_id.lang` (de VME, aan de ingang) |

Rapporten van Odoo zelf (de factuur `account.report_invoice`, ook de ereloonfactuur van de syndicus en van de rentmeester) volgen al de taal van de partner; alleen hun lijnen maken wij, zie hieronder.

Valkuilen in rapporten:

- **`format_date` uit `_get_report_values`** gebruikt de taal van de gebruiker. De rapporten van de notaris en de rentmeester zetten daarom `doc_lang` (dezelfde uitdrukking als `t-lang`) en roepen `format_date(datum, lang=doc_lang)` aan. Velden met `t-field` of `t-options="{'widget': 'date'}"` volgen vanzelf de taal.
- **Geen tekst in een datumformaat.** `'format': 'd MMMM yyyy \'om\' HH:mm'` drukt "om" af in elke taal; zet datum en uur in twee `t-field`'s met "om" als gewone (vertaalbare) tekst ertussen.
- **Geen zinnen in stukken.** "De syndicus nodigt u uit op de `<t t-if>`buitengewone`</t>` algemene vergadering" is in het Frans niet te vertalen (andere woordvolgorde). Zet de volledige zin in elke tak van de `t-if`.
- **Selectiewaarden uit Python.** `dict(field.selection)` geeft het Nederlandse label. Gebruik `field._description_selection(env)` met de env van de ontvanger, of geef de sleutel door en zet het label in het template.

### Teksten die Python maakt

Een omschrijving die in de database belandt (een factuurlijn, het onderwerp van een herinnering), wordt in de taal van de context gemaakt en daarna niet meer vertaald. Maak ze in de taal van de ontvanger:

```python
owner_env = self.with_context(lang=owner.lang).env
"name": owner_env._("%(fund)s oproep %(number)s/%(calls)s %(year)s - kavel %(lot)s (%(shares)s/%(total)s)", ...)
```

Zo gebeurt het in de provisieoproep (`vme_provision_call_wizard.py`), de factuur voor interest en schadevergoeding en de omschrijvingen op een herinnering (`vme_collection.py`), de huurfactuur (`vme_rentmeester/models/rent_contract.py`), de lijnen, de ereloonfactuur en de doorstorting van een afrekening aan de verhuurder (`rent_remittance.py`: `_recompute_lines` en `action_confirm` met de taal van de verhuurder), de lijnen van de ereloonfactuur van de syndicus en de namen van de prestaties (`vme_syndic.py`: `_create_fee_invoice`, `_vme_env`, in de taal van de VME) en de titel van de aanplakbrief.

Vaste teksten op moduleniveau (de rubrieken van het minimumrekeningstelsel in `vme_financial_statements.py`, het websitemenu in `vme_website/models/website.py`) zijn `_lt(...)` van `LazyTranslate(__name__)`; vertaal ze op het moment van gebruik met `env._(LABEL)` in de env van de ontvanger. De balans wordt in `_get_report_values` met de taal van de VME berekend, zodat ook de rekeningnamen van het rekeningstelsel Frans zijn. De twee fondsrekeningen (100100, 100200) krijgen bij het aanmaken van een VME hun naam in elke geïnstalleerde taal (`account_chart_template.py`); een VME van vóór de activering van fr_BE houdt de Nederlandse naam tot iemand die vertaalt in de boekhouding.

Geen vertaalbare tekst in een QWeb-expressie: `t-foreach="[('opening', 'Overgedragen van')]"` komt niet in de `.pot`. Zet het label als tekst in een `t-if`-tak (zoals de tabel met over te dragen middelen in `vme_financial_statements_report.xml`) of in een `<t t-set="title">Activa</t>`. De mailtemplates van de invordering hebben `lang = {{ object.partner_id.lang }}` en worden met `_render_field(..., compute_lang=True)` opgemaakt. Meldingen aan de medewerker (fouten, chatter) blijven in de taal van de gebruiker.

### Wat niet vertaald wordt

Data die een gebruiker ingeeft (namen van VME's, sleutels, kavels, agendapunten, zalen, vrije brieven) en de fictieve demodata. Velden worden niet `translate=True` gemaakt: een Franstalig gebouw geeft die gegevens in het Frans in. Ook de kolomnamen en waarden van de importbestanden (`eigenaars.csv`, `{eigenaar}` in een sjabloon) blijven Nederlands, want de code verwacht ze zo.

## Nieuwe termen bijwerken

Andere stappen voegen nog termen toe. Na het samenvoegen van zo'n branch (of vóór een Franstalige demo):

1. Module upgraden in een database met de drie modules (een eigen Docker-project, niet de demo):
   `docker compose -p vme-fr run --rm odoo odoo -d vme_fr -u vme_belgie,vme_rentmeester,vme_website --stop-after-init`
2. De sjablonen opnieuw exporteren. Het entrypoint geeft de databaseverbinding als extra argumenten mee en dat aanvaardt `odoo i18n` niet, dus via een configbestand:
   ```bash
   docker compose -p vme-fr run --rm --entrypoint sh odoo -c "cat /etc/odoo/odoo.conf > /tmp/o.conf; printf 'db_host = db\ndb_user = odoo\ndb_password = odoo\n' >> /tmp/o.conf; odoo i18n export -c /tmp/o.conf -d vme_fr vme_belgie vme_rentmeester vme_website"
   ```
   Dat schrijft `addons/<module>/i18n/<module>.pot`.
3. De vertaling samenvoegen met de nieuwe sjabloon (nieuwe termen leeg, gewijzigde termen "fuzzy", verdwenen termen weg):
   ```bash
   msgmerge --quiet --update --backup=none --no-wrap addons/vme_belgie/i18n/fr.po addons/vme_belgie/i18n/vme_belgie.pot
   ```
4. De te vertalen termen ophalen: `python3 tools/vertaling.py todo vme_belgie /tmp/todo.json` geeft een lijst `{"id", "msgid", "where", "old"}`.
5. Vertalen volgens de woordenlijst hierboven, als `{"id": "traduction"}` in een JSON-bestand, en invullen: `python3 tools/vertaling.py apply vme_belgie /tmp/vertaald.json`.
6. Controleren: `python3 tools/vertaling.py check vme_belgie` (lege of fuzzy vertalingen, plaatshouders en tags die verschillen) en `msgfmt -c -o /dev/null addons/vme_belgie/i18n/fr.po`.
7. Laden: `-u vme_belgie,vme_rentmeester,vme_website --i18n-overwrite`. Zonder `--i18n-overwrite` laat Odoo bestaande vertalingen in de database staan.
8. `.pot` en `fr.po` samen committen.

Een database met Frans: `--load-language=nl_BE,fr_BE` bij het aanmaken, of later **Instellingen > Talen**. De test `tests/test_translation.py` laadt fr_BE zelf en faalt zodra een term van een `.pot` in `fr.po` ontbreekt of fuzzy is (`test_po_files_are_complete`, voor de drie modules): na nieuwe termen dus altijd stap 1 tot 8.

De productwebsite neemt bij elke installatie of upgrade fr_BE op in haar talen als die taal actief is (`LANGUAGES` in `vme_website/models/website.py`); Nederlands blijft de standaard. Wie fr_BE later activeert, upgradet `vme_website` zodat ook de menunamen vertaald worden.

## Nakijken in een demo

In een eigen demo (nooit op 8069 of `vme_demo`): zet **Eigenaar Linde A3** en de notaris op `fr_BE`, en **Huurder Linde A7**. Dan zijn Frans: de nieuwe provisieoproep (1/4 2027), de pagina van A3 in de jaarafrekening 2026, de inlichtingen aan de notaris voor de verkoop van A3, de oproeping voor de AV, de herinnering (na **Bijwerken**) en de indexatiebrief van A7. Zet ook een verhuurder op `fr_BE` en klik in een concept-doorstorting op **Herberekenen** (afrekening verhuurder), en zet een VME op `fr_BE` voor de balans, de aanplakbrief en een nieuwe ereloonfactuur. Voor tekst uit een PDF: `pdftotext -layout bestand.pdf -`.
