#!/usr/bin/env python3
"""Optional API-Football free-tier data collector for FUTSIM.

Security: APISPORTS_KEY is read ONLY from process environment, never from
frontend or repository files. Calls run in a GitHub runner; the static web
app reads sanitized public metadata, without any secret.

Budget: <= 18 non-status requests per invocation. On absent key it exits
without network calls, retaining the current no-key status.
Free plans may be restricted to historical seasons; this is detected.
No fake injury/xG/lineup values. No betting odds fetched or published.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "data" / "api_football.json"
ENDPOINT = "https://v3.football.api-sports.io"
LEAGUES = {39: "Premier League", 78: "Bundesliga", 140: "La Liga",
           135: "Serie A", 61: "Ligue 1", 88: "Eredivisie",
           203: "Süper Lig", 2: "Şampiyonlar Ligi"}
BUDGET = 18
MAX_SELECTED_FIXTURES = 8

def clean(v, limit=140):
    return str(v or "").strip().replace("\n", " ").replace("\r", " ")[:limit]

def official_fixture(row):
    match = row.get("fixture") or {}
    league = row.get("league") or {}
    clubs = row.get("teams") or {}
    home = clubs.get("home") or {}
    away = clubs.get("away") or {}
    league_id = league.get("id")
    fixture_id = match.get("id")
    if league_id not in LEAGUES or not isinstance(fixture_id, int):
        return None
    date = clean(match.get("date"), 45)
    if len(date) < 10 or not date[:4].isdigit():
        return None
    return {
        "id": fixture_id, "date": date[:10], "kickoff": date,
        "league": LEAGUES[league_id], "league_id": league_id,
        "home": clean(home.get("name"), 85),
        "away": clean(away.get("name"), 85),
        "home_id": home.get("id"), "away_id": away.get("id"),
        "status": clean((match.get("status") or {}).get("short"), 12),
        "source": "API-Football"
    }

def safe_injury(row):
    player = row.get("player") or {}
    team = row.get("team") or {}
    fixture = row.get("fixture") or {}
    # Injuries endpoint may express type/reason as player.type/reason.
    return {
        "player": clean(player.get("name"), 100),
        "team": clean(team.get("name"), 100),
        "type": clean(player.get("type"), 70),
        "reason": clean(player.get("reason"), 130),
        "fixture_id": fixture.get("id")
    }

def safe_lineup(row):
    team = row.get("team") or {}
    coach = row.get("coach") or {}
    starter = []
    for x in (row.get("startXI") or [])[:11]:
        p = x.get("player") or {}
        if p.get("name"):
            starter.append({"name": clean(p.get("name"), 90),
                            "number": p.get("number"), "position": clean(p.get("pos"), 5)})
    return {"team": clean(team.get("name"), 100), "team_id": team.get("id"),
            "formation": clean(row.get("formation"), 24),
            "coach": clean(coach.get("name"), 100),
            "confirmed": len(starter) == 11, "starters": starter}

class Client:
    def __init__(self, key):
        self.key = key
        self.used = 0
        self.messages = []
        self.remaining = None

    def get(self, route, **query):
        if self.used >= BUDGET:
            return None
        qs = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        request = urllib.request.Request(
            ENDPOINT + "/" + route + ("?" + qs if qs else ""),
            headers={"x-apisports-key": self.key}, method="GET")
        self.used += 1
        try:
            with urllib.request.urlopen(request, timeout=24) as response:
                self.remaining = response.headers.get("x-ratelimit-requests-remaining", self.remaining)
                data = json.load(response)
            errors = data.get("errors")
            if errors:
                self.messages.append(f"{route}: API returned error / access limitation")
                return None
            results = data.get("response")
            if not isinstance(results, list):
                self.messages.append(f"{route}: no supported response")
                return None
            return results
        except urllib.error.HTTPError as exc:
            # Numeric HTTP response codes are safe diagnostics; never log headers.
            self.messages.append(f"{route}: HTTP {exc.code} / access restricted or unavailable")
            return None
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            self.messages.append(f"{route}: network response unavailable ({type(exc).__name__})")
            return None

def assemble(client, now):
    local = now.astimezone(ZoneInfo("Europe/Istanbul"))
    today = local.date()
    fixture_map = {}
    successful_days = 0
    for d in (today, today + dt.timedelta(days=1)):
        rows = client.get("fixtures", date=d.isoformat(), timezone="Europe/Istanbul")
        if rows is None:
            continue
        successful_days += 1
        for item in rows:
            f = official_fixture(item)
            if f is not None:
                fixture_map[f["id"]] = f

    fixtures = sorted(fixture_map.values(), key=lambda x: (x["kickoff"], x["id"]))
    # Don't accidentally replace valid CC0 scores/fixtures if current
    # API season is not covered on the user's free account.
    if not fixtures:
        status = "season_unavailable_or_no_fixtures" if successful_days else "api_error_or_season_restricted"
        return {"status": status, "fixtures": [],
                "notes": ["API-Football ücretsiz hesapta 2026/27 erişimi veya uygun fikstür doğrulanamadı."],
                "successful_dates": successful_days}

    # Ignore completed matches when spending limited free-tier calls.
    # Spread coverage across leagues before selecting a second match per league.
    scheduled = [f for f in fixtures if f["status"] in ("NS", "TBD", "PST", "SUSP")]
    scheduled.sort(key=lambda f: (f["kickoff"], f["id"]))
    preferred = []
    leagues_seen = set()
    for f in scheduled:
        if f["league"] not in leagues_seen:
            preferred.append(f)
            leagues_seen.add(f["league"])
    chosen_ids = {f["id"] for f in preferred}
    preferred.extend(f for f in scheduled if f["id"] not in chosen_ids)
    selected = preferred[:MAX_SELECTED_FIXTURES]

    by_id = {}
    for f in selected:
        # One injury query per prioritized fixture, <= 8 calls
        inj = client.get("injuries", fixture=f["id"])
        if inj is None:
            injuries = None
            injuries_checked = False
        else:
            injuries = [safe_injury(x) for x in inj[:28]]
            injuries_checked = True
        by_id[str(f["id"])] = {"injuries": injuries,
                              "injuries_checked": injuries_checked,
                              "lineups": None, "lineups_checked": False}

    # Only inspect lineups on today's fixtures; official lineups are
    # usually announced shortly before kickoff.
    def soon(f):
        try:
            t = dt.datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00"))
            if t.tzinfo is None:return False
            minutes=(t-now).total_seconds()/60
            return -20 <= minutes <= 130
        except (TypeError,ValueError):return False
    lineups_due = [f for f in selected if f["status"] in ("NS", "TBD") and soon(f)][:4]
    for f in lineups_due:
        rows = client.get("fixtures/lineups", fixture=f["id"])
        if rows is not None:
            by_id[str(f["id"])]["lineups_checked"] = True
            by_id[str(f["id"])]["lineups"] = [safe_lineup(x) for x in rows[:2]]

    return {"status": "connected", "fixtures": fixtures[:85],
            "details": by_id,
            "notes": ["API-Football free account season and fixture coverage varies.",
                      "Lineups unconfirmed until 11 starters available.",
                      "No verified xG/xA in this integration."]}

def self_test():
    one = official_fixture({"fixture": {"id": 123, "date": "2026-10-25T18:00:00+03:00",
               "status": {"short": "NS"}},
               "league": {"id": 39},
               "teams": {"home": {"name": "Arsenal", "id": 42},
                         "away": {"name": "Chelsea", "id": 49}}})
    assert one["id"] == 123 and one["date"] == "2026-10-25"
    assert official_fixture({"fixture": {"id": 4, "date": "2026-10-25"}, "league": {"id": 444}}) is None
    assert safe_injury({"player": {"name": "Player Test", "reason": "Knee"},
                        "team": {"name": "Arsenal"}})["reason"] == "Knee"
    assert not safe_lineup({"team": {"name": "Arsenal"}, "startXI": []})["confirmed"]
    assert safe_lineup({"team": {"name": "Arsenal"}, "startXI": [
        {"player":{"name":f"P{i}"}} for i in range(11)]})["confirmed"]
    class Fake:
        used=0
        remaining="88"
        messages=[]
        def get(self, route, **query):
            self.used+=1
            return [{"fixture":{"id":123,"date":"2026-10-25T18:00:00+03:00",
                    "status":{"short":"NS"}},"league":{"id":39},
                    "teams":{"home":{"name":"Arsenal","id":42},"away":{"name":"Chelsea","id":49}}}] if route=="fixtures" else []
    data=assemble(Fake(), dt.datetime(2026,10,25,14,0,tzinfo=dt.timezone.utc))
    assert data["status"] == "connected" and len(data["fixtures"])==1
    assert len(data["details"])==1 and data["details"]["123"]["injuries_checked"]
    assert BUDGET <= 20
    print("FUTSIM API-Football self-test: OK (fake data only; no paid/free account queried)")

def run():
    if "--self-test" in sys.argv:
        return self_test()
    key = os.environ.get("APISPORTS_KEY", "").strip()
    if not key:
        if not TARGET.exists():
            TARGET.parent.mkdir(parents=True,exist_ok=True)
            TARGET.write_text(json.dumps({"status": "not_configured", "fixtures": [],
                             "source": "https://www.api-football.com/",
                             "notes": ["GitHub Actions APISPORTS_KEY secret gereklidir."]},
                            ensure_ascii=False,indent=2),encoding="utf-8")
        print("FUTSIM API-Football: no key configured; made no external requests")
        return
    now = dt.datetime.now(dt.timezone.utc)
    client = Client(key)
    payload = assemble(client,now)
    payload.update({"version":1, "fetched_at_utc":now.isoformat(),
        "source":"https://www.api-football.com/", "request_count":client.used,
        "remaining_daily_requests":client.remaining,
        "message_count":len(client.messages),
        "errors_redacted":client.messages[:12], "timezone":"Europe/Istanbul",
        "measured_xg":False,"measured_xa":False})
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    TARGET.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"FUTSIM API-Football: {payload['status']}; {len(payload['fixtures'])} fixtures; "
          f"{client.used}/{BUDGET} requests, {len(client.messages)} restricted/unavailable endpoints")
if __name__=="__main__":
    run()
