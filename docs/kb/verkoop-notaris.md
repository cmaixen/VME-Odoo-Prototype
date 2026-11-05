# Verkoop van een kavel: inlichtingen aan de notaris

Wordt een appartement of garage verkocht, dan vraagt de notaris de syndicus om inlichtingen: hoeveel reservekapitaal er is, of de verkoper nog iets verschuldigd is, welke werken beslist zijn, en of er procedures lopen. De wet geeft u daarvoor een vaste termijn. Odoo stelt het antwoord voor u samen uit de boekhouding en de beslissingen van de AV, bewaakt de termijn, en zet bij de akte de kavel op naam van de koper.

## Wanneer moet ik antwoorden?

- **Eerste vraag** (vóór de verkoop): binnen **15 dagen**.
- **Tweede vraag** (na het compromis): binnen **30 dagen**.

Odoo rekent de uiterste datum uit en maakt een taak voor de verantwoordelijke met die datum als vervaldag. In de lijst **VME > Verkoopdossiers** kleurt een dossier oranje als u nog hoogstens 7 dagen hebt, en rood als de termijn voorbij is.

## Hoe start ik een verkoopdossier?

1. Open de kavel via **VME > Kavels** en klik bovenaan op **Verkoop starten**. U kunt ook via **VME > Verkoopdossiers > Nieuw** beginnen.
2. Kies de verkochte kavels. Verkoopt de eigenaar appartement en garage samen, neem dan beide.
3. De **verkoper** vult Odoo in: de eigenaar van de kavel vandaag.
4. Vul de **notaris**, zijn **referentie** en de datum waarop de vraag binnenkwam in. De koper mag nog leeg blijven.
5. Bewaar. Odoo maakt meteen de taak met de uiterste antwoorddatum.

## Wat staat er in het antwoord?

Op het tabblad **Antwoord aan de notaris** ziet u het antwoord zoals het vandaag is:

1. **Kavels en quotiteiten** in elke verdeelsleutel.
2. **Reservekapitaal** van de VME en het aandeel van de verkochte kavels. Het reservekapitaal blijft van de VME en wordt niet terugbetaald aan de verkoper.
3. **Werkkapitaal van dit jaar**: het aandeel van de verkoper in de kosten tot vandaag, wat hij aan provisies betaalde, en het voorlopige saldo.
4. **Achterstallen van de verkoper**: elke provisie die nog openstaat, met vervaldag en bedrag.
5. **Beslist maar nog niet uitgevoerde werken**: elke aangenomen AV-beslissing met een geraamde kostprijs die nog niet uitgevoerd is, met het aandeel van de verkochte kavels.
6. **Lopende gerechtelijke procedures**, overgenomen van de VME.
7. De **algemene vergaderingen van de laatste drie jaar** met hun beslissingen.
8. De **uitgereikte sleutels en badges** van de verkochte kavels die nog in gebruik zijn: soort, nummer, datum en wie ze heeft. Dezelfde lijst staat in het tabblad **Sleutels en badges** van het dossier.

Klopt iets niet, pas het dan aan waar het vandaan komt (een betaling, een beslissing, de procedures). Het antwoord volgt vanzelf.

### Werken en procedures bijhouden

- **Werken:** open in de AV het agendapunt (bv. de dakwerken) en vul bij **Werken** de **geraamde kostprijs** in. Gelden de werken alleen voor een deel van het gebouw, kies dan de **sleutel** (bv. de liftsleutel). Zijn de werken klaar, vink dan **Werken uitgevoerd** aan; ze verdwijnen dan uit het antwoord.
- **Procedures:** open de VME, tabblad **Gerechtelijke procedures**. Wat daar staat, komt in elk nieuw verkoopdossier. In het dossier zelf kunt u de tekst nog aanpassen.

## Hoe beantwoord ik de vraag?

1. Klik op **Antwoord eerste vraag (PDF)**.
2. Odoo maakt een PDF in de huisstijl van de VME, gericht aan de notaris en met zijn referentie, en zet die in de chatter van het dossier. De taak wordt afgevinkt.
3. Kijk de PDF na en stuur hem vanuit de chatter naar de notaris (**Bericht verzenden**). Er wordt nooit iets automatisch verstuurd.

Komt de tweede vraag binnen, vul dan **Tweede vraag ontvangen op** in. Odoo zet het dossier op "Tweede vraag ontvangen", maakt een nieuwe taak van 30 dagen, en u beantwoordt met **Antwoord tweede vraag (PDF)**.

## Wat gebeurt er bij de akte?

1. Vul de **datum van de akte** en de **koper** in.
2. Klik op **Akte verleden** en bevestig.
3. Odoo sluit de eigendom van de verkoper af op de dag vóór de akte en zet de koper als eigenaar vanaf de dag van de akte, voor elke verkochte kavel. In de chatter van het dossier en van de VME komt een bericht.
4. De sleutels en badges die de verkoper had, staan in het sleutelregister vanaf dan op naam van de koper; het bericht in de chatter somt ze op, zodat u ze bij de akte kunt laten overhandigen. Sleutels van een huurder blijven op naam van de huurder.

Vanaf dan gaan nieuwe provisieoproepen naar de koper, en worden kosten per dag verdeeld tussen verkoper en koper (zie [Kavels en eigenaars, ook bij een verkoop](kavels-en-eigendom.md)).

**Voorbeeld in de demo:** in Residentie Linde verkoopt de eigenaar van A3 zijn appartement met garage G3. Notariskantoor Voorbeeld stelde de eerste vraag op 28 oktober 2026, dus het antwoord moet er op 12 november zijn. Het dossier staat oranje. Na het laden van de demohistoriek toont het antwoord de onbetaalde vierde provisie van A3 (475,20 euro) en het aandeel van A3 en G3 in de dakwerken die de AV van maart 2026 besliste (2.736 euro op 38.000 euro).

## Veelgestelde vragen

**De verkoper heeft ook nog een andere kavel in hetzelfde gebouw. Staan die achterstallen er ook in?**
Ja. De achterstallen zijn die van de verkoper in deze VME, voor al zijn kavels. Wil de notaris alleen de verkochte kavels, pas dan de PDF aan of vermeld het in uw begeleidende mail.

**Kan ik een dossier annuleren als de verkoop niet doorgaat?**
Ja, met **Annuleren**. De open taken worden afgesloten en de eigendom verandert niet.

**De akte werd verleden voor ik de tweede vraag beantwoordde.**
U kunt **Akte verleden** ook dan gebruiken; Odoo vraagt een extra bevestiging.
