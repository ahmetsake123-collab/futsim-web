#!/usr/bin/env python3
"""SECOND disjoint 500-game chronological walk-forward test.
2024/25 -> 2025/26, distinct from original 2026/27 test.
Tuning updates only after earlier calendar dates. Not a backtest of browser MC UI.
"""
import collections,datetime as dt,json,math,statistics
from validate_walkforward import (SOURCES,BASE,fetch,parse_openfootball,forecast,
                                   poisson_markets,choose_temp,brier,logloss,metrics,outcome)
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/data/validation_second500.json'
def run():
    previous=[];holdout=[];errors=[]
    for league,(repo,pattern) in SOURCES.items():
        for season,target in [('2024-25',previous),('2025-26',holdout)]:
            try:
                url=f'{BASE}{repo}/master/{pattern.format(s=season)}'
                got=parse_openfootball(fetch(url),league,season)
                if not got:raise RuntimeError('no completed fixtures parsed')
                target.extend(got)
            except Exception as ex:errors.append(f'{league} {season}: {type(ex).__name__}')
    if len(previous)<300 or len(holdout)<500:
        raise RuntimeError(f'Not enough actual matches for independent second 500: {len(previous)} prior, {len(holdout)} target. {errors}')
    previous.sort(key=lambda x:(x['date'],x['league']))
    holdout.sort(key=lambda x:(x['date'],x['league'],x['home']))
    ledger=[];finished=[];past_predictions=[];pending=[];temp=1.
    hf=1.;af=1.;last_day=None
    for i,m in enumerate(holdout[:500]):
        if last_day and m['date']!=last_day:
            for raw,truth,hg,ag,lh,la in pending:
                past_predictions.append({'raw':raw,'truth':truth})
                hf=max(.89,min(1.12,hf*.99+.01*max(.75,min(1.25,hg/max(.5,lh)))))
                af=max(.89,min(1.12,af*.99+.01*max(.75,min(1.25,ag/max(.5,la)))))
            temp=choose_temp(past_predictions)
            pending=[]
        last_day=m['date']
        history=previous+[x for x in finished if x['date']<m['date']]
        p=forecast(m,history,hf,af,temp)
        y=outcome(m);guess=max(range(3),key=lambda a:p['p'][a])
        loss=brier(p['p'],y)
        row={'i':i+1,'date':m['date'],'league':m['league'],'home':m.get('home_label',m['home']),
             'away':m.get('away_label',m['away']),'actual':f"{m['hg']}-{m['ag']}",
             'guess':guess,'truth':y,'probs':[round(z,4) for z in p['p']],
             'brier':loss,'log_loss':logloss(p['p'],y),'predicted':guess,'confidence':p['p'][guess],
             'type':('correct' if guess==y else 'unexpected_away' if y==2 and guess==0 else
                'draw_undervalued' if y==1 and guess!=1 else 'unexpected_home' if y==0 and guess==2 else 'other_miss'),
             'min_sample':p['min_sample']}
        ledger.append(row);finished.append(m)
        pending.append((poisson_markets(p['lh'],p['la']),y,m['hg'],m['ag'],p['lh'],p['la']))
    baseline=[{'brier':brier([.43,.27,.30],x['truth']),
               'log_loss':logloss([.43,.27,.30],x['truth']),
               'predicted':0,'truth':x['truth']} for x in ledger]
    perleague={}
    for lg in SOURCES:
        a=[x for x in ledger if x['league']==lg]
        if a:perleague[lg]=metrics(a)
    misses=[x for x in ledger if x['guess']!=x['truth']]
    counts=dict(collections.Counter(x['type'] for x in ledger))
    # Classifier error versus probabilistic calibration are DIFFERENT.
    # A 25% draw frequency does not imply draw probabilities were underforecast
    # unless the aggregate predicted probability is below the observed rate.
    calibration={
        lab:{'predicted_average':round(sum(row['probs'][idx] for row in ledger)/len(ledger),4),
             'observed_rate':round(sum(row['truth']==idx for row in ledger)/len(ledger),4)}
        for idx,lab in enumerate(('home','draw','away'))
    }
    by_sample={
        'fewer_than_5':metrics([x for x in ledger if x['min_sample']<5]),
        '5_to_9':metrics([x for x in ledger if 5<=x['min_sample']<10]),
        '10_or_more':metrics([x for x in ledger if x['min_sample']>=10])}
    biggest_favorites=[x for x in misses if x['confidence']>=.60]
    poor=sorted(misses,key=lambda x:x['brier'],reverse=True)[:12]
    overconf=[x for x in ledger if x['confidence']>=.55]
    report={'period_train':'2024/25','period_test':'2025/26','run_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'disjoint_from_original_2026_27':True,'n':len(ledger),
        'training_available':len(previous),'holdout_available':len(holdout),
        'metrics':metrics(ledger),'baseline':metrics(baseline),
        'per_league':perleague,'calibration_by_outcome':calibration,
        'performance_by_minimum_sample':by_sample,
        'big_favorite_wrong_count':len(biggest_favorites),'mistake_types':counts,
        'wrong':len(misses),'highest_errors':poor,
        'overconfidence':{'n':len(overconf),'correct':sum(x['guess']==x['truth'] for x in overconf),
          'mean_confidence':round(statistics.mean(x['confidence'] for x in overconf),4) if overconf else None,
          'actual_accuracy':round(sum(x['guess']==x['truth'] for x in overconf)/len(overconf),4) if overconf else None},
        'caveats':['Categories describe what went wrong numerically; they DO NOT prove why a team won',
            'No fixture, injury, xG, xA or postmatch info from 2025/26 is leaked into forecasts',
            'This is a separate simple test model, not validation of site Monte Carlo predictions',
            'Baseline is a fixed home/draw/away probability not an optimized bookmaker benchmark'],
        'errors':errors,'examples':ledger[:3]+ledger[-4:]}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SECOND 500 WALK-FORWARD:',json.dumps({
        'n':report['n'],'training':len(previous),'correct':report['metrics']['correct'],
        'accuracy':report['metrics']['accuracy'],'brier':report['metrics']['brier'],
        'baseline_brier':report['baseline']['brier'],'mistakes':counts},ensure_ascii=False))
if __name__=='__main__':run()
