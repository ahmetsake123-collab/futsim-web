#!/usr/bin/env python3
"""Optional, no-key FPL player expected goals and expected assists.

Use the public read-only Fantasy Premier League JSON endpoint. Check robots,
avoid evasion and limit to one request per scheduled job. May be unavailable
if permissions change. FPL expected_goals & expected_assists are season totals.
"""
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.request
import urllib.robotparser

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/data/fpl_xg.json'
URL='https://fantasy.premierleague.com/api/bootstrap-static/'
ROBOTS='https://fantasy.premierleague.com/robots.txt'
AGENT='FUTSIMResearch/1.0'
def flt(v):
    try:
        n=float(v)
        if 0<=n<1000:return round(n,3)
    except (ValueError,TypeError):pass
    return None
def run():
    now=dt.datetime.now(dt.timezone.utc)
    base={'asof':now.date().isoformat(),'source':'Fantasy Premier League',
          'source_url':URL,'teams':[],'players':[],'status':'not_accessible'}
    parser=urllib.robotparser.RobotFileParser()
    parser.set_url(ROBOTS)
    try:
        parser.read()
        if not parser.can_fetch(AGENT,URL):
            base['reason']='robots policy disallows the public API for this client'
            raise PermissionError('robots access denied')
        req=urllib.request.Request(URL,headers={'User-Agent':AGENT,'Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=20) as response:
            obj=json.load(response)
        team_map={t['id']:t['name'] for t in obj.get('teams',[])
            if isinstance(t.get('id'),int) and t.get('name')}
        if len(team_map)<15:raise ValueError('unexpected team coverage')
        grouped={}
        for p in obj.get('elements',[]):
            club=team_map.get(p.get('team'))
            if not club:continue
            g=flt(p.get('expected_goals'));a=flt(p.get('expected_assists'))
            mins=p.get('minutes')
            if not isinstance(mins,(int,float)) or g is None or a is None:continue
            item={'team':club,'name':str(p.get('first_name','')+' '+p.get('second_name','')).strip()[:85],
                  'xg':g,'xa':a,'minutes':int(mins),'goals':int(p.get('goals_scored') or 0),
                  'assists':int(p.get('assists') or 0),
                  'availability_status':str(p.get('status',''))[:12],
                  'availability_news':str(p.get('news',''))[:150],
                  'season':'2026/27'}
            if item['minutes']>=60:base['players'].append(item)
            grouped.setdefault(club,[]).append(item)
        for club,players in grouped.items():
            base['teams'].append({'team':club,'league':'Premier League','matches':None,
              'xg_season':round(sum(x['xg'] for x in players),3),
              'xa_season':round(sum(x['xa'] for x in players),3),
              'source':URL})
        if len(base['players'])<100:raise ValueError('missing player coverage')
        base['status']='verified'
    except (PermissionError,urllib.error.URLError,TimeoutError,ValueError,OSError) as e:
        base['reason']=str(e)[:130] if not isinstance(e,urllib.error.URLError) else type(e).__name__
        if OUT.exists():
            try:
                old=json.loads(OUT.read_text(encoding='utf-8'))
                if old.get('status')=='verified' and (now.date()-dt.date.fromisoformat(old['asof'])).days<=3:
                    print('FPL: retaining recent verified data because upstream failed')
                    return
            except (OSError,ValueError,KeyError):pass
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(base,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FPL xG/xA source:',base['status'],len(base['teams']),'teams',len(base['players']),'players')
if __name__=='__main__':run()
