#!/usr/bin/env python3
"""FUTSIM public match-data refresh; keyless, source-stamped, no invented lineups/xG."""
import csv, datetime as dt, io, json, pathlib, re, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'docs'/'data'
CODES={'Premier League':'E0','Bundesliga':'D1','La Liga':'SP1','Championship':'E1','Serie A':'I1','Ligue 1':'F1','Eredivisie':'N1','Primeira Liga':'P1'}
PRIOR={'Premier League':1580,'Bundesliga':1550,'La Liga':1550,'Championship':1450,'Serie A':1530,'Ligue 1':1515,'Eredivisie':1480,'Primeira Liga':1475,'Süper Lig':1440}
def read_csv(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 FUTSIM data research'})
    with urllib.request.urlopen(req,timeout=24) as res:
        return list(csv.DictReader(io.StringIO(res.read(2_000_000).decode('utf-8-sig','replace'))))
def number(s):
    try:return int(float(s))
    except (TypeError,ValueError):return None
def parse_date(s):
    for fmt in ('%d/%m/%Y','%d/%m/%y','%Y-%m-%d'):
        try:return dt.datetime.strptime(s,fmt).date()
        except (TypeError,ValueError):continue
    return None
def load(league,code,season):
    url=f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv'
    rows=read_csv(url)
    matches=[]
    for r in rows:
        day=parse_date(r.get('Date',''))
        h=(r.get('HomeTeam') or '').strip();a=(r.get('AwayTeam') or '').strip()
        hg=number(r.get('FTHG'));ag=number(r.get('FTAG'))
        if day and h and a and hg is not None and ag is not None and day<dt.datetime.now(dt.timezone.utc).date():
            matches.append(dict(league=league,date=day.isoformat(),home=h,away=a,hg=hg,ag=ag))
    return matches
def aggregate(team,ms):
    subset=sorted((m for m in ms if team in (m['home'],m['away'])),key=lambda x:x['date'],reverse=True)[:15]
    n=len(subset)
    if not n:return dict(matches=0,gf=None,ga=None,raw_gf=None,raw_ga=None,form=[])
    goals=[];conceded=[];pts=0;form=[]
    for m in subset:
        is_home=m['home']==team;gf=m['hg'] if is_home else m['ag'];ga=m['ag'] if is_home else m['hg']
        goals.append(gf);conceded.append(ga);pts+=3 if gf>ga else 1 if gf==ga else 0
        if len(form)<6:form.append(dict(date=m['date'],opponent=m['away'] if is_home else m['home'],gf=gf,ga=ga,h=is_home))
    return dict(matches=n,gf=round(sum(goals)/n,3),ga=round(sum(conceded)/n,3),raw_gf=round(sum(goals)/n,3),raw_ga=round(sum(conceded)/n,3),points=round(pts/n,2),form=form)
def run():
    today=dt.datetime.now(dt.timezone.utc)
    matches=[];prev=[];errors=[]
    for lg,code in CODES.items():
        for season,store in (('2627',matches),('2526',prev)):
            try: store.extend(load(lg,code,season))
            except Exception as ex:errors.append(f'{lg} {season}: {str(ex)[:100]}')
    # Preserve existing records if every upstream site is unavailable.
    if not matches:
        raise RuntimeError('No current-season verified match records; last published data preserved. '+'; '.join(errors))
    catalogue={}
    try:
        s=(ROOT/'docs'/'data'/'snapshot.json').read_text(encoding='utf-8')
        prev_state=json.loads(s)
        for t in prev_state.get('teams',[]):catalogue[t['name'].casefold()]=dict(t)
    except (ValueError,OSError):pass
    membership={}
    for m in matches:
        for t in (m['home'],m['away']):membership[t]=m['league']
    for t,league in membership.items():
        st=aggregate(t,matches);old=aggregate(t,prev)
        if old['matches']>=5:st['last_season']=old
        st['home']=aggregate(t,[m for m in matches if m['home']==t])
        st['away']=aggregate(t,[m for m in matches if m['away']==t])
        st['score_patterns']={'n':st['matches'],'ht_n':0}
        st['ucl_patterns']={'n':0,'ht_n':0}
        ident=re.sub(r'[^a-z0-9]+','-',t.lower()).strip('-')
        item=catalogue.get(t.casefold(),{})
        # League-level prior, adjusted by actual points/goals versus the team's peers.
        # Reject stale, manually assigned club-level strength once match data exists.
        prior=PRIOR.get(league,1480)
        evidence=min(st['matches'],15)/15
        last_n=old['matches']
        season_points=(st.get('points') or 1.3)
        goal_diff=(st.get('gf') or 1.37)-(st.get('ga') or 1.37)
        last_effect=(last_n/15)*((old.get('points') or 1.3)-1.3)*42 if last_n else 0
        current_effect=(season_points-1.3)*65+goal_diff*45
        rating=round(prior+max(-180,min(180,evidence*current_effect+min(.55,max(0,1-evidence))*last_effect)))
        item.update(id=item.get('id',ident),name=t,league=league,stats=st,
                    rating=rating,source='football-data.co.uk, score data',
                    competitions=list(dict.fromkeys([league]+[x for x in item.get('competitions',[]) if x!=league])))
        catalogue[t.casefold()]=item
    # A match score is not evidence of player-level injury, xG, assists or lineups.
    asof=today.date().isoformat()
    coverage={lg:{'finished_matches':sum(m['league']==lg for m in matches),'teams':len({v for m in matches if m['league']==lg for v in (m['home'],m['away'])})} for lg in CODES}
    out=dict(version=4,updated_at_utc=today.isoformat(),asof=asof,season='2026/27',seed=False,
             source='football-data.co.uk (public historical results, coverage varies)',source_url='https://www.football-data.co.uk/',
             teams=list(catalogue.values()),upcoming=[],news=[],coverage=coverage,backtest={'n':0,'status':'not validated'},
             data_health={'finished_matches_count':len(matches),'errors':errors},source_errors=errors)
    DATA.mkdir(parents=True,exist_ok=True)
    (DATA/'snapshot.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'Updated {len(matches)} verified results from {len(coverage)} leagues; {len(errors)} source errors')
if __name__=='__main__':run()
