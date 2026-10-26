#!/usr/bin/env python3
"""Sans option : met à jour data.json depuis isin.txt. Avec --serve : lance le site local.
Aucune dépendance : Python 3.8+ suffit.   Usage :  python update.py [--serve]"""
import json, re, sys, html as H, webbrowser, threading
import urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DIR = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "fr-FR,fr;q=0.9"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")

def to_text(page):
    page = re.sub(r"(?is)<(script|style).*?</\1>", " ", page)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", page)))

def num(s):
    s = s.replace("−", "-").replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try: return float(s)
    except ValueError: return None

def after(text, label, pattern, span=80):
    """Premier motif trouvé dans les `span` caractères qui suivent `label`."""
    m = re.search(re.escape(label) + r".{0,%d}?(%s)" % (span, pattern), text, re.I)
    return m.group(1) if m else None

PCT = r"[+\-−]?\s?\d+(?:[.,]\d+)?\s?%"

# ---------- SOURCE : Boursorama (à adapter ici si le site change) ----------
def fetch_boursorama(isin):
    url, page = get("https://www.boursorama.com/recherche/?query=" + urllib.parse.quote(isin))
    text = to_text(page)
    d = {"url": url}
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S) or re.search(r'og:title" content="([^"]+)', page)
    if m: d["name"] = to_text(m.group(1)).strip()
    for key, lab in (("p1", "1 an"), ("p3", "3 ans"), ("p5", "5 ans")):
        v = after(text, lab, PCT)
        if v: d[key] = num(v.replace("%", ""))
    v = after(text, "Frais de gestion", r"\d+(?:[.,]\d+)?\s?%")
    if v: d["fees"] = num(v.replace("%", ""))
    v = after(text, "Volatilité", r"\d+(?:[.,]\d+)?\s?%")
    if v: d["vol"] = num(v.replace("%", ""))
    v = after(text, "SRI", r"[1-7]\b") or after(text, "Indicateur de risque", r"[1-7]\b")
    if v: d["sri"] = int(v)
    for key, lab in (("manager", "Société de gestion"), ("category", "Catégorie")):
        v = after(text, lab, r"[A-Za-zÀ-ÿ0-9][^|]{2,60}?(?=\s{1,2}(?:[A-ZÉ][a-zé]+\s){0,0}[A-ZÉ]|$)", 70)
        if v: d[key] = v.strip()
    v = after(text, "Dernier cours", r"\d[\d\s]*[.,]\d+", 40) or after(text, "Valeur liquidative", r"\d[\d\s]*[.,]\d+", 40)
    if v: d["nav"] = num(v)
    return d
# ---------------------------------------------------------------------------

def update():
    isins = [l.split("#")[0].strip().upper() for l in (DIR / "isin.txt").read_text(encoding="utf-8").splitlines()]
    isins = [i for i in isins if i]
    old = {}
    try: old = {s["isin"]: s for s in json.loads((DIR / "data.json").read_text(encoding="utf-8"))["supports"]}
    except Exception: pass
    manual = {}
    try: manual = json.loads((DIR / "manuel.json").read_text(encoding="utf-8"))
    except Exception: pass
    out = []
    for isin in isins:
        s = dict(old.get(isin, {"isin": isin}))
        try:
            s.update({k: v for k, v in fetch_boursorama(isin).items() if v not in (None, "")})
            s["ok"] = True
        except Exception as e:
            s["ok"] = False; s["erreur"] = str(e)[:120]
        s.update(manual.get(isin, {}))
        out.append(s)
        print(("OK   " if s["ok"] else "ÉCHEC"), isin, s.get("name", ""))
    (DIR / "data.json").write_text(json.dumps(
        {"maj": datetime.now().isoformat(timespec="minutes"), "source": "Boursorama", "supports": out},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return out

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(DIR), **k)
    def do_GET(self):
        if self.path.startswith("/api/update"):
            update(); self.send_response(204); self.end_headers()
        else: super().do_GET()
    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()

if __name__ == "__main__":
    if "--serve" in sys.argv:
        port = 8000
        threading.Timer(1, lambda: webbrowser.open(f"http://localhost:{port}")).start()
        print(f"Site disponible sur http://localhost:{port}  (Ctrl+C pour arrêter)")
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    else:
        update()
