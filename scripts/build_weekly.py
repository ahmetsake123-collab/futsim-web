#!/usr/bin/env python3
"""Materialize one weekly offline snapshot of ALL clubs and their last-five form.
Distinguish published xG from shot-based proxy. Never label proxy measured xG.
No network requests; join only known canonical club names and existing sources.
"""
import datetime as dt,json,pathlib,re,unicodedata,collections
ROOT=pathlib.Path(__file__).resolve().parents[1]
FOLDER=ROOT/'docs/data'
def load(name):
    try:return json.loads((FOLDER/name).read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError):return {}
def norm(v):
    v=unicodedata.normalize('NFKD',str(v).casefold())
    v=''.join(x for x in v if not unicodedata.combining(x)).replace('ı','i')
    v=re.sub(r'[^a-z0-9]+',' ',v)
    v=re.sub(r'\b(fc|afc|sc|cf|fk|sk|ac|ssc)\b',' ',v)
    v=re.sub(r'\s+',' ',v).strip()
    aliases={'spurs':'tottenham hotspur','tottenham':'tottenham hotspur',
    'brighton':'brighton hove albion','nott m forest':'nottingham forest',
    'bayern munchen':'bayern munich','psv':'psv eindhoven','psg':'paris saint germain',
    'inter milan':'inter','internazionale':'inter','man city':'manchester city',
    'man utd':'manchester united','besiktas':'besiktas','galatasaray':'galatasaray',
    'newcastle':'newcastle united','leeds':'leeds united','coventry':'coventry city',
    'ipswich':'ipswich town','brighton':'brighton hove albion'}
    return aliases.get(v,v)
def n(v):
    try:
        a=float(v)
        return a if a>=0 and a<100 else None
    except (TypeError,ValueError):return None
def main():
    now=dt.datetime.now(dt.timezone.utc)
    snap=load('snapshot.json')
    if not snap.get('teams'):raise RuntimeError('Current published club snapshot missing')
    published=[]
    for srcfile in ('hf_xg.json','striker_xg.json','xg_source.json','fpl_xg.json'):
        src=load(srcfile)
        if not src.get('teams') or src.get('status') not in ('verified',None) or src.get('verified') is False:continue
        try:
            age=(now.date()-dt.date.fromisoformat(src['asof'])).days
            if age<0 or age>8:continue
        except (TypeError,ValueError,KeyError):continue
        for t in src['teams']:
            if 'league' not in t:continue
            published.append((src,t))
    known={(t['league'],norm(t['team'])):(s,t) for s,t in published}
    result=[];real_xg=real_xa=proxy=0
    for t in snap['teams']:
        st=t.get('stats') or {}
        gp=st.get('matches') or 0
        first5=(st.get('form') or [])[:5]
        home5=(st.get('home') or {}).get('form') or []
        home5=home5[:5]
        forms=lambda x:''.join('W' if (m.get('gf') or 0)>(m.get('ga') or 0) else
                               'D' if m.get('gf')==m.get('ga') else 'L' for m in x)
        row={'id':t['id'],'name':t['name'],'league':t['league'],
             'matches':gp,'gf_per_match':st.get('gf'),'ga_per_match':st.get('ga'),
             'shots_per_match':st.get('shots'),'sot_per_match':st.get('sot'),
             'corners_per_match':st.get('corners'),'corners_against_per_match':st.get('corners_against'),
             'form_last5':forms(first5),'last5_count':len(first5),
             'last5_wins':sum((m.get('gf') or 0)>(m.get('ga') or 0) for m in first5),
             'last5_draws':sum(m.get('gf')==m.get('ga') for m in first5),
             'last5_losses':sum((m.get('gf') or 0)<(m.get('ga') or 0) for m in first5),
             'last5_scores':[{'date':x.get('date'),'opponent':x.get('opponent'),
                             'gf':x.get('gf'),'ga':x.get('ga')} for x in first5],
             'home_last5_wins':sum((m.get('gf') or 0)>(m.get('ga') or 0) for m in home5),
             'home_last5_count':len(home5),'home_form_last5':forms(home5),
             'xg_per_match':None,'xa_per_match':None,'xga_per_match':None,
             'xg_proxy_per_match':None,
             'xg_data_kind':'unavailable','xg_source':None,'xg_source_asof':None}
        # A genuine published shot-based measurement is not the same as a goal proxy.
        entry=known.get((t['league'],norm(t['name'])))
        if entry:
            source,raw=entry
            count=raw.get('matches') or 0
            g=n(raw.get('xg_per_match'))
            if g is None and count>=3 and n(raw.get('xg_season')) is not None:g=n(raw['xg_season'])/count
            xa=n(raw.get('xa_per_match'))
            if xa is None and count>=3 and n(raw.get('xa_season')) is not None:xa=n(raw['xa_season'])/count
            ga=n(raw.get('xga_per_match'))
            if g is not None:
                row.update(xg_per_match=round(g,3),xga_per_match=round(ga,3) if ga is not None else None,
                           xg_data_kind='published',xg_source=source.get('source_url') or source.get('source'),
                           xg_source_asof=source.get('asof'))
                real_xg+=1
            if xa is not None:row['xa_per_match']=round(xa,3);real_xa+=1
        shots=n(st.get('shots'));sot=n(st.get('sot'))
        # CALIBRATION NEEDED: this is NOT expected goals; it only provides
        # an offline attack signal for clubs with no legal xG feed.
        if shots is not None and sot is not None and 0<=sot<=shots and gp>=3:
            # Distinct "shot volume / accuracy proxy" scale, no xG claim.
            row['xg_proxy_per_match']=round(0.045*max(0,shots-sot)+0.22*sot,3)
            proxy+=1
        result.append(row)
    payload={'version':1,'generated_at_utc':now.isoformat(),'week_start_utc':(now.date()-dt.timedelta(days=now.weekday())).isoformat(),
             'period':'weekly snapshot; no browsing from website on user selection',
             'teams':result,'coverage':{'clubs':len(result),'published_team_xg':real_xg,'published_team_xa':real_xa,
              'shot_volume_proxies_not_xg':proxy},
             'sources':['docs/data/snapshot.json','docs/data/fpl_xg.json',
                       'docs/data/striker_xg.json','docs/data/xg_source.json','docs/data/hf_xg.json'],
             'limitations':['Published xG / xA only where verified source permits', 'Shot proxy is not actual xG',
               'Sample size for home-form may be fewer than five games early in season',
               'The weekly archive is stale until next automated Monday run']}
    if len(result)<100:raise RuntimeError('Weekly stats coverage too low')
    (FOLDER/'weekly_team_stats.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('WEEKLY STATS:',json.dumps(payload['coverage']))
if __name__=='__main__':main()
