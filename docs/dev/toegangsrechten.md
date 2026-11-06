# Toegangsrechten

Rollenmodel van `vme_belgie` en `vme_rentmeester`, de bevindingen van de review vóór de pilot (november 2026), en de regels voor wie een model toevoegt.

## Rollen

| Rol | Odoo-gebruiker | Groepen | Companies |
| --- | --- | --- | --- |
| Medewerker met alle VME's | intern | `base.group_user` (+ boekhouding), `vme_belgie.group_vme_all_companies` | alle VME-companies; elke nieuwe VME komt er vanzelf bij |
| Medewerker met een deel van de VME's | intern | `base.group_user` (+ boekhouding) | alleen de companies die een beheerder toewijst |
| Rentmeester | intern | als medewerker | de company van het rentmeesterkantoor (+ de VME's die hij nodig heeft) |
| Commissaris van de rekeningen | intern | `vme_belgie.group_vme_auditor` (impliceert `account.group_account_readonly`) | de companies van zijn lopende mandaten, beheerd door `_vme_sync_auditor_access` |
| Eigenaar | portaal | `base.group_portal` | geen VME-company; het portaal leest met sudo via helpers |
| Huurder | (nog geen login) | – | – |
| Raad van mede-eigendom | (geen login) | mandaat op `vme.mandate` | – |
| Verhuurder | (geen login) | partner op het huurcontract | – |

`base.group_system` impliceert `group_vme_all_companies`, dus beheerders krijgen elke nieuwe VME.

## Wat elke rol bereikt

| | Eigen VME's lezen | Eigen VME's wijzigen | Andere VME's | Huurcontracten |
| --- | --- | --- | --- | --- |
| Medewerker, alle VME's | ja | ja | – | alleen met de company van het kantoor |
| Medewerker, deel van de VME's | ja | ja | nee (record rule) | alleen met de company van het kantoor |
| Commissaris | ja, ook de boekhouding | nee | nee | nooit wijzigen |
| Eigenaar (portaal) | alleen zijn kavels, documenten, provisies, afrekening, AV | adresaanvraag, stem, handtekening | nee | nee |

## Hoe het afgedwongen wordt

1. **Globale company-regel per model.** `security/vme_company_security.xml` en `vme_rentmeester/security/rent_security.xml` geven elk `vme.*`-model met een company één regel zonder groep: `company_id in user.company_ids.ids`. Kindmodellen zonder eigen company gaan via hun ouder (`assembly_id.company_id`, `meter_id.company_id`, `contract_id.company_id` …). Adreswijzigingen gaan via de eigendommen van de partner.
   - We gebruiken `user.company_ids` (de toegestane companies) en niet `company_ids` (de geselecteerde in de bedrijvenkiezer). Zo blijven de lijsten en berekeningen over alle VME's heen werken voor wie alle VME's heeft, ook als er maar één company geselecteerd is. Boekhoudrecords (`account.move` …) volgen wel Odoo's eigen regel met de bedrijvenkiezer.
   - Een globale regel geldt (met AND) ook voor de commissaris. Regels van verschillende groepen worden met OR gecombineerd. Daarom is een groepsregel voor `base.group_user` geen optie: die zou de regels van de commissaris, die het schrijven verbieden, opheffen.
2. **Regels van de commissaris.** In `security/vme_council_security.xml` krijgt elk model twee regels: lezen alleen binnen `company_ids`, en schrijven, aanmaken of verwijderen nooit. Gedeelde configuratie (zalen, blokken, mappen, rubrieken) krijgt alleen de regel die schrijven verbiedt.
3. **Knoppen die met sudo schrijven.** Record rules gelden niet voor wat een methode met `sudo()` doet. Zo'n knop roept bovenaan `check_not_auditor(self.env)` aan (`models/vme_access.py`).
4. **Lezen met sudo begint bij een leesbaar record.** Rapporten en berekeningen die met sudo lezen (gebouwkaart, notarisinformatie, verslag van de commissaris, leverancierskaart) starten bij een record dat de gebruiker zelf mag lezen, of roepen eerst `check_access("read")` aan. Een wizard is een transient model zonder regels. Wie er een vreemd record in kan zetten, moet dus eerst gecontroleerd worden, zoals in `vme.annual.statement.wizard._get_statement`.
5. **Portaal.** Portaalgebruikers hebben geen ACL op de VME-modellen. Elke route start bij `request.env.user.partner_id` en gaat via de helpers in `models/vme_portal.py`, `vme_document._portal_domain_for` en `vme_assembly_online`. Wat niet van de eigenaar is, geeft 404.
6. **Nieuwe companies.** `vme.association.create()` (en de demo van het rentmeesterkantoor) koppelt de nieuwe company aan `_vme_all_companies_users()`: de leden van `group_vme_all_companies` en de huidige gebruiker, nooit de commissaris.

## Bevindingen van de review (november 2026)

| # | Lek | Oplossing | Test |
| --- | --- | --- | --- |
| L1 | De commissaris las en wijzigde 33 modellen van alle VME's: alles wat na stap 16 kwam (werken, schade, documenten, contracten, meters, communicatie, aanvragen, SEPA, betaalbatches, AI-controles, adreswijzigingen, rentmeester). Ook `vme.assembly.signature` was schrijfbaar. | Regels voor lezen en tegen schrijven aangevuld. Voor de rentmeestermodellen alleen de regel tegen schrijven. | `test_auditor_reads_only_his_vmes_and_writes_nothing`, `test_auditor_cannot_read_or_change_records_of_another_vme`, `TestRentAccess` |
| L2 | Een medewerker met een deel van de companies zag en wijzigde alle VME's. Elke nieuwe VME ging bovendien naar alle interne gebruikers. | Globale company-regels, de groep "Toegang tot alle VME's", en een migratie `19.0.1.12.0` die de groep geeft aan bestaande interne gebruikers. | `test_every_vme_model_is_limited_to_the_users_companies`, `test_staff_sees_only_the_vmes_of_his_companies`, `test_new_vme_goes_to_users_with_access_to_all_vmes` |
| L3 | Jaarafrekening van een vreemde VME via een zelf aangemaakte wizard (sudo zonder controle). | `check_access("read")` op de VME vóór de sudo. | `test_auditor_cannot_print_the_statement_of_another_vme` |
| L4 | Knoppen die met sudo schrijven, zonder `check_not_auditor`: verdelen, ontvangers opbouwen, herinnering bijwerken, bestelling versturen, bankafschriften inlezen. De bankimport was ook open voor medewerkers zonder boekhoudrechten. | `check_not_auditor`; de bankimport vraagt daarnaast `account.group_account_invoice`. | `test_buttons_that_write_as_superuser_refuse_the_auditor`, `test_bank_import_needs_invoicing_rights` |

Nagekeken zonder lek: het portaal (eigendommen, documenten, provisies, afrekening, AV, stemmen en handtekenen), de gebouwkaart, de leverancierskaart, de notarisinformatie, het verslag en de raadsdossiers van de commissaris (een vreemde VME geeft een AccessError), en de tellers van huurfacturen.

Bewust zo gelaten:
- **Partners zijn gedeeld.** Een medewerker met een deel van de VME's ziet de contactkaarten van eigenaars uit andere VME's in de contactenlijst, maar niet hun eigendommen, provisies of documenten. Afscherming van partners per VME vraagt een eigen regel op `res.partner` en raakt Odoo's eigen schermen; dat is voor later.
- **De bedrijvenkiezer filtert de VME-lijsten niet**, de boekhouding wel (Odoo-standaard).

## Een model toevoegen

1. Een globale regel in `security/vme_company_security.xml` (of in het `security/`-bestand van je module): `company_id in user.company_ids.ids`, of via de ouder.
2. Twee regels voor de commissaris in `security/vme_council_security.xml`: lezen op `company_ids`, nooit schrijven.
3. Een knop die met `sudo()` schrijft: `check_not_auditor(self.env)` bovenaan.
4. Een wizard of rapport dat met sudo leest: begin bij een leesbaar record, of roep eerst `check_access("read")` aan.

`tests/test_access_rules.py` loopt over elk `vme.*`-model in het register, ook die van andere modules, en faalt als stap 1 of 2 ontbreekt. Gedeelde configuratie zonder company staat in `SHARED_MODELS`.

## Testen

```bash
docker compose run --rm odoo odoo -d vme_test -u vme_belgie,vme_rentmeester --test-enable --test-tags /vme_belgie:TestAccessRules,/vme_rentmeester:TestRentAccess --stop-after-init
```
