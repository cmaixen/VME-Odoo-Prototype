# Leveranciersfacturen per e-mail (stap 7b)

Elke VME krijgt een e-mailalias op het aankoopdagboek van haar company. Een mail naar dat adres wordt via Odoo's standaard mail gateway een conceptfactuur in die company; UBL-bijlagen worden ingelezen zoals bij een upload, inclusief onze kostperiode en verdeelregels.

## Flow

```
mailserver ─(fetchmail of odoo-mailgate)─> mail.thread.message_process(False, raw)
   └─ message_route: To = facturen-kaaihuis@syndicus.example.com
        └─ mail.alias van account.journal (purchase, company Kaaihuis)
             alias_defaults = {move_type: in_invoice, company_id, journal_id}
   └─ account.move.message_new         -> conceptfactuur, partner op afzenderadres
   └─ account.move._message_post_after_hook (context from_alias)
        └─ per groep bijlagen: _extend_with_attachments(new=True)
             ├─ standaard: UBL-decoder (account_edi_ubl_cii) vult partner, lijnen, bedragen
             └─ vme_belgie: InvoicePeriod -> vme_period_start/end
        └─ account.move.line: _compute_vme_key_id / _compute_account_id via vme.distribution.rule
```

Bij "Bevestigen" verdeelt `_post` automatisch, zoals bij elke leveranciersfactuur (stap 4b).

Alles behalve de alias is standaard Odoo: `account.journal` erft van `mail.alias.mixin.optional` en `account.move` overschrijft `message_new`, `_routing_check_route` (geen bijlage → bounce, geen factuur) en `_message_post_after_hook` (bijlagen splitsen en inlezen). Een Message-ID die al verwerkt is, negeert `message_process` (geeft `False`).

## Wat de module toevoegt

- `data/mail_alias_domain.xml`: een fictief maildomein `syndicus.example.com` (`mail.alias.domain`). Nieuwe companies krijgen het als standaard (`res.company._default_alias_domain_id` neemt het eerste domein).
- `vme.association._ensure_bill_alias()`: zet op het aankoopdagboek de alias `facturen-<gesaneerde companynaam>` op het domein van de company (en geeft de company het demodomein als ze er geen heeft). Bij een botsing komt het company-id erachter.
  - Opgeroepen in `account.chart.template._post_load_data`, zodra het rekeningstelsel van een nieuwe VME (en dus het aankoopdagboek) bestaat.
  - En via `data/bill_aliases.xml` (`<function>` → `_ensure_all_bill_aliases`) bij elke installatie en upgrade, zodat VME's die vóór 7b bestonden ook hun adres krijgen. Idempotent.
- `vme.association.bill_alias_email` (berekend, niet opgeslagen): het adres van het aankoopdagboek, op het VME-formulier met kopieerknop.

## Aanleveren zonder mailserver

`ai/facturen_mailgate.py` leest de `.eml`-bestanden in `ai/facturen_inbox/` en roept per mail via JSON-RPC `mail.thread.message_process(False, raw)` aan. Dat is precies wat Odoo's eigen `odoo-mailgate.py` doet als een mailserver (Postfix e.d.) inkomende mail aan Odoo doorgeeft; fetchmail (POP/IMAP) roept dezelfde methode aan. Daarna toont het script per mail de aangemaakte conceptfactuur (company, referentie, bedrag, kostperiode, sleutels).

De drie mails komen van de fictieve energieleverancier uit de demodata en hebben als bijlage exact de UBL-bestanden uit `addons/vme_belgie/demo_data/facturen/` (een pytest-test bewaakt dat).

```bash
cd ai
.venv/bin/python facturen_mailgate.py --dry-run   # toont waar elke mail heen gaat
ODOO_URL=http://localhost:8069 .venv/bin/python facturen_mailgate.py
```

Nodig: module `vme_belgie` geüpgraded (alias en domein) en de demodata (leverancier met btw-nummer BE0000000394 en de verdeelregels).

## Valkuilen

- `message_process` zoekt een route op het domein én de aliasnaam. Een company zonder `alias_domain_id` of een dagboekalias zonder domein wordt niet gevonden; daarom zet `_ensure_bill_alias` beide.
- Het afzenderadres bepaalt de partner alleen als de UBL er geen geeft; de UBL-decoder zoekt de leverancier op btw-nummer. In de tests heeft de leverancier daarom btw-nummer BE0000000394.
- De UBL-bestanden vermelden als klant "VME Residentie Linde" enz.; Odoo controleert dat niet tegen de company. De alias bepaalt de VME, dus een leverancier die het verkeerde adres gebruikt, boekt in de verkeerde VME (concept, nagekeken door een mens).
- Een mail zonder bijlage maakt geen factuur maar een bounce-mail (`mail.mail`) naar de afzender. In het prototype is er geen uitgaande mailserver, dus die blijft in de wachtrij.
- In tests: lots zonder eigenaar laten het automatisch verdelen bij het boeken mislukken (bericht in de chatter); geef de testkavels eigenaars.

## Testen

- Odoo: `addons/vme_belgie/tests/test_bill_mail.py` — adres op de VME, mail met UBL → conceptfactuur in de juiste VME met leverancier, kostperiode, sleutel, rekening en bedrag, en verdeling na boeken; dezelfde mail twee keer → één factuur; mail zonder bijlage → geen factuur; onbekend adres → geweigerd; alias hersteld bij upgrade.
- Script: `ai/tests/test_facturen_mailgate.py` — de drie mails (adres, afzender, bijlage gelijk aan de demo-UBL), elke ruwe mail gaat ongewijzigd naar `message_process`, dry-run levert niets aan, een niet-routeerbare mail wordt gemeld en overgeslagen, een al verwerkte mail wordt gemeld.

## Naar een echte mailbox

Zie `docs/beslissingen.md`: eigen domein of subdomein, MX naar de mailserver, inkomende mail via fetchmail (IMAP) of een mailserver die `odoo-mailgate` aanroept, en SPF/DKIM/DMARC voor de bounces en antwoorden die Odoo verstuurt. Het demodomein in `data/mail_alias_domain.xml` moet dan vervangen worden.
