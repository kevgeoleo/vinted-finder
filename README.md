# Vinted Description Finder

Search [vinted.de](https://www.vinted.de) for a product and keep only the listings whose **title or description contains your keywords** – Vinted's own search can't do that. Comes with a local web UI and a command-line version.

- Keyword search in title **and** description (any / all keywords)
- Optional price range (no limit unless you set one)
- Condition filter: *Neu mit Etikett, Neu ohne Etikett, Sehr gut, Gut, Zufriedenstellend*
- Size and color filters for shoes and clothes
- Optional: paste a filtered vinted.de URL to reuse Vinted's own category / brand / size / color filters
- Live progress, cancel button, sortable results, CSV export (opens correctly in German Excel)

> **Disclaimer:** This is an unofficial tool, not affiliated with Vinted. Automated access may violate Vinted's Terms of Service. Use it for personal purposes, at low volume, and at your own risk. Vinted can change its pages or block requests at any time, which may break the tool.

---

## Requirements

| What | Details |
|---|---|
| Python | 3.9 or newer (developed on 3.12) |
| OS | Windows, macOS or Linux |
| Packages | [`curl_cffi`](https://pypi.org/project/curl-cffi/) (recommended) and `requests` (automatic fallback) – see [`requirements.txt`](requirements.txt) |
| Browser | Any modern browser, for the web UI |

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

| Option | Meaning |
|---|---|
| `-q`, `--query` | Search term sent to Vinted (product name). Required unless `--filter-url` contains one |
| `-k`, `--keywords` | One or more keywords that must appear in title/description |
| `--match any\|all` | Match any keyword (default) or all keywords |
| `--min-price`, `--max-price` | Price range in EUR. Not set = no limit |
| `-c`, `--condition` | `new_with_tags` `new_without_tags` `very_good` `good` `satisfactory`. Not set = all |
| `--size` | Sizes to include, e.g. `42 42.5` or `M L` |
| `--color` | Colors to include, e.g. `Schwarz Weiß Blau` (see `COLORS` in `vinted_crawler.py`) |
| `--filter-url` | A filtered vinted.de catalog URL; its category, brand, size and color IDs are forwarded |
| `--pages` | Search result pages to scan, 96 listings each (default 2) |
| `--delay` | Seconds between requests (default 1.5, don't go much lower) |
| `--csv FILE` | Save results as CSV |

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
- **Color** matches by color family and also in English: `Blau` matches *Marineblau* and *blue*.
- Both are read from the listing page on a best-effort basis. If a listing's size or color can't be read, the tool falls back to the title and description text and tells you how many listings that affected.
- For the most precise results, use Vinted's own filters: set category, brand, size and color on vinted.de, copy the URL from the address bar, and paste it into the **Advanced** box of the UI (or `--filter-url`). Wrap the URL in quotes on the command line.

---

# Keyword ideas

Matching is **case-insensitive and substring-based** on title + description. Paste any list below straight into the keywords field (comma-separated).

**Tips**

- Short stems are enough: `geschenk` also finds *Geburtstagsgeschenk*, *Weihnachtsgeschenk* and *geschenkt*.
- Substring matching has no idea about negation: `kratzer` also matches *ohne Kratzer*, `etikett` also matches *ohne Etikett*. Check the hits.
- Avoid very short or generic words (`neu`, `vb`, `ok`): they match inside many other words. `neu` hits *neutral*, *neuwertig*, *Neukauf*.
- Use **any** matching to cast a wide net and **all** to narrow down (e.g. `kaum getragen` + `größe 42`).
- Sellers write umlauts both ways. Add variants when it matters: `ungeöffnet, ungeoeffnet`, `größe, groesse`, `zubehör, zubehoer`.
- Vinted.de listings are mostly German, but many sellers write in English. Try both lists.

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

---

## Troubleshooting

| Problem | What to do |
|---|---|
| `No listings found on the first search page` | Vinted may have blocked the request, or its layout changed. Open the saved `debug_catalog.html` to see what came back. Make sure `curl_cffi` is installed, raise `--delay`, and try again later |
| Errors 403 / 429 or very slow | You're being rate-limited. Increase the delay, scan fewer pages, and don't run many searches in a row |
| The run seems stuck | It's probably working through the listings (1.5 s each). The UI progress bar and the CLI `checking n/total` line show where it is |
| `pip install` fails with a permission error on Windows | Use a virtual environment (see Installation) or `pip install --user -r requirements.txt` |
| `No module named vinted_crawler` | `vinted_ui.py` and `vinted_crawler.py` must be in the same folder; start the UI from that folder |
| Port 8765 already in use | An earlier instance is still running. Close it or change `PORT` at the top of `vinted_ui.py` |
| Size or color notes in the UI | The value couldn't be read on some listings and the title/description was used instead. For exact results use the pasted-URL filter |

## Project structure

```
vinted-description-finder/
├── vinted_crawler.py   # crawler + command-line interface
├── vinted_ui.py        # local web UI (imports vinted_crawler)
├── requirements.txt
└── README.md
```

## License

Add a `LICENSE` file of your choice (for example MIT) before publishing.
