#!/usr/bin/env python3
"""
Local web UI for vinted_crawler.py  (no extra dependencies: Python standard library only).

Put this file in the SAME folder as vinted_crawler.py, then run:
    python vinted_ui.py
It opens http://127.0.0.1:8765 in your browser.

measurement - Messung, meting, maat, Maß, Vermessung 
gift - geschenk, cadeau, regalo, omaggio, dono
number of uses (german) - einmal benuzt, einmal getragen, ungetragen, unrown, used once, worn once, ein oder zwei, wenig getragen, barely used
number of uses (dutch) - Een keer gebruikt, Eén keer gedragen, Ongedragen, Ongebruikt, Eenmaal gebruikt, Eenmaal gedragen, Een of twee keer, Weinig gedragen, Nauwelijks gebruikt
number of uses (french) - Utilisé une fois, Porté une fois, Jamais porté, Non porté, Utilisé une seule fois, Porté une seule fois, Une ou deux fois, Peu porté, À peine utilisé
number of uses (Italian) - Usato una volta, Indossato una volta, Mai indossato, Mai indossato, Usato una sola volta, Indossato una sola volta, Una o due volte, Indossato poco, Usato pochissimo
"""
import json
import sys
import threading
import uuid
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import vinted_crawler as v

HOST, PORT = "127.0.0.1", 8765
JOBS = {}


class Job:
    def __init__(self):
        self.status = "running"      # running | done | error | cancelled
        self.message = "Starting…"
        self.done = 0
        self.total = 0
        self.results = []
        self.error = ""
        self.warning = ""
        self.cancel = False
        self.lock = threading.Lock()


def run_job(job, p):
    try:
        client = v.Client(delay=p["delay"])
        statuses = [v.CONDITIONS[c] for c in p["conditions"] if c in v.CONDITIONS]

        links = {}
        for page in range(1, p["pages"] + 1):
            if job.cancel:
                job.status = "cancelled"
                return
            job.message = f"Scanning search page {page}/{p['pages']}…"
            qs = v.catalog_url_params(p["query"], p["min_price"], p["max_price"], statuses, page, p["extra"])
            page_html = client.get(f"{v.BASE}/catalog?{qs}")
            if page_html is None:
                break
            new = {k: u for k, u in v.extract_item_links(page_html).items() if k not in links}
            if not new:
                if page == 1:
                    with open("debug_catalog.html", "w", encoding="utf-8") as f:
                        f.write(page_html)
                    job.error = ("No listings found on the first search page. Either there are no "
                                 "results, Vinted blocked the request, or its layout changed. "
                                 "Raw page saved to debug_catalog.html.")
                break
            links.update(new)

        job.total = len(links)
        size_unread = color_unread = 0
        for n, (iid, url) in enumerate(links.items(), 1):
            if job.cancel:
                job.status = "cancelled"
                return
            job.message = f"Checking listing {n}/{job.total}…"
            try:
                page_html = client.get(url)
            except Exception:
                page_html = None
            job.done = n
            if page_html is None:
                continue
            info = v.parse_item_page(page_html)
            text = f"{info['title']}\n{info['description']}"
            if p["keywords"] and not v.matches(text, p["keywords"], p["match"]):
                continue
            if p["sizes"]:
                size_unread += not info["size"]
                if not v.size_matches(info["size"], p["sizes"], text):
                    continue
            if p["colors"]:
                color_unread += not info["color"]
                if not v.color_matches(info["color"], p["colors"], text):
                    continue
            price = info["price"]
            if price is not None:
                if p["min_price"] is not None and price < p["min_price"]:
                    continue
                if p["max_price"] is not None and price > p["max_price"]:
                    continue
            with job.lock:
                job.results.append({"id": iid, "title": info["title"] or url, "price": price,
                                    "size": info["size"], "color": info["color"],
                                    "condition": info["condition"], "url": url})

        notes = []
        if size_unread:
            notes.append(f"Size could not be read on {size_unread} listing(s) – title/description text was used instead.")
        if color_unread:
            notes.append(f"Color could not be read on {color_unread} listing(s) – title/description text was used instead.")
        job.warning = " ".join(notes)
        job.status = "error" if (job.error and not job.results) else "done"
        job.message = "Finished."
    except Exception as e:  # noqa: BLE001
        job.status = "error"
        job.error = f"{type(e).__name__}: {e}"


def to_float(x):
    if x in (None, ""):
        return None
    return float(str(x).replace(",", "."))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            chips = "\n".join(
                f'<label class="chip"><input type="checkbox" value="{escape(c)}"> {escape(c)}</label>'
                for c in v.COLORS)
            body = PAGE.replace("__COLOR_CHIPS__", chips).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/status"):
            q = parse_qs(urlparse(self.path).query)
            job = JOBS.get(q.get("id", [""])[0])
            if not job:
                return self._json({"error": "unknown job"}, 404)
            since = int(q.get("since", ["0"])[0])
            with job.lock:
                new = job.results[since:]
                nxt = len(job.results)
            self._json({"status": job.status, "message": job.message, "done": job.done,
                        "total": job.total, "error": job.error, "warning": job.warning,
                        "results": new, "next": nxt})
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/start":
            try:
                extra, url_query = v.parse_filter_url(str(data.get("filter_url", "")))
                p = {
                    "query": str(data.get("query", "")).strip() or url_query,
                    "keywords": [k.strip() for k in data.get("keywords", []) if k.strip()],
                    "match": "all" if data.get("match") == "all" else "any",
                    "min_price": to_float(data.get("min_price")),
                    "max_price": to_float(data.get("max_price")),
                    "conditions": list(data.get("conditions", [])),
                    "sizes": [s.strip() for s in data.get("sizes", []) if s.strip()],
                    "colors": [c for c in data.get("colors", []) if c in v.COLORS],
                    "extra": extra,
                    "pages": max(1, min(10, int(data.get("pages", 2)))),
                    "delay": max(0.8, float(data.get("delay", 1.5))),
                }
            except (ValueError, TypeError):
                return self._json({"error": "Invalid input"}, 400)
            if not p["query"]:
                return self._json({"error": "Search term is required"}, 400)
            job = Job()
            jid = uuid.uuid4().hex
            JOBS[jid] = job
            threading.Thread(target=run_job, args=(job, p), daemon=True).start()
            self._json({"id": jid})
        elif self.path == "/api/cancel":
            job = JOBS.get(data.get("id", ""))
            if job:
                job.cancel = True
            self._json({"ok": True})
        else:
            self.send_error(404)


PAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vinted Description Finder</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--text:#1b1f24;--muted:#6b7280;--line:#e3e6ea;--accent:#007782;--danger:#b42318;--warn:#9a6700}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--card:#1d2125;--text:#e8eaed;--muted:#9aa3ad;--line:#2d333a;--accent:#2bb3c0;--danger:#f97066;--warn:#e3b341}}
*{box-sizing:border-box}
body{margin:0;font:15px/1.45 system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text)}
main{max-width:1060px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:700px){.grid{grid-template-columns:1fr}}
.full{grid-column:1/-1}
label.l{display:block;font-size:13px;font-weight:600;margin-bottom:4px}
.hint{font-weight:400;color:var(--muted)}
input[type=text],input[type=number],select{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:inherit}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;padding:6px 12px;cursor:pointer;background:var(--bg);user-select:none}
.chip input{accent-color:var(--accent)}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
details{border:1px dashed var(--line);border-radius:10px;padding:10px 12px}
summary{cursor:pointer;font-weight:600;font-size:13px}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--text);padding:9px 16px;border-radius:8px;cursor:pointer}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:600}
button:disabled{opacity:.5;cursor:not-allowed}
.bar{height:6px;background:var(--line);border-radius:6px;overflow:hidden;margin-top:10px}
.bar>div{height:100%;width:0;background:var(--accent);transition:width .3s}
#msg{color:var(--muted);margin-top:8px;min-height:20px}
#warn{color:var(--warn);margin-top:6px}
#err{color:var(--danger);margin-top:8px;white-space:pre-wrap}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:13px;color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap}
td.p{white-space:nowrap;font-weight:600}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.empty{color:var(--muted);padding:12px 0}
.wrap{overflow-x:auto}
</style>
</head>
<body>
<main>
  <h1>Vinted Description Finder</h1>
  <p class="sub">Searches vinted.de and keeps only listings whose title or description contains your keywords – with optional price, condition, size and color filters.</p>

  <form id="form" class="card">
    <div class="grid">
      <div class="full">
        <label class="l" for="query">Search term <span class="hint">(product name, sent to Vinted)</span></label>
        <input type="text" id="query" placeholder="z.B. Nike Air Max 90">
      </div>
      <div class="full">
        <label class="l" for="keywords">Keywords in description <span class="hint">(comma-separated, leave empty for no keyword filter)</span></label>
        <input type="text" id="keywords" placeholder="z.B. geschenk, ovp, ungeöffnet">
      </div>
      <div>
        <label class="l" for="match">Keyword matching</label>
        <select id="match">
          <option value="any">Any keyword matches</option>
          <option value="all">All keywords must match</option>
        </select>
      </div>
      <div class="row" style="align-items:flex-end">
        <div style="flex:1">
          <label class="l" for="minp">Min price € <span class="hint">(optional)</span></label>
          <input type="number" id="minp" min="0" step="0.01" placeholder="no limit">
        </div>
        <div style="flex:1">
          <label class="l" for="maxp">Max price € <span class="hint">(optional)</span></label>
          <input type="number" id="maxp" min="0" step="0.01" placeholder="no limit">
        </div>
      </div>
      <div class="full">
        <label class="l">Condition <span class="hint">(none selected = all conditions)</span></label>
        <div class="chips" id="conds">
          <label class="chip"><input type="checkbox" value="new_with_tags"> Neu mit Etikett</label>
          <label class="chip"><input type="checkbox" value="new_without_tags"> Neu ohne Etikett</label>
          <label class="chip"><input type="checkbox" value="very_good"> Sehr gut</label>
          <label class="chip"><input type="checkbox" value="good"> Gut</label>
          <label class="chip"><input type="checkbox" value="satisfactory"> Zufriedenstellend</label>
        </div>
      </div>
      <div class="full">
        <label class="l" for="sizes">Size <span class="hint">(optional, comma-separated, e.g. <code>42, 42.5</code> for shoes or <code>M, L</code> for clothes)</span></label>
        <input type="text" id="sizes" placeholder="no size filter">
      </div>
      <div class="full">
        <label class="l">Color <span class="hint">(optional, none selected = all colors)</span></label>
        <div class="chips" id="colors">
__COLOR_CHIPS__
        </div>
      </div>
      <div class="full">
        <details>
          <summary>Advanced: use exact category / brand / size / color filters from vinted.de</summary>
          <p class="hint" style="margin:8px 0">On vinted.de pick your category, brand, size and color in the normal filters, then copy the address bar URL and paste it here. Those filters are applied by Vinted itself (most precise). The price, condition and keyword settings above still apply.</p>
          <input type="text" id="furl" placeholder="https://www.vinted.de/catalog?catalog[]=1242&size_ids[]=...">
        </details>
      </div>
      <div>
        <label class="l" for="pages">Search pages to scan <span class="hint">(96 listings each, max 10)</span></label>
        <input type="number" id="pages" min="1" max="10" value="2">
      </div>
      <div>
        <label class="l" for="delay">Delay between requests (s) <span class="hint">(min 0.8)</span></label>
        <input type="number" id="delay" min="0.8" step="0.1" value="1.5">
      </div>
    </div>
    <div class="row" style="margin-top:16px">
      <button class="primary" id="go" type="submit">Search</button>
      <button type="button" id="stop" disabled>Cancel</button>
      <button type="button" id="csv" disabled>Export CSV</button>
    </div>
    <div class="bar"><div id="fill"></div></div>
    <div id="msg"></div>
    <div id="warn"></div>
    <div id="err"></div>
  </form>

  <div class="card">
    <div class="row" style="justify-content:space-between;margin-bottom:6px">
      <strong id="count">0 matching listings</strong>
      <span class="hint" style="font-size:13px">Click a column header to sort</span>
    </div>
    <div class="wrap">
      <table>
        <thead><tr>
          <th data-k="price">Price</th><th data-k="title">Listing</th><th data-k="size">Size</th>
          <th data-k="color">Color</th><th data-k="condition">Condition</th>
        </tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <div class="empty" id="empty">No results yet.</div>
  </div>
</main>

<script>
const $ = s => document.querySelector(s);
let jobId = null, timer = null, since = 0, rows = [], sortKey = 'price', sortDir = 1;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const eur = n => n == null ? '–' : n.toLocaleString('de-DE', {style:'currency', currency:'EUR'});
const checked = sel => [...document.querySelectorAll(sel + ' input:checked')].map(i => i.value);

function render() {
  const k = sortKey;
  const sorted = [...rows].sort((a, b) => {
    let x = a[k], y = b[k];
    if (k === 'price') { x = x ?? Infinity; y = y ?? Infinity; return (x - y) * sortDir; }
    return String(x || '').localeCompare(String(y || ''), 'de', {numeric: true}) * sortDir;
  });
  $('#rows').innerHTML = sorted.map(r =>
    `<tr><td class="p">${eur(r.price)}</td>` +
    `<td><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></td>` +
    `<td>${esc(r.size) || '–'}</td><td>${esc(r.color) || '–'}</td><td>${esc(r.condition)}</td></tr>`).join('');
  $('#count').textContent = `${rows.length} matching listing${rows.length === 1 ? '' : 's'}`;
  $('#empty').style.display = rows.length ? 'none' : 'block';
  $('#csv').disabled = !rows.length;
}

document.querySelectorAll('th').forEach(th => th.addEventListener('click', () => {
  const k = th.dataset.k;
  sortDir = (sortKey === k) ? -sortDir : 1; sortKey = k; render();
}));

function setRunning(on) { $('#go').disabled = on; $('#stop').disabled = !on; }

async function poll() {
  try {
    const r = await fetch(`/api/status?id=${jobId}&since=${since}`);
    const d = await r.json();
    since = d.next;
    if (d.results.length) { rows.push(...d.results); render(); }
    $('#msg').textContent = d.message;
    $('#fill').style.width = d.total ? (100 * d.done / d.total) + '%' : '5%';
    if (d.error) $('#err').textContent = d.error;
    if (d.warning) $('#warn').textContent = d.warning;
    if (d.status !== 'running') {
      clearInterval(timer); setRunning(false);
      if (d.status === 'done') $('#fill').style.width = '100%';
      $('#msg').textContent = d.status === 'cancelled' ? 'Cancelled.' :
        d.status === 'done' ? `Done – ${rows.length} match(es) from ${d.total} listings checked.` : '';
    }
  } catch (e) { $('#err').textContent = 'Lost connection to the local server.'; clearInterval(timer); setRunning(false); }
}

$('#form').addEventListener('submit', async e => {
  e.preventDefault();
  rows = []; since = 0; render();
  $('#err').textContent = ''; $('#warn').textContent = ''; $('#fill').style.width = '0';
  const payload = {
    query: $('#query').value,
    keywords: $('#keywords').value.split(/[,\n]/).map(s => s.trim()).filter(Boolean),
    match: $('#match').value,
    min_price: $('#minp').value, max_price: $('#maxp').value,
    conditions: checked('#conds'),
    sizes: $('#sizes').value.split(/[,;\n]/).map(s => s.trim()).filter(Boolean),
    colors: checked('#colors'),
    filter_url: $('#furl').value,
    pages: $('#pages').value, delay: $('#delay').value,
  };
  setRunning(true); $('#msg').textContent = 'Starting…';
  const r = await fetch('/api/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const d = await r.json();
  if (!r.ok) { $('#err').textContent = d.error || 'Error'; $('#msg').textContent = ''; setRunning(false); return; }
  jobId = d.id; clearInterval(timer); timer = setInterval(poll, 1000); poll();
});

$('#stop').addEventListener('click', () => {
  fetch('/api/cancel', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id: jobId})});
  $('#msg').textContent = 'Cancelling…';
});

$('#csv').addEventListener('click', () => {
  const q = s => '"' + String(s ?? '').replace(/"/g, '""') + '"';
  const lines = ['Price EUR;Title;Size;Color;Condition;URL', ...rows.map(r =>
    [r.price == null ? '' : String(r.price).replace('.', ','), q(r.title), q(r.size), q(r.color), q(r.condition), q(r.url)].join(';'))];
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'vinted_results.csv'; a.click();
});
render();
</script>
</body>
</html>
"""


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Vinted Description Finder running at {url}  (Ctrl+C to stop)")
    if not v.IMPERSONATE:
        print("Tip: `pip install curl_cffi` (in a venv) makes blocking less likely.", file=sys.stderr)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
