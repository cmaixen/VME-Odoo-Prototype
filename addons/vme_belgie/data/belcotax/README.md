# Belcotax-schema's

Officiële schema's van de FOD Financiën, ongewijzigd overgenomen van https://financien.belgium.be/nl/E-services/Belcotaxonweb/technische-documentatie (november 2026):

- `Belcotax-2025.xsd`: uit `161-xsd-2025-20260129.zip` ("Belcotax 2025 XSD", versie 2, 29.01.2026). Voor het XML-bestand tot en met inkomsten 2025.
- `2026/`: uit `161-schemas-preproduction-bow.zip` (pre-productie, oktober 2026) de schema's `fiche_2026_50_2_nl.json` (fiche 281.50) en `resource_contact_nl.json`, `resource_person_nl.json`, `resource_organisation_nl.json`. Voor het JSON Lines-bestand van de vernieuwde Belcotax-on-web vanaf inkomsten 2026.

Volgens de gebruiksvoorwaarden (https://fin.belgium.be/nl/gebruiksvoorwaarden) is de informatie op die website vrij van rechten en onvoorwaardelijk herbruikbaar, ook commercieel (gebaseerd op CC0); bronvermelding wordt aangeraden. Dit is niet de officiële bron: haal een nieuwe versie altijd van de pagina hierboven.

`models/belcotax_xml.py` en `models/belcotax_jsonl.py` valideren elk bestand tegen deze schema's voor het aan de gebruiker gegeven wordt.

SHA-256:

- `Belcotax-2025.xsd`: `01ec46cc40265e94d25301b95768197ba860ef34b16d5dd320d433d3f06c69d9`
- `2026/fiche_2026_50_2_nl.json`: `39831f180ef607a3cc922f33adf6fba03b374286d0f86c9946c43bde9fe57638`
- `2026/resource_contact_nl.json`: `dd247a5d716360a79c29333d091b5dc379e04ab3aae0a41331f7f9b7783cf46c`
- `2026/resource_organisation_nl.json`: `95b9b39a1e679d174105da775d3c4de6bad6b5981788ec60720180785cac57ac`
- `2026/resource_person_nl.json`: `070fba9c153b969ac149826d3476040ec24804548c8029684213847461b1d8f2`
