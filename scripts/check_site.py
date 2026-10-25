#!/usr/bin/env python3
"""Build-breaking invariants and JavaScript syntax checks (no fake browser claim)."""
import datetime as dt,json,pathlib,re,subprocess,sys
BASE=pathlib.Path(__file__).resolve().parents[1]
page=(BASE/'docs/index.html').read_text(encoding='utf-8')
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script\s*>',page,re.I|re.S)
if not scripts:raise RuntimeError('No inline JavaScript found')
for i,src in enumerate(scripts):
    if not src.strip():continue
    outcome=subprocess.run(['node','--check'],input=src,text=True,capture_output=True)
    if outcome.returncode:raise RuntimeError(f'JavaScript block {i} invalid: '+outcome.stderr[-1400:])
data=json.loads((BASE/'docs/data/snapshot.json').read_text(encoding='utf-8'))
if len(data.get('teams',[]))<100:raise RuntimeError('Insufficient teams in published snapshot')
leagues={x['league'] for x in data['teams']}
for required in ('Serie A','Ligue 1','Eredivisie','Premier League','Bundesliga','La Liga','Süper Lig'):
    if required not in leagues:raise RuntimeError('Missing requested league: '+required)
for fixture in data.get('upcoming',[]):
    if not fixture.get('date') or not fixture.get('hid') or not fixture.get('aid'):
        raise RuntimeError('Fixture without validated IDs and date')
v=json.loads((BASE/'docs/data/model_validation.json').read_text(encoding='utf-8'))
if v.get('iterations',0)<100:raise RuntimeError('Insufficient real match tests')
if v.get('corners',{}).get('n',0)<100:raise RuntimeError('Insufficient independent corner tests')
if v['model_metrics']['n']!=v['iterations']:raise RuntimeError('Backtest reported inconsistent count')
print(f'FUTSIM SITE CHECK OK: {len(scripts)} JS blocks, {len(data["teams"])} teams, {len(leagues)} leagues, {v["iterations"]} matches, {v["corners"]["n"]} corner tests')
