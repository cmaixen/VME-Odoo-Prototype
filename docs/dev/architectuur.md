# Architectuur

## Uitgangspunten

- **Odoo 19 Community**, zonder Enterprise-code. We gebruiken niets uit het Enterprise-pakket "Property Owner Association" (licentie OEEL-1) en kijken er ook niet in.
- **Eén eigen module voor de VME**, `addons/vme_belgie`. Ze hangt af van `account`, `l10n_be` en `account_peppol` (zie [valkuilen](valkuilen.md#modules-die-odoo-zelf-installeert)). De rentmeesterij staat apart in `addons/vme_rentmeester`, die van `vme_belgie` afhangt; zie [rentmeester.md](rentmeester.md).
- **Code en technische namen in het Engels, labels en teksten in het Nederlands.** Franse vertalingen komen later via `.po`-bestanden; daarom gaan teksten in Python door `self.env._(...)`.
- **Belgische regels krijgen een `# LEGAL-CHECK:`-commentaar met de bron.** [legal-checks.md](legal-checks.md) is het overzicht, gemaakt door `tools/legal_checks.py`.

## Eén company per VME

Een VME is een eigen rechtspersoon met een eigen boekhouding en aparte rekeningen voor werk- en reservekapitaal (`# LEGAL-CHECK: art. 3.89 §5 BW`). Daarom is elke `vme.association` gekoppeld aan precies één `res.company` (SQL-constraints `_company_required` en `_company_unique`).

- `vme.association.create()` maakt de company zelf aan, met land België, euro en het Belgische rekeningstelsel `be_comp`. Elke interne gebruiker krijgt toegang tot de nieuwe company, ook als een script de VME aanmaakt.
- Naam, KBO-nummer en adres zijn `related`-velden naar de company: er is maar één bron.
- Het rekeningstelsel wordt geladen bij de commit; `_post_load_data` vult daarna de VME-specifieke rekeningen aan (zie [odoo-uitbreidingen](odoo-uitbreidingen.md)).
- Records van de module (kavels, sleutels, eigendommen, verdeelregels, budgetten, oproepen) hebben een opgeslagen `company_id` die volgt uit de VME. Er zijn nog geen record rules per company: een medewerker van de syndicus ziet alle VME's.
- Boekhoudkundige records (facturen, betalingen, dagboeken) leven echt in de company van de VME. Code die over VME's heen werkt, schakelt daarom met `with_company(vme.company_id)` of leest met `sudo()` (zie [valkuilen](valkuilen.md#multi-company)).

## Lagen

```text
app VME (menu's, lijsten, formulieren)          Facturatie (standaard Odoo)
  VME's, kavels, sleutels, eigendommen            leveranciersfacturen, Peppol-upload,
  budgetten, provisieoproepen, jaarafrekening     klantfacturen (provisies), betalingen
            │                                                │
            ▼                                                ▼
  vme.* modellen ──────── account.move / account.move.line (uitgebreid)
            │                     │  _post → automatisch verdelen
            │                     │  _compute_account_id / vme_key_id → verdeelregels
            ▼                     ▼
  allocation_tools.largest_remainder: alle afrondingen op duizendsten en centen
```

## Mappen

| Pad | Inhoud |
| --- | --- |
| `models/vme_association.py` | VME, company aanmaken, KBO-controle, bankrekeningen, fondsdagboeken |
| `models/vme_lot.py`, `vme_ownership.py`, `vme_key.py` | Kavels, eigendommen, sleutels met quotiteiten |
| `models/account_move.py` | VME en kostperiode op facturen, verdeling, automatisch verdelen, UBL-periode |
| `models/vme_distribution_rule.py` | Verdeelregels per VME en leverancier |
| `models/vme_budget.py`, `vme_provision_call.py` | Jaarbudget met 5%-regel, provisieoproepen |
| `models/vme_annual_statement.py` | Berekening van de jaarafrekening |
| `models/account_chart_template.py` | Extra rekeningen en standaardkostenrekening na het laden van het rekeningstelsel |
| `models/allocation_tools.py` | `largest_remainder` |
| `wizard/` | Provisieoproep en jaarafrekening (voorbeeld + PDF) |
| `report/` | QWeb-rapport van de jaarafrekening |
| `demo_data/` | Demodata, demohistoriek 2026, Peppol-voorbeeldfacturen |
| `data/demo_actions.xml` | Menu **Configuratie** met de laadacties voor de demo |
| `data/help_menu.xml` | Menu **Help** en systeemparameter `vme_belgie.help_url` |
| `tests/` | Unittests; de trage demojaartest draagt de tag `vme_slow` |

## Help-menu

Het menu **VME > Help** opent de kennisbank in een nieuw tabblad. De basis-URL staat in de systeemparameter `vme_belgie.help_url` (standaard `https://github.com/cmaixen/VME-Odoo-Prototype/tree/main/docs/kb`); elk menu-item plakt er de bestandsnaam van een artikel achter. Een menu kan geen argument meegeven aan een actie en een `ir.actions.act_url` kan geen parameter lezen, daarom is elk item een kleine serveractie. De parameter staat in `noupdate`, zodat een aangepaste URL een upgrade overleeft. Wie de kennisbank ergens anders host, past alleen de parameter aan (**Instellingen > Technisch > Systeemparameters**, in ontwikkelaarsmodus).
