"""Voice-over for the demo video, in Flemish Dutch: calm, professional, for a syndic or an investor.

Each line is (key, spoken text). For the caption lines the key is the caption exactly as record.py
shows it, so the voice says what the viewer reads; the spoken text only writes out what a voice
would otherwise read oddly (kavel "A vier", "vijf procent", "V-M-E"). Keys starting with "#" are
the title cards. Captions without a line here stay silent (short hints while clicking).

The backbone is the "Zeg:" line of each step in docs/demo.md. All names are fictitious.
"""

LINES = [
    # Title cards
    ("#intro", "Quotis. Een platform voor syndici, gebouwd op Odoo. We volgen één werkdag, van de mail van "
               "een eigenaar tot zijn jaarafrekening. De software zet alles klaar; een mens beslist."),
    ("#extras", "Nog twee extra's: het boekjaar afsluiten, en een mail van een eigenaar, rechtstreeks in Outlook."),
    ("#outro", "Quotis. De software zet alles klaar, een mens beslist. Niets vertrekt zonder een klik van uw "
               "medewerker."),

    # Step 1
    ("Mijn werk vandaag: wat te laat is, vandaag of deze week vervalt, over alle gebouwen heen.",
     "Mijn werk vandaag. Wat te laat is, wat vandaag of deze week vervalt: over al uw gebouwen heen, in één lijst."),
    ("Vannacht mailde de eigenaar van A4 over een lek. De AI-assistent zette een antwoord klaar.",
     "Vannacht mailde de eigenaar van appartement A-vier over een lek. De AI-assistent heeft al een antwoord "
     "klaargezet."),
    ("Deze week: de keuring van de lift in blok A plannen. Onthoud die voor stap 3.",
     "Deze week moet de keuring van de lift in blok A gepland worden. Onthoud die even."),
    ("Uw dag begint met één lijst over al uw gebouwen, en alles wat naar buiten moet, staat klaar als concept.",
     "Uw dag begint met één lijst over al uw gebouwen. En alles wat naar buiten moet, staat klaar als concept."),

    # Step 2
    ("De mail staat bij de juiste VME: Residentie Linde, kavel A4, onderwerp lek, dringend.",
     "De mail staat meteen bij de juiste V-M-E: Residentie Linde, kavel A-vier, onderwerp lek, dringend. "
     "Niemand heeft iets overgetikt."),
    ("Het voorstel van de AI-assistent: nog niet verstuurd. Uw medewerker kijkt het na.",
     "Dit is het voorstel van de AI-assistent. Het is nog niet verstuurd: uw medewerker kijkt het eerst na."),
    ("Er staat al een schadedossier klaar, en het antwoord vertelt wat de eigenaar intussen kan doen.",
     "Er staat al een schadedossier klaar, en het antwoord vertelt de eigenaar wat hij intussen kan doen."),
    ("De AI leest de mail, vindt het gebouw en de kavel en schrijft een antwoord; uw medewerker beslist en "
     "verstuurt.",
     "De AI leest de mail, vindt het gebouw en de kavel, en schrijft een antwoord. Uw medewerker beslist, en "
     "verstuurt."),

    # Step 3
    ("De Keuringsdienst mailt de factuur van de liftinspectie naar het factuuradres van Residentie Linde.",
     "Nu mailt de keuringsdienst zijn factuur voor de liftinspectie, naar het factuuradres van Residentie Linde."),
    ("Leverancier, bedrag en btw komen uit de Peppol-e-factuur in bijlage; de verdeelregel koos de liftsleutel.",
     "Leverancier, bedrag en B-T-W komen uit de Peppol-e-factuur in bijlage. De verdeelregel koos zelf de "
     "liftsleutel."),
    ("Eén klik op Bevestigen: geboekt en verdeeld.",
     "Eén klik op bevestigen."),
    ("Verdeeld over 12 eigenaars: alleen de appartementen, want garages gebruiken de lift niet.",
     "De factuur is verdeeld over twaalf eigenaars. Alleen de appartementen: garages gebruiken de lift niet."),
    ("In de historiek: automatisch verdeeld, en de keuring van de lift geregistreerd, met de volgende keuring al "
     "in de agenda.",
     "In de historiek: automatisch verdeeld, en de keuring van de lift is geregistreerd, met de volgende keuring "
     "al in de agenda."),
    ("Eén mail van een leverancier: geboekt, verdeeld over de juiste eigenaars, en uw keuringsagenda is "
     "bijgewerkt. U klikte één keer.",
     "Eén mail van een leverancier: geboekt, verdeeld over de juiste eigenaars, en uw keuringsagenda is "
     "bijgewerkt. U klikte één keer."),

    # Step 4
    ("De AI las de drie offertes voor de gevel. De aandachtspunten staan in het geel.",
     "Voor de gevel liggen drie offertes. De AI heeft ze gelezen, en zet de aandachtspunten in het geel: "
     "een ander B-T-W-tarief, een bedrag dat niet klopt, een post die ontbreekt."),
    ("Bij elk getal de bron: het paginanummer in de offerte.",
     "Bij elk getal staat de bron: de bladzijde in de offerte."),
    ("Een avond offertes naast elkaar leggen wordt tien minuten nakijken, met de bron bij elk getal. De AV kiest; "
     "wij zetten de feiten klaar.",
     "Een avond offertes naast elkaar leggen, wordt tien minuten nakijken. De algemene vergadering kiest; "
     "wij zetten de feiten klaar."),

    # Step 5
    ("Budgetjaar 2027, oproep 1. Het voorbeeld toont per VME het werk- en het reservekapitaal.",
     "De provisies voor tweeduizend zevenentwintig, voor de drie gebouwen tegelijk. Het voorbeeld toont per "
     "V-M-E het werkkapitaal en het reservekapitaal."),
    ("Bij Hof ter Beuken waarschuwt het systeem: het reservekapitaal zit onder de wettelijke 5% van de lasten van "
     "vorig jaar.",
     "Bij Hof ter Beuken waarschuwt het systeem: het reservekapitaal zit onder de wettelijke vijf procent van de "
     "lasten van vorig jaar."),
    ("Per eigenaar een oproep voor werkkapitaal en een voor reservekapitaal, elk met de eigen bankrekening en een "
     "gestructureerde mededeling.",
     "Tweeëntachtig oproepen, in enkele seconden. Per eigenaar één voor het werkkapitaal en één voor het "
     "reservekapitaal, elk met de juiste rekening en een gestructureerde mededeling."),
    ("Uw kwartaaloproep voor tweehonderd gebouwen is één wizard, en de 5%-regel bewaakt zichzelf.",
     "Uw kwartaaloproep voor tweehonderd gebouwen is één wizard. En de vijf-procent-regel bewaakt zichzelf."),

    # Step 6
    ("De AV-planner deelt het hele AV-seizoen in, zonder dubbel geboekte zaal of medewerker.",
     "De planner deelt het hele seizoen van algemene vergaderingen in, zonder dubbel geboekte zaal of "
     "medewerker."),
    ("Elke AV binnen haar wettelijke periode van vijftien dagen. Alles staat op Voorgesteld: bevestigen doet uw "
     "medewerker.",
     "Elke vergadering valt binnen haar wettelijke periode van vijftien dagen. Alles staat op voorgesteld: "
     "bevestigen doet uw medewerker."),
    ("Uw AV-seizoen in één voorstel, binnen elke wettelijke termijn, en wie niet kan komen, stemt online.",
     "Uw seizoen in één voorstel, binnen elke wettelijke termijn. En wie niet kan komen, stemt online mee."),

    # Step 7
    ("De controle: de som van alle aandelen is gelijk aan de geboekte kosten, inclusief de liftfactuur van "
     "daarnet.",
     "De jaarafrekening van tweeduizend zesentwintig. Bovenaan de controle: de som van alle aandelen is gelijk "
     "aan de geboekte kosten, ook de liftfactuur van daarnet."),
    ("Eigenaar Linde A1 krijgt geld terug, A3 heeft nog provisies open staan.",
     "Eigenaar A-één krijgt geld terug. A-drie heeft nog provisies openstaan."),
    ("A5 werd op 1 juli verkocht: verkoper en koper krijgen elk hun eigen afrekening, pro rata hun dagen.",
     "A-vijf werd op één juli verkocht. Verkoper en koper krijgen elk hun eigen afrekening, volgens hun dagen."),
    ("De PDF per eigenaar: kosten per sleutel, provisies, saldo, het reservekapitaal apart en het detail per "
     "factuur.",
     "En de afrekening per eigenaar: kosten per sleutel, provisies, saldo, het reservekapitaal apart, en het "
     "detail per factuur."),
    ("De afrekening die u nu een week kost, staat klaar zodra de laatste factuur geboekt is, tot op de cent en "
     "ook bij een verkoop midden in het jaar.",
     "De afrekening die u nu een week kost, staat klaar zodra de laatste factuur geboekt is. Tot op de cent, "
     "ook bij een verkoop midden in het jaar."),

    # Step 8
    ("Het portaal van Eigenaar Linde A1, op zijn eigen computer.",
     "En dit ziet de eigenaar van A-één, in zijn eigen portaal."),
    ("Zijn kavels A1 en G1, de volgende AV met de agenda, de stand van werk- en reservekapitaal en de provisies, "
     "ook de nieuwe oproep van 2027.",
     "Zijn kavels, de volgende algemene vergadering met de agenda, de stand van werk- en reservekapitaal, en zijn "
     "provisies, ook de nieuwe oproep van daarnet."),
    ("Jaarafrekening 2026, voorlopig: het saldo in zijn voordeel.",
     "Zijn jaarafrekening, voorlopig: het saldo in zijn voordeel."),
    ("En onderaan zijn aandeel in de liftfactuur van Keuringsdienst Voorbeeld vzw: de mail van de leverancier van "
     "daarnet.",
     "En onderaan, zijn aandeel in de liftfactuur. De mail van de leverancier van daarnet."),
    ("Van de mail van de leverancier tot de afrekening bij de eigenaar: niemand heeft iets overgetikt, en niets is "
     "vertrokken zonder een klik van uw medewerker.",
     "Van de mail van de leverancier tot de afrekening bij de eigenaar: niemand heeft iets overgetikt, en niets "
     "is vertrokken zonder een klik van uw medewerker."),

    # Block D
    ("Boekjaar 2026 van Residentie Linde: de controles tonen wat nog ontbreekt, hier een leveranciersfactuur in "
     "concept.",
     "Het boekjaar afsluiten. De controles tonen wat nog ontbreekt: hier een leveranciersfactuur in concept."),
    ("Eén klik op de link: de factuur nakijken en bevestigen.",
     "Eén klik: nakijken en bevestigen."),
    ("Alleen \"het boekjaar loopt nog\" blijft over.",
     "Nu blijft alleen over dat het boekjaar nog loopt."),
    ("Afrekening voorbereiden: per eigenaar een concept-factuur of -creditnota. Er vertrekt niets.",
     "Per eigenaar staat een conceptfactuur of een conceptcreditnota klaar. Er vertrekt niets."),
    ("De afrekening wordt geboekt met één klik van uw medewerker, en het jaar gaat dicht zonder dat er iets "
     "vertrekt.",
     "De afrekening wordt geboekt met één klik van uw medewerker, en het jaar gaat dicht zonder dat er iets "
     "vertrekt."),

    # Block E
    ("Het paneel naast de mail in Outlook, hier als voorbeeld in de browser.",
     "En in Outlook: het paneel naast de mail, hier als voorbeeld in de browser."),
    ("De lekmail van A4: Residentie Linde, kavels A4 en G4, en het voorstel van de AI-assistent, nog niet "
     "verstuurd.",
     "De lekmail van A-vier: het gebouw, de kavels, en het voorstel van de AI-assistent. Nog niet verstuurd."),
    ("Antwoord invoegen zet het voorstel in het antwoordvenster. Verzonden is er niets.",
     "Antwoord invoegen zet het voorstel klaar in het antwoordvenster. Verzonden is er niets."),
    ("Een vraag van B7: onder Wat staat er open, de achterstallige provisies met bedrag en vervaldag.",
     "Bij een vraag van B-zeven ziet uw medewerker meteen wat er openstaat: de achterstallige provisies, met "
     "bedrag en vervaldag."),
    ("Uw medewerkers blijven in Outlook en zien bij elke mail het gebouw, de kavel en wat er openstaat, met een "
     "antwoord klaar om na te kijken. Verzenden blijft hun klik.",
     "Uw medewerkers blijven in Outlook, en zien bij elke mail het gebouw, de kavel en wat er openstaat, met een "
     "antwoord klaar om na te kijken. Verzenden blijft hun klik."),

    # Promo only: the cards around the short version
    ("#promo_intro", "Quotis. Software voor syndici: alles staat klaar, u beslist."),
    ("#promo_outro", "Quotis. De software zet alles klaar, een mens beslist."),
]

SPEECH = dict(LINES)
