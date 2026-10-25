#!/usr/bin/env python3
"""Optional Understat xG/xA data for five supported leagues.

No login bypass, browser spoofing, proxies or anti-bot circumvention.
Check robots.txt and source status. Respect disallow; don't confuse
season aggregates with pre-match forecasts. Do not invent player metrics.
"""
import datetime as dt
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'data'/'xg_source.json'
ROOT_URL='https://understat.com'
AGENT='FUTSIMResearch/1.0'
LEAGUES={'Premier League':'EPL','La Liga':'La_liga','Bundesliga':'Bundesliga',
         'Serie A':'Serie_A','Ligue 1':'Ligue_1'}
def fetch(url,limit=2500000):
    req=urllib.request.Request(url,headers={'User-Agent':AGENT,'Accept':'application/json,text/html'})
    with urllib.request.urlopen(req,timeout=16) as r:
        return r.read(limit).decode('utf-8','replace')
def is_allowed(url):
    # A failed robots retrieval isn't a green light to crawl.
    rp=urllib.robotparser.RobotFileParser()
    rp.set_url(ROOT_URL+'/robots.txt')
    try:rp.read()
    except Exception:return False,'robots.txt not accessible'
    return bool(rp.can_fetch(AGENT,url)), 'robots policy'
def safe_num(v):
    try:
        x=float(v);return round(x,3) if 0<=x<4000 else None
    except (ValueError,TypeError):return None
def prepare_data(obj,league,today):
    teams=obj.get('teams') if isinstance(obj,dict) else None
    players=obj.get('players') if isinstance(obj,dict) else None
    if not teams or not isinstance(players,list):
        raise ValueError('provider returned no teams/players arrays')
    result=[];team_map={}
    for raw in teams.values() if isinstance(teams,dict) else teams:
        name=raw.get('title') or ''
        history=raw.get('history') or []
        valid=[m for m in history if isinstance(m,dict)
               and str(m.get('date',''))[:10]<today
               and m.get('xG') is not None and m.get('xGA') is not None]
        if len(valid)<3:continue
        xgs=[safe_num(m.get('xG')) for m in valid];xgas=[safe_num(m.get('xGA')) for m in valid]
        if any(x is None for x in xgs+xgas):continue
        tid=raw.get('id')
        record={'league':league,'team':name,'team_id':tid,'matches':len(valid),
                'xg_per_match':round(sum(xgs)/len(valid),3),
                'xga_per_match':round(sum(xgas)/len(valid),3),
                'source':'Understat','source_url':f'https://understat.com/league/{LEAGUES[league]}/2026',
                'scope':'Current season games completed before asof date'}
        result.append(record);team_map[name.lower()]=record
    records=[]
    for p in players:
        if not isinstance(p,dict):continue
        club=str(p.get('team_title') or '').split(',')[0].strip()
        if club.lower() not in team_map:continue
        minutes=safe_num(p.get('time'));xg=safe_num(p.get('xG'));xa=safe_num(p.get('xA'))
        if minutes is None or xg is None or xa is None or minutes<60:continue
        records.append({'league':league,'team':club,'name':str(p.get('player_name') or '')[:90],
                        'minutes':int(minutes),'games':int(p.get('games') or 0),
                        'goals':int(p.get('goals') or 0),
                        'xg':xg,'xa':xa,
                        'xg90':round(xg*90/minutes,3),'xa90':round(xa*90/minutes,3)})
    records.sort(key=lambda v:(v['league'],v['team'],-v['xg']))
    return result,records
def run():
    date=dt.datetime.now(dt.timezone.utc).date().isoformat()
    results=[];players=[];coverage={}
    for league,slug in LEAGUES.items():
        url=f'{ROOT_URL}/getLeagueData/{slug}/2026'
        allowed,why=is_allowed(url)
        if not allowed:
            coverage[league]={'status':'not_accessible','reason':why}
            continue
        try:
            obj=json.loads(fetch(url))
            t,p=prepare_data(obj,league,date)
            results.extend(t);players.extend(p)
            coverage[league]={'status':'verified' if t else 'empty','team_count':len(t),'player_count':len(p)}
        except (ValueError,urllib.error.URLError,TimeoutError) as exc:
            coverage[league]={'status':'unavailable','reason':type(exc).__name__}
    # Don't replace previous fresh validated readings with a failed run.
    if not results and OUT.exists():
        try:
            prev=json.loads(OUT.read_text(encoding='utf-8'))
            if prev.get('teams') and prev.get('asof') and (dt.date.fromisoformat(date)-dt.date.fromisoformat(prev['asof'])).days<=3:
                print('Understat unavailable; retained valid recent data')
                return
        except (OSError,ValueError,KeyError):pass
    OUT.parent.mkdir(exist_ok=True,parents=True)
    OUT.write_text(json.dumps({'asof':date,'source':'https://understat.com/','method':'published observed shot-quality model; not FUTSIM xG estimates',
      'teams':results,'players':players,'coverage':coverage,'verified':bool(results)},ensure_ascii=False,indent=2),encoding='utf-8')
    print('FUTSIM xG provider:',json.dumps({k:v['status'] for k,v in coverage.items()}),'teams',len(results),'players',len(players))
if __name__=='__main__':run()
