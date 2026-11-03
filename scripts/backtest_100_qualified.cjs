#!/usr/bin/env node
/* Last 100 actual coupon-day CURRENT FUTSIM daily 2.00 replay with sourced
   1X/12/X2, BTTS, 1.5/2.5/3.5 goal and match-winner odds. Same goalRates, simulate(100000),
   reconcileScoreOutcome, confidenceOf and live coupon chooser are reused.
   Missing market prices are NEVER invented. Corner odds not present in archive.
 */
'use strict';
const fs=require('fs'),vm=require('vm');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const output=process.argv[3];
const html=fs.readFileSync('docs/index.html','utf8');
const inline=html.split('</script><script>');
if(inline.length<4)throw Error('Cannot locate FUTSIM original engine');
const modelSrc=inline[2]+'\n'+inline[3].split('</script>')[0].replace(/\bbootV42\(\);\s*$/,'');
const dailySrc=fs.readFileSync('docs/daily-coupon.js','utf8');
const win={addEventListener(){},FUTSIM_API_FOOTBALL:{fixtures:[],details:{}}};
const doc={readyState:'loading',addEventListener(){},getElementById(){return null}};
const st={getItem(){return null},setItem(){},removeItem(){}};
const seededMath=Object.create(Math);let rngState=0x4f5211ab;
seededMath.random=()=>{rngState^=rngState<<13;rngState^=rngState>>>17;rngState^=rngState<<5;return (rngState>>>0)/4294967296;};
const scope={window:win,document:doc,localStorage:st,console:console,
 Date:Date,Intl:Intl,Math:seededMath,Number:Number,JSON:JSON,String:String,Array:Array,
 Object:Object,Map:Map,Set:Set,URL:URL,performance:{now:()=>0},fetch:()=>{throw Error('No online data allowed in replay')}};
vm.createContext(scope);
vm.runInContext(modelSrc+'\n'+
 'globalThis.BACKTEST_MODEL={goalRates,simulate,pattern,reconcileScoreOutcome,confidenceOf};'+
 'globalThis.setHistoricalTeams=(rows,date)=>{data={seed:false,asof:date,backtest:{status:"walk-forward"},teams:rows,upcoming:[]};teams=rows;byId=Object.fromEntries(rows.map(t=>[t.id,t]));};',
 scope,{timeout:30000});
vm.runInContext(dailySrc,scope,{timeout:30000});
const engine=scope.BACKTEST_MODEL,chooser=scope.window.FUTSIM_DAILY_DIAGNOSTICS;
if(!chooser?.choose||!chooser?.adjustedProbability)throw Error('Cannot load FUTSIM exact coupon chooser');
const PRIOR={'Premier League':1580,'Bundesliga':1550,'La Liga':1550,'Serie A':1530,
 'Ligue 1':1515,'Eredivisie':1480,'Süper Lig':1440};
const markKeys=['1','X','2','1X','12','X2','1,5 Üst','2,5 Üst','2,5 Alt','3,5 Alt','3,5 Üst','KG Var','KG Yok'];
const historicByTeam=new Map(),playedByTeam=new Map(),byDate=new Map();
const key=(lg,t)=>lg+'|'+String(t||'').toLowerCase();
const add=(book,m)=>{
 for(const team of [m.home,m.away]){
  const k=key(m.league,team);
  if(!book.has(k))book.set(k,[]);
  book.get(k).push(m);
 }
};
for(const m of input.last_season)add(historicByTeam,m);
for(const m of input.current){
 if(m.date>=input.window_start&&m.date<=input.window_end){
  if(!byDate.has(m.date))byDate.set(m.date,[]);
  byDate.get(m.date).push(m);
 }
}
function avg(vals){
 if(!vals.length)return null;
 return Math.round(vals.reduce((a,b)=>a+b,0)/vals.length*1000)/1000;
}
function compile(team,games){
 const arr=games.slice(-15).reverse();
 const subset=rows=>({
  matches:rows.length,
  gf:avg(rows.map(m=>m.home===team?m.hg:m.ag)),
  ga:avg(rows.map(m=>m.home===team?m.ag:m.hg)),
  raw_gf:avg(rows.map(m=>m.home===team?m.hg:m.ag)),
  raw_ga:avg(rows.map(m=>m.home===team?m.ag:m.hg)),
  points:avg(rows.map(m=>{
   let a=m.home===team?m.hg:m.ag,b=m.home===team?m.ag:m.hg;
   return a>b?3:a===b?1:0;
  })),
  form:rows.slice(0,6).map(m=>({date:m.date,opponent:m.home===team?m.away:m.home,
    gf:m.home===team?m.hg:m.ag,ga:m.home===team?m.ag:m.hg,h:m.home===team}))
 });
 const base=subset(arr);
 base.home=subset(arr.filter(m=>m.home===team));
 base.away=subset(arr.filter(m=>m.away===team));
 base.score_patterns={n:arr.length,ht_n:0};
 base.ucl_patterns={n:0,ht_n:0};
 return base;
}
function teamObject(league,name,season,date){
 const earlier=playedByTeam.get(key(league,name))||[];
 const games=earlier.filter(m=>m.season===season&&m.date<date);
 const priorSeason=season==='2627'?'2526':season==='2526'?'2425':null;
 const old=[...(historicByTeam.get(key(league,name))||[]),...earlier].filter(m=>m.season===priorSeason&&m.date<date);
 const stats=compile(name,games);
 const prior=compile(name,old);
 if(prior.matches)stats.last_season=prior;
 const n=stats.matches,p=stats.points==null?1.3:stats.points;
 const strength=Math.max(-140,Math.min(140,(p-1.3)*65+((stats.gf||0)-(stats.ga||0))*37));
 return {id:key(league,name),name,league,rating:Math.round(PRIOR[league]+strength*Math.min(n/12,1)),
   stats,competitions:[league],data_verified:true};
}
function impliedPrices(odds){
 const out={};
 for(const keys of [['1','X','2'],['1,5 Üst','1,5 Alt'],['2,5 Üst','2,5 Alt'],
                    ['3,5 Üst','3,5 Alt'],['KG Var','KG Yok']]){
  if(keys.every(k=>Number.isFinite(odds[k]))){
   const inv=keys.map(k=>1/odds[k]),sum=inv.reduce((a,b)=>a+b,0);
   keys.forEach((k,i)=>out[k]=inv[i]/sum);
  }
 }
 if(out['1']!=null&&out['X']!=null&&out['2']!=null){
  out['1X']=out['1']+out['X'];
  out['12']=out['1']+out['2'];
  out['X2']=out['X']+out['2'];
 }
 return out;
}
function pass(m,market){
 const g=m.hg+m.ag;
 switch(market){
  case '1':return m.hg>m.ag;
  case 'X':return m.hg===m.ag;
  case '2':return m.hg<m.ag;
  case '1X':return m.hg>=m.ag;
  case '12':return m.hg!==m.ag;
  case 'X2':return m.hg<=m.ag;
  case '1,5 Üst':return g>=2;
  case '2,5 Üst':return g>=3;
  case '2,5 Alt':return g<=2;
  case '3,5 Üst':return g>=4;
  case '3,5 Alt':return g<=3;
  case 'KG Var':return m.hg>0&&m.ag>0;
  case 'KG Yok':return m.hg===0||m.ag===0;
  default:return false;
 }
}
const rolling=[];
let playedTotal=0,pricedFixtures=0,simulatedFixtures=0,skippedQuality=0;
const first=Date.parse(input.window_start+'T00:00:00Z');
// Preload dated records; every team query filters m.date < target date.
for(const m of input.current)add(playedByTeam,m);
let scanned=0,qualified=0;
for(let i=input.window_calendar_days-1;i>=0;i--){
 const day=new Date(first+i*86400000).toISOString().slice(0,10);
 const matches=byDate.get(day)||[],models=[],eligible=matches.filter(x=>Object.keys(x.odds||{}).length>0);
 let simulated=0;
 for(const m of eligible){
  const h=teamObject(m.league,m.home,m.season,day),a=teamObject(m.league,m.away,m.season,day);
  const state=[h,a];
  scope.setHistoricalTeams(state,day);
  const pp=engine.goalRates(h,a,m.league),quality=engine.confidenceOf(h,a,pp);
  const sample=Math.min(h.stats.matches,a.stats.matches);
  if(sample<3||quality.value<35){skippedQuality++;continue;}
  const raw=engine.simulate(pp,engine.pattern(h,m.league),engine.pattern(a,m.league),100000);
  engine.reconcileScoreOutcome(raw);
  raw.markets['KG Yok']=100-raw.markets['KG Var'];
  raw.markets['12']=raw.markets['1']+raw.markets['2'];
  raw.markets['3,5 Üst']=100-raw.markets['3,5 Alt'];
  const market=impliedPrices(m.odds);
  const options=[];
  for(const k of markKeys){
   const price=Number(m.odds[k]),p=Number(raw.markets[k]);
   if(!Number.isFinite(price)||price<=1.03||price>4.5||!Number.isFinite(p)||p<12||p>99)continue;
   const adj=chooser.adjustedProbability(p/100,market[k],quality.value);
   options.push({key:k,odd:price,prob:adj,real:true,
     modelProb:p/100,marketProb:market[k],source:m.archived_source_url||'football-data.co.uk opening bookmaker/average price',sourceURL:m.archived_source_url||''});
  }
  if(!options.length)continue;
  models.push({f:{hid:m.league+'|'+m.home,aid:m.league+'|'+m.away},
   h,a,options,actual:m});
  simulated++;
 }
 const chosen=chooser.choose(models);
 let entry={date:day,games_with_results:matches.length,priced_games:eligible.length,
   modeled_games:simulated,has_coupon:Boolean(chosen)};
 if(chosen){
  entry.total_odds=Math.round(chosen.odd*10000)/10000;
  entry.model_probability_pct=Math.round(chosen.prob*10000)/100;
  entry.correct=chosen.legs.every(leg=>pass(leg.item.actual,leg.key));
  entry.legs=chosen.legs.map(l=>({home:l.item.actual.home,away:l.item.actual.away,
   competition:l.item.actual.league,market:l.key,price:l.odd,
   prediction_probability_pct:Math.round(l.prob*10000)/100,
   score:l.item.actual.hg+'-'+l.item.actual.ag,won:pass(l.item.actual,l.key)}));
 }
 rolling.push(entry);
 playedTotal+=matches.length;pricedFixtures+=eligible.length;simulatedFixtures+=simulated;
 // No same-day result is ever available to a fixture being predicted above.
 scanned++;
  if(chosen)qualified++;
 if(scanned%15===0||qualified>=input.required_coupon_days)
   console.log('FUTSIM latest-first',scanned,'calendar days scanned;',qualified,'qualified coupon days',flushTime());
  if(qualified>=input.required_coupon_days)break;
}
rolling.reverse();
function flushTime(){return new Date().toISOString().slice(11,19);}
const allCoupons=rolling.filter(x=>x.has_coupon);
const required=input.required_coupon_days||100;
const coupons=allCoupons.slice(-required);
const firstCoupon=coupons.length?coupons[0].date:null;
const selectedDays=firstCoupon?rolling.filter(x=>x.date>=firstCoupon):rolling;
const wins=coupons.filter(x=>x.correct).length,losses=coupons.length-wins;
let streak=0,maxStreak=0,maxStreakEnd=null,firstRunBalance=100,
 firstRunPeak=100,bestResetPeak=100,resetBalance=100,totalOddsProduct=1;
for(const c of coupons){
 if(c.correct){
  streak++;
  if(streak>maxStreak){maxStreak=streak;maxStreakEnd=c.date;}
  resetBalance*=c.total_odds;
  bestResetPeak=Math.max(bestResetPeak,resetBalance);
  if(firstRunBalance>0){
   firstRunBalance*=c.total_odds;
   firstRunPeak=Math.max(firstRunPeak,firstRunBalance);
  }
 }else{
  streak=0;
  resetBalance=100;firstRunBalance=0;
 }
}
const report={
 status:coupons.length===required?'completed_100_qualified_coupon_days':'insufficient_real_coupon_days',
 title:'CURRENT FUTSIM — last 100 actual daily ~2.00 coupons, extending across seasons',
 required_coupon_days:required,all_coupon_days_in_full_scan:allCoupons.length,
 calendar_days_scanned:rolling.length,
 scan_start:input.window_start,
 first_selected_coupon_day:firstCoupon,
 selected_coupon_dates:coupons.map(x=>x.date),
 created_utc:new Date().toISOString(),
 window_start:firstCoupon||input.window_start,window_end:input.window_end,
 calendar_days:selectedDays.length,
 days_with_finished_matches:selectedDays.filter(x=>x.games_with_results>0).length,
 days_with_publicly_priced_matches:selectedDays.filter(x=>x.priced_games>0).length,
 days_with_coupon:coupons.length,
 days_no_coupon:selectedDays.length-coupons.length,
 match_results_count:selectedDays.reduce((a,x)=>a+x.games_with_results,0),
 match_with_bookmaker_odds_count:selectedDays.reduce((a,x)=>a+x.priced_games,0),
 model_evaluated_matches:selectedDays.reduce((a,x)=>a+x.modeled_games,0),
 model_low_data_skips:skippedQuality,
 archived_multi_market_odds:input.real_archived_market_coverage,
 backed_price_markets:markKeys,
 successful_coupons:wins,failed_coupons:losses,
 success_rate_pct:coupons.length?Math.round(wins/coupons.length*10000)/100:null,
 longest_consecutive_winning_coupons:maxStreak,
 longest_streak_end_date:maxStreakEnd,
 initial_bankroll_try:100,
 single_no_reset_bankroll_end:Math.round(firstRunBalance*100)/100,
 single_no_reset_bankroll_peak:Math.round(firstRunPeak*100)/100,
 highest_100tl_restarted_chain_balance:Math.round(bestResetPeak*100)/100,
 odds_source:'https://www.football-data.co.uk/downloadm.php and https://zirveoran.com archived match prices',
 odds_columns:'Archived source posted median market quotes for 1X/12/X2/BTTS/1.5/3.5 when found; football-data.co.uk opening prices for match winner and 2.5 as baseline. No fair odds substituted.',
 previous_season_pre_match_priors:'2024/25 then 2025/26 prior-season stats; no future season matches',
 markets_available:markKeys,
 markets_without_historical_quotes:['corners','European competitions (historical fixture coverage unavailable)'],
 model_method:'LIVE FUTSIM goalRates, simulate(100000), reconcileScoreOutcome, adjustedProbability and choose on each chronological date. Real historical 1X/12/X2, goals, KG and MS prices only when archived; no date-leak.',
 important_limitations:[
   'The exact live coupon selector and 100000 simulation engine are reused. Historical market coverage is broader but NOT complete; corner odds and Champions League match source are missing.',
   'This replays the current model retroactively with only earlier results; missing lineup, injury, xG and historically timestamped market refreshes were not reproduced.',
   'Archived public match prices are indicated as closing or pre-match quotes when present, without original recording timestamp in all cases. Not independently verified pre-kickoff snapshots.',
   'Predicted coupon probabilities have not been independently verified as calibration of joint events.',
   'Exactly 100 qualifying coupon dates are targeted; the scan is longer than 100 calendar days and all no-coupon days remain excluded from wins.',
   '100 TL maximum restarted chain assumes full winnings re-staked after each win, a new 100 TL hypothetical start after each loss, ignores limits/taxes and is not realized profit.',
   'A 100 TL all-in challenge with no reset ends at zero after its first failed coupon.'
 ],
 fetch_errors:input.fetch_errors,
 price_sources:input.sources,
 daily:selectedDays
};
fs.mkdirSync(require('path').dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n','utf8');
console.log('RESULT',JSON.stringify({target:report.required_coupon_days,qualified:report.days_with_coupon,days:report.calendar_days,wins,losses,
 success:report.success_rate_pct,maxStreak,bestResetPeak:report.highest_100tl_restarted_chain_balance,
 firstRunPeak:report.single_no_reset_bankroll_peak,errors:report.fetch_errors.length}));
