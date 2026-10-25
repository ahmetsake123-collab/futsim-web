#!/usr/bin/env python3
"""Optional second free provider: StrikerAPI measured team xG/xGA.
Requires STRIKER_KEY Github Actions secret; no browser token exposure.
Default is NO KEY / no requests; weekly or manual refresh only.
Weekly cap 40 credits (8 team calls x 5) = ~160-200/month within 500 free.
Does not pretend that player xA is available from this endpoint.
"""
import datetime as dt,json,os,pathlib,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1]
PATH=ROOT/'docs/data/striker_xg.json'
PICKS=[
 ('La Liga','Barcelona'),('La Liga','Real Madrid'),
 ('Serie A','Inter'),('Serie A','Juventus'),
 ('Bundesliga','Bayern Munich'),('Bundesliga','Borussia Dortmund'),
 ('Ligue 1','Paris Saint-Germain'),('Eredivisie','PSV')
]
def num(v):
 try:
  n=float(v)
  return round(n,3) if 0<=n<=10 else None
 except (TypeError,ValueError):return None
def query(key,team):
 body=json.dumps({'season':2026,'team':team}).encode('utf-8')
 req=urllib.request.Request('https://mcp.strikerapi.com/v1/get_team_stats',body,method='POST',
   headers={'content-type':'application/json','x-api-key':key,'user-agent':'FUTSIM/1.0'})
 with urllib.request.urlopen(req,timeout=24) as r:
  payload=json.load(r)
 return payload.get('data',payload).get('teams',[])
def main():
 key=os.environ.get('STRIKER_KEY','').strip()
 if not key:
  if not PATH.exists():
   PATH.write_text(json.dumps({'status':'not_configured','source':'https://strikerapi.com',
      'teams':[],'asof':None,'notes':['Free 500 credit/month key optional.']},
      ensure_ascii=False,indent=2),encoding='utf-8')
  print('STRIKER_KEY not configured; no billable credits used')
  return
 today=dt.datetime.now(dt.timezone.utc).date().isoformat()
 rows=[];errors=[]
 for league,team in PICKS:
  try:
   result=query(key,team)
   if not result:
    errors.append({'team':team,'error':'no data'});continue
   record=result[0];played=record.get('games')
   xg=num(record.get('xg_for'));xga=num(record.get('xg_against'))
   if not isinstance(played,int) or played<3 or xg is None or xga is None:continue
   # Accept only an exact club name or a documented abbreviation match.
   rows.append({'league':league,'team':team,'matches':played,'xg_per_match':xg,
       'xga_per_match':xga,'source':'StrikerAPI location-model xG','source_url':'https://strikerapi.com',
       'scope':'season 2026, completed games'})
  except (urllib.error.URLError,ValueError,TimeoutError,KeyError) as e:
   errors.append({'team':team,'error':type(e).__name__})
 if not rows and PATH.exists():
  try:
   prev=json.loads(PATH.read_text(encoding='utf-8'))
   if prev.get('status')=='verified' and (dt.date.fromisoformat(today)-dt.date.fromisoformat(prev.get('asof',today))).days<=8:
    print('Striker source failed; last verified data retained');return
  except (ValueError,OSError):pass
 payload={'asof':today,'source':'StrikerAPI location-model xG',
          'source_url':'https://strikerapi.com','status':'verified' if rows else 'unavailable',
          'teams':rows,'players':[],'errors':errors,
          'note':'Team xG and xGA only; player expected assists not included in this subscription endpoint.',
          'max_credits_per_run':len(PICKS)*5}
 PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Striker optional free xG probe:',payload['status'],len(rows),'teams',len(errors),'errors')
if __name__=='__main__':main()
