#!/usr/bin/env python3
"""Replay recent 100 calendar dates using archived prices for all live FUTSIM markets.

Real match result/goal datasets: football-data.co.uk opening odds, scores.
Other actual market prices: archived Zirve Oran match pages where available.
Never fill missing 1X/12/X2, BTTS or 1.5/3.5 market prices from model odds.
"""
import concurrent.futures
import datetime as dt
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from update_public_odds import MarketParser, convert, find_match_urls
from backtest_daily100 import LEAGUES, BASE, fetch, parse

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"docs/data/daily100_current_backtest.json"
SITE="https://zirveoran.com"
KNOWN={
"man united":"manchester united","man city":"manchester city","nott'm forest":"nottingham forest",
"wolves":"wolverhampton wanderers","brighton":"brighton","newcastle":"newcastle",
"tottenham":"tottenham","leicester":"leicester","west ham":"west ham",
"ath madrid":"atletico madrid","ath bilbao":"athletic club","sociedad":"real sociedad",
"betis":"real betis","vallecano":"rayo vallecano","espanol":"espanyol",
"alaves":"deportivo alaves","la coruna":"deportivo la coruna",
"fc koln":"koln","m gladbach":"borussia monchengladbach","leverkusen":"bayer leverkusen",
"dortmund":"borussia dortmund","bayern munich":"bayern munchen",
"psg":"paris saint germain","inter":"inter","milan":"ac milan",
"utrecht":"utrecht","psv":"psv eindhoven","ajax":"ajax",
"sparta rotterdam":"sparta rotterdam","twente":"twente",
"alkmaar":"az alkmaar","sociedad":"real sociedad"
}
def norm(s):
    s=unicodedata.normalize("NFKD",str(s or "").lower())
    s="".join(ch for ch in s if not unicodedata.combining(ch))
    s=s.replace("ı","i").replace("ø","o").replace("ß","ss")
    s=re.sub(r"[^a-z0-9 ]+"," ",s)
    s=" ".join(s.split())
    return KNOWN.get(s,s)

def slug(s):
    return norm(s).replace(" ","-")

def fetch_url(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; FUTSIMHistoricalResearch/1.0; read-only)"})
        with urllib.request.urlopen(req,timeout=11) as r:
            if r.status!=200:return ""
            return r.read(2_000_000).decode("utf-8","replace")
    except (OSError,ValueError,TimeoutError):
        return ""

def parse_price_page(text,source_url):
    if not text or "<table" not in text.lower():return None
    p=MarketParser()
    p.feed(text)
    title=p.title
    row=convert(p.rows)
    odds,prob,fair=row
    # Older public match-page layouts use "Alt / Üst 2.5"
    for section,cells in p.rows:
        m=re.search(r"(1[,.]5|2[,.]5|3[,.]5)\s*$",section)
        if m and ("alt" in norm(section)) and ("ust" in norm(section)):
            side=norm(cells[0]) if cells else ""
            key=m.group(1).replace(".",",")+" "+("Üst" if side=="ust" else "Alt" if side=="alt" else "")
            if side in ("alt","ust") and len(cells)>1:
                try:
                    val=float(cells[1].replace(",","."))
                    if 1.01<val<100:odds[key]=val
                except (ValueError,TypeError):pass
    if not {"1","X","2"}.issubset(odds):return None
    title=re.sub(r"\s+(?:İddaa\s+)?Oranlar[ıi].*","",title,flags=re.I)
    title=re.sub(r"\s+İddaa.*","",title,flags=re.I)
    title=re.sub(r"\s+Maçı.*","",title,flags=re.I)
    bits=re.split(r"\s+[—–-]\s+",title,maxsplit=1)
    if len(bits)!=2:return None
    return {"home":bits[0],"away":bits[1],"odds":odds,"fair_probabilities":prob,
            "source_url":source_url,"kind":"public dated match-price archive"}

def match_name(actual,site):
    a=norm(actual);b=norm(site)
    if a==b:return True
    if a in b or b in a:return min(len(a),len(b))>=5
    aw=set(a.split());bw=set(b.split())
    return (len(aw&bw)>=2 and len(aw&bw)>=min(len(aw),len(bw))*.66)

def archive_day(day,rows):
    index_text=fetch_url(SITE+"/bulten/"+day)
    daylinks=find_match_urls(index_text,day)
    records=[]
    for m in rows:
        suffix="-"+day
        root=SITE+"/mac/"+slug(m["home"])+"-"+slug(m["away"])+suffix
        candidates=[x for x in daylinks if slug(m["home"]) in x and slug(m["away"]) in x]
        if root not in candidates:candidates.append(root)
        records.append((m,candidates[:2]))
    return records

def collect_archive(matches,window_start,window_end):
    subset=[m for m in matches if window_start<=m["date"]<=window_end]
    grouped=defaultdict(list)
    for m in subset:grouped[m["date"]].append(m)
    tasks=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(archive_day,date,rows):date for date,rows in grouped.items()}
        for f in concurrent.futures.as_completed(futures):
            try:tasks.extend(f.result())
            except Exception as e:print("index issue:",futures[f],str(e)[:90],flush=True)
    total=len(tasks)
    found=0;covered=defaultdict(int);failed=0;data=[]
    def process(task):
        m,urls=task
        for url in urls:
            body=fetch_url(url)
            rec=parse_price_page(body,url)
            if rec and match_name(m["home"],rec["home"]) and match_name(m["away"],rec["away"]):
                return m,rec
        return m,None
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(process,x) for x in tasks]
        for idx,f in enumerate(concurrent.futures.as_completed(futures),1):
            try:
                m,p=f.result()
                if p:
                    for k,v in p["odds"].items():
                        if 1.03<=v<=4.5:m["odds"][k]=v
                    m["archived_fair_probabilities"]=p["fair_probabilities"]
                    m["archived_source_url"]=p["source_url"]
                    found+=1
                    covered[m["date"]]+=1
                    data.append({"date":m["date"],"home":m["home"],"away":m["away"],
                                 "archived_url":p["source_url"],"markets":list(p["odds"])})
            except Exception as exc:
                failed+=1
            if idx%80==0:print("archived quoted match pages",idx,"/",total,
                               "verified matches",found,flush=True)
    return {"attempted":total,"found":found,"failed_requests":failed,
            "market_days":len(covered),"days_coverage":dict(covered),
            "matches":data}

def run():
    days=100
    ending=dt.datetime.now(dt.timezone.utc).date()-dt.timedelta(days=1)
    beginning=ending-dt.timedelta(days=days-1)
    historic=[];current=[];errors=[];sources={}
    for season,book in [("2526",historic),("2627",current)]:
        for league,div in LEAGUES.items():
            url=BASE.format(season=season,division=div)
            try:
                records=parse(fetch(url),league,season)
                if not records:raise ValueError("no scored matches")
                book.extend(records)
                sources[f"{league} {season}"]={"url":url,"matches":len(records)}
            except Exception as e:
                errors.append({"league":league,"season":season,"error":str(e)[:180]})
    current=[m for m in current if m["date"]<=ending.isoformat()]
    print("Scored current season",len(current),"previous",len(historic),flush=True)
    archive=collect_archive(current,beginning.isoformat(),ending.isoformat())
    print("Verified additional historical market prices",archive["found"],
          "from",archive["market_days"],"days",flush=True)
    payload={
        "window_start":beginning.isoformat(),"window_end":ending.isoformat(),
        "window_calendar_days":days,"last_season":historic,"current":current,
        "sources":sources,"fetch_errors":errors,
        "real_archived_market_coverage":archive
    }
    tmp=ROOT/"docs/data/_daily100_current_input.tmp.json"
    tmp.write_text(json.dumps(payload,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
    import subprocess
    try:
        subprocess.run(["node","scripts/backtest_current100.cjs",str(tmp),str(OUT)],
                       cwd=str(ROOT),check=True,timeout=1200)
    finally:
        if tmp.exists():tmp.unlink()
    print("FULL CURRENT MODEL 100-DAY REPORT",str(OUT),flush=True)

if __name__=="__main__":run()
