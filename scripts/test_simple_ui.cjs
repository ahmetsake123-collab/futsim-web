'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('docs/index.html','utf8');
for(const id of ['betSummary','showAdvanced','couponMarket','autoPick','matchName','xgReadout']){
 assert(html.includes('id="'+id+'"'),'Missing UI anchor: '+id);
}
assert(html.includes('body:not(.show-extras) .extra-panel'),'Advanced panes not hidden by default');
assert(html.includes("toggle.onclick=()=>"),'Show/hide details not wired');
assert(html.includes('const genuineFixture=Boolean(f?.date)'),'Unscheduled matches require explicit warning');
const i=html.indexOf('function futsimModelLean('),j=html.indexOf('function renderCouponChoice(',i);
assert(i>0&&j>i,'Model pick rationale function missing');
const picksStart=html.indexOf('const couponKeys=');
const picksEnd=html.indexOf('function couponSave(',picksStart);
assert(picksStart>0&&picksEnd>picksStart,'Shared allowed-market configuration missing');
const fn=vm.runInNewContext(html.slice(picksStart,picksEnd)+'\n'+html.slice(i,j)+'; futsimModelLean',{
 fmt:(v)=>Number(v).toFixed(1),esc:x=>String(x),data:{weekly_meta:{week_start_utc:'2026-10-26'}}
});
const h={name:'Aston Villa',stats:{matches:8,gf:1.125,ga:1.5,xg:1.296},weekly_stats:{form_last5:'WWDWL',last5_wins:3}};
const a={name:'Galatasaray',stats:{matches:8,gf:2.125,ga:1.375},weekly_stats:{form_last5:'WWLWW',last5_wins:4}};
const r={markets:{'1X':70,'X2':71,'2,5 Üst':73,'3,5 Alt':58,'Korner 8,5 Üst':null}};
const item=fn(h,a,r,{},null);
assert.equal(item.pick.k,'2,5 Üst');
const chelsea={name:'Chelsea',stats:{matches:9,gf:2.0,ga:1.2}};
const manU={name:'Manchester United',stats:{matches:9,gf:1.7,ga:1.5}};
const chelseaPick=fn(chelsea,manU,{markets:{
 '1':49.03,'X':24.61,'2':26.36,'2,5 Üst':58,'2,5 Alt':42,
 'KG Var':60.99,'KG Yok':39.01,'Dep gol':72.54,'1X':73
}}, {}, null);
assert.equal(chelseaPick.pick.k,'KG Var','Do not select unwanted away-score or double chance markets');
const cornerPick=fn(chelsea,manU,{markets:{
 '1':49.03,'X':24.61,'2':26.36,'KG Var':60.99,'Korner 10,5 Alt':76
}}, {}, null);
assert.equal(cornerPick.pick.k,'Korner 10,5 Alt','Choose highest among approved markets');
assert(item.reasons.some(v=>v.includes('3/5')&&v.includes('4/5')),'Last-5 form missing from rationale');
assert(item.reasons.some(v=>v.includes('Aston Villa')&&v.includes('Galatasaray')&&v.includes('1.1')),'Goals missing from rationale');
assert(item.reasons.some(v=>v.includes('yalnızca Aston Villa')),'Missing-side xG must not be fabricated');
console.log('FUTSIM compact UX + model rationale regression: OK');