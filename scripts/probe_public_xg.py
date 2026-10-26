#!/usr/bin/env python3
"""One-time diagnostics ONLY, for a third-party public xG table.
Respects robots.txt. Never bypasses access restrictions or stores content.
"""
import urllib.request,urllib.robotparser,urllib.error,re
from html.parser import HTMLParser
HOST='https://statz.ai'
AGENT='FUTSIMResearch/1.0'
URL=HOST+'/competitions/super-lig/xg'
try:
 parser=urllib.robotparser.RobotFileParser()
 parser.set_url(HOST+'/robots.txt')
 parser.read()
 allowed=parser.can_fetch(AGENT,URL)
 print('STATZ_PUBLIC_XG_PROBE robots_allowed=',allowed)
 if allowed:
  req=urllib.request.Request(URL,headers={'User-Agent':AGENT,'Accept':'text/html'})
  with urllib.request.urlopen(req,timeout=18) as res:
   html=res.read(500000).decode('utf-8','replace')
  print('STATZ_PUBLIC_XG_PROBE html_bytes=',len(html),'tables=',html.lower().count('<table'),
        'xg_labels=',html.lower().count('xga'),'next_data=',html.count('__NEXT_DATA__'),
        'rsc_payload=',html.count('self.__next_f.push'),'has_galatasaray=',bool(re.search('Galatasaray',html,re.I)))
except (urllib.error.URLError,TimeoutError,OSError) as ex:
 print('STATZ_PUBLIC_XG_PROBE unavailable type=',type(ex).__name__)
