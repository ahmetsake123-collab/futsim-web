#!/usr/bin/env python3
"""Fetch publicly displayed, DATE-MATCHED real market odds for FUTSIM.
Prices are international-market median odds, NOT Turkish official iddaa prices.
We never substitute de-vig "fair odds" for an actual quoted market price.
Only publicly exposed HTML is read; no betting placement, logins or private API.
"""
import datetime as dt
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/data/daily_market_odds.json"
TZ = ZoneInfo("Europe/Istanbul")
SITE = "https://zirveoran.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FUTSIMResearch/1.0; public-fixture-price-research)"}

def obtain(url):
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=14) as response:
            if response.status != 200:
                return ""
            body = response.read(2_000_000)
            return body.decode("utf-8", "replace")
    except (OSError, ValueError, TimeoutError):
        return ""

class MarketParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.heading_type = None
        self.heading_fragments = []
        self.section = ""
        self.title = ""
        self.cell_type = None
        self.cell_fragments = []
        self.row = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if self.skip:
            return
        if tag in ("h1", "h2"):
            self.heading_type = tag
            self.heading_fragments = []
        if tag == "tr":
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            self.cell_type = tag
            self.cell_fragments = []

    def handle_data(self, text):
        if self.skip:
            return
        if self.heading_type is not None:
            self.heading_fragments.append(text)
        if self.cell_type is not None:
            self.cell_fragments.append(text)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("h1", "h2") and self.heading_type == tag:
            name = " ".join(" ".join(self.heading_fragments).split())
            if tag == "h1": self.title = name
            else: self.section = name
            self.heading_type = None
        if tag in ("td", "th") and self.cell_type == tag:
            self.row.append(" ".join(" ".join(self.cell_fragments).split()))
            self.cell_type = None
        if tag == "tr" and self.row is not None:
            self.rows.append((self.section, self.row[:]))
            self.row = None

def number(text):
    text = str(text).replace("\u00a0", "").strip()
    if re.fullmatch(r"\d+(?:[.,]\d{1,3})?", text):
        return float(text.replace(",", "."))
    return None

def convert(rows):
    odds = {}
    probs = {}
    fair = {}
    for section, row in rows:
        if len(row) < 3:
            continue
        k = row[0].strip().upper().replace(" ", "")
        sec = section.casefold()
        key = None
        if "maç sonucu" in sec:
            key = {"1":"1", "X":"X", "2":"2"}.get(k)
        elif "çifte şans" in sec:
            key = {"1-X":"1X", "1X":"1X", "1-2":"12", "12":"12", "X-2":"X2", "X2":"X2"}.get(k)
        elif "karşılıklı gol" in sec:
            key = {"VAR":"KG Var", "YOK":"KG Yok"}.get(k)
        elif "gol alt/üst" in sec:
            prefix = re.search(r"(\d[,.]5)", section)
            if prefix:
                key = prefix.group(1).replace(".", ",") + " " + {"ÜST":"Üst","ALT":"Alt"}.get(k, "")
                if key.endswith(" "): key = None
        if not key:
            continue
        # Row format: Selection | actual MARKET price | highest quoted | FAIR (no-vig) | implied prob.
        value = number(row[1])
        if value is None or not 1.01 <= value <= 100:
            continue
        odds[key] = round(value, 3)
        if len(row) >= 4:
            v = number(row[3])
            if v is not None and v > 1:
                fair[key] = v
        if len(row) >= 5:
            v = re.search(r"\d+(?:[,.]\d+)?", row[4])
            if v:
                probability = float(v.group().replace(",","."))
                if 0 < probability < 100:
                    probs[key] = round(probability, 2)
    return odds, probs, fair

def find_match_urls(text, day):
    matches = set(re.findall(r"""(?:href=["']|["'])((?:https?://zirveoran\.com)?/mac/[^"'<>?# ]+-\d{4}-\d{2}-\d{2})""",text,re.I))
    matches.update(re.findall(r"""/mac/[a-z0-9-]+-\d{4}-\d{2}-\d{2}""", text, re.I))
    clean = []
    for p in sorted(matches):
        url = urllib.parse.urljoin(SITE, html.unescape(p))
        if url.endswith(day):
            clean.append(url)
    return list(dict.fromkeys(clean))[:85]

def teams_from_title(title):
    text = re.sub(r"\s+oranlar[ıi].*$", "", title, flags=re.I).strip()
    parts = re.split(r"\s+[–—]\s+|\s+-\s+", text, maxsplit=1)
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0].strip(), parts[1].strip()

def parse_match(page, url, day, captured):
    parser = MarketParser()
    parser.feed(page)
    names = teams_from_title(parser.title)
    odds, probabilities, fair = convert(parser.rows)
    if not names or len(odds) < 3 or not all(k in odds for k in ("1", "X", "2")):
        return None
    return {
        "date": day, "home": names[0], "away": names[1],
        "source": "Zirve Oran — uluslararası piyasa ortancası",
        "source_type": "international_bookmaker_median_not_turkish_iddaa",
        "source_mode": "published_snapshot",
        "source_url": url,
        "captured_at": captured,
        "markets": odds,
        "market_fair_probabilities": probabilities,
        "market_fair_odds": fair,
    }

def save_day(day, fetch=obtain):
    captured = dt.datetime.now(dt.timezone.utc).isoformat()
    # Keep only today's quotes to prevent stale odds from being shown as current.
    listing = fetch(f"{SITE}/bulten/{day}")
    links = find_match_urls(listing, day)
    items = []
    for url in links:
        body = fetch(url)
        if not body:
            continue
        row = parse_match(body, url, day, captured)
        if row:
            items.append(row)
    output = {
        "date": day, "fetched_at_utc": captured, "source": SITE,
        "price_type": "international market median; not Turkish official iddaa",
        "status": "ok" if items else "no_usable_odds",
        "matches": items, "links_found": len(links),
        "notes": ["Only visible dated public market prices are included.",
                  "Fair odds and implied probabilities are separate metadata, never used as bookmaker quotes.",
                  "Odds can change. Check the bookmaker's actual price before use."],
    }
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    TARGET.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"FUTSIM odds: {day}, {len(links)} match pages, {len(items)} matches with actual median-market prices")
    return output

def self_test():
    sample = """<h1>Galatasaray – VfB Stuttgart oranları</h1>
<h2>Maç Sonucu</h2><table><tr><th>Seçim</th><th>Piyasa</th></tr>
<tr><td>1</td><td>2.15</td><td>2.24</td><td>2.22</td><td>%45,0</td></tr>
<tr><td>X</td><td>4.20</td><td>4.26</td><td>4.41</td><td>%22,7</td></tr>
<tr><td>2</td><td>3.00</td><td>3.05</td><td>3.10</td><td>%32,3</td></tr></table>
<h2>Çifte Şans</h2><table><tr><td>1-X</td><td>1.40</td><td>1.44</td><td>1.48</td><td>%67,7</td></tr></table>
<h2>2,5 Gol Alt/Üst</h2><table><tr><td>Üst</td><td>1.36</td><td>1.38</td><td>1.40</td><td>%71,3</td></tr></table>"""
    row=parse_match(sample,SITE+"/mac/galatasaray-vfb-stuttgart-2026-11-03","2026-11-03","2026-11-03T09:00:00Z")
    assert row and row["markets"]["1X"]==1.40
    assert row["market_fair_odds"]["1X"]==1.48
    assert row["markets"]["2,5 Üst"]==1.36
    assert row["market_fair_probabilities"]["1X"]==67.7
    assert find_match_urls('<a href="/mac/galatasaray-vfb-stuttgart-2026-11-03">x</a>',"2026-11-03")
    print("FUTSIM odds parser self-test OK (real 1X=1.40, fair 1X=1.48, not mixed)")

if __name__ == "__main__":
    if "--self-test" in sys.argv: self_test()
    else:
        day = dt.datetime.now(TZ).date().isoformat()
        save_day(day)
