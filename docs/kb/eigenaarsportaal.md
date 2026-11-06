# Het eigenaarsportaal

In het portaal ziet een eigenaar na het inloggen alleen zijn eigen VME en zijn eigen kavels: de documenten, zijn provisies met de betaalstatus, zijn jaarafrekeningen en de volgende algemene vergadering. Hij kan er ook zijn adres wijzigen; u keurt die wijziging eerst goed.

## Hoe geef ik een eigenaar toegang?

1. Ga naar **VME > Eigenaars > Register van eigenaars**.
2. Kijk na of het e-mailadres van de eigenaar klopt: dat wordt zijn login.
3. Klik op de regel van de eigenaar op **Portaaltoegang**.
4. Zet in het venster **Toegang verlenen** aan voor de eigenaar. Odoo stuurt dan de uitnodiging met een link om een wachtwoord te kiezen. Dat gebeurt pas als u zelf klikt; het platform verstuurt nooit uit zichzelf uitnodigingen.

In de kolom **Portaal** ziet u wie al toegang heeft.

## Wat ziet de eigenaar?

Na het inloggen klikt de eigenaar op **Mijn mede-eigendom**. Per VME ziet hij:

- **Zijn kavels**, met de datum waarop hij eigenaar werd (en tot wanneer, na een verkoop).
- **De volgende algemene vergadering**: de periode, of zodra ze gepland is de datum, de plaats en de agenda.
- Bij een hybride of online AV een knop **Online deelnemen en stemmen**, en na de vergadering de melding **Notulen te ondertekenen** (zie [Een hybride of online algemene vergadering houden](digitale-av.md)).
- **Provisies**: elke provisieoproep met fonds, vervaldag, bedrag, wat nog te betalen is en de status (betaald, deels betaald, open, vervallen). Met een PDF per oproep.
- **Jaarafrekeningen**: per jaar zijn kosten per verdeelsleutel, de facturen, wat hij betaalde en zijn saldo, ook als PDF. Het lopende jaar staat er als "voorlopig".
- **Documenten**, per map (zie [Documenten van een VME en van een kavel](documenten.md)).
- **Bevragingen** om te beantwoorden en **Mijn aanvragen** met hun status (zie [Aanvragen en bevragingen in het eigenaarsportaal](portaal-aanvragen-bevragingen.md)). Ook een huurder met een login ziet die twee, maar niet de documenten en provisies.

Wat de eigenaar nooit ziet: andere VME's, kavels van andere eigenaars, verkoopdossiers, invorderingsdossiers en herinneringen, interne documenten.

## Hoe keur ik een adreswijziging goed?

Een eigenaar wijzigt zijn adres in het portaal via **Adres wijzigen**. Zijn gegevens veranderen dan nog niet: er komt een aanvraag, en u krijgt een taak.

1. Ga naar **VME > Eigenaars > Adreswijzigingen**. U ziet de aanvragen die te keuren zijn.
2. Open de aanvraag. Links staan de nieuwe gegevens, rechts de gegevens van op het moment van de aanvraag.
3. Klopt het, klik dan op **Goedkeuren**: Odoo past de eigenaar aan. Anders klikt u op **Weigeren**.

Zolang een aanvraag openstaat, kan de eigenaar geen nieuwe indienen.

**Voorbeeld in de demo:** log in als eigenaar van A1 in Residentie Linde (login `eigenaar.linde.a1@example.com`, wachtwoord `portaal-demo`). U ziet A1 en garage G1, vier betaalde provisieoproepen per fonds in 2026, de voorlopige jaarafrekening 2026 en de documenten van het gebouw en van A1. Zijn adreswijziging naar Gent wacht op goedkeuring. Met `eigenaar.linde.a5@example.com` ziet u de verkoper van A5: hij ziet niets meer van na 1 juli 2026.

## Veelgestelde vragen

**De eigenaar ziet geen volgende AV.**
Er is nog geen AV voor volgend jaar. Zodra de AV-planner (zie [Algemene vergaderingen plannen](av-planner.md)) ze aanmaakt, ziet de eigenaar de periode; na het bevestigen ook datum, plaats en agenda.

**Kan een eigenaar zijn adres niet gewoon zelf aanpassen bij "Mijn account"?**
Nee. Het register van eigenaars moet kloppen, want daar gaan oproepingen en afrekeningen naartoe. Odoo stuurt de eigenaar daarom naar het formulier met goedkeuring.

**Een eigenaar heeft twee kavels in verschillende gebouwen die wij beheren.**
Hij ziet beide VME's onder **Mijn mede-eigendom**, elk apart.

**Ziet de eigenaar ook de facturen van de leveranciers?**
Alleen in zijn jaarafrekening: leverancier, omschrijving, sleutel, het totaal en zijn aandeel. De facturen zelf ziet de commissaris van de rekeningen (volgende stap).
