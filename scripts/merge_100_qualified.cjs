#!/usr/bin/env node
// FUTSIM parallel backtest reducer: latest 100 ACTUAL coupon-producing days.
// Every shard uses the same live 100,000 simulation engine with date-isolated history.
'use strict';
const fs=require('fs'),path=require('path');
const files=process.argv.slice(2);
if(files.length!==4)throw Error('Exactly 4 independent shard reports are required');
const parts=files.map(p=>JSON.parse(fs.readFileSync(p,'utf8')));
const sh=new Set(parts.map(p=>p.shard_index));
if(sh.size!==4||![0,1,2,3].every(i=>sh.has(i)))throw Error('Missing or duplicate shard');
const days=parts.flatMap(p=>p.daily||[]).sort((a,b)=>a.date.localeCompare(b.date));
const daySet=new Set(days.map(d=>d.date));
if(daySet.size!==days.length)throw Error('Duplicate date in parallel results');
if(!days.length)throw Error('No dated results');
const allCoupons=days.filter(d=>d.has_coupon);
const TARGET=100,selectedCoupons=allCoupons.slice(-TARGET);
const n=selectedCoupons.length;
const first=selectedCoupons[0]?.date||null;
const selectedDays=first?days.filter(d=>d.date>=first):days;
if(selectedCoupons.some(c=>!Array.isArray(c.legs)||!c.legs.length||c.legs.some(l=>!Number.isFinite(l.price)||l.price<=1)||c.correct!==c.legs.every(x=>x.won)))throw Error('Malformed/unauditable coupon');
const wins=selectedCoupons.filter(c=>c.correct).length,losses=n-wins;
const fm=x=>Math.round(x*100)/100;
let streak=0,longest=0,longestEnd=null,resetBalance=100,resetPeak=100,oneRun=100,oneRunPeak=100;
let flatPayout=0;
const marketUse={},legDistribution={};
for(const c of selectedCoupons){
 legDistribution[c.legs.length]=(legDistribution[c.legs.length]||0)+1;
 for(const l of c.legs){
  const z=marketUse[l.market]||(marketUse[l.market]={selections:0,correct:0});
  z.selections++;if(l.won)z.correct++;
 }
 if(c.correct){
  flatPayout+=100*c.total_odds;
  resetBalance*=c.total_odds;
  resetPeak=Math.max(resetPeak,resetBalance);
  if(oneRun>0){oneRun*=c.total_odds;oneRunPeak=Math.max(oneRunPeak,oneRun);}
  streak++;
  if(streak>longest){longest=streak;longestEnd=c.date;}
 }else{
  resetBalance=100;oneRun=0;streak=0;
 }
}
const firstShard=parts[0];
const stakes=100*n;
const result={
 status:n===TARGET?'completed_100_qualified_coupon_days':'insufficient_real_coupon_days',
 title:'FUTSIM CURRENT 100 daily coupons: 100k-simulation multi-season independent-price backtest',
 created_utc:new Date().toISOString(),
 target_coupon_days:TARGET,achieved_coupon_days:n,
 total_eligible_coupon_days_in_scanned_range:allCoupons.length,
 total_scanned_calendar_days:days.length,
 full_data_range_start:days[0]?.date,
 full_data_range_end:days[days.length-1]?.date,
 first_selected_coupon_day:first,
 window_start:first,window_end:days[days.length-1]?.date,
 calendar_days:selectedDays.length,
 days_with_finished_matches:selectedDays.filter(d=>d.games_with_results>0).length,
 days_with_publicly_priced_matches:selectedDays.filter(d=>d.priced_games>0).length,
 days_with_coupon:n,days_no_coupon:selectedDays.length-n,
 match_results_count:selectedDays.reduce((a,d)=>a+d.games_with_results,0),
 match_with_bookmaker_odds_count:selectedDays.reduce((a,d)=>a+d.priced_games,0),
 model_evaluated_matches:selectedDays.reduce((a,d)=>a+d.modeled_games,0),
 successful_coupons:wins,failed_coupons:losses,
 success_rate_pct:n?fm(wins/n*100):null,
 longest_consecutive_winning_coupons:longest,
 longest_streak_end_date:longestEnd,
 initial_bankroll_try:100,
 single_no_reset_bankroll_peak:fm(oneRunPeak),
 single_no_reset_bankroll_end:fm(oneRun),
 highest_100tl_restarted_chain_balance:fm(resetPeak),
 fixed_100tl_stake_total:stakes,
 fixed_100tl_stake_payout:fm(flatPayout),
 fixed_100tl_stake_net:fm(flatPayout-stakes),
 fixed_100tl_stake_roi_pct:stakes?fm((flatPayout-stakes)/stakes*100):null,
 bankroll_explanation:'The restarted-chain peak adds new 100 TL after a loss and is NOT net profit. One unrefilled all-in sequence ends at zero after its first loss.',
 coupon_leg_count_distribution:legDistribution,
 market_selection_performance:marketUse,
 archived_multi_market_odds:firstShard.archived_multi_market_odds,
 backed_price_markets:firstShard.backed_price_markets,
 odds_source:firstShard.odds_source,
 price_sources:firstShard.price_sources,
 fetch_errors:firstShard.fetch_errors,
 source_repo:'ahmetsake123-collab/futsim-web',
 model_method:'Live FUTSIM goalRates and simulate(...,100000) for each priced eligible fixture; live probability blending and 1–6 leg coupon chooser. Four independent shards use only team results before each fixture date, then the most recent 100 distinct eligible days are merged in order.',
 important_limitations:[
  'These are 100 distinct coupon-producing dates, not 100 contiguous calendar days. No-coupon dates cannot count as wins.',
  'Historical 1X, 12, X2, KG and broader goal markets are included only where actual public posted prices could be matched. Corner-price and Champions League archives are incomplete and not fabricated.',
  'The algorithm of the current app was retroactively replayed, not a live historical version frozen before each match.',
  'Archived market pages do not always prove exact bookmaker price timestamp before kick-off; all price-based results are conditional on archive accuracy.',
  'No historical lineup, injury, or measured xG data were retro-invented; model joint probabilities are not independently calibrated.',
  'Full-bankroll all-in is highly risky; fees, taxes, exchange-rate differences and bookmaker restrictions are not represented.'
 ],
 selected_coupon_dates:selectedCoupons.map(c=>c.date),
 daily:selectedDays
};
const out='docs/data/daily100_qualified_backtest.json';
fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n','utf8');
console.log('FUTSIM_100_QUALIFIED_RESULT',JSON.stringify({target:TARGET,achieved:n,calendar_days:result.calendar_days,successes:wins,losses,hit_pct:result.success_rate_pct,longest,peak_reset:result.highest_100tl_restarted_chain_balance,fixed_roi_pct:result.fixed_100tl_stake_roi_pct,archived_market_matches:firstShard.archived_multi_market_odds?.found}));
if(n!==TARGET){console.error('Target missed: extend fixture archive backward and re-run, never fabricate missing coupon days');process.exitCode=2;}
