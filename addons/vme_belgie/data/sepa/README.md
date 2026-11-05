# SEPA-schema's

`pain.001.001.09.xsd` (CustomerCreditTransferInitiationV09) en `pain.008.001.08.xsd` (CustomerDirectDebitInitiationV08) zijn de officiële ISO 20022-berichtschema's, ongewijzigd overgenomen uit het berichtenarchief van https://www.iso20022.org/ (november 2026).

Volgens de gebruiksvoorwaarden van die website mag het materiaal vrij gebruikt en gereproduceerd worden onder het ISO 20022 Intellectual Property Right Policy. Dit is niet de officiële bron: de enige bron van actuele ISO 20022-berichtstandaarden is https://www.iso20022.org/.

SHA-256 (na omzetting van CRLF naar LF):

- `pain.001.001.09.xsd`: `05440a7e84f695e7dbc6677082f43623cd7393881b76a5e8d648ae21d7d728e3`
- `pain.008.001.08.xsd`: `3b2efe2239fceea22b17eb980df58c8b80db7322cf7781f8fd64ee8d17696210`

`models/sepa_xml.py` valideert elk bestand tegen deze schema's voor het aan de gebruiker gegeven wordt.
