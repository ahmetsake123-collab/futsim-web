#!/usr/bin/env python3
"""100 sequential, genuinely out-of-sample football evaluations using openfootball CC0.
For each match train ONLY on earlier calendar dates; update the learning tracker after scoring.
Corner coverage comes from open-matchday, attributed informational/noncommercial feed.
No source returns measured current xG/xA or confirmed injury lists; never manufacture them.
"""
import collections, csv, datetime as dt, io, json, math, pathlib, re, statistics, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'data'
BASE='https://raw.githubusercontent.com/'
SOURCES={
 'Premier League':('openfootball/england','{s}/1-premierleague.txt'),
 'Bundesliga':('openfootball/deutschland','{s}/1-bundesliga.txt'),
 'La Liga':('openfootball/espana','{s}/1-liga.txt'),
 'Serie A':('openfootball/italy','{s}/1-seriea.txt'),
 'Ligue 1':('openfootball/europe','italy/NA'), # handled below
 'Eredivisie':('openfootball/europe','netherlands/{s}_nl1.txt'),
 'Süper Lig':('openfootball/europe','turkey/{s}_tr1.txt'),
}
SOURCES['Ligue 1']=('openfootball/europe','france/{s}_fr1.txt')
CORNER_SOURCES={'Premier League':'ENG_1_premier-league','Bundesliga':'GER_1_bundesliga',
 'La Liga':'ESP_1_la-liga','Serie A':'ITA_1_serie-a','Ligue 1':'FRA_1_ligue-1',
 'Eredivisie':'NED_1_eredivisie','Süper Lig':'TUR_1_super-lig'}
MONTH={x:i for i,x in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(),1)}
DATE=re.compile(r'^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3})\s+(\d\d?)(?:\s+(\d{4}))?\s*$')
MATCH=re.compile(r'^\s*(?:(?:\d{1,2}:\d{2})\s+)?(.+?)\s{2,}v\s+(.+?)\s{2,}(\d+)-(\d+)(?:\s+\((\d+)-(\d+)\))?\s*$')
OLD_MATCH=re.compile(r'^\s*(?:(?:\d{1,2}:\d{2})\s+)?(.+?)\s{2,}(\d+)-(\d+)(?:\s+\(\d+-\d+\))?\s{2,}(.+?)\s*$')
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'FUTSIM-personal-research/1.0 (source cited)'})
    with urllib.request.urlopen(req,timeout=26) as r:return r.read().decode('utf-8-sig','replace')
def parse_openfootball(raw,league,season):
    year=int(season[:4]);d=None;records=[]
    for line in raw.splitlines():
        x=DATE.match(line)
        if x:
            month=MONTH.get(x.group(1));day=int(x.group(2))
            if not month:continue
            yr=int(x.group(3)) if x.group(3) else year+(month<7)
            try:d=dt.date(yr,month,day).isoformat()
            except ValueError:d=None
            continue
        m=MATCH.match(line)
        legacy=OLD_MATCH.match(line) if not m else None
        if not (m or legacy) or not d:continue
        if m:
            home,away=m.group(1).strip(),m.group(2).strip()
            hg,ag=int(m.group(3)),int(m.group(4))
        else:
            home,away=legacy.group(1).strip(),legacy.group(4).strip()
            hg,ag=int(legacy.group(2)),int(legacy.group(3))
        if not home or not away:continue
        records.append(dict(date=d,league=league,home=normalized(home),away=normalized(away),
                            home_label=home,away_label=away,hg=hg,ag=ag,hc=None,ac=None))
    return records
def normalized(s):
    import unicodedata
    v=unicodedata.normalize('NFKD',s.casefold())
    v=''.join(c for c in v if not unicodedata.combining(c)).replace('ı','i')
    v=re.sub(r'[^a-z0-9]+',' ',v)
    v=re.sub(r'\b(fc|afc|cfc|ssc|sc|cf|as|sv|ac|fk|sk)\b',' ',v)
    v=re.sub(r'\s+',' ',v).strip()
    aliases={'man utd':'manchester united','man u':'manchester united','man united':'manchester united',
      'man city':'manchester city','spurs':'tottenham hotspur','nott m forest':'nottingham forest',
      'hull':'hull city','newcastle':'newcastle united','leeds':'leeds united','brighton':'brighton hove albion',
      'paris saint germain':'psg','paris sg':'psg','psg':'psg','bayern munchen':'bayern munich'}
    return aliases.get(v,v)
def fetch_corners(season_end='2026-10-25'):
    rows={};status={}
    for league,folder in CORNER_SOURCES.items():
        url=f'{BASE}oladeeayo/open-matchday/master/data/{folder}/results_2627.csv'
        try:
            text=fetch(url)
            count=0
            for r in csv.DictReader(io.StringIO(text)):
                home=(r.get('home') or '').strip();away=(r.get('away') or '').strip()
                day=(r.get('date') or '')[:10]
                try:hc=int(r.get('home_corners') or '');ac=int(r.get('away_corners') or '')
                except ValueError:continue
                if not home or not away or not day or day>=season_end:continue
                key=(league,day,normalized(home),normalized(away))
                rows[key]=(hc,ac);count+=1
            status[league]=count
        except Exception as e:status[league]='unavailable: '+str(e)[:120]
    return rows,status
def join_corners(matches,corner_rows):
    # Strict team-name matching; if name systems disagree, skip (no invented match).
    found=0
    for r in matches:
        pair=corner_rows.get((r['league'],r['date'],normalized(r['home']),normalized(r['away'])))
        if pair is not None:r['hc'],r['ac']=pair;found+=1
    return found
def teamstats(team,matches,league):
    selected=[m for m in matches if m['league']==league and team in (m['home'],m['away'])][-15:]
    w=[.93**i for i in range(len(selected)-1,-1,-1)]
    def avg(field):
        vals=[(m[field],ww) for m,ww in zip(selected,w) if m[field] is not None]
        return sum(v*ww for v,ww in vals)/sum(ww for _,ww in vals) if vals else None
    gf=[];ga=[];cf=[];ca=[]
    for m in selected:
        h=team==m['home']
        gf.append(m['hg'] if h else m['ag']);ga.append(m['ag'] if h else m['hg'])
        cf.append(m['hc'] if h else m['ac']);ca.append(m['ac'] if h else m['hc'])
    def weighted(a):
        pairs=[(v,ww) for v,ww in zip(a,w) if v is not None]
        return sum(v*ww for v,ww in pairs)/sum(ww for _,ww in pairs) if pairs else None
    return {'n':len(selected),'gf':weighted(gf),'ga':weighted(ga),'cf':weighted(cf),'ca':weighted(ca),
            'nc':sum(v is not None for v in cf),'form':selected[-5:]}
def prior(v,n,mean,scale=7):
    return (mean*scale+(v if v is not None else mean)*n)/(n+scale)
def poiss(k,mu):
    return math.exp(-mu+k*math.log(max(.00001,mu))-math.lgamma(k+1))
def poisson_markets(lh,la):
    h=[poiss(k,lh) for k in range(13)];a=[poiss(k,la) for k in range(13)]
    p=[0.,0.,0.]
    for i,ph in enumerate(h):
        for j,pa in enumerate(a):
            p[0 if i>j else 1 if i==j else 2]+=ph*pa
    mass=sum(p)
    return [x/mass for x in p]
def forecast(m,history,home_factor=1.,away_factor=1.,temperature=1):
    l=m['league'];h=teamstats(m['home'],history,l);a=teamstats(m['away'],history,l)
    p_h=prior(h['gf'],h['n'],1.4);p_defa=prior(a['ga'],a['n'],1.4)
    p_a=prior(a['gf'],a['n'],1.3);p_defh=prior(h['ga'],h['n'],1.3)
    # A direct attack/defence rate avoids artificial cross-league Elo differences.
    lh=max(.25,min(3.9,1.10*math.sqrt(p_h*p_defa)*home_factor))
    la=max(.25,min(3.9,.91*math.sqrt(p_a*p_defh)*away_factor))
    probs=poisson_markets(lh,la)
    # Temperature always fitted to PREVIOUS predictions only.
    probs=[max(1e-9,v)**(1/max(.65,min(1.55,temperature))) for v in probs]
    tot=sum(probs);probs=[v/tot for v in probs]
    # Conservative average: corn.for + corners conceded. No corners, no probability.
    cn=min(h['nc'],a['nc'])
    lch=prior(h['cf'],h['nc'],4.6,7) if h['nc'] else None
    lca=prior(a['cf'],a['nc'],4.6,7) if a['nc'] else None
    corners=None
    if cn>=4 and h['ca'] is not None and a['ca'] is not None:
        expected_h=max(1,min(11,(lch+prior(a['ca'],a['nc'],4.6,7))/2))
        expected_a=max(1,min(11,(lca+prior(h['ca'],h['nc'],4.6,7))/2))
        mean=expected_h+expected_a
        # Poisson over 8.5 corners; in production treat as low-confidence unless tested.
        over=1-sum(poiss(k,mean) for k in range(9))
        corners={'mean':round(mean,2),'over85':round(over,5),'observations_min':cn,'over95':round(1-sum(poiss(k,mean) for k in range(10)),5)}
    return {'p':probs,'lh':lh,'la':la,'corners':corners,'min_sample':min(h['n'],a['n'])}
def outcome(m):return 0 if m['hg']>m['ag'] else 1 if m['hg']==m['ag'] else 2
def brier(prob,actual):return sum((p-(i==actual))**2 for i,p in enumerate(prob))
def logloss(prob,actual):return -math.log(max(1e-9,prob[actual]))
def choose_temp(archive):
    # Strong shrinkage to temperature 1 prevents early unstable fitting.
    if len(archive)<30:return 1.
    recent=archive[-180:]
    options=[.85,.92,1.,1.08,1.16,1.25]
    values=[]
    for t in options:
        loss=0.
        for record in recent:
            z=[max(1e-8,v)**(1/t) for v in record['raw']]
            sm=sum(z);loss+=brier([v/sm for v in z],record['truth'])
        values.append(loss/len(recent)+.003*(t-1)**2)
    best=options[values.index(min(values))]
    # Do not fit over-aggressively to a few games.
    return 1+(best-1)*min(.75,len(archive)/180)
def metrics(rows):
    if not rows:return {'n':0}
    n=len(rows); y=lambda k:round(sum(row[k] for row in rows)/n,5)
    return {'n':n,'brier':y('brier'),'log_loss':y('log_loss'),
            'accuracy':round(sum(x['predicted']==x['truth'] for x in rows)/n,4),
            'correct':sum(x['predicted']==x['truth'] for x in rows)}
def run():
    historical=[];fresh=[];errors=[]
    cutoff=dt.datetime.now(dt.timezone.utc).date().isoformat()
    for league,(repo,pattern) in SOURCES.items():
        for season,store in [('2025-26',historical),('2026-27',fresh)]:
            path=pattern.format(s=season)
            url=f'{BASE}{repo}/master/{path}'
            try:
                data=parse_openfootball(fetch(url),league,season)
                if not data:raise ValueError('parsed zero completed fixtures')
                store.extend([r for r in data if r['date']<cutoff])
            except Exception as e:errors.append({'league':league,'season':season,'error':str(e)[:150]})
    history=sorted(historical,key=lambda x:(x['date'],x['league']))
    testing=sorted(fresh,key=lambda x:(x['date'],x['league'],x['home']))
    if len(testing)<100 or len(history)<400:
        raise RuntimeError(f'Insufficient ACTUAL historical matches. training={len(history)},test={len(testing)},errors={errors}')
    corner_rows,corner_status=fetch_corners(cutoff)
    joined=join_corners(testing,corner_rows)
    # 100 consecutive matches, with all prior dates available; same-day scores excluded.
    rolling=[];archive=[];seen=[];corner_eval=[]
    home_factor=1.;away_factor=1.;temperature=1.
    for idx,m in enumerate(testing[:500]):
        actual_hist=history+[x for x in seen if x['date']<m['date']]
        pred=forecast(m,actual_hist,home_factor,away_factor,temperature)
        actual=outcome(m)
        row={'test':idx+1,'date':m['date'],'league':m['league'],'home':m.get('home_label',m['home']),'away':m.get('away_label',m['away']),
             'actual_score':f"{m['hg']}-{m['ag']}",'prob_1x2':[round(v,4) for v in pred['p']],
             'predicted':max(range(3),key=lambda i:pred['p'][i]),'truth':actual,
             'brier':brier(pred['p'],actual),'log_loss':logloss(pred['p'],actual),
             'confidence':max(pred['p']),'temperature_used':round(temperature,3),
             'status':'correct' if max(range(3),key=lambda i:pred['p'][i])==actual else 'miss',
             'prediction_lambdas':[round(pred['lh'],3),round(pred['la'],3)]}
        if pred['corners'] and m['hc'] is not None and m['ac'] is not None:
            label=int(m['hc']+m['ac']>=9)
            p=pred['corners']['over85']
            row['corner_over85']={'predicted':p,'actual':label,'total':m['hc']+m['ac'],
                'brier':round((p-label)**2,5)}
            corner_eval.append(row['corner_over85'])
        rolling.append(row);seen.append(m)
        raw=poisson_markets(pred['lh'],pred['la'])
        archive.append({'raw':raw,'truth':actual})
        temperature=choose_temp(archive)
        # Tiny, bounded update from past errors only; learns after scoring.
        home_factor=max(.89,min(1.12,home_factor*.99+.01*max(.75,min(1.25,m['hg']/max(.5,pred['lh'])))))
        away_factor=max(.89,min(1.12,away_factor*.99+.01*max(.75,min(1.25,m['ag']/max(.5,pred['la'])))))
    baseline=[{'brier':brier([.43,.27,.30],x['truth']),'log_loss':logloss([.43,.27,.30],x['truth']),
               'predicted':0,'truth':x['truth']} for x in rolling]
    acc=metrics(rolling);base=metrics(baseline)
    pred_bins=[]
    for lower in [0,.4,.5,.6,.7,.8,.9]:
        upper={0:.4,.4:.5,.5:.6,.6:.7,.7:.8,.8:.9,.9:1.00001}[lower]
        subset=[x for x in rolling if lower<=x['confidence']<upper]
        if subset:pred_bins.append({'range':f'{lower:.1f}-{upper:.1f}','n':len(subset),
                                    'avg_confidence':round(statistics.mean(x['confidence'] for x in subset),3),
                                    'accuracy':round(sum(x['predicted']==x['truth'] for x in subset)/len(subset),3)})
    corner_metrics={'n':len(corner_eval),'brier':round(statistics.mean(x['brier'] for x in corner_eval),4) if corner_eval else None,
                    'warning':'Small and incomplete corner source coverage; no strong bet claims.'}
    report={'run_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'method':'At least 100 next-match chronological walk-forward tests; 2025/26 prehistory, 2026/27 out-of-sample. After each prediction error, adjust using past ONLY; same-day excluded.',
            'source_results':'https://github.com/openfootball (public domain)','source_corners':'https://github.com/oladeeayo/open-matchday (informational non-commercial, attribution)',
            'training_matches':len(history),'available_test_matches':len(testing),'iterations':len(rolling),
            'final_temperature':round(temperature,4),'goal_factors':{'home':round(home_factor,4),'away':round(away_factor,4)},
            'model_metrics':acc,'baseline':base,
            'improved_over_baseline_brier':acc['brier']<base['brier'],
            'corners':corner_metrics,'corner_records_matched':joined,'corner_coverage_status':corner_status,
            'calibration_bins':pred_bins,'errors':errors,'samples':rolling[:8]+rolling[-8:],
            'result_distribution':{'1':sum(x['truth']==0 for x in rolling),'X':sum(x['truth']==1 for x in rolling),'2':sum(x['truth']==2 for x in rolling)},
            'limitations':['100 tests are not 100 independent model designs','No guaranteed profit; unverified bookmaker prices excluded','Injuries, xG and xA not verified by these sources','Corner coverage limited; Poisson corner assumptions not validated on every league']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'model_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    # Only activate modest goal calibration after a meaningful out-of-sample edge.
    tuned={'validated':bool(acc['brier']<base['brier'] and acc['n']>=100),'temperature':round(temperature,4),
           'home_factor':round(home_factor,4),'away_factor':round(away_factor,4),
           'note':'Tuning derived only from prior outcomes; baseline beat required; no betting promise'}
    (OUT/'model_params.json').write_text(json.dumps(tuned,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FUTSIM 100 TESTS: '+json.dumps({'n':acc['n'],'model_brier':acc['brier'],'baseline_brier':base['brier'],
      'accuracy':acc['accuracy'],'corner_test_n':len(corner_eval),'verified_corner_matches':joined,
      'use_tuning':tuned['validated']},ensure_ascii=False))
if __name__=='__main__':run()
)
OLD_MATCH=re.compile(r'^\s*(?:(?:\d{1,2}:\d{2})\s+)?(.+?)\s{2,}(\d+)-(\d+)(?:\s+\(\d+-\d+\))?\s{2,}(.+?)\s*
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'FUTSIM-personal-research/1.0 (source cited)'})
    with urllib.request.urlopen(req,timeout=26) as r:return r.read().decode('utf-8-sig','replace')
def parse_openfootball(raw,league,season):
    year=int(season[:4]);d=None;records=[]
    for line in raw.splitlines():
        x=DATE.match(line)
        if x:
            month=MONTH.get(x.group(1));day=int(x.group(2))
            if not month:continue
            yr=int(x.group(3)) if x.group(3) else year+(month<7)
            try:d=dt.date(yr,month,day).isoformat()
            except ValueError:d=None
            continue
        m=MATCH.match(line)
        if not m or not d:continue
        home,away=m.group(1).strip(),m.group(2).strip()
        if not home or not away:continue
        records.append(dict(date=d,league=league,home=home,away=away,hg=int(m.group(3)),ag=int(m.group(4)),hc=None,ac=None))
    return records
def normalized(s):
    return ''.join(c for c in s.casefold() if c.isalnum())
def fetch_corners(season_end='2026-10-25'):
    rows={};status={}
    for league,folder in CORNER_SOURCES.items():
        url=f'{BASE}oladeeayo/open-matchday/master/data/{folder}/results_2627.csv'
        try:
            text=fetch(url)
            count=0
            for r in csv.DictReader(io.StringIO(text)):
                home=(r.get('home') or '').strip();away=(r.get('away') or '').strip()
                day=(r.get('date') or '')[:10]
                try:hc=int(r.get('home_corners') or '');ac=int(r.get('away_corners') or '')
                except ValueError:continue
                if not home or not away or not day or day>=season_end:continue
                key=(league,day,normalized(home),normalized(away))
                rows[key]=(hc,ac);count+=1
            status[league]=count
        except Exception as e:status[league]='unavailable: '+str(e)[:120]
    return rows,status
def join_corners(matches,corner_rows):
    # Strict team-name matching; if name systems disagree, skip (no invented match).
    found=0
    for r in matches:
        pair=corner_rows.get((r['league'],r['date'],normalized(r['home']),normalized(r['away'])))
        if pair is not None:r['hc'],r['ac']=pair;found+=1
    return found
def teamstats(team,matches,league):
    selected=[m for m in matches if m['league']==league and team in (m['home'],m['away'])][-15:]
    w=[.93**i for i in range(len(selected)-1,-1,-1)]
    def avg(field):
        vals=[(m[field],ww) for m,ww in zip(selected,w) if m[field] is not None]
        return sum(v*ww for v,ww in vals)/sum(ww for _,ww in vals) if vals else None
    gf=[];ga=[];cf=[];ca=[]
    for m in selected:
        h=team==m['home']
        gf.append(m['hg'] if h else m['ag']);ga.append(m['ag'] if h else m['hg'])
        cf.append(m['hc'] if h else m['ac']);ca.append(m['ac'] if h else m['hc'])
    def weighted(a):
        pairs=[(v,ww) for v,ww in zip(a,w) if v is not None]
        return sum(v*ww for v,ww in pairs)/sum(ww for _,ww in pairs) if pairs else None
    return {'n':len(selected),'gf':weighted(gf),'ga':weighted(ga),'cf':weighted(cf),'ca':weighted(ca),
            'nc':sum(v is not None for v in cf),'form':selected[-5:]}
def prior(v,n,mean,scale=7):
    return (mean*scale+(v if v is not None else mean)*n)/(n+scale)
def poiss(k,mu):
    return math.exp(-mu+k*math.log(max(.00001,mu))-math.lgamma(k+1))
def poisson_markets(lh,la):
    h=[poiss(k,lh) for k in range(13)];a=[poiss(k,la) for k in range(13)]
    p=[0.,0.,0.]
    for i,ph in enumerate(h):
        for j,pa in enumerate(a):
            p[0 if i>j else 1 if i==j else 2]+=ph*pa
    mass=sum(p)
    return [x/mass for x in p]
def forecast(m,history,home_factor=1.,away_factor=1.,temperature=1):
    l=m['league'];h=teamstats(m['home'],history,l);a=teamstats(m['away'],history,l)
    p_h=prior(h['gf'],h['n'],1.4);p_defa=prior(a['ga'],a['n'],1.4)
    p_a=prior(a['gf'],a['n'],1.3);p_defh=prior(h['ga'],h['n'],1.3)
    # A direct attack/defence rate avoids artificial cross-league Elo differences.
    lh=max(.25,min(3.9,1.10*math.sqrt(p_h*p_defa)*home_factor))
    la=max(.25,min(3.9,.91*math.sqrt(p_a*p_defh)*away_factor))
    probs=poisson_markets(lh,la)
    # Temperature always fitted to PREVIOUS predictions only.
    probs=[max(1e-9,v)**(1/max(.65,min(1.55,temperature))) for v in probs]
    tot=sum(probs);probs=[v/tot for v in probs]
    # Conservative average: corn.for + corners conceded. No corners, no probability.
    cn=min(h['nc'],a['nc'])
    lch=prior(h['cf'],h['nc'],4.6,7) if h['nc'] else None
    lca=prior(a['cf'],a['nc'],4.6,7) if a['nc'] else None
    corners=None
    if cn>=4 and h['ca'] is not None and a['ca'] is not None:
        expected_h=max(1,min(11,(lch+prior(a['ca'],a['nc'],4.6,7))/2))
        expected_a=max(1,min(11,(lca+prior(h['ca'],h['nc'],4.6,7))/2))
        mean=expected_h+expected_a
        # Poisson over 8.5 corners; in production treat as low-confidence unless tested.
        over=1-sum(poiss(k,mean) for k in range(9))
        corners={'mean':round(mean,2),'over85':round(over,5),'observations_min':cn,'over95':round(1-sum(poiss(k,mean) for k in range(10)),5)}
    return {'p':probs,'lh':lh,'la':la,'corners':corners,'min_sample':min(h['n'],a['n'])}
def outcome(m):return 0 if m['hg']>m['ag'] else 1 if m['hg']==m['ag'] else 2
def brier(prob,actual):return sum((p-(i==actual))**2 for i,p in enumerate(prob))
def logloss(prob,actual):return -math.log(max(1e-9,prob[actual]))
def choose_temp(archive):
    # Strong shrinkage to temperature 1 prevents early unstable fitting.
    if len(archive)<30:return 1.
    recent=archive[-180:]
    options=[.85,.92,1.,1.08,1.16,1.25]
    values=[]
    for t in options:
        loss=0.
        for record in recent:
            z=[max(1e-8,v)**(1/t) for v in record['raw']]
            sm=sum(z);loss+=brier([v/sm for v in z],record['truth'])
        values.append(loss/len(recent)+.003*(t-1)**2)
    best=options[values.index(min(values))]
    # Do not fit over-aggressively to a few games.
    return 1+(best-1)*min(.75,len(archive)/180)
def metrics(rows):
    if not rows:return {'n':0}
    n=len(rows); y=lambda k:round(sum(row[k] for row in rows)/n,5)
    return {'n':n,'brier':y('brier'),'log_loss':y('log_loss'),
            'accuracy':round(sum(x['predicted']==x['truth'] for x in rows)/n,4),
            'correct':sum(x['predicted']==x['truth'] for x in rows)}
def run():
    historical=[];fresh=[];errors=[]
    cutoff=dt.datetime.now(dt.timezone.utc).date().isoformat()
    for league,(repo,pattern) in SOURCES.items():
        for season,store in [('2025-26',historical),('2026-27',fresh)]:
            path=pattern.format(s=season)
            url=f'{BASE}{repo}/master/{path}'
            try:
                data=parse_openfootball(fetch(url),league,season)
                if not data:raise ValueError('parsed zero completed fixtures')
                store.extend([r for r in data if r['date']<cutoff])
            except Exception as e:errors.append({'league':league,'season':season,'error':str(e)[:150]})
    history=sorted(historical,key=lambda x:(x['date'],x['league']))
    testing=sorted(fresh,key=lambda x:(x['date'],x['league'],x['home']))
    if len(testing)<100 or len(history)<400:
        raise RuntimeError(f'Insufficient ACTUAL historical matches. training={len(history)},test={len(testing)},errors={errors}')
    corner_rows,corner_status=fetch_corners(cutoff)
    joined=join_corners(testing,corner_rows)
    # 100 consecutive matches, with all prior dates available; same-day scores excluded.
    rolling=[];archive=[];seen=[];corner_eval=[]
    home_factor=1.;away_factor=1.;temperature=1.
    for idx,m in enumerate(testing[:100]):
        actual_hist=history+[x for x in seen if x['date']<m['date']]
        pred=forecast(m,actual_hist,home_factor,away_factor,temperature)
        actual=outcome(m)
        row={'test':idx+1,'date':m['date'],'league':m['league'],'home':m['home'],'away':m['away'],
             'actual_score':f"{m['hg']}-{m['ag']}",'prob_1x2':[round(v,4) for v in pred['p']],
             'predicted':max(range(3),key=lambda i:pred['p'][i]),'truth':actual,
             'brier':brier(pred['p'],actual),'log_loss':logloss(pred['p'],actual),
             'confidence':max(pred['p']),'temperature_used':round(temperature,3),
             'status':'correct' if max(range(3),key=lambda i:pred['p'][i])==actual else 'miss',
             'prediction_lambdas':[round(pred['lh'],3),round(pred['la'],3)]}
        if pred['corners'] and m['hc'] is not None and m['ac'] is not None:
            label=int(m['hc']+m['ac']>=9)
            p=pred['corners']['over85']
            row['corner_over85']={'predicted':p,'actual':label,'total':m['hc']+m['ac'],
                'brier':round((p-label)**2,5)}
            corner_eval.append(row['corner_over85'])
        rolling.append(row);seen.append(m)
        raw=poisson_markets(pred['lh'],pred['la'])
        archive.append({'raw':raw,'truth':actual})
        temperature=choose_temp(archive)
        # Tiny, bounded update from past errors only; learns after scoring.
        home_factor=max(.89,min(1.12,home_factor*.99+.01*max(.75,min(1.25,m['hg']/max(.5,pred['lh'])))))
        away_factor=max(.89,min(1.12,away_factor*.99+.01*max(.75,min(1.25,m['ag']/max(.5,pred['la'])))))
    baseline=[{'brier':brier([.43,.27,.30],x['truth']),'log_loss':logloss([.43,.27,.30],x['truth']),
               'predicted':0,'truth':x['truth']} for x in rolling]
    acc=metrics(rolling);base=metrics(baseline)
    pred_bins=[]
    for lower in [0,.4,.5,.6,.7,.8,.9]:
        upper={0:.4,.4:.5,.5:.6,.6:.7,.7:.8,.8:.9,.9:1.00001}[lower]
        subset=[x for x in rolling if lower<=x['confidence']<upper]
        if subset:pred_bins.append({'range':f'{lower:.1f}-{upper:.1f}','n':len(subset),
                                    'avg_confidence':round(statistics.mean(x['confidence'] for x in subset),3),
                                    'accuracy':round(sum(x['predicted']==x['truth'] for x in subset)/len(subset),3)})
    corner_metrics={'n':len(corner_eval),'brier':round(statistics.mean(x['brier'] for x in corner_eval),4) if corner_eval else None,
                    'warning':'Small and incomplete corner source coverage; no strong bet claims.'}
    report={'run_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'method':'100 next-match chronological walk-forward tests; 2025/26 prehistory, 2026/27 out-of-sample. After each prediction error, adjust using past ONLY; same-day excluded.',
            'source_results':'https://github.com/openfootball (public domain)','source_corners':'https://github.com/oladeeayo/open-matchday (informational non-commercial, attribution)',
            'training_matches':len(history),'available_test_matches':len(testing),'iterations':len(rolling),
            'final_temperature':round(temperature,4),'goal_factors':{'home':round(home_factor,4),'away':round(away_factor,4)},
            'model_metrics':acc,'baseline':base,
            'improved_over_baseline_brier':acc['brier']<base['brier'],
            'corners':corner_metrics,'corner_records_matched':joined,'corner_coverage_status':corner_status,
            'calibration_bins':pred_bins,'errors':errors,'samples':rolling[:8]+rolling[-8:],
            'result_distribution':{'1':sum(x['truth']==0 for x in rolling),'X':sum(x['truth']==1 for x in rolling),'2':sum(x['truth']==2 for x in rolling)},
            'limitations':['100 tests are not 100 independent model designs','No guaranteed profit; unverified bookmaker prices excluded','Injuries, xG and xA not verified by these sources','Corner coverage limited; Poisson corner assumptions not validated on every league']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'model_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    # Only activate modest goal calibration after a meaningful out-of-sample edge.
    tuned={'validated':bool(acc['brier']<base['brier'] and acc['n']>=100),'temperature':round(temperature,4),
           'home_factor':round(home_factor,4),'away_factor':round(away_factor,4),
           'note':'Tuning derived only from prior outcomes; baseline beat required; no betting promise'}
    (OUT/'model_params.json').write_text(json.dumps(tuned,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FUTSIM 100 TESTS: '+json.dumps({'n':acc['n'],'model_brier':acc['brier'],'baseline_brier':base['brier'],
      'accuracy':acc['accuracy'],'corner_test_n':len(corner_eval),'verified_corner_matches':joined,
      'use_tuning':tuned['validated']},ensure_ascii=False))
if __name__=='__main__':run()
)
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'FUTSIM-personal-research/1.0 (source cited)'})
    with urllib.request.urlopen(req,timeout=26) as r:return r.read().decode('utf-8-sig','replace')
def parse_openfootball(raw,league,season):
    year=int(season[:4]);d=None;records=[]
    for line in raw.splitlines():
        x=DATE.match(line)
        if x:
            month=MONTH.get(x.group(1));day=int(x.group(2))
            if not month:continue
            yr=int(x.group(3)) if x.group(3) else year+(month<7)
            try:d=dt.date(yr,month,day).isoformat()
            except ValueError:d=None
            continue
        m=MATCH.match(line)
        if not m or not d:continue
        home,away=m.group(1).strip(),m.group(2).strip()
        if not home or not away:continue
        records.append(dict(date=d,league=league,home=home,away=away,hg=int(m.group(3)),ag=int(m.group(4)),hc=None,ac=None))
    return records
def normalized(s):
    return ''.join(c for c in s.casefold() if c.isalnum())
def fetch_corners(season_end='2026-10-25'):
    rows={};status={}
    for league,folder in CORNER_SOURCES.items():
        url=f'{BASE}oladeeayo/open-matchday/master/data/{folder}/results_2627.csv'
        try:
            text=fetch(url)
            count=0
            for r in csv.DictReader(io.StringIO(text)):
                home=(r.get('home') or '').strip();away=(r.get('away') or '').strip()
                day=(r.get('date') or '')[:10]
                try:hc=int(r.get('home_corners') or '');ac=int(r.get('away_corners') or '')
                except ValueError:continue
                if not home or not away or not day or day>=season_end:continue
                key=(league,day,normalized(home),normalized(away))
                rows[key]=(hc,ac);count+=1
            status[league]=count
        except Exception as e:status[league]='unavailable: '+str(e)[:120]
    return rows,status
def join_corners(matches,corner_rows):
    # Strict team-name matching; if name systems disagree, skip (no invented match).
    found=0
    for r in matches:
        pair=corner_rows.get((r['league'],r['date'],normalized(r['home']),normalized(r['away'])))
        if pair is not None:r['hc'],r['ac']=pair;found+=1
    return found
def teamstats(team,matches,league):
    selected=[m for m in matches if m['league']==league and team in (m['home'],m['away'])][-15:]
    w=[.93**i for i in range(len(selected)-1,-1,-1)]
    def avg(field):
        vals=[(m[field],ww) for m,ww in zip(selected,w) if m[field] is not None]
        return sum(v*ww for v,ww in vals)/sum(ww for _,ww in vals) if vals else None
    gf=[];ga=[];cf=[];ca=[]
    for m in selected:
        h=team==m['home']
        gf.append(m['hg'] if h else m['ag']);ga.append(m['ag'] if h else m['hg'])
        cf.append(m['hc'] if h else m['ac']);ca.append(m['ac'] if h else m['hc'])
    def weighted(a):
        pairs=[(v,ww) for v,ww in zip(a,w) if v is not None]
        return sum(v*ww for v,ww in pairs)/sum(ww for _,ww in pairs) if pairs else None
    return {'n':len(selected),'gf':weighted(gf),'ga':weighted(ga),'cf':weighted(cf),'ca':weighted(ca),
            'nc':sum(v is not None for v in cf),'form':selected[-5:]}
def prior(v,n,mean,scale=7):
    return (mean*scale+(v if v is not None else mean)*n)/(n+scale)
def poiss(k,mu):
    return math.exp(-mu+k*math.log(max(.00001,mu))-math.lgamma(k+1))
def poisson_markets(lh,la):
    h=[poiss(k,lh) for k in range(13)];a=[poiss(k,la) for k in range(13)]
    p=[0.,0.,0.]
    for i,ph in enumerate(h):
        for j,pa in enumerate(a):
            p[0 if i>j else 1 if i==j else 2]+=ph*pa
    mass=sum(p)
    return [x/mass for x in p]
def forecast(m,history,home_factor=1.,away_factor=1.,temperature=1):
    l=m['league'];h=teamstats(m['home'],history,l);a=teamstats(m['away'],history,l)
    p_h=prior(h['gf'],h['n'],1.4);p_defa=prior(a['ga'],a['n'],1.4)
    p_a=prior(a['gf'],a['n'],1.3);p_defh=prior(h['ga'],h['n'],1.3)
    # A direct attack/defence rate avoids artificial cross-league Elo differences.
    lh=max(.25,min(3.9,1.10*math.sqrt(p_h*p_defa)*home_factor))
    la=max(.25,min(3.9,.91*math.sqrt(p_a*p_defh)*away_factor))
    probs=poisson_markets(lh,la)
    # Temperature always fitted to PREVIOUS predictions only.
    probs=[max(1e-9,v)**(1/max(.65,min(1.55,temperature))) for v in probs]
    tot=sum(probs);probs=[v/tot for v in probs]
    # Conservative average: corn.for + corners conceded. No corners, no probability.
    cn=min(h['nc'],a['nc'])
    lch=prior(h['cf'],h['nc'],4.6,7) if h['nc'] else None
    lca=prior(a['cf'],a['nc'],4.6,7) if a['nc'] else None
    corners=None
    if cn>=4 and h['ca'] is not None and a['ca'] is not None:
        expected_h=max(1,min(11,(lch+prior(a['ca'],a['nc'],4.6,7))/2))
        expected_a=max(1,min(11,(lca+prior(h['ca'],h['nc'],4.6,7))/2))
        mean=expected_h+expected_a
        # Poisson over 8.5 corners; in production treat as low-confidence unless tested.
        over=1-sum(poiss(k,mean) for k in range(9))
        corners={'mean':round(mean,2),'over85':round(over,5),'observations_min':cn,'over95':round(1-sum(poiss(k,mean) for k in range(10)),5)}
    return {'p':probs,'lh':lh,'la':la,'corners':corners,'min_sample':min(h['n'],a['n'])}
def outcome(m):return 0 if m['hg']>m['ag'] else 1 if m['hg']==m['ag'] else 2
def brier(prob,actual):return sum((p-(i==actual))**2 for i,p in enumerate(prob))
def logloss(prob,actual):return -math.log(max(1e-9,prob[actual]))
def choose_temp(archive):
    # Strong shrinkage to temperature 1 prevents early unstable fitting.
    if len(archive)<30:return 1.
    recent=archive[-180:]
    options=[.85,.92,1.,1.08,1.16,1.25]
    values=[]
    for t in options:
        loss=0.
        for record in recent:
            z=[max(1e-8,v)**(1/t) for v in record['raw']]
            sm=sum(z);loss+=brier([v/sm for v in z],record['truth'])
        values.append(loss/len(recent)+.003*(t-1)**2)
    best=options[values.index(min(values))]
    # Do not fit over-aggressively to a few games.
    return 1+(best-1)*min(.75,len(archive)/180)
def metrics(rows):
    if not rows:return {'n':0}
    n=len(rows); y=lambda k:round(sum(row[k] for row in rows)/n,5)
    return {'n':n,'brier':y('brier'),'log_loss':y('log_loss'),
            'accuracy':round(sum(x['predicted']==x['truth'] for x in rows)/n,4),
            'correct':sum(x['predicted']==x['truth'] for x in rows)}
def run():
    historical=[];fresh=[];errors=[]
    cutoff=dt.datetime.now(dt.timezone.utc).date().isoformat()
    for league,(repo,pattern) in SOURCES.items():
        for season,store in [('2025-26',historical),('2026-27',fresh)]:
            path=pattern.format(s=season)
            url=f'{BASE}{repo}/master/{path}'
            try:
                data=parse_openfootball(fetch(url),league,season)
                if not data:raise ValueError('parsed zero completed fixtures')
                store.extend([r for r in data if r['date']<cutoff])
            except Exception as e:errors.append({'league':league,'season':season,'error':str(e)[:150]})
    history=sorted(historical,key=lambda x:(x['date'],x['league']))
    testing=sorted(fresh,key=lambda x:(x['date'],x['league'],x['home']))
    if len(testing)<100 or len(history)<400:
        raise RuntimeError(f'Insufficient ACTUAL historical matches. training={len(history)},test={len(testing)},errors={errors}')
    corner_rows,corner_status=fetch_corners(cutoff)
    joined=join_corners(testing,corner_rows)
    # 100 consecutive matches, with all prior dates available; same-day scores excluded.
    rolling=[];archive=[];seen=[];corner_eval=[]
    home_factor=1.;away_factor=1.;temperature=1.
    for idx,m in enumerate(testing[:100]):
        actual_hist=history+[x for x in seen if x['date']<m['date']]
        pred=forecast(m,actual_hist,home_factor,away_factor,temperature)
        actual=outcome(m)
        row={'test':idx+1,'date':m['date'],'league':m['league'],'home':m['home'],'away':m['away'],
             'actual_score':f"{m['hg']}-{m['ag']}",'prob_1x2':[round(v,4) for v in pred['p']],
             'predicted':max(range(3),key=lambda i:pred['p'][i]),'truth':actual,
             'brier':brier(pred['p'],actual),'log_loss':logloss(pred['p'],actual),
             'confidence':max(pred['p']),'temperature_used':round(temperature,3),
             'status':'correct' if max(range(3),key=lambda i:pred['p'][i])==actual else 'miss',
             'prediction_lambdas':[round(pred['lh'],3),round(pred['la'],3)]}
        if pred['corners'] and m['hc'] is not None and m['ac'] is not None:
            label=int(m['hc']+m['ac']>=9)
            p=pred['corners']['over85']
            row['corner_over85']={'predicted':p,'actual':label,'total':m['hc']+m['ac'],
                'brier':round((p-label)**2,5)}
            corner_eval.append(row['corner_over85'])
        rolling.append(row);seen.append(m)
        raw=poisson_markets(pred['lh'],pred['la'])
        archive.append({'raw':raw,'truth':actual})
        temperature=choose_temp(archive)
        # Tiny, bounded update from past errors only; learns after scoring.
        home_factor=max(.89,min(1.12,home_factor*.99+.01*max(.75,min(1.25,m['hg']/max(.5,pred['lh'])))))
        away_factor=max(.89,min(1.12,away_factor*.99+.01*max(.75,min(1.25,m['ag']/max(.5,pred['la'])))))
    baseline=[{'brier':brier([.43,.27,.30],x['truth']),'log_loss':logloss([.43,.27,.30],x['truth']),
               'predicted':0,'truth':x['truth']} for x in rolling]
    acc=metrics(rolling);base=metrics(baseline)
    pred_bins=[]
    for lower in [0,.4,.5,.6,.7,.8,.9]:
        upper={0:.4,.4:.5,.5:.6,.6:.7,.7:.8,.8:.9,.9:1.00001}[lower]
        subset=[x for x in rolling if lower<=x['confidence']<upper]
        if subset:pred_bins.append({'range':f'{lower:.1f}-{upper:.1f}','n':len(subset),
                                    'avg_confidence':round(statistics.mean(x['confidence'] for x in subset),3),
                                    'accuracy':round(sum(x['predicted']==x['truth'] for x in subset)/len(subset),3)})
    corner_metrics={'n':len(corner_eval),'brier':round(statistics.mean(x['brier'] for x in corner_eval),4) if corner_eval else None,
                    'warning':'Small and incomplete corner source coverage; no strong bet claims.'}
    report={'run_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'method':'100 next-match chronological walk-forward tests; 2025/26 prehistory, 2026/27 out-of-sample. After each prediction error, adjust using past ONLY; same-day excluded.',
            'source_results':'https://github.com/openfootball (public domain)','source_corners':'https://github.com/oladeeayo/open-matchday (informational non-commercial, attribution)',
            'training_matches':len(history),'available_test_matches':len(testing),'iterations':len(rolling),
            'final_temperature':round(temperature,4),'goal_factors':{'home':round(home_factor,4),'away':round(away_factor,4)},
            'model_metrics':acc,'baseline':base,
            'improved_over_baseline_brier':acc['brier']<base['brier'],
            'corners':corner_metrics,'corner_records_matched':joined,'corner_coverage_status':corner_status,
            'calibration_bins':pred_bins,'errors':errors,'samples':rolling[:8]+rolling[-8:],
            'result_distribution':{'1':sum(x['truth']==0 for x in rolling),'X':sum(x['truth']==1 for x in rolling),'2':sum(x['truth']==2 for x in rolling)},
            'limitations':['100 tests are not 100 independent model designs','No guaranteed profit; unverified bookmaker prices excluded','Injuries, xG and xA not verified by these sources','Corner coverage limited; Poisson corner assumptions not validated on every league']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'model_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    # Only activate modest goal calibration after a meaningful out-of-sample edge.
    tuned={'validated':bool(acc['brier']<base['brier'] and acc['n']>=100),'temperature':round(temperature,4),
           'home_factor':round(home_factor,4),'away_factor':round(away_factor,4),
           'note':'Tuning derived only from prior outcomes; baseline beat required; no betting promise'}
    (OUT/'model_params.json').write_text(json.dumps(tuned,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FUTSIM 100 TESTS: '+json.dumps({'n':acc['n'],'model_brier':acc['brier'],'baseline_brier':base['brier'],
      'accuracy':acc['accuracy'],'corner_test_n':len(corner_eval),'verified_corner_matches':joined,
      'use_tuning':tuned['validated']},ensure_ascii=False))
if __name__=='__main__':run()
