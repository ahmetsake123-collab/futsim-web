#!/usr/bin/env python3
"""No-key FPL *team aggregate* expected goals and expected assists.

Use public read-only Fantasy Premier League JSON. Aggregate team xG/xA from
individual player season totals internally; no player performance stored or
published. Inspect robots; no evasion. FPL data may change without notice.
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
          'source_url':URL,'teams':[],'players':[],'status':'not_accessible',
          'method':'Sum of FPL player season xG and xA, shown ONLY as team totals. Different providers may define xA differently.'}
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
        checked_player_count=0
        for p in obj.get('elements',[]):
            club=team_map.get(p.get('team'))
            if not club:continue
            g=flt(p.get('expected_goals'));a=flt(p.get('expected_assists'))
            mins=p.get('minutes')
            if not isinstance(mins,(int,float)) or g is None or a is None:continue
            # Only the team aggregates will leave this process. All players
            # with valid season metrics count (including brief substitutes).
            grouped.setdefault(club,[]).append((g,a))
            checked_player_count+=1
        # Prefer same-provider completed fixtures to derive per-match rates.
        # Never divide by stale or differently sourced match counts.
        completed={}
        fixture_url='https://fantasy.premierleague.com/api/fixtures/'
        if parser.can_fetch(AGENT,fixture_url):
            try:
                request=urllib.request.Request(fixture_url,headers={'User-Agent':AGENT,'Accept':'application/json'})
                with urllib.request.urlopen(request,timeout=20) as response:
                    matches=json.load(response)
                for game in matches:
                    if game.get('finished') is not True:continue
                    day=str(game.get('kickoff_time') or '')[:10]
                    if not day or day>now.date().isoformat():continue
                    for f_id in (game.get('team_h'),game.get('team_a')):
                        club=team_map.get(f_id)
                        if club:completed[club]=completed.get(club,0)+1
            except (urllib.error.URLError,TimeoutError,ValueError,OSError):
                pass
        for club,values in grouped.items():
            n=completed.get(club)
            g=round(sum(xg for xg,xa in values),3)
            a=round(sum(xa for xg,xa in values),3)
            base['teams'].append({'team':club,'league':'Premier League','matches':n,
              'xg_season':g,'xa_season':a,
              'xg_per_match':round(g/n,3) if n and n>=3 else None,
              'xa_per_match':round(a/n,3) if n and n>=3 else None,
              'source':URL,'metric_scope':'2026/27 season team sum; match rates require FPL finished fixtures'})
        base['sampled_player_count']=checked_player_count
        if checked_player_count<100 or len(base['teams'])!=20:raise ValueError('missing Premier League coverage')
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
    print('FPL team xG/xA source:',base['status'],len(base['teams']),'teams',base.get('sampled_player_count',0),'player rows used only internally')
if __name__=='__main__':run()
