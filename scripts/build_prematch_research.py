#!/usr/bin/env python3
"""Headlines-only pre-match research snapshots for static GitHub Pages.
Sources are hints, NOT verified injury or manager claims. 7-day window.
"""
import datetime as dt
import email.utils
import json
import pathlib
import re
import urllib.parse
import xml.etree.ElementTree as ET
from validate_walkforward import fetch
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/'docs/data/snapshot.json'
DEST=ROOT/'docs/data/prematch_research.json'
def norm(s):
 import unicodedata
 s=''.join(x for x in unicodedata.normalize('NFKD',str(s).lower()) if not unicodedata.combining(x))
 return re.sub(r'[^a-z0-9]+',' ',s).strip()
def run():
 now=dt.datetime.now(dt.timezone.utc)
 d=json.loads(SOURCE.read_text(encoding='utf-8'))
 upcoming=[]
 for fixture in d.get('upcoming',[]):
  try:date=dt.date.fromisoformat(fixture['date'])
  except (KeyError,ValueError):continue
  if 0<=(date-now.date()).days<=7:upcoming.append(fixture)
 upcoming.sort(key=lambda f:f['date'])
 rows=[];errors=[]
 for fixture in upcoming[:14]:
  home,away=str(fixture['home']),str(fixture['away'])
  query=home+' '+away+' preview team news injuries coach lineup'
  url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'en','gl':'GB','ceid':'GB:en'})
  try:
   root=ET.fromstring(fetch(url))
   stories=[];seen=set()
   for item in root.findall('.//item')[:30]:
    title=(item.findtext('title') or '').strip()
    link=(item.findtext('link') or '').strip()
    src=(item.findtext('source') or '').strip() or 'Kaynak belirtilmedi'
    when=(item.findtext('pubDate') or '').strip()
    try:
     published=email.utils.parsedate_to_datetime(when)
     if published.tzinfo is None:published=published.replace(tzinfo=dt.timezone.utc)
    except Exception:continue
    # No post-match content, older than 10 days, or future content.
    if published.date()>dt.date.fromisoformat(fixture['date']) or published<now-dt.timedelta(days=10):continue
    simple=norm(title)
    # Both team names must be referenced; prevent unrelated headlines.
    if not (norm(home) in simple and norm(away) in simple):continue
    if not link.startswith('https://'):continue
    if src in seen:continue
    seen.add(src)
    keys={'injury':['injury','injured','sakat','fitness'],
      'coach':['coach','manager','teknik direkt','new boss'],
      'rotation':['rotation','rotasyon','lineup','first xi','starting xi'],
      'form':['form','winning','unbeaten','run','momentum']}
    tags=[k for k,terms in keys.items() if any(t in simple for t in terms)]
    stories.append({'headline':title[:260],'source':src[:90],
      'published_at':published.isoformat(),'url':link,'headline_tags':tags,
      'verification':'headline_only_not_confirmed'})
    if len(stories)>=8:break
   rows.append({'date':fixture['date'],'home':home,'away':away,
    'league':fixture.get('league'),'headline_count':len(stories),'headlines':stories})
  except Exception as exc:errors.append({'home':home,'away':away,'error':str(exc)[:140]})
 result={'fetched_at_utc':now.isoformat(),'source':'Google News RSS search headlines',
  'usage':'News headlines are not validated articles. Never modify winning probabilities or claim verified injuries using headlines alone.',
  'searched_matches':len(upcoming[:14]),'results':rows,'errors':errors}
 DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PREMATCH RESEARCH: '+json.dumps({'n':len(rows),'found':sum(x['headline_count'] for x in rows),
   'errors':len(errors)},ensure_ascii=False))
if __name__=='__main__':run()
