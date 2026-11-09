# Demovideo

Een video van ongeveer zeven minuten, met een Vlaamse voice-over (standaard de macOS-stem Ellen), met het scenario van `docs/demo.md`: de acht stappen en de extra blokken D (boekjaar afsluiten) en E (Outlook-paneel in de browser). Nederlandse ondertitels staan in het beeld, met per stap de "Zeg:"-zin uit het draaiboek. Alle data is fictief en er wordt niets verstuurd: de video toont de concepten en de labels "nog niet verstuurd".

Het resultaat staat in `build/demo_video/quotis-demo.mp4`, de korte promoversie (ongeveer een minuut) in `build/demo_video/quotis-promo.mp4`. De map `build/` staat in `.gitignore`.

## Opnieuw maken

Docker (OrbStack) aan, `ffmpeg` en `ffprobe` op de Mac (`brew install ffmpeg`).

```bash
tools/demo_video/record.sh                  # alles: database, AI-concepten, opname, MP4 (ongeveer 15 minuten)
SKIP_BUILD=1 tools/demo_video/record.sh     # hergebruik de verse kopie van een vorige keer (ongeveer 9 minuten)
```

Het script raakt de demoserver op poort 8069 en de database `vme_demo` niet aan. Het gebruikt een eigen compose-project:

| | Demo | Video |
| --- | --- | --- |
| Compose-project | `vme-prototype` | `vme-video` (`tools/demo_video/dc.sh`) |
| Database | `vme_demo` | `vme_video`, met de kopie `vme_video_fresh` |
| Poort | 8069 | 8695 |
| Netwerk | standaard | vast subnet `10.219.61.0/24` |

Het vaste subnet staat in `compose.video.yml` omdat Docker zonder adresbereiken valt als er veel compose-projecten naast elkaar draaien ("all predefined address pools have been fully subnetted").

## Hoe het werkt

| Bestand | Rol |
| --- | --- |
| `build_db.sh` | Verse database met demodata en demohistoriek ("Vooraf", stap 1). |
| `reset_db.sh` | Zet `vme_video` terug op de kopie `vme_video_fresh` en draait `prepare.py`. Zo begint elke opname gelijk. |
| `prepare.py` | "Vooraf" stap 3 en 4 zonder API-sleutel: `assistant.py --mock` en `offertes.py --offline`, na de knop "Offertes vergelijken" via JSON-RPC. |
| `Dockerfile` | Playwright 1.49 met Chromium en PyMuPDF, als service `recorder` (profiel `video`). |
| `record.py` | De opname: drie browsercontexten (medewerker, eigenaar, extra's), elk met een eigen WebM. |
| `overlay.js` | In elke pagina: een zichtbare muisaanwijzer, een klikring en de ondertitelband. |
| `make_video.py` | Knipt het witte begin van elk deel, voegt een overgang toe en maakt één MP4 (H.264, 1920x1080, 25 fps). |

Keuzes en valkuilen:

- **Ondertitels in de pagina, niet in ffmpeg.** De ffmpeg van Homebrew heeft geen `drawtext` of `subtitles` (geen freetype of libass). De band zit daarom in de pagina (`overlay.js`) en staat zo mee in de video. Een init-script loopt vóór `<html>` bestaat: de MutationObserver kijkt naar `document`, niet naar `document.documentElement`.
- **Headless Chromium tekent geen muisaanwijzer.** `overlay.js` volgt de echte `mousemove`-events van Playwright; `Recorder.click` laat de aanwijzer eerst naar het element glijden.
- **Inloggen buiten beeld.** `record.py` logt in een aparte context in en geeft de sessie mee (`storage_state`). Ook "Verbinden met Odoo" voor het Outlook-paneel gebeurt buiten beeld, want dat opent een popup en elke pagina krijgt in Playwright een eigen video.
- **Nieuwe tabbladen.** De link naar een conceptfactuur in de afsluiting heeft `target="_blank"`; het script haalt dat weg zodat alles in één tabblad blijft.
- **De PDF van de jaarafrekening.** Headless Chromium downloadt een PDF in plaats van hem te tonen. Het script vangt de download op en toont de eerste twee bladzijden als afbeelding (PyMuPDF).
- **De terminal van stap 3** is een nagemaakt venster: `record.py` draait `facturen_mailgate.py --inbox demo_inbox` echt en toont de echte uitvoer regel per regel.
- **Ondertitel en knoppen onderaan.** Als de aanwijzer naar een knop in de onderste 190 pixels gaat (bv. "Afdrukken (PDF)" in een dialoog), wordt de band even doorzichtig.
- **Het Outlook-paneel** is in de browser zo breed als het venster. Het script maakt het een smalle kolom met `zoom` op de inhoud, niet op `body`, anders verschuiven de ondertitel en de klikposities.

## Voice-over

De tekst staat in `tools/demo_video/narration.py`: per ondertitel de gesproken zin, in het Vlaams, rustig en zakelijk, met de "Zeg:"-zinnen van `docs/demo.md` als ruggengraat. De sleutel is de ondertitel letterlijk, zodat de stem zegt wat in beeld staat; de gesproken tekst schrijft alleen uit wat een stem anders vreemd leest ("A-vier", "vijf procent", "V-M-E"). Korte hints tijdens het klikken blijven stil. Na een wijziging aan een ondertitel in `record.py` moet de sleutel in `narration.py` mee veranderen; anders blijft die zin stil.

De stem kies je met `VOICE_ENGINE` in `tools/demo_video/.env` (kopie van `.env.example`, in `.gitignore`):

| `VOICE_ENGINE` | Wat | Script |
| --- | --- | --- |
| `say` (standaard) | Een stem van macOS zelf: gratis, zonder netwerk, voor elke regel dezelfde. Standaard Ellen (nl_BE, Vlaams) aan 175 woorden per minuut (`SAY_VOICE`, `SAY_RATE`). Andere Nederlandse stemmen op de Mac: `say -v '?' \| grep nl_` (standaard alleen Ellen en Xander; betere varianten installeer je via Systeeminstellingen > Toegankelijkheid > Gesproken inhoud). | `voice_say.py` |
| `elevenlabs` | ElevenLabs via de API, met `ELEVENLABS_API_KEY`. | `voice.py` |
| `connector` | ElevenLabs via de connector in Claude, fragmenten vooraf gemaakt (zie hieronder). | `voice_connector.py manifest` |
| `none` | Geen stem, alleen ondertitels. | |

De huidige video's gebruiken `say` met Ellen. Meng geen stemmen: de vijf ElevenLabs-fragmenten die al bestaan, staan los in `build/demo_video/voice/` en worden niet gebruikt.

**ElevenLabs via de connector in Claude** (geen API-sleutel nodig).

1. Stem: "Rutger Vlaams – Calm & Articulate" (`LoLnBvKBzvdDcAUMNbKV`, nl-flemish), model `eleven_multilingual_v2`, één take per regel, alles in één flow.
2. `python3 tools/demo_video/voice_connector.py lines` geeft de genummerde regels. Laat Claude ze met `creative_generate_speech` maken, **één per keer**: het gratis abonnement weigert gelijktijdige generaties ("Free generations are busy"; zo'n weigering kost niets). Een regel die gestart is, nooit opnieuw sturen: dat kost opnieuw.
3. Bewaar elke take als `build/demo_video/voice/NN.mp3` (de `content_url` uit `creative_get_flow_run_status`) en draai `python3 tools/demo_video/voice_connector.py manifest`.

Kosten: 1 credit per teken; de hele tekst is ongeveer 5.220 tekens. Let op: in november 2026 schakelde ElevenLabs het gratis abonnement van het account uit ("unusual activity") na vijf regels; deze route vraagt dus een betaald abonnement.

**ElevenLabs via de API.** Zet `ELEVENLABS_API_KEY` (en eventueel `ELEVENLABS_VOICE_ID`) in `tools/demo_video/.env` (in `.gitignore`, voorbeeld in `.env.example`); `record.sh` draait dan `voice.py`, dat de ontbrekende fragmenten maakt via `POST /v1/text-to-speech/{voice_id}`.

Beide routes schrijven `build/demo_video/voice/manifest.json` (ondertitel → bestand en duur). Daarmee:

- **`record.py`** wacht na elke ondertitel tot de zin uitgesproken is voor de volgende ondertitel komt, en schrijft per deel `timeline.json` (wanneer welke zin begint). De opname past zich zo aan de stem aan, niet omgekeerd.
- **`align.py`** zet die momenten op de klok van de video zelf. De WebM van Playwright loopt niet gelijk met de klok van de opname: binnen een take schuift ze tot enkele seconden op, en niet gelijkmatig (gemeten: 0,1 s aan het begin van een deel, 1,3 s een halve minuut later). Daarom zet `overlay.js` bij elke uitgesproken zin een vierkantje van 12 pixels rechtsonder in de pagina om van magenta naar groen of terug; `align.py` leest die wissels uit de video en koppelt de n-de wissel aan de n-de zin. Klopt het aantal niet, dan stopt het script. Resultaat in `timeline_aligned.json` (veld `v`). Afstemmen op de ondertitelband alleen bleek niet betrouwbaar: een nieuwe ondertitel van dezelfde grootte verandert het beeld nauwelijks.
- **`make_video.py`** legt elk fragment op zijn moment uit `timeline_aligned.json` (min de geknipte witte start), nooit over de vorige zin heen, en mengt ze op een stille band, zodat elk deel dezelfde audio heeft voor het samenvoegen. Het vierkantje verft het weg met ffmpeg `delogo`.
- **`promo.py`** knipt de promo: de sterkste momenten (mail en concept-antwoord, verdeling, offertes, afrekening, portaal, Outlook) beginnen telkens op het moment van hun zin, zodat ondertitel en stem samenvallen; een eigen begin- en slotzin op de titelkaarten. Geen muziek: er is geen rechtenvrije track met gedocumenteerde licentie.

Zonder manifest is de video stil, met alleen ondertitels. 

## Debuggen

```bash
tools/demo_video/reset_db.sh
tools/demo_video/dc.sh run --rm -T recorder python3 tools/demo_video/record.py \
    --out build/demo_video/shots --shots --speed 0.3
```

`--shots` maakt geen video maar een schermafbeelding bij elk resultaat, `--speed 0.3` maakt de pauzes korter, en `--only step7_statement,step8_portal` draait alleen die stappen (de stappen veranderen de database: begin opnieuw met `reset_db.sh`). Bij een fout staat `ERROR_<deel>.png` in de uitvoermap.

## Verschillen met `docs/demo.md`

- Met `--mock` wordt de lekmail van A4 geen aanvraag AANV/2026/0003 maar een AI-voorstel als taak op Residentie Linde, met een schadedossier. Stap 1 en 2 tonen daarom *AI-voorstel: Lek of waterschade (A4)*. Met een API-sleutel (Claude) maakt de assistent er een aanvraag van, zoals het draaiboek zegt.
- De video noemt geen bedragen in de ondertitels. Sinds de fiches 281.50 staat in de demodata een factuur van 1.800 € van Advies Voorbeeld BV bij Residentie Linde, waardoor de jaarafrekening 20.616,80 € is in plaats van 18.816,80 € en A1 411,03 € terugkrijgt in plaats van 547,83 €.
