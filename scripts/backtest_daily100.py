#!/usr/bin/env python3
"""100 calendar-day, date-isolated FUTSIM coupon replay.

Actual bookmaker opening match-winner and O/U 2.5 prices are from the
football-data.co.uk 2026/27 season CSVs. 2025/26 results initialize priors.
Unsupported historic markets (1X/X2/BTTS/corners) are excluded, NEVER
fabricated using fair 1/p quotes. Results are only revealed after predictions.
Not the full live feature set; report labels this scope accurately.
"""
import collections
import csv
import datetime as dt
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"docs"/"data"/"daily100_backtest.json"
LEAGUES={"Premier League":"E0","Bundesliga":"D1","La Liga":"SP1","Serie A":"I1",
         "Ligue 1":"F1","Eredivisie":"N1","Süper Lig":"T1"}
BASE="https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"
START_DEFAULT=None

def fetch(url):
    err=None
    for attempt in range(2):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 FUTSIM historical model testing"})
            with urllib.request.urlopen(req,timeout=20) as response:
                data=response.read(3_500_000)
            return data.decode("utf-8-sig","replace")
        except (urllib.error.URLError,TimeoutError,OSError) as e:
            err=e
            if attempt==0:time.sleep(.25)
    raise RuntimeError(str(err)[:120])

def n(v):
    try:
        x=float(str(v or "").strip())
        return x if x==x and x>0 else None
    except (ValueError,TypeError):return None

def day(v):
    v=str(v or "").strip()
    for pat in ("%d/%m/%Y","%d/%m/%y","%d/%m/%Y %H:%M","%d/%m/%y %H:%M","%Y-%m-%d"):
        try:return dt.datetime.strptime(v,pat).date().isoformat()
        except ValueError:pass
    return None

def price(row,fields):
    for field in fields:
        value=n(row.get(field))
        if value and 1.01<value<40:return round(value,3)
    return None

def parse(text,league,season):
    items=[]
    for row in csv.DictReader(io.StringIO(text)):
        date=day(row.get("Date"))
        home=(row.get("HomeTeam") or "").strip()
        away=(row.get("AwayTeam") or "").strip()
        try:
            hg=int(row.get("FTHG",""));ag=int(row.get("FTAG",""))
            if min(hg,ag)<0 or max(hg,ag)>25:continue
        except (TypeError,ValueError):continue
        if not date or not home or not away or home==away:continue
        odds={
          "1":price(row,("B365H","AvgH","PSH","WHH")),
          "X":price(row,("B365D","AvgD","PSD","WHD")),
          "2":price(row,("B365A","AvgA","PSA","WHA")),
          "2,5 Üst":price(row,("B365>2.5","Avg>2.5","P>2.5")),
          "2,5 Alt":price(row,("B365<2.5","Avg<2.5","P<2.5"))
        }
        items.append({"date":date,"league":league,"home":home,"away":away,
                      "hg":hg,"ag":ag,"odds":{k:v for k,v in odds.items() if v is not None}})
    return items

def run(days=100):
    ending=dt.datetime.now(dt.timezone.utc).date()-dt.timedelta(days=1)
    beginning=ending-dt.timedelta(days=days-1)
    historic=[];current=[];errors=[];sources={}
    for season,target in [("2526",historic),("2627",current)]:
        for league,division in LEAGUES.items():
            url=BASE.format(season=season,division=division)
            try:
                text=fetch(url)
                data=parse(text,league,season)
                if not data:raise RuntimeError("no completed games parsed")
                target.extend(data)
                sources[league+" "+season]={"url":url,"rows":len(data),"priced":sum(bool(m["odds"]) for m in data)}
                print("read",league,season,len(data),"priced",sources[league+" "+season]["priced"],flush=True)
            except Exception as ex:
                errors.append({"league":league,"season":season,"issue":str(ex)[:150]})
                print("unavailable",league,season,str(ex)[:140],flush=True)
    current=[m for m in current if m["date"]<=ending.isoformat()]
    historic.sort(key=lambda m:(m["date"],m["league"],m["home"]))
    current.sort(key=lambda m:(m["date"],m["league"],m["home"]))
    tests=[m for m in current if beginning.isoformat()<=m["date"]<=ending.isoformat()]
    payload={"window_start":beginning.isoformat(),"window_end":ending.isoformat(),
             "window_calendar_days":days,
             "last_season":historic,"current":current,"test_fixtures_count":len(tests),
             "sources":sources,"fetch_errors":errors}
    if len(tests)<100 or len(historic)<600:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps({"status":"insufficient_historical_data","window_start":beginning.isoformat(),
                 "window_end":ending.isoformat(),"observed_current_matches":len(tests),
                 "previous_season_matches":len(historic),"sources":sources,
                 "fetch_errors":errors},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("NOT ENOUGH real chronological matches for coupon report");return
    tmp=ROOT/"docs"/"data"/"_daily100_input.tmp.json"
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    try:
        subprocess.run(["node",str(ROOT/"scripts"/"backtest_daily100.cjs"),str(tmp),str(OUT)],check=True,timeout=1600,cwd=str(ROOT))
    finally:
        if tmp.exists():tmp.unlink()
    print("Backtest results saved",OUT,flush=True)

if __name__=="__main__":
    run(int(sys.argv[1]) if len(sys.argv)>1 else 100)
