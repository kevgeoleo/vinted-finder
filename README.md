# Vinted Description Finder

Search [vinted.de](https://www.vinted.de) for a product and keep only the listings whose **title or description contains your keywords** – Vinted's own search can't do that. Comes with a local web UI and a command-line version.

- Keyword search in title **and** description (any / all keywords)
- Optional price range (no limit unless you set one)
- Condition filter: _Neu mit Etikett, Neu ohne Etikett, Sehr gut, Gut, Zufriedenstellend_
- Size and color filters for shoes and clothes
- Optional: paste a filtered vinted.de URL to reuse Vinted's own category / brand / size / color filters
- Live progress, cancel button, sortable results, CSV export (opens correctly in German Excel)

> **Disclaimer:** This is an unofficial tool, not affiliated with Vinted. Automated access may violate Vinted's Terms of Service. Use it for personal purposes, at low volume, and at your own risk. Vinted can change its pages or block requests at any time, which may break the tool.

---

## Requirements

| What     | Details                                                                                                                                           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python   | 3.9 or newer (developed on 3.12)                                                                                                                  |
| OS       | Windows, macOS or Linux                                                                                                                           |
| Packages | [`curl_cffi`](https://pypi.org/project/curl-cffi/) (recommended) and `requests` (automatic fallback) – see [`requirements.txt`](requirements.txt) |
| Browser  | Any modern browser, for the web UI                                                                                                                |

The web UI itself uses only the Python standard library.

## Installation

Use a virtual environment so nothing touches your system Python.

**Windows (PowerShell)**

```powershell
git clone https://github.com/<your-user>/vinted-description-finder.git
cd vinted-description-finder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run the activation script, run this once and activate again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**macOS / Linux**

```bash
git clone https://github.com/<your-user>/vinted-description-finder.git
cd vinted-description-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the web UI

```bash
python vinted_ui.py
```

Your browser opens `http://127.0.0.1:8765`. Fill in the form and click **Search**. The server only listens on your own machine (`127.0.0.1`). Press `Ctrl+C` in the terminal to stop it.

Without activating the venv (Windows): `.\.venv\Scripts\python.exe .\vinted_ui.py`

## Run from the command line

```bash
python vinted_crawler.py -q "JBL Charge 6" -k geschenk
```

| Option                       | Meaning                                                                                 |
| ---------------------------- | --------------------------------------------------------------------------------------- |
| `-q`, `--query`              | Search term sent to Vinted (product name). Required unless `--filter-url` contains one  |
| `-k`, `--keywords`           | One or more keywords that must appear in title/description                              |
| `--match any\|all`           | Match any keyword (default) or all keywords                                             |
| `--min-price`, `--max-price` | Price range in EUR. Not set = no limit                                                  |
| `-c`, `--condition`          | `new_with_tags` `new_without_tags` `very_good` `good` `satisfactory`. Not set = all     |
| `--size`                     | Sizes to include, e.g. `42 42.5` or `M L`                                               |
| `--color`                    | Colors to include, e.g. `Schwarz Weiß Blau` (see `COLORS` in `vinted_crawler.py`)       |
| `--filter-url`               | A filtered vinted.de catalog URL; its category, brand, size and color IDs are forwarded |
| `--pages`                    | Search result pages to scan, 96 listings each (default 2)                               |
| `--delay`                    | Seconds between requests (default 1.5, don't go much lower)                             |
| `--csv FILE`                 | Save results as CSV                                                                     |

Examples:

```bash
# Unopened gift items, new condition only, up to 120 EUR
python vinted_crawler.py -q "JBL Charge 6" -k geschenk ovp ungeöffnet versiegelt \
    -c new_with_tags new_without_tags --max-price 120

# Sneakers in size 42 or 42.5, black or white, barely worn
python vinted_crawler.py -q "Nike Air Max 90" --size 42 42.5 --color Schwarz Weiß \
    -k "kaum getragen" ungetragen neuwertig -c very_good new_without_tags --csv results.csv

# Broken devices for repair projects
python vinted_crawler.py -q "iPhone 13" -k defekt bastler ersatzteile --max-price 120
```

## How it works

1. Loads the normal vinted.de search page (`/catalog?search_text=...`) with your price, condition and (optional) forwarded filters, and collects the listing URLs.
2. Opens every listing page and reads title, description, price, size and color.
3. Keeps the listings that match your keywords, size and color. Results are sorted by price.

Because every listing has to be opened, a run takes a few minutes (about 1.5 s per listing). Fewer pages, a price range or a condition filter make it faster, because Vinted then returns fewer listings.

## Size and color filters

- **Size** matches whole tokens: `42` matches `42` but not `42.5`; `S` matches `S` but not `XS`; `M` matches `M / 38 / 10`.
- **Color** matches by color family and also in English: `Blau` matches _Marineblau_ and _blue_.
- Both are read from the listing page on a best-effort basis. If a listing's size or color can't be read, the tool falls back to the title and description text and tells you how many listings that affected.
- For the most precise results, use Vinted's own filters: set category, brand, size and color on vinted.de, copy the URL from the address bar, and paste it into the **Advanced** box of the UI (or `--filter-url`). Wrap the URL in quotes on the command line.

---

# Keyword ideas

Matching is **case-insensitive and substring-based** on title + description. Paste any list below straight into the keywords field (comma-separated).

**Tips**

- Short stems are enough: `geschenk` also finds _Geburtstagsgeschenk_, _Weihnachtsgeschenk_ and _geschenkt_.
- Substring matching has no idea about negation: `kratzer` also matches _ohne Kratzer_, `etikett` also matches _ohne Etikett_. Check the hits.
- Avoid very short or generic words (`neu`, `vb`, `ok`): they match inside many other words. `neu` hits _neutral_, _neuwertig_, _Neukauf_.
- Use **any** matching to cast a wide net and **all** to narrow down (e.g. `kaum getragen` + `größe 42`).
- Sellers write umlauts both ways. Add variants when it matters: `ungeöffnet, ungeoeffnet`, `größe, groesse`, `zubehör, zubehoer`.
- Vinted.de listings are mostly German, but many sellers write in English, and some in Dutch, French or Italian. Try several lists, see [German](#-german), [English](#-english), [Dutch](#-dutch-nederlands), [French](#-french-français) and [Italian](#-italian-italiano). The Dutch, French and Italian sections end with a few extra notes.

## 🇩🇪 German

### Gift, unused or unwanted purchase

Items that are new or never used, often sold because they were a gift or a wrong buy.

```
geschenk, nie benutzt, ungenutzt, unbenutzt, originalverpackt, ovp, ungeöffnet, ungeoeffnet, versiegelt, ungetragen, fehlkauf, doppelt bekommen, passt nicht, falsche größe, falsche groesse
```

### Excellent condition / like new

```
neuwertig, wie neu, einwandfrei, makellos, top zustand, sehr guter zustand, kaum benutzt, kaum getragen, einmal getragen, nur anprobiert, ohne gebrauchsspuren, nichtraucher, rauchfrei, tierfrei
```

### Defects, repair and spare parts

For bargains and repair projects.

```
defekt, kaputt, bastler, ersatzteile, reparatur, funktioniert nicht, geht nicht, akku schwach, riss, loch, löcher, fleck, kratzer, macken, gebrauchsspuren, verfärbt
```

### Motivated seller, negotiable, bundles

```
verhandlungsbasis, verhandelbar, muss weg, schnell weg, dringend, umzug, haushaltsauflösung, haushaltsaufloesung, preisnachlass, bundle, paketpreis, mehrere artikel, mehrkauf
```

### Complete set, accessories, proof of purchase

```
originalkarton, originalverpackung, zubehör, zubehoer, komplett, vollständig, ladekabel, netzteil, ladegerät, bedienungsanleitung, rechnung, kaufbeleg, kassenbon, seriennummer
```

### Electronics and tech

```
garantie, rechnung, seriennummer, akkukapazität, akkugesundheit, zyklen, entsperrt, ohne simlock, zurückgesetzt, neugerät, displayschutz
```

### Authentic, vintage, rare, collectible

```
original, authentisch, echtheitszertifikat, vintage, retro, selten, rar, limitiert, sammler, deadstock, vergriffen, ausverkauft
```

### Clothes and shoes: fit and sizing

```
fällt klein aus, fällt groß aus, passt nicht, zu klein, zu groß, falsche größe, nur anprobiert, einmal getragen, ungetragen, mit etikett
```

## 🇬🇧 English

### Gift, unused or unwanted purchase

```
gift, never used, unused, unopened, sealed, brand new, bnib, nwt, nwot, still in box, unworn, never worn, wrong size, doesn't fit, received twice
```

### Excellent condition / like new

```
like new, mint condition, excellent condition, flawless, barely used, hardly worn, worn once, tried on, no signs of wear, smoke-free, pet-free, non-smoker
```

### Defects, repair and spare parts

```
defective, broken, faulty, not working, for parts, spares or repair, needs repair, stain, hole, tear, scratch, damaged, worn out, as is
```

### Motivated seller, negotiable, bundles

```
negotiable, obo, or nearest offer, must go, quick sale, urgent, moving, clearance, bundle, discount, make an offer
```

### Complete set, accessories, proof of purchase

```
complete, full set, original box, original packaging, accessories, charger, manual, receipt, invoice, serial number
```

### Electronics and tech

```
warranty, receipt, serial number, battery health, cycles, unlocked, sim-free, factory reset, icloud, brand new device
```

### Authentic, vintage, rare, collectible

```
authentic, genuine, vintage, retro, rare, limited edition, collector, deadstock, sold out, discontinued
```

### Clothes and shoes: fit and sizing

```
runs small, runs large, true to size, tried on, wrong size, doesn't fit, tags attached
```

## 🇳🇱 Dutch (Nederlands)

### Gift, unused or unwanted purchase

```
cadeau, nooit gebruikt, ongebruikt, ongedragen, nooit gedragen, originele verpakking, ongeopend, verzegeld, nieuw in doos, dubbel gekregen, miskoop, past niet, verkeerde maat
```

### Excellent condition / like new

```
als nieuw, zo goed als nieuw, nieuwstaat, perfecte staat, uitstekende staat, zeer goede staat, nauwelijks gebruikt, amper gedragen, een keer gedragen, eenmaal gedragen, alleen gepast, geen gebruikssporen, rookvrij, huisdiervrij
```

### Defects, repair and spare parts

```
defect, kapot, voor onderdelen, onderdelen, reparatie, werkt niet, doet het niet, gaatje, gaten, scheur, vlek, kras, beschadigd, gebruikssporen, verkleurd, accu zwak
```

### Motivated seller, negotiable, bundles

```
onderhandelbaar, biedingen, moet weg, mag weg, snel weg, dringend, verhuizing, opruiming, huisontruiming, korting, bundel, bundelkorting, meerdere items
```

### Complete set, accessories, proof of purchase

```
originele doos, originele verpakking, accessoires, toebehoren, compleet, volledig, oplaadkabel, lader, adapter, handleiding, aankoopbewijs, factuur, kassabon, serienummer
```

### Electronics and tech

```
garantie, factuur, serienummer, accugezondheid, batterijconditie, cycli, ontgrendeld, simlockvrij, fabrieksinstellingen, nieuw toestel, screenprotector
```

### Authentic, vintage, rare, collectible

```
origineel, authentiek, echtheidscertificaat, vintage, retro, zeldzaam, gelimiteerd, limited edition, verzamelaar, deadstock, uitverkocht, niet meer verkrijgbaar
```

### Clothes and shoes: fit and sizing

```
valt klein, valt groot, past niet, te klein, te groot, verkeerde maat, alleen gepast, eenmaal gedragen, ongedragen, met label, met kaartje
```

## 🇫🇷 French (Français)

### Gift, unused or unwanted purchase

```
cadeau, jamais utilisé, jamais utilise, non utilisé, jamais porté, non porté, emballage d'origine, sous blister, scellé, jamais ouvert, non ouvert, neuf avec étiquette, neuf avec etiquette, reçu en double, mauvaise taille, erreur d'achat
```

### Excellent condition / like new

```
comme neuf, état neuf, très bon état, tres bon etat, excellent état, parfait état, impeccable, à peine utilisé, très peu porté, porté une fois, porté une seule fois, juste essayé, aucune trace d'usure, non-fumeur, sans animaux
```

### Defects, repair and spare parts

```
défectueux, defectueux, cassé, hors service, pour pièces, pièces détachées, à réparer, ne fonctionne pas, ne marche pas, un trou, petit trou, déchirure, déchiré, une tache, petite tache, rayure, abîmé, traces d'usure, décoloré, batterie faible
```

### Motivated seller, negotiable, bundles

```
négociable, negociable, à débattre, doit partir, urgent, déménagement, demenagement, vide-dressing, vide dressing, réduction, remise, bundle, lot de, plusieurs articles, faire une offre
```

### Complete set, accessories, proof of purchase

```
boîte d'origine, boite d'origine, emballage d'origine, accessoires, complet, ensemble complet, câble de charge, chargeur, adaptateur, notice, mode d'emploi, facture, ticket de caisse, preuve d'achat, numéro de série
```

### Electronics and tech

```
garantie, facture, numéro de série, santé de la batterie, cycles, débloqué, désimlocké, réinitialisé, appareil neuf, protection d'écran
```

### Authentic, vintage, rare, collectible

```
authentique, original, certificat d'authenticité, vintage, rétro, rare, édition limitée, collector, collection, deadstock, épuisé, introuvable
```

### Clothes and shoes: fit and sizing

```
taille petit, taille grand, taille normalement, trop petit, trop grand, ne me va pas, mauvaise taille, juste essayé, porté une fois, jamais porté, avec étiquette
```

## 🇮🇹 Italian (Italiano)

### Gift, unused or unwanted purchase

```
regalo, mai usato, mai utilizzato, non usato, mai indossato, non indossato, confezione originale, imballo originale, sigillato, mai aperto, ancora imballato, nuovo con cartellino, taglia sbagliata, acquisto sbagliato
```

### Excellent condition / like new

```
come nuovo, pari al nuovo, ottime condizioni, ottimo stato, perfette condizioni, impeccabile, usato pochissimo, poco usato, indossato una volta, indossato una sola volta, solo provato, nessun segno di usura, non fumatori, senza animali
```

### Defects, repair and spare parts

```
difettoso, rotto, guasto, per ricambi, pezzi di ricambio, da riparare, non funziona, buco, strappo, macchia, graffio, graffi, rovinato, segni di usura, scolorito, batteria scarica
```

### Motivated seller, negotiable, bundles

```
trattabile, urgente, deve sparire, trasloco, svuota armadio, svuotatutto, sconto, più articoli, lotto, pacchetto, fai un'offerta
```

### Complete set, accessories, proof of purchase

```
scatola originale, confezione originale, imballo originale, accessori, completo, set completo, cavo di ricarica, caricabatterie, alimentatore, manuale, istruzioni, fattura, scontrino, prova d'acquisto, numero di serie
```

### Electronics and tech

```
garanzia, fattura, scontrino, numero di serie, salute della batteria, cicli, sbloccato, senza blocco sim, ripristinato, resettato, dispositivo nuovo, protezione schermo
```

### Authentic, vintage, rare, collectible

```
autentico, originale, certificato di autenticità, vintage, retrò, raro, edizione limitata, da collezione, collezionisti, deadstock, esaurito, introvabile
```

### Clothes and shoes: fit and sizing

```
veste piccolo, veste grande, veste bene, calza piccolo, calza grande, troppo piccolo, troppo grande, taglia sbagliata, solo provato, indossato una volta, mai indossato, con cartellino
```

### Notes on the Dutch, French and Italian lists

- The tool is set up for **vinted.de**. Sellers there mostly write German or English, but Dutch, French and Italian listings do turn up. To search another Vinted country (vinted.nl, vinted.fr, vinted.it), change `BASE` at the top of `vinted_crawler.py`. This is untested.
- The **color filter** only knows German and English color names. For Dutch, French or Italian listings, put the color word into the keywords instead (for example `zwart`, `noir`, `nero`) or use the pasted-URL filter.
- Short words also match inside longer ones, so the lists use phrases such as `un trou` instead of `trou` (which would match _trouvé_) or `une tache` instead of `tache` (which would match _attache_). Keep that in mind when you add your own words.

---

## Troubleshooting

| Problem                                                | What to do                                                                                                                                                                                      |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `No listings found on the first search page`           | Vinted may have blocked the request, or its layout changed. Open the saved `debug_catalog.html` to see what came back. Make sure `curl_cffi` is installed, raise `--delay`, and try again later |
| Errors 403 / 429 or very slow                          | You're being rate-limited. Increase the delay, scan fewer pages, and don't run many searches in a row                                                                                           |
| The run seems stuck                                    | It's probably working through the listings (1.5 s each). The UI progress bar and the CLI `checking n/total` line show where it is                                                               |
| `pip install` fails with a permission error on Windows | Use a virtual environment (see Installation) or `pip install --user -r requirements.txt`                                                                                                        |
| `No module named vinted_crawler`                       | `vinted_ui.py` and `vinted_crawler.py` must be in the same folder; start the UI from that folder                                                                                                |
| Port 8765 already in use                               | An earlier instance is still running. Close it or change `PORT` at the top of `vinted_ui.py`                                                                                                    |
| Size or color notes in the UI                          | The value couldn't be read on some listings and the title/description was used instead. For exact results use the pasted-URL filter                                                             |

## Project structure

```
vinted-description-finder/
├── vinted_crawler.py   # crawler + command-line interface
├── vinted_ui.py        # local web UI (imports vinted_crawler)
├── requirements.txt
└── README.md
```
