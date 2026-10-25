#!/usr/bin/env python3
"""Build FUTSIM 2026/27 public snapshot from public-domain football.db records.
Supplement shots/corners/fixtures ONLY when open-matchday non-commercial source
makes them available, with visible attribution. Missing xG/xA/injuries stay null.
"""
import collections, csv, datetime as dt, io, json, math, pathlib, re, unicodedata
from validate_walkforward import SOURCES, CORNER_SOURCES, BASE, fetch, parse_openfootball, normalized, teamstats
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'docs'/'data'
PRIOR={'Premier League':1580,'Bundesliga':1550,'La Liga':1550,'Serie A':1530,'Ligue 1':1515,'Eredivisie':1480,'Süper Lig':1440}
def avg(vals):
    vals=[x for x in vals if isinstance(x,(int,float)) and math.isfinite(x)]
    return round(sum(vals)/len(vals),3) if vals else None
def stat_matches(team, rows):
    ms=sorted((m for m in rows if team in (m['home'],m['away'])),key=lambda x:x['date'],reverse=True)[:15]
    home=[x for x in ms if x['home']==team];away=[x for x in ms if x['away']==team]
    def compile(part):
        goals=[];conceded=[];pts=[];form=[]
        for m in part:
            h=m['home']==team;gf=m['hg'] if h else m['ag'];ga=m['ag'] if h else m['hg']
            goals.append(gf);conceded.append(ga);pts.append(3 if gf>ga else 1 if gf==ga else 0)
            if len(form)<6:form.append({'date':m['date'],'opponent':m['away_label'] if h else m['home_label'],'gf':gf,'ga':ga,'h':h})
        return {'matches':len(part),'gf':avg(goals),'ga':avg(conceded),'raw_gf':avg(goals),
                'raw_ga':avg(conceded),'points':avg(pts),'form':form}
    base=compile(ms)
    base['home']=compile(home);base['away']=compile(away)
    base['score_patterns']={'n':len(ms),'ht_n':0}
    base['ucl_patterns']={'n':0,'ht_n':0}
    return base
def load_catalogue():
    original={}
    try:
        h=(ROOT/'docs'/'index.html').read_text(encoding='utf-8')
        m=re.search(r'window\.FUTSIM_SEED\s*=\s*(\{.*?\})\s*;',h,re.S)
        if m:
            for t in json.loads(m.group(1)).get('teams',[]):
                key=normalized(t['name'])
                original[key]=dict(t)
    except (ValueError,OSError) as e:print('No template seed:',e)
    try:
        snap=json.loads((DATA/'snapshot.json').read_text(encoding='utf-8'))
        for t in snap.get('teams',[]):
            key=normalized(t['name'])
            if key not in original:original[key]=dict(t)
    except (ValueError,OSError):pass
    return original
def from_matchday(today):
    rows=collections.defaultdict(list);fixtures=[];errors=[];coverage={}
    for league,folder in CORNER_SOURCES.items():
        root=f'{BASE}oladeeayo/open-matchday/master/data/{folder}/'
        try:
            source=fetch(root+'results_2627.csv')
            matches=list(csv.DictReader(io.StringIO(source)))
        except Exception as ex:
            errors.append(f'{league}: results {str(ex)[:80]}');continue
        for m in matches:
            date=(m.get('date') or '')[:10]
            if not date or date>=today:continue
            def n(field):
                try:return int(m.get(field) or '')
                except (TypeError,ValueError):return None
            h=normalized(m.get('home') or '');a=normalized(m.get('away') or '')
            if not h or not a:continue
            row={'date':date,'home':h,'away':a,'hg':n('ft_home'),'ag':n('ft_away'),'hc':n('home_corners'),'ac':n('away_corners'),
                'hs':n('home_shots'),'as':n('away_shots'),'hst':n('home_target'),'ast':n('away_target'),
                'hc1':n('home_corners_1h'),'ac1':n('away_corners_1h'),
                'home_label':m.get('home'),'away_label':m.get('away')}
            rows[league].append(row)
        coverage[league]={'matchday_results':len(rows[league]),
                          'with_corners':sum(x['hc'] is not None and x['ac'] is not None for x in rows[league])}
        try:
            items=list(csv.DictReader(io.StringIO(fetch(root+'fixtures_2627.csv'))))
            for m in items:
                day=(m.get('date') or '')[:10]
                if not today<=day<=(dt.date.fromisoformat(today)+dt.timedelta(days=8)).isoformat():continue
                home=normalized(m.get('home') or '');away=normalized(m.get('away') or '')
                if home and away:fixtures.append({'date':day,'time':(m.get('time') or '')[:8],'league':league,
                                                    'home':home,'away':away})
        except Exception as ex:errors.append(f'{league}: fixtures {str(ex)[:80]}')
    return rows,fixtures,errors,coverage
def enrichment(team,league,matches):
    # Exact normalized club joins ONLY. No approximate xG, injuries or made-up corner samples.
    rows=sorted((m for m in matches if team in (m['home'],m['away'])),key=lambda r:r['date'],reverse=True)[:12]
    def val(x,key_home,key_away):
        return x[key_home] if x['home']==team else x[key_away]
    def v(key_home,key_away):return [val(x,key_home,key_away) for x in rows]
    cs=v('hc','ac');ca=v('ac','hc')
    hs=v('hs','as');st=v('hst','ast')
    nc=sum(a is not None for a in cs)
    return {'shots':avg(hs),'sot':avg(st),'corners':avg(cs),'corners_against':avg(ca),
            'corners_1h':avg(v('hc1','ac1')),
            'corner_matches':nc,'shot_matches':sum(z is not None for z in hs),
            'xg':None,'xa':None,
            'advanced_source_url':'https://github.com/oladeeayo/open-matchday' if rows else None}
def run():
    today=dt.datetime.now(dt.timezone.utc).date().isoformat()
    base=load_catalogue()
    current=[];previous=[];errors=[]
    leagues=set()
    for league,(repo,template) in SOURCES.items():
        for season,target in [('2026-27',current),('2025-26',previous)]:
            url=f'{BASE}{repo}/master/{template.format(s=season)}'
            try:
                arr=parse_openfootball(fetch(url),league,season)
                if not arr:raise RuntimeError('No completed fixtures parsed')
                target.extend(m for m in arr if m['date']<today);leagues.add(league)
            except Exception as e:errors.append(f'{league}/{season}: {str(e)[:95]}')
    if len(current)<100:raise RuntimeError(f'Current-season openfootball data unavailable ({len(current)}); preserving last snapshot')
    matchday,fixtures,source_errors,shot_coverage=from_matchday(today)
    errors.extend(source_errors)
    # Extend public-domain historical results with more recent fully scored
    # matches from the attributed NON-COMMERCIAL compilation; do not duplicate.
    # Choose one current-season score provider for each league to avoid
    # duplicated games from different club name conventions.
    current_by_league=collections.defaultdict(list)
    for m in current:current_by_league[m['league']].append(m)
    extra_count=0
    for lg,rows in matchday.items():
        scored=[{**m,'league':lg} for m in rows if m.get('hg') is not None and m.get('ag') is not None
                and m['hg']>=0 and m['ag']>=0]
        if len(scored)>=10:
            current_by_league[lg]=scored
            extra_count+=len(scored)
    current=[m for rows in current_by_league.values() for m in rows]
    teams=[];seen=set();matches_per_league=collections.defaultdict(int)
    roster=collections.defaultdict(set)
    for m in current:
        roster[m['home']].add(m['league']);roster[m['away']].add(m['league'])
        matches_per_league[m['league']]+=1
    for key,ls in sorted(roster.items()):
        domestic=sorted(ls)[0]
        old=base.get(key,{})
        stats=stat_matches(key,[m for m in current if m['league']==domestic])
        prev=stat_matches(key,[m for m in previous if m['league']==domestic])
        if prev['matches']:stats['last_season']=prev
        extras=enrichment(key,domestic,matchday[domestic]);stats.update(extras)
        # Current result-derived rating with conservative prior.
        n=stats['matches'];p=stats['points'] if stats['points'] is not None else 1.3
        strength=max(-140,min(140,(p-1.3)*65+(stats['gf']-stats['ga'])*37))
        rating=round(PRIOR[domestic]+strength*min(n/12,1))
        label=old.get('name') or next((m['home_label'] if m['home']==key else m['away_label']
             for m in current if key in (m['home'],m['away'])) ,key)
        if not isinstance(label,str):label=key
        item={'id':old.get('id',key),'name':label,'league':domestic,'rating':rating,'stats':stats,
              'source':'openfootball public domain results; open-matchday supplemental stats (noncommercial)',
              'competitions':list(dict.fromkeys([domestic]+old.get('competitions',[]))),
              'data_verified':True,'injuries':None,'xa':None,'xg':None}
        teams.append(item);seen.add(key)
    for key,old in base.items():
        if key in seen:continue
        # Active domestic clubs all come from this season's verified roster;
        # obsolete/renamed catalogue entries should not appear as duplicates.
        if old.get('league') in SOURCES and 'Şampiyonlar Ligi' not in old.get('competitions',[]):continue
        t=dict(old)
        t['stats']={'matches':0,'form':[],'score_patterns':{'n':0,'ht_n':0},'ucl_patterns':{'n':0,'ht_n':0}}
        t['given']={'played':0,'gf':0,'ga':0}
        t['rating']=PRIOR.get(t.get('league'),1480)
        t['source']='Katalog takımı; bu sezonun maç sonucu doğrulanmadı'
        t['data_verified']=False;t['injuries']=None;t['xa']=None;t['xg']=None
        teams.append(t)
    ident={normalized(x['name']):x['id'] for x in teams}
    upcoming=[]
    for row in fixtures:
        hid=ident.get(row['home']);aid=ident.get(row['away'])
        if hid and aid and hid!=aid:upcoming.append({**row,'hid':hid,'aid':aid})
    coverage={lg:{'finished_matches':matches_per_league[lg],
                   **shot_coverage.get(lg,{})} for lg in SOURCES}
    val={}
    try:val=json.loads((DATA/'model_validation.json').read_text(encoding='utf-8'))
    except (ValueError,OSError):pass
    snapshot={'version':6,'asof':today,'updated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'seed':False,
       'season':'2026/27','source':'openfootball CC0 + open-matchday non-commercial attribution',
       'source_url':'https://github.com/openfootball',
       'shot_source_url':'https://github.com/oladeeayo/open-matchday',
       'teams':teams,'upcoming':upcoming,'news':[],'backtest':{
          'n':val.get('iterations',0),'status':'walk-forward' if val.get('iterations',0)>=100 else 'unvalidated',
          'holdout_brier':val.get('model_metrics',{}).get('brier'),
          'baseline_brier':val.get('baseline',{}).get('brier')},
       'coverage':coverage,'recent_verified_matches_added':extra_count,'data_health':{'finished_matches_count':len(current),
          'errors':errors},'source_errors':errors,'xg_coverage':'unavailable',
       'xa_coverage':'unavailable','injury_coverage':'unavailable'}
    DATA.mkdir(exist_ok=True,parents=True)
    (DATA/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'teams':len(teams),'results':len(current),'fixture_count':len(upcoming),'leagues':len(leagues),
      'corners':sum(s['stats'].get('corner_matches',0) for s in teams),'errors':len(errors)},ensure_ascii=False))
if __name__=='__main__':run()
