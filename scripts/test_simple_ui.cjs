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
const fn=vm.runInNewContext(html.slice(i,j)+'; futsimModelLean',{
 fmt:(v)=>Number(v).toFixed(1),esc:x=>String(x),data:{weekly_meta:{week_start_utc:'2026-10-26'}}
});
const h={name:'Aston Villa',stats:{matches:8,gf:1.125,ga:1.5,xg:1.296},weekly_stats:{form_last5:'WWDWL',last5_wins:3}};
const a={name:'Galatasaray',stats:{matches:8,gf:2.125,ga:1.375},weekly_stats:{form_last5:'WWLWW',last5_wins:4}};
const r={markets:{'1X':70,'X2':71,'2,5 Üst':73,'3,5 Alt':58,'Korner 8,5 Üst':null}};
const item=fn(h,a,r,{},null);
assert.equal(item.pick.k,'2,5 Üst');
assert(item.reasons.some(v=>v.includes('3/5')&&v.includes('4/5')),'Last-5 form missing from rationale');
assert(item.reasons.some(v=>v.includes('1.3')&&v.includes('Galatasaray')),'Goals missing from rationale');
assert(item.reasons.some(v=>v.includes('yalnızca Aston Villa')),'Missing-side xG must not be fabricated');
console.log('FUTSIM compact UX + model rationale regression: OK');