# Mails in Outlook koppelen aan de VME en de kavel

Met de invoegtoepassing voor Outlook ziet u bij elke mail van een eigenaar of huurder meteen over wie het gaat: de VME, de kavel en of het een eigenaar of een huurder is. U ziet ook wat er voor die persoon openstaat (onbetaalde provisies, aanvragen, schadedossiers) en, als de AI-assistent de mail al las, het antwoord dat hij voorstelt. U hoeft Odoo niet te openen om een mail te plaatsen.

> **Er vertrekt nooit iets vanzelf.** "Antwoord invoegen" opent het gewone antwoordvenster van Outlook met het voorstel erin. U leest het na, past het aan en drukt zelf op **Verzenden**.

## Hoe installeer ik de invoegtoepassing?

Dit doet één keer een beheerder, daarna elke medewerker in zijn eigen Outlook.

1. In Odoo: **VME > Configuratie > Outlook-invoegtoepassing**.
2. Kijk het **Adres van Odoo voor Outlook** na. Outlook werkt alleen met een adres dat met `https://` begint. Uw beheerder of leverancier kent dat adres.
3. Klik op **Manifest downloaden**. U krijgt het bestand `vme-outlook-manifest.xml`. Het bevat het adres van úw Odoo: de invoegtoepassing praat dus altijd met uw eigen kantoor.
4. Open Outlook op het web (of Outlook op uw computer) en ga naar **Apps** of **Invoegtoepassingen** > **Mijn invoegtoepassingen** > **Aangepaste invoegtoepassing toevoegen** > **Toevoegen vanuit bestand**. Kies het manifest en bevestig.
5. Open een mail. In het lint staat nu de knop **VME-dossier**. Klik erop: rechts opent het paneel.
6. De eerste keer klikt u op **Verbinden met Odoo**. Log in met uw gewone gebruiker van Odoo en klik op **Allow**. Outlook blijft daarna 30 dagen verbonden.

## Wat zie ik bij een mail?

- **Bovenaan**: de VME en de kavel, met **eigenaar** of **huurder**, en waarom het paneel die koppeling maakt ("gekoppeld op het e-mailadres van … op vandaag"). Een klik op een naam opent die fiche in Odoo.
- **Voorstel van de AI-assistent**, als er een is: het onderwerp, hoe zeker de koppeling is en het conceptantwoord, met het label **nog niet verstuurd**.
- **Wat staat er open**: achterstallige provisies met bedrag en vervaldag, open aanvragen en open schadedossiers van deze persoon.
- **Acties**: bewaren bij het dossier en een aanvraag maken.

Is een eigenaar eigenaar in twee VME's, dan kiest u bovenaan de juiste VME. Kent het paneel de afzender niet (een nieuw e-mailadres, een notaris, een buur), dan zoekt u de VME of de kavel, bv. *Linde A4*.

## Hoe beantwoord ik een mail met het voorstel?

1. Open de mail en het paneel.
2. Lees het voorstel onder **Voorstel van de AI-assistent**.
3. Klik op **Antwoord invoegen**. Het antwoordvenster van Outlook opent, met het voorstel als tekst.
4. Vul plaatshouders in (zoals *[datum]*), pas aan waar nodig en druk zelf op **Verzenden**.
5. Markeer daarna in Odoo de activiteit *AI-voorstel* als gedaan (zie [Een antwoord behandelen dat de AI-assistent voorstelt](ai-voorstellen-mails.md)).

## Hoe bewaar ik een mail bij het dossier?

1. Kies onder **Bewaren bij** waar de mail hoort: bij de VME, of bij een open aanvraag of schadedossier.
2. Klik op **Bewaren bij dossier**.

De mail staat dan in Odoo als **interne notitie**, met afzender, onderwerp, tekst en bijlagen. Wie het dossier volgt, krijgt daar geen mail van.

## Hoe maak ik een aanvraag van een mail?

1. Kies de **Soort aanvraag**, bv. *Extra sleutel of badge*.
2. Klik op **Aanvraag maken**.

Odoo maakt de aanvraag en start de vaste procedure: het vraagt bewijsstukken op of zet de bestelling klaar, altijd als concept. Zie [Aanvragen van bewoners](aanvragen-sleutels-badges.md). Een tweede klik op dezelfde mail maakt geen tweede aanvraag.

**Voorbeeld in de demo:** zonder Outlook toont u het paneel in de browser. Log in Odoo in als `admin` en open `http://localhost:8069/vme_mail_plugin/static/outlook/taskpane.html?demo=1` (of **VME > Configuratie > Outlook-invoegtoepassing > Voorbeeld in de browser**). Kies bovenaan een van de acht fictieve mails. Bij de mail over het lek van **Eigenaar Linde A4** toont het paneel Residentie Linde, kavel A4 en het voorstel van de AI-assistent. Bij de vraag van **Eigenaar Beuken B7** staan zijn onbetaalde provisies.

## Veelgestelde vragen

**Kan de invoegtoepassing zelf een antwoord versturen?**
Nee. Ze opent alleen het antwoordvenster. Versturen is altijd uw klik in Outlook.

**Waarom staat er geen voorstel van de AI-assistent?**
De assistent heeft de mail nog niet gelezen, of de mail werd doorgestuurd (dan heeft ze een andere referentie). U ziet wel de koppeling en wat er openstaat.

**De afzender is eigenaar, maar het paneel kent hem niet.**
Het paneel zoekt op het e-mailadres in de fiche van de eigenaar, op vandaag. Schrijft hij van een ander adres, zoek de kavel dan op naam en vul het nieuwe adres aan in Odoo.

**Ik ben commissaris van de rekeningen. Waarom zijn de knoppen grijs?**
Als commissaris kijkt u in, maar bewaart of maakt u niets. U ziet alleen de VME's van uw mandaat.

**Moet ik opnieuw verbinden?**
Na 30 dagen vraagt het paneel opnieuw om **Verbinden met Odoo**. U kunt de toegang ook zelf intrekken in Odoo: uw voorkeuren > **Account Security** > API-sleutels.
