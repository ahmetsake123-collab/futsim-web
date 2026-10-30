/* FUTSIM competition-aware narrative, grounded only in published score records. */
(function(){
'use strict';
let current=null,learning=null,research=null,cornerAudit=null,last=null;
const $=id=>document.getElementById(id);
const numeric=x=>Number.isFinite(Number(x))?Number(x):null;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function norm(s){return String(s||'').toLocaleLowerCase('tr-TR').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/ı/g,'i').replace(/[^a-z0-9]+/g,' ').trim().replace(/^(fc|ac|ssc|cf) /,'');}
function find(t){let teams=current?.teams||{};return teams[t.id]||teams[norm(t.name)]||{};}
function venue(t,home){
 let stats=t.stats||{},local=home?stats.home:stats.away,n=Number(local?.matches)||0;
 if(n<3)return null;
 let matches=(local.form||[]).slice(0,8);
 if(matches.length<3)return null;
 let unbeaten=matches.filter(m=>(m.gf??-1)>=(m.ga??1e6)).length;
 let win=matches.filter(m=>m.gf>m.ga).length;
 return {n:matches.length,unbeaten,win};
}
function build(h,a,comp){
 const thoughts=[],hs=h.stats||{},as=a.stats||{};
 const home=venue(h,true),away=venue(a,false);
 const hforms=find(h),aforms=find(a);
 const hLeague=hforms[h.league],aLeague=aforms[a.league];
 // Venue form can contradict the club's broader points production.
 if(home&&home.unbeaten/home.n>=.75&&hs.points!=null&&hs.points<1.6){
  thoughts.push(h.name+' genel lig performansında zorlanıyor olsa da, incelenen '+home.n+' iç saha maçının '+home.unbeaten+' tanesinde yenilmedi.');
 }else if(home&&home.win/home.n>=.7){
  thoughts.push(h.name+' son '+home.n+' iç saha maçının '+home.win+' tanesini kazandı; sahasındaki sonuçları ayrıca değerlendirmek gerekiyor.');
 }
 if(away&&away.unbeaten/away.n>=.75){
  thoughts.push(a.name+' deplasmanda dirençli: incelenen '+away.n+' dış saha maçının '+away.unbeaten+' tanesinde yenilmedi.');
 }
 for(const t of [h,a]){
  const form=find(t)[t.league];
  if(form&&form.matches_current>=8&&form.last5>=4&&form.prior6_goal_difference!=null){
   const shift=form.last5_goal_difference-form.prior6_goal_difference;
   if(shift>=.8)thoughts.push(t.name+' son maçlarda yükselişte: maç başına gol farkı bir önceki döneme göre artmış.');
   if(shift<=-.8)thoughts.push(t.name+' son maçlarda zorlanıyor: maç başına gol farkı bir önceki döneme göre gerilemiş.');
  }
 }
 if(comp==='Şampiyonlar Ligi'){
  let found=0;
  for(const t of [h,a]){
   const rec=find(t),u=rec['Şampiyonlar Ligi'],dom=rec[t.league];
   if(u&&dom&&u.matches_current>=3&&dom.matches_current>=5){
    let gap=u.current_gf-dom.current_gf;
    if(gap>=.55){thoughts.push(t.name+' Avrupa maçlarında ligine göre daha gollü oynuyor; yalnızca ligdeki gol ortalamasını kullanmak yanıltıcı olur.');found++;}
    else if(gap<=-.55){thoughts.push(t.name+' Avrupa maçlarında ligine göre daha az gol üretiyor; yarışmalar ayrı değerlendirilmelidir.');found++;}
   }
  }
  if(!found)thoughts.push('Şampiyonlar Ligi örneklemi sınırlıysa lig istatistikleri temel kalır; Avrupa formu için yeterli kanıt olmadan ekstra gol uydurulmaz.');
 }
 if(!thoughts.length){
  thoughts.push('Son form, iç saha ile deplasman performansı ve rakip seviyesi birlikte değerlendiriliyor; bu maçın sonucu tek bir yüzdeye indirgenmemeli.');
 }
 return thoughts.slice(0,4);
}
function renderNews(h,a){
 if(!research?.results)return;
 const match=(research.results||[]).find(x=>
   norm(x.home)===norm(h.name)&&norm(x.away)===norm(a.name));
 const status=$('researchStatus'),root=$('researchSources');
 if(!status||!root)return;
 if(!match){status.textContent='Bu maç için güncel başlık arşivinde doğrulanmış kayıt yok.';return;}
 const sourceTime=research.fetched_at_utc?new Date(research.fetched_at_utc).toLocaleString('tr-TR'):'bilinmiyor';
 status.textContent='Kaynak başlığı araştırması: '+match.headline_count+' yayın · Son tarama '+sourceTime+
 ' · Haber başlıkları doğrulanmış sakatlık veya kadro bilgisi sayılmaz.';
 root.innerHTML=(match.headlines||[]).map(x=>'<div><b>'+esc(x.source)+'</b><p>'+esc(x.headline)+'</p>'+
   '<small>'+esc(x.published_at?.slice(0,10))+' · yalnızca başlık okundu</small> · '+
   '<a rel="noopener noreferrer" target="_blank" href="'+esc(x.url)+'">Haberi aç</a></div>').join('')||
   '<div>İlgili iki takımın adını birlikte içeren tarihli bir yayın başlığı bulunamadı.</div>';
}
function render(h,a,comp,r,corners){
 last={h,a,comp,r,corners};
 const dest=$('contextInsights');if(!dest)return;
 const lines=build(h,a,comp);
 const mm=Math.abs(r.markets['1']-r.markets['2']);
 const market=mm<8?'Sonuç olasılıkları yakın; favorinin kaybetmesi olağan senaryolar arasında.':'Favori daha yüksek olasılığa sahip, fakat diğer sonuçların toplam ihtimali de önemlidir.';
 let explain=lines.map(x=>'<p class="small" style="margin:8px 0">'+esc(x)+'</p>').join('');
 if(corners?.ok)explain+='<p class="small"><b>Korner (ayrı model):</b> 8,5 üst %'+corners.over85.toFixed(1)+' · 9,5 üst %'+corners.over95.toFixed(1)+' · '+corners.n+' maç veri. Bu korner tahmini ayrı doğrulama gerektirir.</p>';
 else explain+='<p class="small">Doğrulanmış yeterli korner verisi bulunmadığından korner bahisleri seçilmez.</p>';
 explain+='<p class="small">'+esc(market)+'</p>';
 explain+='<p class="small" style="color:#fcb969">Sakatlıklar, teknik direktör değişikliği ve olası rotasyon ancak tarihli güvenilir kaynakla doğrulanırsa yorumlanmalıdır. Bu sinyaller henüz simülasyon yüzdelerine otomatik etki etmiyor.</p>';
 dest.innerHTML=explain;
 renderNews(h,a);
 renderCornerAudit(comp);
 const audit=$('contextLearningSummary');if(audit){
  const d=learning;
  audit.textContent=d?('2025/26 geçmiş test: '+d.complete_test_matches+' maç; mevcut basit model Brier '+d.season_metrics.existing_simple_baseline.brier+', bağlam modeli '+d.season_metrics.context_candidate.brier+'. '+(d.deployment.recommend_context_model?'Yeni model iki dönemde de daha iyi göründü; uygulamaya henüz geçirilmedi.':'İyileştirme iki dönemde doğrulanmadı; mevcut model korundu.')+' Kapsam: 7 lig + Şampiyonlar Ligi.'):'Tam sezon test raporu henüz yüklenmedi.';
 }
}
function renderCornerAudit(competition){
 const el=$('cornerExperimentReadout');if(!el)return;
 const d=cornerAudit;
 if(!d){el.textContent='Korner model deneyi raporu henüz yüklenmedi.';return;}
 const tr=d.training||{},val=d.holdout||{},now=val.selected||{},older=val.old_poisson||{};
 const best=tr.selected||{};
 const ntr=best.n||0,nval=now.n||0;
 const label=(v)=>Number.isFinite(v)?(v*100).toFixed(1)+'%':'—';
 const league=d.by_competition?.holdout?.[competition];
 const leagueDetail=league&&league.n?(' '+competition+': '+league.correct+'/'+league.n+' ('+label(league.accuracy)+') [deneysel].'):'';
 const badge=d.deployment?.eligible?'Yeterli sonuç işareti, canlı sürüm henüz güncellenmedi.':'Canlı model korunuyor: iyileşme bütün ölçütleri karşılamadı.';
 el.innerHTML='<b>Korner model karşılaştırması:</b> '+esc(d.tested_candidates)+' aday yöntem. 2025–26: deneysel '+best.correct+'/'+ntr+' ('+label(best.accuracy)+
 '); bağımsız 2026–27: deneysel '+now.correct+'/'+nval+' ('+label(now.accuracy)+'), eski '+older.correct+'/'+nval+
 ' ('+label(older.accuracy)+'). Deneysel Brier '+esc(now.brier)+'; eski '+esc(older.brier)+'. '+esc(leagueDetail)+
 ' <b>'+esc(badge)+'</b> <a href="data/corner_experiment.json" rel="noopener" target="_blank">Raporu incele</a>';
}
async function init(){
 try{
 const [a,b,c,d]=await Promise.allSettled([
   fetch('data/competition_form.json?v=20261030',{cache:'no-store'}).then(x=>x.ok?x.json():null),
   fetch('data/model_learning_full.json?v=20261030',{cache:'no-store'}).then(x=>x.ok?x.json():null),
   fetch('data/prematch_research.json?v=20261030',{cache:'no-store'}).then(x=>x.ok?x.json():null),
   fetch('data/corner_experiment.json?v=20261030-v2',{cache:'no-store'}).then(x=>x.ok?x.json():null)]);
 if(a.status==='fulfilled')current=a.value;
 if(b.status==='fulfilled')learning=b.value;
 if(c.status==='fulfilled')research=c.value;
 if(d.status==='fulfilled')cornerAudit=d.value;
 renderCornerAudit(last?.comp);
 if(last)render(last.h,last.a,last.comp,last.r,last.corners);
 }catch(e){}
}
window.FUTSIM_CONTEXT={render,build,getForVideo:build,learning:()=>learning,cornerAudit:()=>cornerAudit};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();