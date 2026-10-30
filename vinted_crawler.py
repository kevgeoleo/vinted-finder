#!/usr/bin/env python3
"""
Vinted.de crawler (v3): search by keywords in title/description, with optional
price range, condition, size and color filters.

Vinted retired its public JSON API (/api/v2/catalog/items -> 404), so this version
reads the normal server-rendered pages instead:
  1. /catalog?search_text=...&price_from=...&status_ids[]=...   -> listing URLs
  2. /items/<id>-<slug>                                         -> description, size, color

Install:   pip install curl_cffi        (recommended: looks like a real Chrome)

Examples:
  python vinted_crawler.py -q "JBL Charge 6" -k geschenk
  python vinted_crawler.py -q "nike air max" --size 42 42.5 --color Schwarz Weiß -c very_good good
  python vinted_crawler.py -q "levis 501" --filter-url "https://www.vinted.de/catalog?catalog[]=257&size_ids[]=208"
"""
import argparse
import csv
import html
import json
import re
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlparse

try:
    from curl_cffi import requests as http
    IMPERSONATE = {"impersonate": "chrome"}
except ImportError:  # fallback
    import requests as http
    IMPERSONATE = {}

BASE = "https://www.vinted.de"

CONDITIONS = {
    "new_with_tags": 6,
    "new_without_tags": 1,
    "very_good": 2,
    "good": 3,
    "satisfactory": 4,
}

# UI/CLI color name -> words that count as a match in the listing's color text
COLORS = {
    "Schwarz": ["schwarz", "black"],
    "Weiß": ["weiß", "weiss", "white"],
    "Grau": ["grau", "grey", "gray"],
    "Beige/Creme": ["beige", "creme", "cream"],
    "Braun": ["braun", "brown"],
    "Rot": ["rot", "red", "bordeaux"],
    "Rosa": ["rosa", "pink"],
    "Orange": ["orange"],
    "Gelb": ["gelb", "yellow", "senf"],
    "Grün": ["grün", "gruen", "green", "khaki", "oliv"],
    "Türkis": ["türkis", "turkis", "turquoise"],
    "Blau": ["blau", "blue", "marine", "navy"],
    "Lila": ["lila", "violett", "purple"],
    "Mehrfarbig": ["mehrfarbig", "multi"],
    "Silber": ["silber", "silver"],
    "Gold": ["gold"],
}

# Vinted filter params we are willing to copy from a pasted catalog URL
FORWARD_KEYS = {"catalog[]": "catalog[]", "catalog": "catalog[]", "brand_ids[]": "brand_ids[]",
                "size_ids[]": "size_ids[]", "color_ids[]": "color_ids[]",
                "material_ids[]": "material_ids[]"}

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
if not IMPERSONATE:
    HEADERS["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

# Matches /items/123456789-some-slug, also inside JSON-escaped strings (\/items\/...)
ITEM_RE = re.compile(r'\\?/items\\?/(\d{6,})-([^"\'\\\s?#<>/]+)')
LDJSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
META_DESC_RE = re.compile(
    r'<meta[^>]+(?:property=["\']og:description["\']|name=["\']description["\'])'
    r'[^>]+content=["\'](.*?)["\']', re.S | re.I
)
LABELS = {"größe", "groesse", "size", "farbe", "color", "colour", "zustand", "marke",
          "brand", "material", "condition"}


class Client:
    def __init__(self, delay=1.5):
        self.delay = delay
        self.s = http.Session(**IMPERSONATE) if IMPERSONATE else http.Session()
        self.s.headers.update(HEADERS)
        self._warm_up()

    def _warm_up(self):
        r = self.s.get(BASE + "/", timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"Homepage returned HTTP {r.status_code} (blocked?)")

    def get(self, url, params=None, retries=3):
        last = None
        for attempt in range(retries):
            time.sleep(self.delay)
            r = self.s.get(url, params=params, timeout=30)
            last = r.status_code
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429):
                time.sleep(8 * (attempt + 1))
                try:
                    self._warm_up()
                except Exception:
                    pass
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
        raise RuntimeError(f"HTTP {last} for {url} after {retries} tries")


def parse_filter_url(text):
    """Take a pasted vinted.de catalog URL (or bare query string).
    Returns (extra_params, search_text)."""
    text = (text or "").strip()
    if not text:
        return [], ""
    query = urlparse(text).query if "?" in text or text.startswith("http") else text
    extra, search_text = [], ""
    for k, val in parse_qsl(query, keep_blank_values=False):
        if k == "search_text":
            search_text = val
        elif k in FORWARD_KEYS and val:
            extra.append((FORWARD_KEYS[k], val))
    return extra, search_text


def catalog_url_params(query, min_price, max_price, statuses, page, extra=()):
    p = [("search_text", query), ("page", page), ("order", "newest_first")]
    if min_price is not None:
        p.append(("price_from", min_price))
    if max_price is not None:
        p.append(("price_to", max_price))
    p.append(("currency", "EUR"))
    for sid in statuses:
        p.append(("status_ids[]", sid))
    p.extend(extra)
    return urlencode(p)


def extract_item_links(page_html):
    """Return ordered {item_id: url} found in a catalog page."""
    found = {}
    for m in ITEM_RE.finditer(page_html):
        iid, slug = m.group(1), m.group(2)
        found.setdefault(iid, f"{BASE}/items/{iid}-{slug}")
    return found


def _walk_ld(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk_ld(n)
    elif isinstance(node, dict):
        yield node
        for v in node.values():
            if isinstance(v, (dict, list)):
                yield from _walk_ld(v)


def _as_text(x):
    if isinstance(x, dict):
        x = x.get("name") or x.get("value") or ""
    if isinstance(x, list):
        x = ", ".join(_as_text(i) for i in x)
    return re.sub(r"\s+", " ", str(x or "")).strip()


def _testid_value(page_html, name):
    """Text value of <... data-testid="name">label<value></...> (label words are skipped)."""
    m = re.search(r'data-testid=["\']' + re.escape(name) + r'["\'][^>]*>', page_html)
    if not m:
        return ""
    rest = page_html[m.end(): m.end() + 800]
    nxt = rest.find("data-testid")
    if nxt != -1:
        rest = rest[:nxt]
    rest = re.sub(r"<[^>]*$", "", rest)
    for frag in re.split(r"<[^>]*>", rest):
        t = html.unescape(frag).strip()
        if t and t.lower().rstrip(":") not in LABELS:
            return re.sub(r"\s+", " ", t)
    return ""


def _json_field(page_html, key):
    m = re.search(r'\\?"' + key + r'\\?"\s*:\s*\\?"([^"\\]+)', page_html)
    return html.unescape(m.group(1)).strip() if m else ""


def parse_item_page(page_html):
    """Return dict(title, description, price, condition, size, color) from an item page."""
    info = {"title": "", "description": "", "price": None, "condition": "", "size": "", "color": ""}
    for m in LDJSON_RE.finditer(page_html):
        try:
            data = json.loads(html.unescape(m.group(1)).strip())
        except Exception:
            try:
                data = json.loads(m.group(1).strip())
            except Exception:
                continue
        for d in _walk_ld(data):
            t = d.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                info["title"] = info["title"] or d.get("name", "") or ""
                info["description"] = info["description"] or d.get("description", "") or ""
                info["size"] = info["size"] or _as_text(d.get("size"))
                info["color"] = info["color"] or _as_text(d.get("color"))
                offers = d.get("offers")
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                if isinstance(offers, dict):
                    try:
                        info["price"] = float(offers.get("price"))
                    except (TypeError, ValueError):
                        pass
                    cond = offers.get("itemCondition") or d.get("itemCondition") or ""
                    info["condition"] = str(cond).rsplit("/", 1)[-1]
    if not info["description"]:
        m = META_DESC_RE.search(page_html)
        if m:
            info["description"] = html.unescape(m.group(1))
    # size / color: fall back to the visible attribute block, then to embedded JSON
    info["size"] = (info["size"] or _testid_value(page_html, "item-attributes-size")
                    or _json_field(page_html, "size_title"))
    if not info["color"]:
        info["color"] = _testid_value(page_html, "item-attributes-color")
    if not info["color"]:
        c1, c2 = _json_field(page_html, "color1"), _json_field(page_html, "color2")
        info["color"] = ", ".join(c for c in (c1, c2) if c)
    return info


def matches(text, keywords, mode):
    text = text.lower()
    hits = [k.lower() in text for k in keywords]
    return all(hits) if mode == "all" else any(hits)


def size_matches(attr, wanted, fallback=""):
    """True if any wanted size appears as a whole token in the size text.
    Uses the listing's size attribute; if unknown, falls back to title/description text."""
    text = (attr or fallback or "").lower()
    for w in wanted:
        w = w.strip().lower()
        if w and re.search(r"(?<!\w)(?<!\d[.,])" + re.escape(w) + r"(?!\w)(?![.,]\d)", text):
            return True
    return False


def color_matches(attr, wanted, fallback=""):
    """True if any wanted color matches. Attribute text: substring match (so 'Marineblau'
    matches Blau). Fallback title/description text: word-start match to limit false hits."""
    for key in wanted:
        words = COLORS.get(key, [key.lower()])
        if attr:
            if any(w in attr.lower() for w in words):
                return True
        else:
            if any(re.search(r"(?<!\w)" + re.escape(w), fallback.lower()) for w in words):
                return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Vinted.de keyword crawler")
    ap.add_argument("-q", "--query", default="", help="Search term sent to Vinted (e.g. product name)")
    ap.add_argument("-k", "--keywords", nargs="*", default=[],
                    help="Keywords that must appear in title/description (case-insensitive)")
    ap.add_argument("--match", choices=["any", "all"], default="any")
    ap.add_argument("--min-price", type=float, default=None, help="Min price EUR (default: none)")
    ap.add_argument("--max-price", type=float, default=None, help="Max price EUR (default: none)")
    ap.add_argument("-c", "--condition", nargs="*", choices=list(CONDITIONS), default=[],
                    help="Conditions to include (default: all)")
    ap.add_argument("--size", nargs="*", default=[], help="Sizes to include, e.g. 42 42.5 M")
    ap.add_argument("--color", nargs="*", choices=list(COLORS), default=[], help="Colors to include")
    ap.add_argument("--filter-url", default="",
                    help="Paste a filtered vinted.de catalog URL: category/brand/size/color ids are forwarded")
    ap.add_argument("--pages", type=int, default=2, help="Catalog pages to scan")
    ap.add_argument("--delay", type=float, default=1.5, help="Seconds between requests")
    ap.add_argument("--csv", help="Optional CSV output path")
    args = ap.parse_args()

    extra, url_query = parse_filter_url(args.filter_url)
    query = args.query or url_query
    if not query:
        ap.error("Provide -q/--query (or a --filter-url that contains search_text)")

    if not IMPERSONATE:
        print("Tip: `pip install curl_cffi` makes blocking much less likely.", file=sys.stderr)

    statuses = [CONDITIONS[c] for c in args.condition]
    client = Client(delay=args.delay)

    links = {}
    for page in range(1, args.pages + 1):
        qs = catalog_url_params(query, args.min_price, args.max_price, statuses, page, extra)
        page_html = client.get(f"{BASE}/catalog?{qs}")
        if page_html is None:
            print(f"Page {page}: 404 - stopping.", file=sys.stderr)
            break
        found = extract_item_links(page_html)
        new = {k: v for k, v in found.items() if k not in links}
        print(f"Page {page}: {len(new)} new listings", file=sys.stderr)
        if not new:
            if page == 1:
                with open("debug_catalog.html", "w", encoding="utf-8") as f:
                    f.write(page_html)
                print("No listings found on page 1. Saved raw page to debug_catalog.html "
                      "(possible block or layout change).", file=sys.stderr)
            break
        links.update(new)

    results = []
    size_unread = color_unread = 0
    for n, (iid, url) in enumerate(links.items(), 1):
        print(f"  checking {n}/{len(links)} ... ({len(results)} matches so far)", file=sys.stderr, flush=True)
        try:
            page_html = client.get(url)
        except Exception as e:
            print(f"  skip {iid}: {e}", file=sys.stderr)
            continue
        if page_html is None:
            continue
        info = parse_item_page(page_html)
        text = f"{info['title']}\n{info['description']}"
        if args.keywords and not matches(text, args.keywords, args.match):
            continue
        if args.size:
            size_unread += not info["size"]
            if not size_matches(info["size"], args.size, text):
                continue
        if args.color:
            color_unread += not info["color"]
            if not color_matches(info["color"], args.color, text):
                continue
        # safety net in case the server-side price filter was ignored
        if info["price"] is not None:
            if args.min_price is not None and info["price"] < args.min_price:
                continue
            if args.max_price is not None and info["price"] > args.max_price:
                continue
        results.append({
            "id": iid,
            "title": info["title"],
            "price_eur": info["price"] if info["price"] is not None else "",
            "size": info["size"],
            "color": info["color"],
            "condition": info["condition"],
            "url": url,
        })
        print(f"  match: {info['title'][:60]}", file=sys.stderr)

    if size_unread:
        print(f"Note: size not readable on {size_unread} listing(s); title/description text was used.", file=sys.stderr)
    if color_unread:
        print(f"Note: color not readable on {color_unread} listing(s); title/description text was used.", file=sys.stderr)

    results.sort(key=lambda r: (r["price_eur"] == "", r["price_eur"] or 0))
    print(f"\n{len(results)} matching listings:\n")
    for r in results:
        price = f"{r['price_eur']:.2f}" if r["price_eur"] != "" else "  ?  "
        extra_info = " | ".join(x for x in (r["size"], r["color"]) if x)
        print(f"{price:>8} EUR | {r['title'][:55]}  [{extra_info}]\n           {r['url']}")

    if args.csv and results:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=results[0].keys(), delimiter=";")
            w.writeheader()
            w.writerows(results)
        print(f"\nSaved to {args.csv}")


if __name__ == "__main__":
    main()
