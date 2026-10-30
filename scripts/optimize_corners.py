#!/usr/bin/env python3
"""FUTSIM honest corner-market experiment.
Train/choose using chronologically forecast 2025/26 outcomes; assess once on
disjoint 2026/27 games. Per-kickoff inputs contain only older dates.
A selection's holdout success is not sufficient to claim bettor profit.
"""
import collections,datetime as dt,itertools,json,math,pathlib,statistics
from train_full_season import get_season,UCL
from validate_walkforward import poiss
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/data/corner_experiment.json'
LEAGUES=['Premier League','Bundesliga','La Liga','Serie A','Ligue 1','Eredivisie','Süper Lig']
def clamp(x,a,b):return min(b,max(a,x))
def avg(xs):return sum(xs)/len(xs) if xs else None
def shrink(v,n,mu,k):
    return (n*v+k*mu)/(n+k) if v is not None and n else mu
def sigmoid(x):
    return 1/(1+math.exp(-clamp(x,-40,40)))
def logit(x):
    x=clamp(x,.004,.996);return math.log(x/(1-x))
def poisson_over(lam,k=8):
    p=math.exp(-lam);s=p
    for j in range(1,k+1):
        p*=lam/j;s+=p
    return clamp(1-s,.001,.999)
def nb_over(mu,var,k=8):
    # NB whose mean=mu and variance=var; use Poisson for no dispersion.
    if var<=mu*1.015:return poisson_over(mu,k)
    shape=clamp(mu*mu/(var-mu),.3,1000)
    p=(shape/(shape+mu))**shape;s=p
    for j in range(1,k+1):
        p*=((j-1+shape)/j)*(mu/(shape+mu));s+=p
    return clamp(1-s,.001,.999)
def observations(match,team,venue=None):
    home=match['home']==team
    if not(home or match['away']==team):return None
    if venue is not None and home!=venue:return None
    if match['hc'] is None or match['ac'] is None:return None
    return {'for':match['hc'] if home else match['ac'],
        'against':match['ac'] if home else match['hc'],
        'total':match['hc']+match['ac'],'over':int(match['hc']+match['ac']>=9)}
def stats(history,team,venue=None,window=12):
    xs=[o for match in history if (o:=observations(match,team,venue)) is not None][-window:]
    return {k:avg([x[k] for x in xs]) for k in ('for','against','total','over')}|{'n':len(xs)}
def derive(match,history):
    # History is limited to matches completed on EARLIER dates, same league.
    league=match['league']
    hm=[x for x in history if x['league']==league]
    totals=[x['hc']+x['ac'] for x in hm if x['hc'] is not None and x['ac'] is not None]
    last=totals[-200:]
    prio=(sum(x>=9 for x in last)+6)/(len(last)+12)
    mean=avg(last) if last else 9.3
    var=avg([(x-mean)**2 for x in last]) if last else 10.5
    h,a=match['home'],match['away']
    return {'league':league,'prior':prio,'n_prior':len(last),'mu':mean,'variance':var,
     'line_priors':{str(k):(sum(v>k for v in last)+6)/(len(last)+12) for k in (7,8,9,10)},
     'h_all':stats(hm,h,window=15),'a_all':stats(hm,a,window=15),
     'h_home':stats(hm,h,True,10),'a_away':stats(hm,a,False,10),
     'h_last5':stats(hm,h,window=5),'a_last5':stats(hm,a,window=5)}
def features(f,param):
    hs=f['h_all'];as_=f['a_all'];hv=f['h_home'];av=f['a_away']
    mu=f['mu']
    k=param['shrink']
    home_for=shrink(hs['for'],hs['n'],mu/2,k)
    home_con=shrink(hs['against'],hs['n'],mu/2,k)
    away_for=shrink(as_['for'],as_['n'],mu/2,k)
    away_con=shrink(as_['against'],as_['n'],mu/2,k)
    venue=param['venue']
    vh=shrink(hv['for'],hv['n'],home_for,5)
    vha=shrink(hv['against'],hv['n'],home_con,5)
    va=shrink(av['for'],av['n'],away_for,5)
    vac=shrink(av['against'],av['n'],away_con,5)
    h=venue*vh+(1-venue)*home_for
    ac=venue*vac+(1-venue)*away_con
    a=venue*va+(1-venue)*away_for
    hc=venue*vha+(1-venue)*home_con
    expected=(h+ac+a+hc)/2
    if param['recent']:
        h5=f['h_last5'];a5=f['a_last5']
        if h5['n']>=3 and a5['n']>=3:
            recent=(h5['for']+a5['against']+a5['for']+h5['against'])/2
            expected=expected*(1-param['recent'])+recent*param['recent']
    return clamp(expected,4.0,17.0)
def predict(f,p):
    mean=features(f,p)
    method=p['method'];prior=f['prior'];raw=None
    if method=='prior':raw=prior
    elif method=='poisson':raw=poisson_over(mean)
    elif method=='nb':raw=nb_over(mean, max(mean+.1,f['variance']*(mean/max(1,f['mu']))**2))
    elif method=='logistic':raw=sigmoid(logit(prior)+(mean-f['mu'])*p['scale'])
    elif method=='league':raw=prior
    elif method=='team_over':
        h=f['h_all'];a=f['a_all']
        team=(shrink(h['over'],h['n'],prior,8)+shrink(a['over'],a['n'],prior,8))/2
        raw=clamp(team,0,1)
    elif method=='hybrid':
        logi=sigmoid(logit(prior)+(mean-f['mu'])*p['scale'])
        raw=.5*logi+.5*nb_over(mean,max(mean+.1,f['variance']))
    else:raise ValueError(method)
    return clamp(prior*(1-p['weight'])+raw*p['weight'],.03,.97)
def candidates():
    options=[{'method':'prior','shrink':10,'venue':0,'recent':0,'scale':.2,'weight':0}]
    for method,venue,k,recent,weight,scale in itertools.product(
       ('poisson','nb','logistic','hybrid','team_over','league'),
       (0,.5,1),(3,10,22),(0,.35),(.45,.8,1),(.18,.35)):
        if method=='league' and (venue or recent or k!=3 or weight!=1 or scale!=.18):continue
        if method=='team_over' and (venue or recent or scale!=.18):continue
        if method in ('poisson','nb') and scale!=.18:continue
        if method in ('logistic','hybrid') and weight==1 and recent==.35 and k==3:continue
        options.append({'method':method,'shrink':k,'venue':venue,'recent':recent,
            'scale':scale,'weight':weight})
    # remove duplicate predictions by construction
    seen=set();unique=[]
    for p in options:
        token=json.dumps(p,sort_keys=True)
        if token not in seen:seen.add(token);unique.append(p)
    return unique
def multithreshold_search(training,holdout,threshold):
    def guess(features,param):
        mu=features['mu'];mean=features_mean(features,param)
        prior=features['line_priors'][str(threshold)]
        if param['dist']=='poisson':raw=poisson_over(mean,threshold)
        elif param['dist']=='nb':
            raw=nb_over(mean,max(mean+.1,features['variance']*(mean/max(1,mu))**2),threshold)
        return clamp((1-param['weight'])*prior+param['weight']*raw,.02,.98)
    trials=[]
    for dist,venue,shrink_factor,recent,weight in itertools.product(
      ('poisson','nb'),(0,.5,1),(3,10,22),(0,.35),(.3,.65,1)):
        p={'method':'poisson','dist':dist,'venue':venue,'shrink':shrink_factor,
          'recent':recent,'weight':weight,'scale':.2}
        tr=[dict(x,y=int(x['total']>threshold)) for x in training]
        pp=[guess(x['f'],p) for x in tr]
        stats=stats_for(tr,pp)
        trials.append((stats['brier'],p,stats))
    trials.sort(key=lambda x:x[0])
    _,winner,train_stats=trials[0]
    hold=[dict(x,y=int(x['total']>threshold)) for x in holdout]
    chosen=[guess(x['f'],winner) for x in hold]
    old=[poisson_over(features_mean(x['f'],{'shrink':10,'venue':0,'recent':0}),threshold) for x in hold]
    league=[x['f']['line_priors'][str(threshold)] for x in hold]
    result={'threshold':threshold+.5,'trials':len(trials),'selection':winner,
      'training':train_stats,
      'holdout':{'selected':stats_for(hold,chosen),'old_poisson':stats_for(hold,old),
          'league_prior':stats_for(hold,league)}}
    z=result['holdout'];result['independent_improvement']=(
      z['selected']['brier']<min(z['old_poisson']['brier'],z['league_prior']['brier'])-.001
      and z['selected']['accuracy']>max(z['old_poisson']['accuracy'],
                                        z['selected']['constant_over_accuracy']))
    return result
def features_mean(f,param):
    return features(f,param)

def chronological_matches(season,initial):
    # One feature vector per match, exactly once, before its score is seen.
    history=[x for x in initial if x['hc'] is not None and x['ac'] is not None]
    rows=[]
    for day,it in itertools.groupby(season,key=lambda x:x['date']):
        batch=list(it)
        for match in batch:
            if match['league']==UCL:continue
            if match['hc'] is None or match['ac'] is None:continue
            fe=derive(match,history)
            if min(fe['h_all']['n'],fe['a_all']['n'])<4 or fe['n_prior']<20:continue
            rows.append({'date':match['date'],'league':match['league'],
              'home':match['home'],'away':match['away'],'total':match['hc']+match['ac'],
              'y':int(match['hc']+match['ac']>=9),'f':fe})
        # Include all matches that became known at end of day, even if not evaluated.
        history.extend(x for x in batch if x['hc'] is not None and x['ac'] is not None)
    return rows
def stats_for(rows,probs):
    n=len(rows)
    if not n:return {'n':0}
    labels=[x['y'] for x in rows]
    bs=[(p-y)**2 for p,y in zip(probs,labels)]
    signs=[int(p>=.5) for p in probs]
    good=sum(z==y for z,y in zip(signs,labels))
    over=sum(labels)
    eps=1e-8
    logs=[-(y*math.log(max(eps,p))+(1-y)*math.log(max(eps,1-p))) for p,y in zip(probs,labels)]
    return {'n':n,'correct':good,'accuracy':round(good/n,5),
     'brier':round(avg(bs),6),'log_loss':round(avg(logs),6),
     'predicted_overs':sum(signs),'observed_overs':over,
     'constant_over_accuracy':round(over/n,5),
     'majority_accuracy':round(max(over,n-over)/n,5),
     'prior_average':round(avg(probs),4)}
def byleague(rows,prob):
    return {lg:stats_for([r for r in rows if r['league']==lg],
        [p for r,p in zip(rows,prob) if r['league']==lg])
        for lg in LEAGUES}
def run():
    training,cov_old,e0=get_season('2024-25',True)
    sample,cov_sample,e1=get_season('2025-26',True)
    later,cov_later,e2=get_season('2026-27',False)
    today=dt.datetime.now(dt.timezone.utc).date().isoformat()
    later=[m for m in later if m['date']<today]
    x_train=chronological_matches(sample,training)
    x_hold=chronological_matches(later,training+sample)
    if len(x_train)<400 or len(x_hold)<100:raise RuntimeError('Insufficient real corner matches')
    cand=candidates()
    results=[]
    for p in cand:
        probs=[predict(x['f'],p) for x in x_train]
        met=stats_for(x_train,probs)
        results.append((met['brier'],met['log_loss'],p,met))
    results.sort(key=lambda x:(x[0],x[1]))
    best=results[0][2]
    # Holdout evaluated AFTER candidate is frozen. No re-selection using holdout.
    ptrain=[predict(x['f'],best) for x in x_train]
    phold=[predict(x['f'],best) for x in x_hold]
    # Old-site baseline: source data only current 12, simple independent Poisson.
    def old(x):
        h=x['f']['h_all'];a=x['f']['a_all']
        mu=(h['for']+a['against']+a['for']+h['against'])/2
        return poisson_over(clamp(mu,1,24))
    oldtrain=[old(x) for x in x_train];oldhold=[old(x) for x in x_hold]
    leaguebase=[x['f']['prior'] for x in x_hold]
    summary={'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'period_selection':'2025-26 chronological, prior 2024-25',
      'period_independent_holdout':'2026-27 chronological',
      'tested_candidates':len(cand)+3*108,
      'tested_candidates_8_5':len(cand),
      'selected_parameters':best,
      'training':{'selected':stats_for(x_train,ptrain),
         'old_poisson':stats_for(x_train,oldtrain),
         'league_prior':stats_for(x_train,[x['f']['prior'] for x in x_train])},
      'holdout':{'selected':stats_for(x_hold,phold),
         'old_poisson':stats_for(x_hold,oldhold),
         'league_prior':stats_for(x_hold,leaguebase)},
      'by_competition':{'selection':byleague(x_train,ptrain),'holdout':byleague(x_hold,phold)},
      'top_12_selection':[{'parameters':p,'metrics':m} for _,_,p,m in results[:12]],
      'data_source':'Football-Data historical corner columns, independent CC0 league results for scores',
      'limitations':['No prior-match outcome or matchday corners used for same-day prediction',
       'Same 8.5 threshold for all teams; no bookmaker prices or profitability claim',
       'Any 2025 model selection can overfit; 2026 data is evaluated only once',
       'Browser FUTSIM uses different data aggregation, so this experiment is not direct production performance',
       'No verified Champions League corner coverage in source.'],
      'additional_lines':{str(k+0.5):multithreshold_search(x_train,x_hold,k) for k in (7,9,10)},
      'sample_date_ranges':{'train':[x_train[0]['date'],x_train[-1]['date']],
        'holdout':[x_hold[0]['date'],x_hold[-1]['date']]},
      'coverage':{'2024-25':cov_old,'2025-26':cov_sample,'2026-27':cov_later},
      'errors':e0+e1+e2}
    c=summary['holdout']
    strong=(
      c['selected']['brier']<c['old_poisson']['brier']-.001 and
      c['selected']['brier']<c['league_prior']['brier']-.001 and
      c['selected']['accuracy']>c['old_poisson']['accuracy'] and
      c['selected']['accuracy']>c['selected']['constant_over_accuracy']
      and c['selected']['n']>=250)
    summary['deployment']={'eligible':bool(strong),
      'reason':'Promotion only if holdout Brier beats old+league baseline by >0.001 and accuracy beats old+always-over.',
      'deployed':False}
    OUT.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CORNERS EXPERIMENT:',json.dumps({'candidates':len(cand),'train':summary['training'],
       'holdout':c,'selected':best,'eligible':strong},ensure_ascii=False))
if __name__=='__main__':run()
