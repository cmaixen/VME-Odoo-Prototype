# Aanvragen en bevragingen in het eigenaarsportaal

Eigenaars en huurders kunnen in het portaal zelf een aanvraag indienen voor hun kavel (een extra sleutel of badge, een defect, een attest, …) en zien daar hoe ver die staat. Ze beantwoorden er ook de bevragingen die u verstuurt. U blijft beslissen: een aanvraag uit het portaal volgt dezelfde procedure als een aanvraag per mail, en er wordt niets besteld of verstuurd zonder dat u klikt.

## Wat ziet de eigenaar of huurder?

Onder **Mijn mede-eigendom** staan, naast de kavels:

- **Bevragingen**: elke bevraging die hij kreeg, met "Uw antwoord gevraagd", "Beantwoord" of "Afgesloten".
- **Mijn aanvragen**: de laatste aanvragen met hun status, en de knop **Nieuwe aanvraag**.
- Een huurder ziet **Gehuurde kavels**. Documenten, provisies en afrekeningen van het gebouw blijven voor de eigenaars.

De status van een aanvraag in het portaal:

| In het portaal | In Odoo |
| --- | --- |
| Wacht op uw bewijs | Wacht op bewijs |
| In behandeling | In behandeling |
| Besteld | Besteld |
| Afgehandeld | Afgehandeld |
| Geweigerd (met uw reden) | Geweigerd |

De eigenaar ziet ook de berichten die u hem vanuit de aanvraag stuurde (bijvoorbeeld de bewijsvraag), maar nooit uw interne notities, de concepten of de bestelling aan de slotenmaker.

## Hoe behandel ik een aanvraag uit het portaal?

1. Ga naar **VME > Aanvragen**. Een aanvraag uit het portaal heeft als kanaal **Portaal**; u krijgt er ook een taak voor.
2. Odoo herkent de aanvrager zoals bij een mail: is hij eigenaar van de kavel, dan is de aanvraag meteen geverifieerd (hij is aangemeld; een mail moet de eigenaar eerst bevestigen). Een huurder bezorgt de toestemming van de eigenaar en het huurcontract.
3. Wacht de aanvraag op bewijs, klik dan op **Bewijs opvragen** zoals altijd. De huurder kan de documenten in het portaal opladen bij **Bewijs bezorgen**; u krijgt dan de taak **Bewijs uit het portaal nakijken**. Vink na het nakijken de bewijsstukken aan en klik op **Bewijs goedkeuren**.
4. Daarna loopt de procedure verder zoals in [Aanvragen van bewoners](aanvragen-sleutels-badges.md): de bestelling staat klaar als concept en vertrekt pas als u op **Bestelling versturen** klikt.

Een eigenaar kan alleen een aanvraag indienen voor de kavels die hij vandaag bezit, een huurder voor de kavel die hij huurt. Na een verkoop kan de verkoper geen nieuwe aanvragen meer doen; zijn oude aanvragen blijft hij zien.

## Hoe zie ik de antwoorden op een bevraging?

1. Verstuur de bevraging zoals beschreven in [Communicatie met eigenaars](communicatie.md). Wie een login voor het portaal heeft, krijgt in de mail een link om te antwoorden.
2. Open de verzending. In het tabblad **Ontvangers en antwoorden** staat per eigenaar het antwoord, de opmerking, de datum en **Antwoord via**: "Portaal" als de eigenaar zelf antwoordde, of "Ingegeven door de syndicus" als een medewerker een antwoord op papier of aan de telefoon ingaf.
3. In het tabblad **Bevraging** ziet u per mogelijk antwoord het aantal.

Een eigenaar kan zijn antwoord wijzigen tot de datum bij **Antwoorden tegen**. Daarna is de bevraging afgesloten in het portaal; u kunt zelf nog antwoorden ingeven.

**Voorbeeld in de demo:** log in als eigenaar van A1 in Residentie Linde (`eigenaar.linde.a1@example.com`, wachtwoord `portaal-demo`). Onder **Mijn aanvragen** staat zijn aanvraag voor een attest van de betaalde provisies, "In behandeling". Bij **Bevragingen** ziet u dat hij de bevraging over laadpalen al beantwoordde ("Ja, binnen het jaar", met een opmerking); de eigenaars van A2 en A3 antwoordden op papier. Log in als `eigenaar.linde.a6@example.com` om live te antwoorden, of als huurder van A6 (`huurder.linde.a6@example.com`) om een badge aan te vragen: die aanvraag wacht op bewijs.

## Veelgestelde vragen

**Wordt er iets automatisch besteld als een eigenaar een badge vraagt?**
Nee. De bestelbon en de mail aan de slotenmaker staan klaar als concept; alleen u verstuurt ze.

**Ziet een eigenaar de aanvragen van zijn huurder?**
Nee, alleen zijn eigen aanvragen. Wordt een sleutel voor de huurder aangerekend, dan krijgt de eigenaar wel de factuur.

**Kan een huurder in het portaal zonder login?**
Nee. Geef de huurder toegang zoals een eigenaar (zie [Het eigenaarsportaal](eigenaarsportaal.md)); hij moet als huurder van de kavel geregistreerd zijn (tabblad **Huurders en bewoners** van de kavel, of een huurcontract bij de rentmeester).

**Een eigenaar zegt dat hij de bevraging niet ziet.**
Kijk na of de verzending **Verstuurd** is en of hij bij de ontvangers staat: een concept verschijnt niet in het portaal.
