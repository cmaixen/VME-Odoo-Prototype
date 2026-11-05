# LEGAL-CHECK-punten

Automatisch gemaakt door `python3 tools/legal_checks.py`; niet met de hand bewerken.
Elke rij is een wettelijke regel in de code die nog juridisch gevalideerd moet worden.

Aantal punten: 11.

## Per bron

- **KB 12 juli 2012 (minimum chart of accounts for VMEs)**: [account_chart_template.py:6](../../addons/vme_belgie/models/account_chart_template.py#L6), [vme_association.py:80](../../addons/vme_belgie/models/vme_association.py#L80)
- **art. 3.85 §1 BW**: [vme_key.py:60](../../addons/vme_belgie/models/vme_key.py#L60)
- **art. 3.86 §3 BW**: [vme_budget.py:5](../../addons/vme_belgie/models/vme_budget.py#L5)
- **art. 3.89 §5 BW**: [account_move.py:52](../../addons/vme_belgie/models/account_move.py#L52), [vme_association.py:12](../../addons/vme_belgie/models/vme_association.py#L12), [vme_association.py:31](../../addons/vme_belgie/models/vme_association.py#L31), [vme_association.py:109](../../addons/vme_belgie/models/vme_association.py#L109), [vme_association.py:132](../../addons/vme_belgie/models/vme_association.py#L132), [vme_provision_call_wizard.py:115](../../addons/vme_belgie/wizard/vme_provision_call_wizard.py#L115)
- **art. 3.94 BW**: [account_move.py:144](../../addons/vme_belgie/models/account_move.py#L144)

## Alle punten

| Bestand | Regel | Bron | Tekst |
| --- | --- | --- | --- |
| [addons/vme_belgie/models/account_chart_template.py](../../addons/vme_belgie/models/account_chart_template.py#L6) | 6 | KB 12 juli 2012 (minimum chart of accounts for VMEs) | align these codes. |
| [addons/vme_belgie/models/account_move.py](../../addons/vme_belgie/models/account_move.py#L52) | 52 | art. 3.89 §5 BW | a provision is paid to the bank account of its fund. |
| [addons/vme_belgie/models/account_move.py](../../addons/vme_belgie/models/account_move.py#L144) | 144 | art. 3.94 BW | costs are split between seller and buyer by the number of days each one owned the lot within the cost period. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L12) | 12 | art. 3.89 §5 BW | every VME keeps its own accounts, so each association gets its own res.company. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L31) | 31 | art. 3.89 §5 BW | working and reserve capital on separate accounts. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L80) | 80 | KB 12 juli 2012 (minimum chart of accounts for VMEs) | The full Belgian PCMN is the closest standard Odoo chart for now. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L109) | 109 | art. 3.89 §5 BW | working and reserve capital must not share an account. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L132) | 132 | art. 3.89 §5 BW | working and reserve capital on separate bank accounts. |
| [addons/vme_belgie/models/vme_budget.py](../../addons/vme_belgie/models/vme_budget.py#L5) | 5 | art. 3.86 §3 BW | yearly reserve fund contribution of at least 5% of the ordinary common charges of the previous year, unless the general assembly decides otherwise with a 4/5 majority. |
| [addons/vme_belgie/models/vme_key.py](../../addons/vme_belgie/models/vme_key.py#L60) | 60 | art. 3.85 §1 BW | the deed of division sets each lot's share in the common parts; the shares of a key must add up to its total. |
| [addons/vme_belgie/wizard/vme_provision_call_wizard.py](../../addons/vme_belgie/wizard/vme_provision_call_wizard.py#L115) | 115 | art. 3.89 §5 BW | working and reserve capital on separate bank accounts, so each fund gets its own invoice paid to its own account. |
