#!/usr/bin/env python3
"""Weekly public CC-BY data-lake import: team xG/xGA only if actually covered.
The source itself warns values are coarse shot-zone estimates, not event-level xG.
Match xG=0 is valid ONLY if the provider marked the fixture xg_covered=True.
Fixture dates must fall inside 2026/27 completed league season and before today.
No API key needed. No player statistics or betting odds copied.
"""
import collections,datetime as dt,json,pathlib,tempfile,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/data/hf_xg.json'
BASE='https://huggingface.co/datasets/eatpizzanot/soccer-dataset/resolve/main/'
FILENAMES=('fixtures','match_stats','teams','leagues')
def safe(v):
 try:
  n=float(v)
  return n if 0<=n<=6 else None
 except (TypeError,ValueError):return None
def state(reason):
 # Fallback preserves recently verified previous data.
 if DEST.exists():
  try:
   x=json.loads(DEST.read_text(encoding='utf-8'))
   if x.get('status')=='verified':print('HuggingFace xG unavailable, keeping last verified snapshot: '+reason);return
  except (ValueError,OSError):pass
 DEST.write_text(json.dumps({'status':'unavailable','reason':reason,'teams':[],'source':BASE},ensure_ascii=False),encoding='utf-8')
def run():
 try:import pyarrow.parquet as pq
 except ImportError:return state('pyarrow unavailable')
 try:
  with tempfile.TemporaryDirectory() as tmp:
   refs={}
   for fn in FILENAMES:
    dest=pathlib.Path(tmp)/(fn+'.parquet')
    req=urllib.request.Request(BASE+fn+'.parquet',headers={'User-Agent':'FUTSIMResearch/1.0'})
    with urllib.request.urlopen(req,timeout=55) as response, dest.open('wb') as out:
     total=0
     while True:
      buf=response.read(1024*512)
      if not buf:break
      total+=len(buf)
      if total>25000000:raise ValueError('unexpected dataset size for '+fn)
      out.write(buf)
    refs[fn]=dest
   tmap={x['id']:x['name'] for x in pq.read_table(refs['teams'],columns=['id','name']).to_pylist()}
   leagues={x['id']:(str(x['name']),str(x.get('country') or ''))
           for x in pq.read_table(refs['leagues'],columns=['id','name','country']).to_pylist()}
   targets={'Premier League':'Premier League','Bundesliga':'Bundesliga','La Liga':'La Liga',
             'Serie A':'Serie A','Ligue 1':'Ligue 1','Eredivisie':'Eredivisie','Süper Lig':'Süper Lig'}
   def match_league(n,c):
    n=n.casefold();c=c.casefold()
    if 'premier league' in n and ('england' in c or 'eng'==c):return 'Premier League'
    if 'bundesliga' in n and ('germany' in c or 'ger'==c) and '2.' not in n:return 'Bundesliga'
    if 'la liga' in n and ('spain' in c or 'esp'==c):return 'La Liga'
    if 'serie a' in n and ('italy' in c or 'ita'==c):return 'Serie A'
    if 'ligue 1' in n and ('france' in c or 'fra'==c):return 'Ligue 1'
    if 'eredivisie' in n:return 'Eredivisie'
    if 'super lig' in n or 'süper lig' in n:return 'Süper Lig'
    return None
   wanted={x:match_league(*v) for x,v in leagues.items()}
   wanted={k:v for k,v in wanted.items() if v}
   if not wanted:return state('source league IDs not recognized')
   now=dt.datetime.now(dt.timezone.utc).date()
   start=dt.date(2026,7,1);fixtures={}
   for batch in pq.ParquetFile(refs['fixtures']).iter_batches(columns=['id','league_id','home_team_id','away_team_id','date_utc','is_played'],batch_size=20000):
    for row in batch.to_pylist():
     if row['league_id'] not in wanted or not row['is_played']:continue
     date=row['date_utc']
     if not date:continue
     day=date.date() if isinstance(date,dt.datetime) else date
     if not start<=day<now:continue
     fixtures[row['id']]=(wanted[row['league_id']],row['home_team_id'],row['away_team_id'],day)
   if not fixtures:return state('no completed current-season fixtures in source')
   stats=collections.defaultdict(lambda:{'games':0,'xg':0.,'xga':0.,'last':None})
   for batch in pq.ParquetFile(refs['match_stats']).iter_batches(columns=['fixture_id','home_xg','away_xg','xg_covered'],batch_size=20000):
    for row in batch.to_pylist():
     fix=fixtures.get(row['fixture_id'])
     if not fix or row.get('xg_covered') is not True:continue
     hg=safe(row.get('home_xg'));ag=safe(row.get('away_xg'))
     if hg is None or ag is None:continue
     league,home,away,day=fix
     for ident,g,xga in ((home,hg,ag),(away,ag,hg)):
      name=tmap.get(ident)
      if not name:continue
      entry=stats[(league,name)]
      entry['games']+=1;entry['xg']+=g;entry['xga']+=xga
      if entry['last'] is None or day>entry['last']:entry['last']=day
   out=[]
   for (league,team),r in stats.items():
    if r['games']<3 or (now-r['last']).days>25:continue
    out.append({'league':league,'team':team,'matches':r['games'],
       'xg_per_match':round(r['xg']/r['games'],3),
       'xga_per_match':round(r['xga']/r['games'],3),
       'latest_fixture':r['last'].isoformat(),'kind':'coarse published shot-zone xG'})
   if not out:return state('source has no sufficiently recent team xG; not substituting zeros')
   payload={'status':'verified','source':'Global Football Data Lake (API-Football coarse zone xG)',
     'source_url':'https://huggingface.co/datasets/eatpizzanot/soccer-dataset',
     'asof':now.isoformat(),'teams':out,'players':[],'method':'CC-BY-4.0 compilation; upstream shot-zone approximation',
     'notes':['Values may underrepresent shot quality', 'Provider rights still apply','No inferred player xA']}
   DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
   print('HuggingFace team xG:',len(out),'teams',dict(collections.Counter(x['league'] for x in out)))
 except (urllib.error.URLError,TimeoutError,OSError,ValueError,KeyError,TypeError) as ex:
  state(type(ex).__name__+': '+str(ex)[:95])
if __name__=='__main__':run()
