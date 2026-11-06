# Een hybride of online algemene vergadering houden

Eigenaars kunnen een algemene vergadering ook van thuis volgen: ze melden zich aan in het eigenaarsportaal, stemmen daar per agendapunt met hun quotiteiten, en ondertekenen na afloop de notulen. Over sommige punten kunnen ze zelfs vooraf schriftelijk stemmen. De rest van de AV (agenda, aanwezigheidslijst, volmachten, quorum, meerderheden) werkt zoals in [De algemene vergadering](algemene-vergadering.md).

Odoo verstuurt nooit zelf iets: de uitnodiging is een concept dat u nakijkt en verstuurt.

> De wettelijke regels hieronder (deelname op afstand, schriftelijke stemming, ondertekening) zijn nog niet juridisch nagekeken.

## Hoe zet ik een AV online of hybride?

1. Open de AV in **VME > Algemene vergaderingen**.
2. Ga naar het tabblad **Online** en kies de **Vorm**:
   - **In de zaal**: zoals vroeger, zonder online deelname;
   - **Hybride**: in de zaal én online;
   - **Volledig online**.
3. Vul de **Videolink** in (bv. van Jitsi of Teams). Eigenaars zien die pas als ze zich aangemeld hebben.
4. Odoo maakt een **Link online deelname** voor deze AV. Die staat vanzelf in de concept-oproeping.

Een **buitengewone AV** (bv. voor één dringende beslissing) maakt u met **Nieuw**, **Soort: Buitengewone AV** en een **Onderwerp**. Ze krijgt alleen het openingspunt op de agenda; de andere punten voegt u zelf toe. Een buitengewone AV heeft geen vaste periode en telt niet mee in de AV-planner.

## Hoe stuur ik de uitnodiging met de link?

Zoals elke oproeping: **Oproepingen aanmaken**, open een oproeping en klik op **Versturen**. De e-mail die opent, vermeldt de link voor online deelname en, als er punten zijn waarover vooraf gestemd kan worden, ook dat. De PDF van de oproeping vermeldt dezelfde link. U kijkt de mail na en verstuurt ze zelf.

## Wat doe ik op de avond van de vergadering?

1. Klik op **Online onthaal openen**. Vanaf nu kunnen eigenaars zich in het portaal aanmelden met **Ik ben aanwezig (online)**. Ze tellen meteen mee voor het quorum; de kolom **Hoe** in de aanwezigheidslijst toont "Online" en het tijdstip.
2. Wie een volmacht gaf, kan zich niet zelf aanmelden: zijn volmachthouder stemt voor hem. Wil hij toch zelf deelnemen, pas dan de aanwezigheidslijst aan.
3. Behandel de agenda. Klik bij een agendapunt op **Stemming openen**. Eigenaars stemmen in het portaal voor, tegen of onthouding. Een volmachthouder stemt in één keer voor zichzelf en voor wie hij vertegenwoordigt.
4. De stemmen van wie in de zaal zit, geeft u in zoals vroeger met **Stemmen**. Wie online stemt, staat daar niet bij: zijn stem komt uit het portaal.
5. Klik op **Stemming sluiten** als iedereen gestemd heeft. Daarna kan niemand nog stemmen over dat punt, en ziet iedereen in het portaal de uitslag.
6. Na het laatste punt klikt u op **Gehouden**. Dat lukt pas als alle stemmingen gesloten zijn; het online onthaal sluit dan vanzelf.

**Voorbeeld uit de demo.** Residentie Linde heeft een buitengewone hybride AV over laadpalen in de garage op 19 november 2026. Eigenaar Linde A7 gaf volmacht aan Linde A1. In het portaal meldt A1 zich online aan en stemt hij voor A1 én A7. Linde A6, de secretaris, meldt zich ook online aan. Over de schilderwerken van de traphal kan vooraf schriftelijk gestemd worden.

## Hoe werkt schriftelijk stemmen vooraf?

Zet bij een agendapunt het vinkje **Schriftelijk vooraf** aan (kolom in de agenda, of in het agendapunt zelf). Tot het online onthaal opengaat, kan een eigenaar dan in het portaal over dat punt stemmen. Hij telt mee als aanwezig, met "Schriftelijk vooraf" in de aanwezigheidslijst.

Kijk per punt na of de wet en het reglement van mede-eigendom dat toelaten.

## Hoe laat ik de notulen ondertekenen?

1. Vul de **voorzitter** en de **secretaris** in, en zet de AV op **Gehouden**.
2. Klik op **Notulen ter ondertekening**. Odoo maakt de PDF van de notulen en zet hem vast. Voorzitter, secretaris en alle eigenaars die in de zaal of online aanwezig waren, krijgen een aanvraag. Wie alleen vooraf schriftelijk stemde, niet.
3. De ondertekenaars zien in het portaal bij hun VME **Notulen te ondertekenen**. Ze openen de PDF, typen hun naam, vinken aan dat ze de notulen gelezen hebben en klikken op **Ondertekenen**.
4. In het tabblad **Ondertekening** van de AV ziet u per ondertekenaar wanneer hij tekende, vanaf welk IP-adres, en de vingerafdruk (SHA-256) van de PDF die hij tekende.

## Veelgestelde vragen

**Wat als de notulen na het ondertekenen nog veranderen?**
Dan zijn de handtekeningen ongeldig: de vingerafdruk van de nieuwe PDF klopt niet meer. Odoo toont een rode melding. Klik opnieuw op **Notulen ter ondertekening**: de ondertekenaars krijgen een nieuwe aanvraag voor de nieuwe PDF. De oude handtekeningen blijven bewaard als bewijs, met het label ongeldig.

**Kan een eigenaar zijn stem nog wijzigen?**
Nee. Een stem uit het portaal is definitief en kan ook door de syndicus niet gewijzigd of verwijderd worden. Zo blijft het auditspoor betrouwbaar.

**Kan iemand twee keer stemmen, bv. zelf en via zijn volmachthouder?**
Nee. Per eigenaar en agendapunt is er één stem. Wie een volmacht gaf, kan niet zelf stemmen, en een volmachthouder kan niet twee keer voor dezelfde eigenaar stemmen.

**Telt een online stem anders?**
Nee. Een online stem telt precies zoals een stem in de zaal: met de quotiteiten, de regels voor het quorum, de meerderheden, het plafond per eigenaar en de grens van drie volmachten.

**Moet de eigenaar het portaal vernieuwen?**
Ja. Opent u een stemming, dan ziet de eigenaar ze na **Vernieuwen**.

**Is dit een gekwalificeerde elektronische handtekening?**
Nee. Het is een eenvoudige elektronische handtekening met een auditspoor (wie, wanneer, IP-adres en vingerafdruk van de PDF). Voor stukken die een gekwalificeerde handtekening vereisen, gebruikt u een erkende dienst.
