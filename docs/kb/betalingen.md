# Hoe betaal ik leveranciers en hoe domicilieer ik provisies?

Het platform maakt de betaalopdrachten van een VME klaar als een bestand dat u in de bankapplicatie oplaadt. Er gaat nooit iets vanzelf naar de bank: u downloadt het bestand, laadt het op en ondertekent het in de bank, zoals u dat vandaag met de hand doet. Het volgende rekeninguittreksel bevestigt daarna elke betaling.

Er zijn twee soorten bestanden:

- **Overschrijvingen** naar leveranciers (het SEPA-formaat "pain.001"). Eén bestand per VME en per rekening: werkkapitaal of reservekapitaal.
- **Domiciliëringen** van provisies bij eigenaars die een mandaat ondertekend hebben (het SEPA-formaat "pain.008"). Eén bestand per provisieoproep.

## Eerst goedkeuren

Een leveranciersfactuur komt pas in een betaalvoorstel als ze goedgekeurd is.

1. Ga naar **VME > Betalingen > Facturen goedkeuren**. U ziet de bevestigde facturen die nog betaald moeten worden, per status.
2. Open een factuur, kijk ze na en klik op **Goedkeuren voor betaling** (of op het vinkje in de lijst).
3. Is het bedrag (btw inbegrepen) gelijk aan of hoger dan het bedrag dat op de VME ingesteld is, dan staat de factuur op **Wacht op tweede goedkeuring**. De tweede goedkeurder van de VME (bijvoorbeeld een lid van de raad van mede-eigendom) krijgt een taak en klikt op **Tweede goedkeuring**. Dat moet een andere persoon zijn dan wie de factuur eerst goedkeurde.

U stelt het bedrag en de tweede goedkeurder in op de VME, tabblad **Betalingen**. Zet u het bedrag op 0, dan volstaat altijd één goedkeuring. Zet u een factuur terug naar concept om ze te wijzigen, dan vervalt de goedkeuring.

## Leveranciers betalen

1. Ga naar **VME > Betalingen > Betaalbatches** en klik op **Nieuw**.
2. Kies de **VME** en de **Fondsrekening** waarvan u betaalt (meestal werkkapitaal). Een factuur die uit het reservekapitaal betaald moet worden, zet u op de factuur bij **Te betalen uit** op Reservekapitaal.
3. Pas zo nodig **Vervallen tot en met** en de **Uitvoeringsdatum** aan, en klik op **Betaalvoorstel vullen**. Het voorstel neemt alle goedgekeurde facturen die tegen die dag vervallen.
4. Het tabblad **Niet opgenomen** toont welke facturen er niet in staan en waarom: nog niet goedgekeurd, wacht op de tweede goedkeuring, of geen bevestigd rekeningnummer van de leverancier. Een betaling die u nu niet wilt doen, verwijdert u met het vuilbakje.
5. Klik op **SEPA-bestand maken**. Het platform controleert het bestand tegen het officiële SEPA-schema.
6. Klik op **Bestand downloaden**, laad het op in de bankapplicatie van de VME en onderteken het daar.
7. Klik in Odoo op **Opgeladen in de bank**. De betalingen staan nu op **Verstuurd**.
8. Lees het volgende rekeninguittreksel in (**VME > Bank > Bankafschriften inlezen**). Elke betaling die de bank uitvoerde, staat dan op **Bevestigd door de bank** en de factuur op betaald. Zijn alle betalingen bevestigd, dan staat de batch op **Afgehandeld**.

Het platform betaalt nooit naar een rekeningnummer dat niet bevestigd is. Een nieuw rekeningnummer van een leverancier laat u eerst bevestigen door iemand met dat recht: open de leverancier, tabblad **Facturatie**, de rekening, en zet **Betalen** aan.

## Provisies domiciliëren

1. Leg het mandaat van de eigenaar vast: **VME > Betalingen > SEPA-mandaten > Nieuw**, of op de VME, tabblad **Betalingen**. Vul de eigenaar, zijn rekeningnummer en de datum van ondertekening in; de mandaatreferentie wordt automatisch ingevuld (of neem de referentie van het papieren mandaat over).
2. Kijk op de VME, tabblad **Betalingen**, de **Schuldeiseridentificatie** na. Die wordt uit het KBO-nummer gemaakt; uw bank bevestigt ze wanneer u het incassocontract voor de VME afsluit.
3. Open de provisieoproep (**VME > Provisieoproepen**) en klik op **Domiciliëren**. U krijgt een incassobatch met de open provisies van de eigenaars met een mandaat; de anderen staan onder **Niet opgenomen**.
4. De inningsdatum ligt standaard op de vervaldag, en ten vroegste 14 dagen na de provisieoproep: de eigenaar moet vooraf weten hoeveel en wanneer er geïnd wordt.
5. **SEPA-bestand maken**, **Bestand downloaden**, opladen in de bank en **Opgeladen in de bank**, zoals bij de overschrijvingen. Werkkapitaal en reservekapitaal komen elk op hun eigen rekening.
6. Lees het rekeninguittreksel in. Elke geïnde provisie staat dan op betaald.

### Een domiciliëring komt terug

Heeft een eigenaar onvoldoende saldo of weigert hij de inning, dan boekt de bank het bedrag terug. Bij het inlezen van dat uittreksel:

- staat de beweging in **Op te volgen betalingen** met de uitzondering **Domiciliëring teruggekomen** en de reden (bijvoorbeeld "AM04 Onvoldoende saldo");
- is de provisie weer open, met haar oorspronkelijke vervaldag;
- staat de eigenaar in **VME > Invordering > Dossiers** met een notitie over de mislukte inning. Vanaf daar volgt u de gewone invordering.

## Voorbeeld uit de demo

Laad na de demodata en de demohistoriek ook **VME > Configuratie > Demo betalingsverkeer laden**. Een demomedewerker heeft dan alle open leveranciersfacturen goedgekeurd; de facturen vanaf 2.500 euro wachten op uw tweede goedkeuring, want u bent de tweede goedkeurder van de drie demo-VME's. Vijf eigenaars hebben een mandaat, onder wie **Eigenaar Beuken B7**.

1. Keur bij Hof ter Beuken de gasfactuur van 14.520 euro voor de tweede keer goed.
2. Maak een betaalbatch voor Hof ter Beuken, werkkapitaal: de gasfactuur staat erin, de andere facturen staan onder **Niet opgenomen** (wachten op de tweede goedkeuring). De elektriciteitsfactuur staat er ook niet in: het rekeningnummer van de energieleverancier is nooit bevestigd.
3. Maak het bestand en markeer het als opgeladen.
4. Open **Hof ter Beuken oproep 4/4 2026** en klik op **Domiciliëren**: de open provisie van B7 (220 euro) komt erin.
5. **VME > Configuratie > Demo-afschrift voor betaalbatches** leest een verzonnen uittreksel in dat alle verstuurde batches bevestigt, maar de inning bij B7 laat terugkomen wegens onvoldoende saldo.

## Veelgestelde vragen

**Stuurt het platform betalingen naar de bank?**
Nee. U downloadt het bestand en laadt het zelf op. Een rechtstreekse koppeling met de bank is voor later.

**Waarom staat een factuur niet in het betaalvoorstel?**
Kijk in het tabblad **Niet opgenomen**: niet goedgekeurd, wacht op de tweede goedkeuring, geen of een niet-bevestigd rekeningnummer. Staat ze daar ook niet, dan vervalt ze later dan **Vervallen tot en met**, hoort ze bij het andere fonds, zit ze al in een andere batch of is ze al betaald.

**Ik heb het bestand gemaakt maar nog niet opgeladen, en wil iets wijzigen.**
Klik op **Terug naar concept**, wijzig en maak het bestand opnieuw. Is het al opgeladen, dan annuleert u in de bank zelf.

**De bank bevestigt een betaling niet.**
Zolang het uittreksel de betaling niet bevat, blijft ze op **Verstuurd**. Kijk in de bankapplicatie of het bestand ondertekend en uitgevoerd is.

**Een eigenaar trekt zijn mandaat in.**
Open het mandaat en klik op **Intrekken**. Volgende provisieoproepen komen dan niet meer in het incassobestand.

**Mag de eigenaar een geïnde provisie terugvragen?**
Ja, bij een SEPA-domiciliëring kan hij dat bij zijn bank tot acht weken na de inning. Dat komt terug als een teruggekomen domiciliëring en gaat naar de invordering.
