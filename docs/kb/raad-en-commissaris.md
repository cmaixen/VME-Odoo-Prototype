# De raad van mede-eigendom en de commissaris van de rekeningen

De algemene vergadering kiest elk jaar een **commissaris van de rekeningen**, die de boekhouding van de VME nakijkt en daarover verslag uitbrengt op de volgende AV. In een gebouw met minstens twintig kavels (garages en bergingen niet meegeteld) kiest ze ook een **raad van mede-eigendom**, die toeziet op het werk van de syndicus.

In Odoo legt u per VME vast wie in de raad zit en wie commissaris is. De commissaris kan een eigen login krijgen om de boekhouding, de facturen en de bankafschriften van zijn VME in te kijken. Hij kan niets wijzigen en ziet niets van andere VME's. Voor de raad maakt Odoo een overzicht van alle lopende dossiers.

> De wettelijke regels hieronder zijn nog niet juridisch nagekeken.

## Hoe leg ik de raad en de commissaris vast?

1. Open de VME in **VME > VME's** en ga naar het tabblad **Raad en commissaris**.
2. Klik op **Regel toevoegen** en kies:
   - de **rol**: voorzitter van de raad, lid van de raad of commissaris van de rekeningen;
   - de **persoon**;
   - de **begindatum** van het mandaat. Het einde vult Odoo in op één jaar later; u kunt het aanpassen.
3. Bewaar de VME.

Open een mandaat om ook de **beslissing van de AV** te kiezen waarmee de persoon werd aangesteld, en bij een commissaris het **boekjaar** dat hij controleert.

Alle mandaten van alle VME's samen staan in **VME > Raad en commissaris > Leden en mandaten**.

**Voorbeeld uit de demo.** Hof ter Beuken heeft 24 appartementen, dus een raad is verplicht. Eigenaar Beuken B1 is voorzitter, B6 en B11 zijn lid, en Commissaris Voorbeeld Beuken (geen eigenaar) is commissaris. In Residentie Linde (12 appartementen en 8 garages) is een raad niet verplicht; eigenaar Linde A2 is er commissaris.

## Wanneer waarschuwt Odoo?

Bovenaan het tabblad **Raad en commissaris** staat een gele waarschuwing als:

- de VME twintig kavels of meer heeft (zonder garages en bergingen) en er geen lopend mandaat in de raad is;
- er geen lopende commissaris van de rekeningen is.

Odoo weigert ook:

- een lid of voorzitter van de raad die op de begindatum geen eigenaar is in deze VME. De commissaris mag wel iemand van buiten zijn;
- twee voorzitters van de raad in dezelfde periode.

## Hoe geef ik de commissaris toegang?

Dit kan alleen wie gebruikers beheert (bv. de beheerder van Odoo).

1. Open het mandaat van de commissaris. Zijn e-mailadres moet ingevuld zijn: dat wordt zijn login.
2. Klik op **Leestoegang geven**. Odoo maakt een gebruiker voor hem aan die alleen deze VME ziet.
3. Odoo stuurt **geen** uitnodiging. Wilt u hem laten inloggen, open dan de gebruiker (via het veld **Gebruiker** op het mandaat) en verstuur zelf de e-mail om een wachtwoord te kiezen.

Is iemand commissaris in twee VME's, dan geeft u op beide mandaten toegang: het is dezelfde gebruiker, die dan beide VME's ziet.

Wat de commissaris kan:

- in het menu **VME > Commissaris**: de leveranciersfacturen, de provisies en afrekeningen, de bankbewegingen en de boekingen van zijn VME;
- de VME, kavels, eigenaars, verdeelsleutels, budgetten, verkoopdossiers, invordering, keuringen en AV's van zijn VME bekijken;
- het overzicht van de lopende dossiers bekijken;
- zijn verslag aan de AV afdrukken (zie hieronder).

Wat hij niet kan: iets aanmaken, wijzigen of verwijderen, berichten plaatsen, betalingen koppelen of herinneringen maken. De knoppen **Nieuw** en **Bewerken** ziet hij niet. Klikt hij op een andere knop, dan krijgt hij de melding dat hij als commissaris alleen kan inkijken.

## Wanneer vervalt de toegang?

- Elke nacht kijkt Odoo welke mandaten nog lopen. Na het einde van het laatste mandaat wordt de gebruiker gearchiveerd: hij kan niet meer inloggen.
- Met **Leestoegang intrekken** op het mandaat stopt u de toegang meteen.
- Herkiest de AV de commissaris, maak dan een nieuw mandaat en klik opnieuw op **Leestoegang geven**. Odoo gebruikt dezelfde gebruiker opnieuw.

## Hoe maakt de commissaris zijn verslag?

1. Open het mandaat (de commissaris zelf via **VME > Commissaris > Mijn mandaten en verslag**).
2. Klik op **Sjabloon verslag aan de AV**.
3. Odoo maakt een PDF met:
   - de opdracht: wie, door welke AV-beslissing, en over welk boekjaar;
   - de cijfers uit de boekhouding van dat boekjaar: aantal en totaal van de leveranciersfacturen en van de provisies en afrekeningen, per bankrekening het aantal bewegingen en het saldo volgens de bankafschriften, wat eigenaars en leveranciers op het einde van het jaar nog moeten betalen of krijgen, en de stand van het reservekapitaal;
   - een lijst van controles om af te vinken, een vak voor de bevindingen en drie mogelijke besluiten voor de AV;
   - plaats voor datum en handtekening.

De commissaris vult de controles, bevindingen en het besluit zelf in.

## Hoe zie ik de lopende dossiers voor de raad?

1. Open **VME > Raad en commissaris > Lopende dossiers**, of klik op een VME op de knop **Lopende dossiers**.
2. U ziet per VME en per soort:
   - **Verkoop**: verkoopdossiers waarvan de akte nog niet verleden is, met de termijn voor het antwoord aan de notaris;
   - **Invordering**: lopende of doorgestuurde dossiers, met het laatst verstuurde niveau;
   - **Keuring**: opmerkingen uit keuringsverslagen die nog open of gepland zijn, met hun termijn;
   - **Opvolging AV**: open opvolgtaken van beslissingen van de AV.
3. Wat over termijn is, staat in het rood. Met **Openen** gaat u naar het dossier zelf.
4. Op het tabblad **Raad en commissaris** van de VME drukt u met **Overzicht voor de raad afdrukken** dezelfde lijst af als PDF, om mee te nemen naar de vergadering van de raad.

Werken en schadegevallen komen later in hetzelfde overzicht.

**Voorbeeld uit de demo.** Residentie Linde heeft vijf lopende dossiers: de verkoop van A3 en G3 (antwoord aan de notaris tegen 12 november), de invordering bij A3, twee opmerkingen uit keuringen en de opvolgtaak "Drie offertes vragen voor de dakwerken".

## Veelgestelde vragen

**Kan een lid van de raad ook inloggen?**
Nog niet. In deze versie krijgt alleen de commissaris een login. De raad krijgt het overzicht van de lopende dossiers als PDF.

**De commissaris ziet een knop, maar krijgt een foutmelding als hij erop klikt. Is dat normaal?**
Ja. Hij ziet dezelfde schermen als een medewerker, maar alles wat iets wijzigt, wordt geweigerd.

**Ziet de commissaris de eigenaars van andere gebouwen?**
Nee. Hij ziet alleen de eigenaars, leveranciers en dossiers van zijn eigen VME, en de namen van de medewerkers van de syndicus.

**Moet de commissaris een eigenaar zijn?**
Nee. De AV mag ook iemand van buiten kiezen, bv. een boekhouder. Leden van de raad moeten wel eigenaar zijn.

**Een medewerker van ons kantoor is ook commissaris in een VME. Kan hij toegang krijgen?**
Niet met zijn gewone gebruiker: Odoo weigert dat, omdat die gebruiker al meer rechten heeft. Geef hem een aparte gebruiker met een ander e-mailadres.
