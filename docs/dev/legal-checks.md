# LEGAL-CHECK-punten

Automatisch gemaakt door `python3 tools/legal_checks.py`; niet met de hand bewerken.
Elke rij is een wettelijke regel in de code die nog juridisch gevalideerd moet worden.

Aantal punten: 37.

## Per bron

- **AREI (Algemeen Reglement op de Elektrische Installaties)**: [vme_installation.py:22](../../addons/vme_belgie/models/vme_installation.py#L22)
- **KB 12 juli 2012 (minimum chart of accounts for VMEs)**: [account_chart_template.py:6](../../addons/vme_belgie/models/account_chart_template.py#L6), [vme_association.py:87](../../addons/vme_belgie/models/vme_association.py#L87)
- **KB 9 maart 2003**: [vme_installation.py:33](../../addons/vme_belgie/models/vme_installation.py#L33)
- **KB 9 maart 2003 betreffende de beveiliging van liften**: [vme_installation.py:17](../../addons/vme_belgie/models/vme_installation.py#L17)
- **NBN S21-050**: [vme_installation.py:20](../../addons/vme_belgie/models/vme_installation.py#L20)
- **Vlaamse regelgeving verwarmingsaudit/onderhoud**: [vme_installation.py:25](../../addons/vme_belgie/models/vme_installation.py#L25)
- **art. 3.85 §1 BW**: [vme_key.py:60](../../addons/vme_belgie/models/vme_key.py#L60), [vme_migration.py:739](../../addons/vme_belgie/models/vme_migration.py#L739)
- **art. 3.86 §3 BW**: [vme_budget.py:5](../../addons/vme_belgie/models/vme_budget.py#L5), [vme_migration.py:445](../../addons/vme_belgie/models/vme_migration.py#L445)
- **art. 3.87 §10 BW**: [vme_assembly_meeting.py:232](../../addons/vme_belgie/models/vme_assembly_meeting.py#L232)
- **art. 3.87 §2 BW**: [vme_assembly.py:13](../../addons/vme_belgie/models/vme_assembly.py#L13), [vme_assembly.py:38](../../addons/vme_belgie/models/vme_assembly.py#L38)
- **art. 3.87 §3 BW**: [vme_assembly.py:17](../../addons/vme_belgie/models/vme_assembly.py#L17), [vme_assembly.py:42](../../addons/vme_belgie/models/vme_assembly.py#L42), [vme_assembly.py:234](../../addons/vme_belgie/models/vme_assembly.py#L234), [vme_assembly_meeting.py:168](../../addons/vme_belgie/models/vme_assembly_meeting.py#L168)
- **art. 3.87 §5 BW**: [vme_assembly_meeting.py:54](../../addons/vme_belgie/models/vme_assembly_meeting.py#L54), [vme_assembly_meeting.py:109](../../addons/vme_belgie/models/vme_assembly_meeting.py#L109)
- **art. 3.87 §6 BW**: [vme_assembly_meeting.py:122](../../addons/vme_belgie/models/vme_assembly_meeting.py#L122), [vme_assembly_meeting.py:285](../../addons/vme_belgie/models/vme_assembly_meeting.py#L285)
- **art. 3.87 §7 BW**: [vme_assembly_meeting.py:25](../../addons/vme_belgie/models/vme_assembly_meeting.py#L25), [vme_assembly_meeting.py:381](../../addons/vme_belgie/models/vme_assembly_meeting.py#L381)
- **art. 3.88 §1-3 BW**: [vme_assembly_meeting.py:8](../../addons/vme_belgie/models/vme_assembly_meeting.py#L8)
- **art. 3.88 §3 BW**: [vme_assembly_meeting.py:302](../../addons/vme_belgie/models/vme_assembly_meeting.py#L302)
- **art. 3.89 §5 BW**: [account_move.py:52](../../addons/vme_belgie/models/account_move.py#L52), [vme_association.py:15](../../addons/vme_belgie/models/vme_association.py#L15), [vme_association.py:34](../../addons/vme_belgie/models/vme_association.py#L34), [vme_association.py:170](../../addons/vme_belgie/models/vme_association.py#L170), [vme_association.py:193](../../addons/vme_belgie/models/vme_association.py#L193), [vme_migration.py:621](../../addons/vme_belgie/models/vme_migration.py#L621), [vme_provision_call_wizard.py:115](../../addons/vme_belgie/wizard/vme_provision_call_wizard.py#L115)
- **art. 3.93 §4 BW**: [vme_assembly_meeting.py:212](../../addons/vme_belgie/models/vme_assembly_meeting.py#L212)
- **art. 3.94 BW**: [account_move.py:144](../../addons/vme_belgie/models/account_move.py#L144)
- **art. III.88 WER**: [vme_migration.py:476](../../addons/vme_belgie/models/vme_migration.py#L476)
- **no general legal interval found; manufacturer and fire department advice**: [vme_installation.py:28](../../addons/vme_belgie/models/vme_installation.py#L28)

## Alle punten

| Bestand | Regel | Bron | Tekst |
| --- | --- | --- | --- |
| [addons/vme_belgie/models/account_chart_template.py](../../addons/vme_belgie/models/account_chart_template.py#L6) | 6 | KB 12 juli 2012 (minimum chart of accounts for VMEs) | align these codes. |
| [addons/vme_belgie/models/account_move.py](../../addons/vme_belgie/models/account_move.py#L52) | 52 | art. 3.89 §5 BW | a provision is paid to the bank account of its fund. |
| [addons/vme_belgie/models/account_move.py](../../addons/vme_belgie/models/account_move.py#L144) | 144 | art. 3.94 BW | costs are split between seller and buyer by the number of days each one owned the lot within the cost period. |
| [addons/vme_belgie/models/vme_assembly.py](../../addons/vme_belgie/models/vme_assembly.py#L13) | 13 | art. 3.87 §2 BW | the ordinary general assembly takes place every year within the period of fifteen days fixed in the rules of co-ownership. |
| [addons/vme_belgie/models/vme_assembly.py](../../addons/vme_belgie/models/vme_assembly.py#L17) | 17 | art. 3.87 §3 BW | the convocation is sent at least fifteen days before the meeting, unless the rules of co-ownership set another term. |
| [addons/vme_belgie/models/vme_assembly.py](../../addons/vme_belgie/models/vme_assembly.py#L38) | 38 | art. 3.87 §2 BW | fifteen-day period from the rules of co-ownership. |
| [addons/vme_belgie/models/vme_assembly.py](../../addons/vme_belgie/models/vme_assembly.py#L42) | 42 | art. 3.87 §3 BW | at least 15 days unless the rules of co-ownership say otherwise. |
| [addons/vme_belgie/models/vme_assembly.py](../../addons/vme_belgie/models/vme_assembly.py#L234) | 234 | art. 3.87 §3 BW | convocation at least 15 days before the meeting. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L8) | 8 | art. 3.88 §1-3 BW | required majorities. Abstentions, blank and invalid votes do not count as cast votes (art. 3.87 §8 BW). Unanimity is of all co-owners, not only those present (art. 3.88 §3 BW). |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L25) | 25 | art. 3.87 §7 BW | nobody may hold more than three proxies, unless the votes they hold themselves plus those of their proxies do not exceed 10% of all votes. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L54) | 54 | art. 3.87 §5 BW | without quorum a second assembly may be convened at least fifteen days later; it deliberates whatever the number of members present. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L109) | 109 | art. 3.87 §5 BW | more than half of the co-owners holding at least half of the shares, or co-owners holding more than three quarters of the shares. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L122) | 122 | art. 3.87 §6 BW | each co-owner votes with the shares of his lots in the common parts. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L168) | 168 | art. 3.87 §3 BW | convocation at least fifteen days before the meeting. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L212) | 212 | art. 3.93 §4 BW | the syndic keeps a register of the decisions of the general assembly. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L232) | 232 | art. 3.87 §10 BW | the syndic writes the minutes, signed at the end of the meeting by the chair, the secretary and the co-owners still present. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L285) | 285 | art. 3.87 §6 BW | nobody votes with more votes than all other present or represented co-owners together. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L302) | 302 | art. 3.88 §3 BW | unanimity of the votes of all co-owners. |
| [addons/vme_belgie/models/vme_assembly_meeting.py](../../addons/vme_belgie/models/vme_assembly_meeting.py#L381) | 381 | art. 3.87 §7 BW | more than three proxies only up to 10% of all votes. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L15) | 15 | art. 3.89 §5 BW | every VME keeps its own accounts, so each association gets its own res.company. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L34) | 34 | art. 3.89 §5 BW | working and reserve capital on separate accounts. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L87) | 87 | KB 12 juli 2012 (minimum chart of accounts for VMEs) | The full Belgian PCMN is the closest standard Odoo chart for now. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L170) | 170 | art. 3.89 §5 BW | working and reserve capital must not share an account. |
| [addons/vme_belgie/models/vme_association.py](../../addons/vme_belgie/models/vme_association.py#L193) | 193 | art. 3.89 §5 BW | working and reserve capital on separate bank accounts. |
| [addons/vme_belgie/models/vme_budget.py](../../addons/vme_belgie/models/vme_budget.py#L5) | 5 | art. 3.86 §3 BW | yearly reserve fund contribution of at least 5% of the ordinary common charges of the previous year, unless the general assembly decides otherwise with a 4/5 majority. |
| [addons/vme_belgie/models/vme_installation.py](../../addons/vme_belgie/models/vme_installation.py#L17) | 17 | KB 9 maart 2003 betreffende de beveiliging van liften | preventive inspection by an accredited inspection body (EDTC). |
| [addons/vme_belgie/models/vme_installation.py](../../addons/vme_belgie/models/vme_installation.py#L20) | 20 | NBN S21-050 | yearly maintenance check of portable fire extinguishers and hoses. |
| [addons/vme_belgie/models/vme_installation.py](../../addons/vme_belgie/models/vme_installation.py#L22) | 22 | AREI (Algemeen Reglement op de Elektrische Installaties) | periodic inspection of the common parts of residential buildings. |
| [addons/vme_belgie/models/vme_installation.py](../../addons/vme_belgie/models/vme_installation.py#L25) | 25 | Vlaamse regelgeving verwarmingsaudit/onderhoud | gas boilers; differs per region and fuel (fuel oil is yearly). |
| [addons/vme_belgie/models/vme_installation.py](../../addons/vme_belgie/models/vme_installation.py#L28) | 28 | no general legal interval found; manufacturer and fire department advice | - |
| [addons/vme_belgie/models/vme_installation.py](../../addons/vme_belgie/models/vme_installation.py#L33) | 33 | KB 9 maart 2003 | risk analysis of an elevator at least every 15 years. |
| [addons/vme_belgie/models/vme_key.py](../../addons/vme_belgie/models/vme_key.py#L60) | 60 | art. 3.85 §1 BW | the deed of division sets each lot's share in the common parts; the shares of a key must add up to its total. |
| [addons/vme_belgie/models/vme_migration.py](../../addons/vme_belgie/models/vme_migration.py#L445) | 445 | art. 3.86 §3 BW | the reserve fund belongs to the VME and goes over in full; it is not settled with the owners. |
| [addons/vme_belgie/models/vme_migration.py](../../addons/vme_belgie/models/vme_migration.py#L476) | 476 | art. III.88 WER | accounting documents are kept for 7 years (check whether 10 years applies); art. 3.89 §5, 13° BW - the previous syndic hands over the archive. |
| [addons/vme_belgie/models/vme_migration.py](../../addons/vme_belgie/models/vme_migration.py#L621) | 621 | art. 3.89 §5 BW | working and reserve capital on separate accounts. |
| [addons/vme_belgie/models/vme_migration.py](../../addons/vme_belgie/models/vme_migration.py#L739) | 739 | art. 3.85 §1 BW | the shares of a key must add up to its total. |
| [addons/vme_belgie/wizard/vme_provision_call_wizard.py](../../addons/vme_belgie/wizard/vme_provision_call_wizard.py#L115) | 115 | art. 3.89 §5 BW | working and reserve capital on separate bank accounts, so each fund gets its own invoice paid to its own account. |
