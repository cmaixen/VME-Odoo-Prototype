# Hoe behandel ik een aanvraag voor een sleutel, badge of andere vaste procedure?

Bewoners vragen vaak hetzelfde: een extra badge, een sleutel van de garagepoort, een verhuis, een nieuwe huurder melden. In Odoo wordt elke vraag een **aanvraag** met een vaste procedure en een checklist. Bij een sleutel of badge kijkt Odoo eerst na of de aanvrager er recht op heeft, zet de bestelling voor de slotenmaker klaar en rekent de kost aan de eigenaar van het appartement aan.

**Er vertrekt nooit iets vanzelf.** De vraag om bewijs, de herinnering en de bestelling staan als concept klaar. Ze vertrekken pas als u op de knop klikt.

## Waar vind ik de aanvragen?

- **VME > Aanvragen > Aanvragen**: alle open aanvragen van alle gebouwen. Met de filters **Wacht op bewijs**, **Herinnering nodig**, **Te bestellen** en **Besteld** ziet u meteen wat u moet doen.
- Op een **VME** toont de knop **Aanvragen** bovenaan de open aanvragen van dat gebouw.
- Op een **kavel** staan de aanvragen, de **huurders en bewoners** en de **sleutels en badges** in aparte tabbladen.

## Hoe komt een aanvraag binnen?

- **Per mail.** De AI-assistent leest de mails van bewoners. Vraagt iemand een extra badge, dan maakt hij geen gewone taak maar een aanvraag, met de mail en de bijlagen erbij (zie [Een antwoord behandelen dat de AI-assistent voorstelt](ai-voorstellen-mails.md)).
- **Manueel.** Iemand belt of komt langs: klik op **VME > Aanvragen > Aanvragen > Nieuw**, kies het gebouw, de kavel, de soort aanvraag en de aanvrager.
- **Via het portaal**: komt later. Een aanvraag uit het portaal volgt dezelfde procedure.

## Wie is de aanvrager?

Odoo herkent de aanvrager aan zijn e-mailadres:

| Aanvrager | Wat er gebeurt |
| --- | --- |
| **Eigenaar van de kavel** | Via het portaal of manueel: meteen geverifieerd, de bestelling staat meteen klaar. Per mail: eerst bevestigen (zie hieronder). |
| **Huurder van de kavel** | Bezorgt de **schriftelijke toestemming van de eigenaar** en een **kopie van het huurcontract**. |
| **Onbekend** (adres niet gekend, of eigenaar van een ander appartement) | Bezorgt een **eigendomsbewijs**, bijvoorbeeld de akte of een attest van de notaris. |

Een afzenderadres van een mail kan vervalst worden. Vraagt een eigenaar per mail een sleutel of badge, dan wacht de aanvraag op zijn bevestiging. Klik op **Bewijs opvragen**: de mail vertrekt naar het adres dat bij ons gekend is, dus naar de echte eigenaar. Antwoordt hij, of bevestigt hij telefonisch, vink dan **Eigenaar bevestigde de aanvraag** aan en klik op **Bewijs goedkeuren**.

Stelt iemand zich anders voor dan Odoo denkt (bv. een onbekend adres dat schrijft "ik ben de nieuwe huurder"), pas dan **Aanvrager is** aan en klik op **Opnieuw starten**.

Huurders staan bij de kavel, tabblad **Huurders en bewoners**, of in **VME > Aanvragen > Huurders en bewoners**.

## Stappen voor een extra sleutel of badge

1. **Open de aanvraag.** Kijk de soort na in het tabblad **Sleutel of badge**: veiligheidssleutel van de inkom, sleutel of afstandsbediening van de garagepoort, of badge. Odoo raadt de soort uit de mail; pas ze aan als het niet klopt. Pas ook het **aantal** en de **prijs per stuk** aan indien nodig.
2. **Is de aanvrager geen eigenaar?** Bovenaan staat in het geel welk bewijs ontbreekt.
   - Kijk de **bewijsvraag** na in het tabblad **Berichten** en klik op **Bewijs opvragen**. De mail vertrekt naar de aanvrager.
   - Na **7 dagen** zonder antwoord krijgt u een taak, en de knop **Herinnering versturen** wordt blauw.
   - Komt het bewijs binnen, voeg het toe in het tabblad **Bewijs**, vink aan wat u ontvangen en nagekeken hebt, en klik op **Bewijs goedkeuren**. Zat het bewijs al bij de mail, dan staat het daar al.
   - Klopt het niet, vul in het tabblad **Weigering** de reden in en klik op **Weigeren**.
3. **Bestellen.** Na de verificatie maakt Odoo een **bestelbon** in de huisstijl van de VME, met het nummer van het sleutelcertificaat, en een conceptmail aan de slotenmaker van het gebouw. Kijk ze na in het tabblad **Berichten** en klik op **Bestelling versturen**. Alleen de syndicus mag veiligheidssleutels bestellen.
4. **Levering.** Geeft de slotenmaker de sleutels af, vul dan de **nummers** in (gescheiden door komma's) en klik op **Levering registreren**. Odoo:
   - zet elke sleutel of badge in het **sleutelregister** van de kavel, op naam van de aanvrager;
   - maakt een **factuur aan de eigenaar** van de kavel, ook als een huurder de aanvraag deed. Die kost wordt **niet** over de andere eigenaars verdeeld.
5. Vink in de **checklist** af wat er nog buiten Odoo gebeurde, zoals de handtekening voor ontvangst.

### Waar stel ik de slotenmaker en het sleutelcertificaat in?

Open de VME, tabblad **Sleutels en aanvragen**: kies de **slotenmaker**, vul het **nummer van het sleutelcertificaat** in en voeg eventueel een kopie van het certificaat toe. Die kopie gaat mee als bijlage bij elke bestelling.

## De andere soorten aanvragen

Elke soort heeft een eigen checklist. De lijst van stappen kan een beheerder aanpassen in **VME > Configuratie > Soorten aanvragen**.

| Soort | Wat Odoo extra doet |
| --- | --- |
| **Verlies of diefstal van een badge** | Kies in het tabblad **Blokkeren** de verloren badges en klik op **Blokkeren**: ze staan dan als geblokkeerd in het register. Laat ze ook blokkeren in het toegangssysteem. Een vervangbadge is een nieuwe aanvraag. |
| **Verhuis** | Checklist: lift reserveren, liftbescherming, borg, naambordje en brievenbus. |
| **Nieuwe huurder melden** | Vul de nieuwe huurder en de begindatum in en klik op **Huurder registreren**. Bezorg de huurder het reglement van orde. |
| **Toestemming voor werken** (airco, ramen, zonnepanelen, laadpaal) | Vraag het advies van de raad van mede-eigendom, of klik op **Op de volgende AV zetten**: Odoo zet een agendapunt op de eerstvolgende algemene vergadering van het gebouw. |
| **Defect of schade** | Odoo maakt een taak om het door te sturen naar een schadedossier. |
| **Document opvragen** | Checklist: opzoeken, nagaan of de aanvrager het mag krijgen, bezorgen. |
| **Klacht over overlast** | Checklist: feiten noteren, de betrokkene aanschrijven, opvolgen. |

Klaar? Klik op **Afgehandeld**.

## Het sleutelregister

**VME > Aanvragen > Sleutelregister** toont per gebouw welke sleutels en badges in gebruik zijn: nummer, datum en wie ze heeft. Bij een **verkoop** komt het register van de verkochte kavels in het antwoord aan de notaris, en bij **Akte verleden** gaan de sleutels van de verkoper over naar de koper (zie [Verkoop van een kavel](verkoop-notaris.md)).

## Voorbeeld uit de demodata

De demo heeft een slotenmaker (Slotenmaker Voorbeeld BV), een sleutelcertificaat per gebouw, een sleutelregister en drie huurders. Na het verwerken van de mails met de AI-assistent staan er drie aanvragen:

| Aanvraag | Aanvrager | Wat u ziet |
| --- | --- | --- |
| Extra badge voor de inkom | Eigenaar Linde A4 | Wacht op de bevestiging van de eigenaar, want de aanvraag kwam per mail. Vink **Eigenaar bevestigde de aanvraag** aan en klik op **Bewijs goedkeuren**: de bestelling aan Slotenmaker Voorbeeld BV staat klaar met de bestelbon. |
| Extra sleutel van de inkom | Huurder Linde A6 | Wacht op bewijs: toestemming van de eigenaar en huurcontract. Klik op **Bewijs opvragen**. |
| Extra badge met toestemming | Huurder Beuken B12 | Wacht op bewijs, maar de toestemming en het huurcontract zitten als bijlage bij de mail. Vink beide aan en klik op **Bewijs goedkeuren**. |

Een badge kost in de demo 25 euro, een veiligheidssleutel 45 euro. Na **Levering registreren** krijgt de eigenaar een factuur van dat bedrag, ook voor de aanvraag van zijn huurder.

## Veelgestelde vragen

**Vertrekt de bestelling niet vanzelf na de verificatie?**
Nee, nog niet. De bestelling staat klaar en vertrekt met één klik. Of dat later per gebouw automatisch mag, is nog niet beslist.

**De eigenaar woont zelf niet in het gebouw en vraagt een badge voor zijn huurder. Moet hij bewijs leveren?**
Nee. De aanvraag komt van de eigenaar zelf: via het portaal is ze meteen geverifieerd, per mail na zijn bevestiging. De badge komt op naam van de eigenaar in het register; pas de naam aan als de huurder hem krijgt.

**Waarom krijgt de eigenaar de factuur als de huurder de aanvraag deed?**
De VME rekent alleen met eigenaars af. De eigenaar regelt de kost met zijn huurder.

**Hoe zie ik of de factuur betaald is?**
Klik in de aanvraag op de **factuur eigenaar**. Een onbetaalde factuur komt ook in de invordering terecht, net als een provisie.

**Iemand mailt opnieuw over dezelfde badge. Krijg ik een tweede aanvraag?**
Niet voor dezelfde mail: Odoo herkent een mail die al verwerkt is. Een nieuwe mail wordt wel een nieuwe aanvraag; annuleer die dan.
