# Ontwerpbeslissingen

- **Odoo 19 Community voor het prototype.** Zo is er geen licentie nodig en blijft de code onafhankelijk van het Enterprise-pakket van Odoo. Of het product later op Enterprise draait, beslissen we na de pilot.
- **Elke VME is een aparte company.** Dat volgt de wettelijke scheiding van boekhouding en fondsen. Schaal met honderden companies testen we apart.
- **AI-assistent als los script via de API.** Zo blijft de AI-laag los van de Odoo-versie en kan ze later ook naast andere syndicussoftware werken.
- **Een VME maakt zelf haar company aan.** Bij het opslaan van een nieuwe VME maakt de module automatisch een Belgische company met het volledige PCMN-rekeningstelsel (`be_comp`). Of het minimumschema voor VME's (KB 12 juli 2012) een eigen rekeningstelsel vraagt, bekijken we bij de boekhoudstappen.
- **`l10n_be` en `account_peppol` zijn vaste afhankelijkheden.** Anders installeert Odoo ze zelf zodra de eerste Belgische company bestaat, midden in het opslaan, en loopt dat verzoek vast. Peppol is in België sowieso nodig om e-facturen van leveranciers te ontvangen.
- **De som van de quotiteiten is een harde controle.** Een sleutel waarvan de lijnen niet optellen tot het totaal, kan niet worden opgeslagen; het formulier toont het verschil al tijdens het invullen. Zo kan een fout in de sleutel nooit doorlopen naar de verdeling van kosten.
- **Eén eigenaar per kavel tegelijk.** Een verkoop is een eigendom dat eindigt op de dag voor het volgende begint, en overlappende periodes worden geweigerd. Mede-eigendom en vruchtgebruik (verdeling over meerdere personen) komen later.
- **Nog geen record rules per company.** Een medewerker van de syndicus moet alle VME's tegelijk kunnen zien en bewerken. Afscherming per VME of per gebruiker komt pas als er een echte gebruikersgroep "Syndicus" is.
