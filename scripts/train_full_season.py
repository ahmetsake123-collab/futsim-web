#!/usr/bin/env python3
"""FUTSIM: full-season, chronological league + Champions League audit.
CC0 score data; no same-day leakage; no fabricated injury/lineup/player metrics.
Reports are evaluation, NOT proof of betting profitability.
"""
import collections
import csv
import io
import datetime as dt
import json
import math
import pathlib
import re
import statistics
from validate_walkforward import (BASE, SOURCES, fetch, parse_openfootball, normalized,
                                  forecast, poisson_markets, brier, logloss, outcome, poiss)
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'data'
UCL='Şampiyonlar Ligi'
UCL_SRC=BASE+'openfootball/champions-league/master/{season}/cl.txt'
DATE_RE=re.compile(r'^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$')
MATCH_RE=re.compile(r'^\s*(?:\d{1,2}:\d{2}\s+)?(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)(?:\s|$)')
MONTH={x:i for i,x in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(),1)}
ALIASES={'internazionale milano':'internazionale','bayern munchen':'bayern munich',
 'fc barcelona':'barcelona','barcelona':'barcelona','sporting clube de portugal':'sporting',
 'sport lisboa e benfica':'benfica','atletico de madrid':'atletico madrid',
 'real madrid':'real madrid','chelsea':'chelsea','arsenal':'arsenal',
 'paris saint germain':'psg','olympique de marseille':'marseille',
 'olympique marseille':'marseille','tottenham hotspur':'tottenham hotspur',
 'juventus':'juventus','borussia dortmund':'borussia dortmund',
 'atalanta bc':'atalanta','sporting clube portugal':'sporting'}
def club(raw):
    raw=re.sub(r'\s*\([A-Z]{3}\)\s*$','',raw.strip())
    v=normalized(raw)
    return ALIASES.get(v,v)
def read_ucl(season):
    raw=fetch(UCL_SRC.format(season=season))
    date=None;stage=None;out=[];year=int(season[:4])
    for line in raw.splitlines():
        if line.lstrip().startswith('▪'):
            stage=line.strip().lstrip('▪').strip();continue
        m=DATE_RE.match(line)
        if m:
            month=MONTH.get(m.group(1));day=int(m.group(2))
            y=int(m.group(3)) if m.group(3) else year+(month<7)
            try: date=dt.date(y,month,day).isoformat()
            except ValueError:date=None
            continue
        if not date or ' pen.' in line or 'a.e.t.' in line:continue
        m=MATCH_RE.match(line)
        if not m:continue
        h,away=m.group(1).strip(),m.group(2).strip()
        hg,ag=int(m.group(3)),int(m.group(4))
        # Ignore preliminary qualifiers; only 36-team league phase + knockout.
        if not stage or not (stage.startswith('League') or stage.startswith('Playoffs') or stage.startswith('Finals')):continue
        out.append(dict(date=date,league=UCL,home=club(h),away=club(away),
          home_label=h,away_label=away,hg=hg,ag=ag,hc=None,ac=None,stage=stage))
    return out
# Independent score/corner archive for historical research. Aggregate reports only.
DIVS={'Premier League':'E0','Bundesliga':'D1','La Liga':'SP1','Serie A':'I1','Ligue 1':'F1','Eredivisie':'N1','Süper Lig':'T1'}
def current_ucl_fallback():
    # 2026/27 CC0-like public fixture collection when OpenFootball UCL has no
    # current season file yet. Independent match source; verify row by row.
    url=BASE+'oladeeayo/open-matchday/master/data/UEFA_1_champions-league/results_2627.csv'
    rows=[]
    for r in csv.DictReader(io.StringIO(fetch(url))):
        try:
            day=(r.get('date') or '')[:10]
            dt.date.fromisoformat(day)
            h=(r.get('home') or '').strip();a=(r.get('away') or '').strip()
            if not h or not a:continue
            rows.append(dict(date=day,league=UCL,home=club(h),away=club(a),
              home_label=h,away_label=a,hg=int(r['ft_home']),ag=int(r['ft_away']),
              hc=None,ac=None,stage='League'))
        except (ValueError,TypeError,KeyError):continue
    return rows
def csv_season(lg,season):
    year=int(season[:4]);code=f'{year%100:02d}{(year+1)%100:02d}'
    raw=fetch('https://www.football-data.co.uk/mmz4281/'+code+'/'+DIVS[lg]+'.csv')
    matches=[]
    for row in csv.DictReader(io.StringIO(raw)):
        try:
            day=None
            for fmt in ('%d/%m/%Y','%d/%m/%y'):
                try:day=dt.datetime.strptime(row.get('Date','').strip(),fmt).date().isoformat();break
                except ValueError:continue
            if not day:continue
            home=row.get('HomeTeam','').strip();away=row.get('AwayTeam','').strip()
            if not home or not away:continue
            def count(col):
                try:return int(float(row.get(col) or ''))
                except (TypeError,ValueError):return None
            matches.append(dict(date=day,league=lg,home=normalized(home),away=normalized(away),
              home_label=home,away_label=away,hg=int(row['FTHG']),ag=int(row['FTAG']),
              hc=count('HC'),ac=count('AC')))
        except (ValueError,KeyError,AttributeError):continue
    return matches
def enrich_season(matches,season,errors):
    by=collections.defaultdict(list)
    for m in matches:by[m['league']].append(m)
    for lg in DIVS:
        try:
            rows=csv_season(lg,season)
            if len(rows)<max(30,len(by[lg])*.65):raise ValueError('CSV coverage too small: '+str(len(rows)))
            if len(rows)>len(by[lg])*1.20:by[lg]=rows
            else:
                idx={(m['date'],m['home'],m['away']):m for m in rows}
                for m in by[lg]:
                    found=idx.get((m['date'],m['home'],m['away']))
                    if found:m['hc'],m['ac']=found['hc'],found['ac']
        except Exception as e:
            errors.append({'league':lg,'season':season,'source':'independent CSV',
             'error':str(e)[:120]})
    return [m for rows in by.values() for m in rows]

def get_season(season,mandatory=False):
    matches=[];errors=[];coverage={}
    for lg,(repo,pat) in SOURCES.items():
        try:
            rows=parse_openfootball(fetch(BASE+repo+'/master/'+pat.format(s=season)),lg,season)
            if not rows:raise ValueError('parsed zero results')
            matches+=rows;coverage[lg]=len(rows)
        except Exception as exc:
            coverage[lg]=0;errors.append({'league':lg,'season':season,'error':str(exc)[:125]})
    try:
        rows=read_ucl(season)
        if not rows:raise ValueError('parsed zero UCL scores')
        matches+=rows;coverage[UCL]=len(rows)
    except Exception as exc:
        coverage[UCL]=0
        if season=='2026-27':
            try:
                rows=current_ucl_fallback()
                matches+=rows;coverage[UCL]=len(rows)
            except Exception as fallback:
                errors.append({'league':UCL,'season':season,'error':str(exc)[:95],
                               'fallback_error':str(fallback)[:95]})
        else:errors.append({'league':UCL,'season':season,'error':str(exc)[:125]})
    matches=enrich_season(matches,season,errors)
    coverage.update({lg:sum(m['league']==lg for m in matches) for lg in SOURCES})
    # guard against mistakenly treating incomplete snapshots as full seasons
    if mandatory and (any(not coverage.get(lg) for lg in list(SOURCES)+[UCL]) or len(matches)<1700):
        raise RuntimeError('Required source coverage missing: '+str(coverage)+' errors='+str(errors))
    matches.sort(key=lambda m:(m['date'],m['league'],m['home'],m['away']))
    return matches,coverage,errors
def team_games(team,competition,history):
    return [m for m in history if m['league']==competition and team in (club(m['home']),club(m['away']))]
def outcomes_for(team,games):
    d=[]
    for m in games:
        mine=club(m['home'])==team
        gf=m['hg'] if mine else m['ag'];ga=m['ag'] if mine else m['hg']
        d.append((gf,ga,mine))
    return d
def venue_and_form(t,lg,history,is_home):
    games=outcomes_for(club(t),team_games(club(t),lg,history))
    recent=games[-5:]
    earlier=games[-11:-5]
    venues=[x for x in games if x[2]==is_home][-8:]
    def diff(rows):return statistics.mean(a-b for a,b,_ in rows) if rows else 0
    def unbeaten(rows):return sum(a>=b for a,b,_ in rows)/len(rows) if rows else .5
    return {'last_n':len(recent),'recent_diff':diff(recent),'earlier_diff':diff(earlier),
      'venue_n':len(venues),'venue_unbeaten':unbeaten(venues),'venue_gf':statistics.mean(x[0] for x in venues) if venues else None,
      'venue_ga':statistics.mean(x[1] for x in venues) if venues else None,
      'n_total':len(games),'gf':statistics.mean(x[0] for x in games[-10:]) if games else None,
      'ga':statistics.mean(x[1] for x in games[-10:]) if games else None}
def clamp(x,a,b):return min(b,max(a,x))
def enhanced(m,history,prior_ucl):
    # Base forecast always comes from pre-kickoff result history.
    base=forecast(m,history)
    h=club(m['home']);a=club(m['away']);comp=m['league']
    hs=venue_and_form(h,comp,history,True)
    ass=venue_and_form(a,comp,history,False)
    htrend=clamp((hs['recent_diff']-hs['earlier_diff']) if hs['last_n']>=4 and hs['n_total']>=8 else 0,-2.5,2.5)
    atrend=clamp((ass['recent_diff']-ass['earlier_diff']) if ass['last_n']>=4 and ass['n_total']>=8 else 0,-2.5,2.5)
    # Venue-specific unbeaten history: a modest shrinkage, not a hard win rate.
    hw=clamp(hs['venue_n']/8,0,1)
    aw=clamp(ass['venue_n']/8,0,1)
    venue_edge=clamp((hs['venue_unbeaten']-.60)*hw-(ass['venue_unbeaten']-.42)*aw,-.55,.55)
    lh=base['lh']*math.exp(clamp(.075*htrend-.045*atrend+.15*venue_edge,-.22,.22))
    la=base['la']*math.exp(clamp(.075*atrend-.045*htrend-.15*venue_edge,-.22,.22))
    ucl_n=[0,0];league_hint=None
    if comp==UCL:
        # No mixing a team's Champions League goal rate with its domestic rate
        # as though the opponents were interchangeable; both get bounded weight.
        hg=outcomes_for(h,team_games(h,UCL,history))[-8:]
        ag=outcomes_for(a,team_games(a,UCL,history))[-8:]
        ucl_n=[len(hg),len(ag)]
        def expected(rows,metric):
            return statistics.mean(row[metric] for row in rows) if rows else None
        def blend(old,gf,oppga,n1,n2):
            if gf is None or oppga is None:return old
            raw=math.sqrt(max(.2,gf)*max(.2,oppga))
            evidence=min(n1,n2)
            weight=min(.55,evidence/(evidence+8))
            # Only modest competition shift when sample is small.
            return old*(1-weight)+clamp(raw,.3,3.9)*weight
        lh=blend(lh,expected(hg,0),expected(ag,1),len(hg),len(ag))
        la=blend(la,expected(ag,0),expected(hg,1),len(ag),len(hg))
    lh=clamp(lh,.23,4.3);la=clamp(la,.23,4.3)
    return {'lh':lh,'la':la,'p':poisson_markets(lh,la),'context':{
      'home':hs,'away':ass,'ucl_samples':ucl_n,'venue_edge':round(venue_edge,3),
      'home_form_delta':round(htrend,3),'away_form_delta':round(atrend,3)}}
def corner_estimate(m,history):
    lg=m['league']
    if lg==UCL:return None
    def team(t):
        rows=[x for x in history if x['league']==lg and t in (x['home'],x['away']) and x['hc'] is not None and x['ac'] is not None][-15:]
        if len(rows)<4:return None
        own=[x['hc'] if x['home']==t else x['ac'] for x in rows]
        conceded=[x['ac'] if x['home']==t else x['hc'] for x in rows]
        return ((sum(own)+4.6*6)/(len(rows)+6),(sum(conceded)+4.6*6)/(len(rows)+6))
    h=team(m['home']);a=team(m['away'])
    if h is None or a is None:return None
    mean=clamp((h[0]+a[1]+a[0]+h[1])/2,4,16)
    return 1-sum(poiss(k,mean) for k in range(9))
def score_measures(rows):
    if not rows:return {'n':0}
    n=len(rows)
    def avg(k):return round(sum(x[k] for x in rows)/n,5)
    return {'n':n,'brier':avg('brier'),'log_loss':avg('log_loss'),
     'accuracy':round(sum(x['hit'] for x in rows)/n,4),
     'correct':sum(x['hit'] for x in rows),
     'over25_brier':avg('over25_brier'),'btts_brier':avg('btts_brier'),
     'home_goal_mae':avg('home_goal_mae'),'away_goal_mae':avg('away_goal_mae'),
     'corner_over85':{'n':sum(x.get('corner_brier') is not None for x in rows),
        'brier':round(statistics.mean(x['corner_brier'] for x in rows if x.get('corner_brier') is not None),5) if any(x.get('corner_brier') is not None for x in rows) else None}}
def other_markets(lh,la):
    # Poisson independent-goal baseline, cap at 11 with tail retained.
    hp=[poiss(k,lh) for k in range(12)]
    ap=[poiss(k,la) for k in range(12)]
    over=0;kg=0
    for h,x in enumerate(hp):
      for a,y in enumerate(ap):
        if h+a>=3:over+=x*y
        if h>0 and a>0:kg+=x*y
    return over,kg
def row(m,pred,name,corner_probability=None):
    truth=outcome(m);p=pred['p'];guess=max(range(3),key=lambda i:p[i])
    over,kg=other_markets(pred['lh'],pred['la'])
    return {'date':m['date'],'league':m['league'],'home':m['home_label'],'away':m['away_label'],
      'actual':str(m['hg'])+'-'+str(m['ag']),'predicted':guess,'truth':truth,
      'probs':[round(z,5) for z in p],'brier':brier(p,truth),'log_loss':logloss(p,truth),
      'hit':int(guess==truth),'over25_brier':(over-int(m['hg']+m['ag']>=3))**2,
      'btts_brier':(kg-int(m['hg']>0 and m['ag']>0))**2,
      'home_goal_mae':abs(pred['lh']-m['hg']),'away_goal_mae':abs(pred['la']-m['ag']),
      'corner_brier':(corner_probability-int(m['hc']+m['ac']>=9))**2 if corner_probability is not None and m['hc'] is not None and m['ac'] is not None else None,
      'risk':'upset' if guess!=truth and max(p)>=.5 else 'ordinary',
      'context':pred.get('context',{})}
def evaluate(tests,initial):
    # Day batching: no match is ever used to predict another fixture on same date.
    history=initial[:];ledger=[];candidates=[];start=0
    for day,group_iter in __import__('itertools').groupby(tests,key=lambda x:x['date']):
        group=list(group_iter)
        for m in group:
            original=forecast(m,history)
            candidate=enhanced(m,history,initial)
            cp=corner_estimate(m,history)
            ledger.append(row(m,original,'baseline',cp))
            candidates.append(row(m,candidate,'context',cp))
        history.extend(group)
    return ledger,candidates
def seasons_context(prior,current):
    # Only match-level observations, not individual player performance.
    history=prior+current
    out={}
    clubs={(m['league'],club(t)) for m in current for t in (m['home'],m['away'])}
    for lg,t in sorted(clubs):
        form=venue_and_form(t,lg,history,True)
        away=venue_and_form(t,lg,history,False)
        # Store current-season-only competition aggregates separately for UCL.
        latest=[m for m in current if m['league']==lg and club(t) in (club(m['home']),club(m['away']))]
        rates=outcomes_for(t,latest)
        record={'competition':lg,'team':t,'matches_current':len(rates),
            'last5':form['last_n'],'last5_goal_difference':round(form['recent_diff'],3),
            'prior6_goal_difference':round(form['earlier_diff'],3),
            'home_unbeaten':round(form['venue_unbeaten'],3),'home_matches':form['venue_n'],
            'away_unbeaten':round(away['venue_unbeaten'],3),'away_matches':away['venue_n'],
            'current_gf':round(statistics.mean(x[0] for x in rates),3) if rates else None,
            'current_ga':round(statistics.mean(x[1] for x in rates),3) if rates else None}
        out.setdefault(t,{})[lg]=record
    return out
def run():
    train,traincov,old_errors=get_season('2024-25',mandatory=True)
    season,coverage,errors=get_season('2025-26',mandatory=True)
    current,currcov,errcurrent=get_season('2026-27')
    today=dt.datetime.now(dt.timezone.utc).date().isoformat()
    current=[x for x in current if x['date']<today]
    previous,experimental=evaluate(season,train)
    future_ref,future_candidate=evaluate(current,train+season) if current else ([],[])
    byleague={lg:{
      'baseline':score_measures([x for x in previous if x['league']==lg]),
      'context':score_measures([x for x in experimental if x['league']==lg]),
      'home_upsets':sum(x['truth']==2 and x['predicted']==0 for x in experimental if x['league']==lg),
      'draw_surprises':sum(x['truth']==1 and x['predicted']!=1 for x in experimental if x['league']==lg)}
      for lg in list(SOURCES)+[UCL]}
    old=score_measures(previous);new=score_measures(experimental)
    later0=score_measures(future_ref);later1=score_measures(future_candidate)
    accepted=bool(later0['n']>=100 and new['brier']<=old['brier'] and later1['brier']<later0['brier'])
    missed=[x for x in experimental if not x['hit']]
    biggest=sorted(missed,key=lambda x:x['brier'],reverse=True)[:20]
    high_score=[x for x in experimental if sum(map(int,x['actual'].split('-')))>=5]
    report={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'season_train':'2024-25',
       'season_test':'2025-26','competitions':list(SOURCES)+[UCL],
       'coverage':{'train':traincov,'full_season':coverage,'independent_2026_27':currcov},
       'complete_test_matches':len(season),'season_metrics':{'existing_simple_baseline':old,'context_candidate':new},
       'independent_2026_27':{'baseline':later0,'candidate':later1,'n':len(current)},
       'per_competition':byleague,
       'discovered_mistake_patterns':{
         'underdog_away_wins_missed':sum(x['truth']==2 and x['predicted']==0 for x in experimental),
         'draws_not_top_pick':sum(x['truth']==1 and x['predicted']!=1 for x in experimental),
         'five_plus_goal_matches':len(high_score),
         'five_plus_goal_model_home_mae':round(statistics.mean(x['home_goal_mae'] for x in high_score),3) if high_score else None,
         'upsets_when_favourite_over_60_percent':sum(x['risk']=='upset' and max(x['probs'])>=.60 for x in experimental)},
       'biggest_errors':biggest,
       'deployment':{'recommend_context_model':accepted,
          'rule':'Only promote if both full 2025/26 and independent 2026/27 Brier improve.',
          'ui_engine_updated':False,
          'commentary_data_only':True},
       'data_limits':['2025/26 Champions League uses openfootball league/knockout stages, no qualifiers; penalty/extra-time results excluded',
       'No verified per-player event/lineup/injury/coaching history in these match-score files',
       'Corners are independently joined from historical CSV only when verified; missing corners are not invented',
       'Historical match results are only visible AFTER each game for all subsequent dates; no same-day leakage',
       'This is NOT full validation of the browser two-half 100k Monte Carlo engine; independent league score model'],
       'source_errors':old_errors+errors+errcurrent}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'model_learning_full.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    forms=seasons_context(season,current)
    (OUT/'competition_form.json').write_text(json.dumps({'generated_utc':report['created_utc'],
       'season':'2026-27','teams':forms,
       'note':'Competition-specific results / form only; no invented player data or injuries.'},ensure_ascii=False),encoding='utf-8')
    print('FUTSIM FULL LEARNING:',json.dumps({'matches_2025_26':len(season),'by_league':coverage,
      'baseline':old,'candidate':new,'independent_baseline':later0,
      'independent_candidate':later1,'promote':accepted},ensure_ascii=False))
if __name__=='__main__':run()
