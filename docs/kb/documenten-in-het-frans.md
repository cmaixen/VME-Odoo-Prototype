# Documenten in het Frans sturen

Odoo kent het Nederlands en het Frans. Elke eigenaar, huurder, notaris of leverancier heeft een taal. Wat Odoo voor die persoon opmaakt (provisieoproep, jaarafrekening, oproeping voor de AV, herinnering, brief, inlichtingen aan de notaris, indexatiebrief, afrekening aan de verhuurder), komt in zijn taal, ook als u zelf in het Nederlands werkt.

## Hoe stel ik de taal van een eigenaar in?

1. Open de eigenaar, bijvoorbeeld via **VME > Kavels**, de kavel en dan de naam van de eigenaar.
2. Kies in het veld **Taal** "French (BE) / Français (BE)".
3. Bewaar.

Vanaf nu komen nieuwe documenten voor die eigenaar in het Frans.

## Hoe werk ik zelf in het Frans?

Klik rechtsboven op uw naam, kies **Mijn voorkeuren** en zet de **Taal** op "French (BE) / Français (BE)". De menu's en schermen worden Frans: VME heet dan ACP, provisieoproep "appel de fonds", werkkapitaal "fonds de roulement".

Staat het Frans nog niet in de lijst, dan moet een beheerder het eerst activeren via **Instellingen > Talen**.

## Welke documenten volgen welke taal?

| Document | Taal van |
| --- | --- |
| Provisieoproep, jaarafrekening, oproeping AV, herinnering en aanmaning, brief | de eigenaar |
| Inlichtingen aan de notaris | de notaris |
| Indexatiebrief, afrekening lasten (rentmeester) | de huurder |
| Afrekening aan de verhuurder en de ereloonfactuur van de rentmeester | de verhuurder |
| Bestelbon | de leverancier |
| Notulen, verslag van de commissaris, lopende dossiers, balans en resultatenrekening, aanplakbrief van de syndicus, ereloonfactuur van de syndicus | de VME (taal van de VME-company) |

## Voorbeeld uit de demo

Zet **Eigenaar Linde A3** van Residentie Linde op Frans en maak de jaarafrekening 2026: de pagina van A3 staat in het Frans ("Décompte annuel 2026", "Votre quote-part"), die van de andere eigenaars in het Nederlands, in dezelfde PDF.

Voor een Franstalig gebouw zet u de taal van de VME zelf op Frans (de contactfiche van de VME, veld **Taal**). Dan komen de balans en resultatenrekening ("Bilan et compte de résultats"), de aanplakbrief aan de ingang ("Désignation du syndic") en de lijnen op de ereloonfactuur ("Honoraires fixes") in het Frans.

## De productwebsite in het Frans

Is het Frans geactiveerd, dan heeft de website een Franse versie (adres met `/fr/`, bijvoorbeeld http://localhost:8069/fr/), met het menu in het Frans. De Nederlandse versie blijft de standaard.

## Veelgestelde vragen

**Blijven sommige woorden toch Nederlands?**
Ja: wat u zelf ingeeft, wordt niet vertaald. De naam van een verdeelsleutel ("Algemene sleutel"), de tekst van een agendapunt, de naam van een zaal of een vrije brief blijven zoals u ze schreef. Voor een Franstalig gebouw geeft u die meteen in het Frans in.

**Een provisieoproep die al gemaakt was, staat nog in het Nederlands.**
De omschrijving van een factuur wordt vastgelegd op het moment dat ze gemaakt wordt. Pas de taal van de eigenaar aan vóór de volgende oproep; de vorige facturen blijven zoals ze zijn.

**Een doorstorting aan de verhuurder staat nog in het Nederlands.**
Zolang ze een concept is, klikt u op **Herberekenen**: de lijnen worden opnieuw gemaakt in de taal van de verhuurder. Een bevestigde doorstorting blijft zoals ze is.

**Een herinnering staat al klaar in het Nederlands.**
Klik in het concept van de herinnering op **Bijwerken**: Odoo maakt de tekst opnieuw op in de taal van de eigenaar.

**Wordt er iets automatisch in het Frans verstuurd?**
Nee. De taal bepaalt alleen hoe het document opgemaakt wordt. U kijkt elk document na en verstuurt het zelf.
