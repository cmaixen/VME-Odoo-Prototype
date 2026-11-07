# Keuringen en liften opvolgen

Elke VME heeft installaties die op vaste tijdstippen gekeurd moeten worden: de lift, de brandblussers, de elektrische installatie van de gemene delen, de centrale verwarmingsketel, de rookluiken. Het menu **VME > Keuringen** toont ze voor al uw VME's samen, met wat vervallen is en wat binnenkort vervalt.

## Hoe zie ik welke keuringen vervallen?

1. Open **VME > Keuringen > Installaties en vervaldata**.
2. De kleur van elke lijn vertelt hoe dringend het is:
   - **rood**: vervallen
   - **oranje**: vervalt binnen 30 dagen
   - **blauw**: vervalt binnen 60 of 90 dagen
   - **groen**: in orde
3. Gebruik de filters bovenaan: *Vervallen*, *Vervalt binnen 30/60/90 dagen*, *Herkeuring nodig* of *Liften*, en groepeer per VME of per soort.
4. Liever een kalender? Klik rechtsboven op het kalendericoon: elke installatie staat op de dag van haar volgende keuring.

**Voorbeeld in de demo:** de brandblussers van Residentie Linde staan in het rood (vervallen sinds 1 oktober 2026), de lift en de rookluiken van Hof ter Beuken in het oranje.

## Hoe voeg ik een installatie toe?

1. Open de VME en ga naar het tabblad **Installaties**, of klik in **VME > Keuringen** op **Nieuw**.
2. Vul de naam in (bv. "Lift blok A"), de soort, de plaats en de verantwoordelijke medewerker.
3. Vul de onderhoudsfirma en het keuringsorganisme in. Voor een lift is dat de erkende dienst voor technische controle (EDTC). Het onderhoudscontract zelf, met einddatum en opzegtermijn, voegt u toe onder **VME > Contracten** met deze installatie erbij (zie [Contracten en personeel](contracten.md)). Het verschijnt dan hier.
4. De **keuringsfrequentie** wordt automatisch ingevuld volgens de soort (bv. 6 maanden voor een lift). U kunt ze per installatie aanpassen.

## Hoe registreer ik een keuring en de opmerkingen?

1. Open de installatie en ga naar het tabblad **Keuringsverslagen**. Klik op **Regel toevoegen**.
2. Kies de soort: preventieve inspectie, herkeuring, risicoanalyse of onderhoudsbezoek. Een onderhoudsbezoek telt niet als keuring.
3. Vul de datum en het resultaat in en voeg het verslag (PDF) toe.
4. Neem elke opmerking uit het verslag over als aparte lijn, met de ernst, de termijn en wie het moet oplossen.
5. De volgende vervaldatum wordt meteen berekend. Is het resultaat "niet conform", dan krijgt de installatie het lint **Herkeuring nodig** tot er een conforme herkeuring is.

## Hoe volg ik de opmerkingen uit de verslagen op?

1. Open **VME > Keuringen > Opmerkingen keuringen**. Standaard ziet u alle open opmerkingen, per VME.
2. Met de filter **Over termijn** ziet u wat te laat is. Die lijnen staan in het rood.
3. Pas de status rechtstreeks in de lijst aan: *Gepland*, *Opgelost* of *Herkeurd*. Bij "Opgelost" wordt de datum automatisch ingevuld.

**Voorbeeld in de demo:** bij de lift van Residentie Linde staat "Noodverlichting in de liftkooi werkt niet" open en over termijn (31 augustus 2026).

## Krijg ik een herinnering?

Ja. Elke nacht maakt Odoo een taak voor de verantwoordelijke medewerker zodra een keuring of een risicoanalyse van een lift binnen 60 dagen vervalt. U ziet de taak in het activiteitenicoon bovenaan en bij de installatie. Per vervaldatum komt er maar één taak. Zodra de nieuwe keuring geregistreerd is, met de hand of via de factuur van het keuringsorganisme, vinkt Odoo die taak zelf af.

## Werkt de vervaldatum zichzelf bij als de factuur van de keuring binnenkomt?

Ja, als er een verdeelregel is voor dat keuringsorganisme met de installatie erbij (**VME > Configuratie > Verdeelregels**, kolom *Installatie*). Bij het bevestigen van de factuur:
- wordt de keuring geregistreerd op de factuurdatum
- schuift de volgende vervaldatum op
- komt er een bericht bij de factuur en de installatie

Vul daarna wel het verslag en eventuele opmerkingen aan.

**Voorbeeld in de demo:** een factuur van *Keuringsdienst Voorbeeld vzw* in Residentie Linde registreert de keuring van "Lift blok A".

## Veelgestelde vragen

**Kloppen de wettelijke frequenties?** Het zijn standaardwaarden die nog juridisch nagekeken moeten worden, en voor verwarming verschillen ze per gewest. Pas ze per installatie aan als uw contract of gewest iets anders voorschrijft.

**Ik zie een installatie niet in de lijst.** Kijk of de filter *Gearchiveerd* niet nodig is, en of u geen filter op een andere VME hebt staan.
