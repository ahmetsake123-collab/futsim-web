
/* FUTSIM Daily Coupon | uses the existing two-half 100k simulation engine.
   User interface contains only today's coupon, a probability gauge and its video studio. */
(function(){
'use strict';
var $d=function(id){return document.getElementById(id);};
var app=null, view=null, initialized=false, calculating=false, updating=false;
var selected=null, fixtureModels=[], skipped=[], genuineQuotes=0, videoURL=null, dailyMarket=null, marketIssue='';
var MARKET_KEYS=['1','X','2','1X','12','X2','1,5 Üst','2,5 Alt','2,5 Üst','3,5 Alt','3,5 Üst','KG Var','KG Yok'];
var ALT={'atletico de madrid':'atletico madrid','atletico madrid':'atletico madrid','as roma':'roma','roma':'roma','vfb stuttgart':'vfb stuttgart','stuttgart':'vfb stuttgart','sporting cp':'sporting','lask linz':'lask','lask':'lask','lille':'losc lille','losc lille':'losc lille','paris saint germain':'psg','paris saint-germain':'psg','inter':'internazionale','internazionale':'internazionale','bodo glimt':'bodo glimt'};
function $text(t){return String(t==null?'':t);}
function escapeText(t){return $text(t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function fix(n){return Number(n).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2});}
function pct(n){return Number(n).toLocaleString('tr-TR',{maximumFractionDigits:1})+'%';}
function whenDay(){return typeof istanbulDay==='function'?istanbulDay():new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Istanbul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function label(k){return {'1':'MS 1','X':'MS X','2':'MS 2','12':'Çifte şans 12','1X':'Çifte şans 1X','X2':'Çifte şans X2','1,5 Üst':'1,5 gol üstü'}[k]||k;}
function canonical(n){return canonicalJS(n);}
function team(name){
 var c=canonical(name),target=ALT[c]||c;
 var matches=(typeof teams!=='undefined'?teams:[]).filter(function(t){
  return t.id===target||canonical(t.name)===target||t.id===c||canonical(t.name)===c;
 });
 return matches.sort(function(a,b){return (b.stats?.matches||0)-(a.stats?.matches||0);})[0]||null;
}

function marketMatches(row,home,away,date){
 if(row?.date!==date)return false;
 var h=team(row.home),a=team(row.away);
 return Boolean(h&&a&&h.id===home.id&&a.id===away.id);
}
async function loadDailyOdds(){
 marketIssue='';
 try{
  var res=await fetch('data/daily_market_odds.json?t='+Date.now(),{cache:'no-store'});
  if(!res.ok)throw Error('Oran arşivi henüz yayımlanmadı');
  var obj=await res.json();
  if(obj?.date!==whenDay())throw Error('Oran kaydının tarihi bugün değil');
  var age=(Date.now()-Date.parse(obj.fetched_at_utc||''))/3600000;
  if(!Number.isFinite(age)||age<0||age>20)throw Error('Piyasa verisi güncel değil');
  if(!Array.isArray(obj.matches)||!obj.matches.length)throw Error('Açık piyasa oranı bulunamadı');
  dailyMarket=obj;
 }catch(e){dailyMarket=null;marketIssue=e.message||'Fiyat kaynağına erişilemiyor';}
}
function fixtureList(){
 var today=whenDay(),api=window.FUTSIM_API_FOOTBALL||{};
 var age=(Date.now()-Date.parse(api.fetched_at_utc||''))/3600000;
 var goodAPI=api.status==='connected'&&age>=0&&age<=39;
 var by=new Map();
 if(goodAPI)for(var f of (api.fixtures||[])){
  if(f.date!==today||!['NS','TBD'].includes(f.status))continue;
  var kick=Date.parse(f.kickoff);
  if(Number.isFinite(kick)&&kick<=Date.now()+120000)continue;
  var h=team(f.home),a=team(f.away);
  if(!h||!a||h.id===a.id){skipped.push(f.home+' – '+f.away+': takım eşleşmesi eksik');continue;}
  var fx={date:f.date,league:f.league,time:Number.isFinite(kick)?new Intl.DateTimeFormat('tr-TR',{timeZone:'Europe/Istanbul',hour:'2-digit',minute:'2-digit'}).format(new Date(kick)):'—',home:h.name,away:a.name,hid:h.id,aid:a.id,api:f};
  by.set(today+'|'+h.id+'|'+a.id,fx);
 }
 // Public odds pages are dated match pages. They recover today's fixtures
 // when the optional API cannot return the current season.
 for(var row of (dailyMarket?.matches||[])){
  if(row.date!==today)continue;
  var h=team(row.home),a=team(row.away);
  if(!h||!a||h.id===a.id)continue;
  var key=today+'|'+h.id+'|'+a.id;
  if(!by.has(key))by.set(key,{date:today,league:'Bugünün fikstürü',time:'Bugün',home:h.name,away:a.name,hid:h.id,aid:a.id,marketFixture:true});
 }
 return {rows:[...by.values()],fresh:goodAPI||Boolean(dailyMarket?.matches?.length),age:age};
}
function calibrate(r){
 var b=data?.backtest||{};
 if(b.status==='gelişti'&&Number.isFinite(Number(b.temperature))&&Number(b.temperature)>0&&Number(b.temperature)!==1){
  var keys=['1','X','2'],t=Number(b.temperature),x=keys.map(function(k){return Math.pow(r.markets[k]/100,1/t);}),sum=x.reduce(function(s,v){return s+v;},0);
  keys.forEach(function(k,i){r.markets[k]=x[i]*100/sum;});
  r.markets['1X']=r.markets['1']+r.markets.X;
  r.markets.X2=r.markets.X+r.markets['2'];
 }
 reconcileScoreOutcome(r);
 r.markets['KG Yok']=100-r.markets['KG Var'];
}
function historyReasons(h,a,k){
 var reasons=[];
 if((h.stats?.form||[]).length>=3&&(a.stats?.form||[]).length>=3)
  reasons.push('iki takımın son maç formu');
 if(h.stats?.home?.matches>=3&&a.stats?.away?.matches>=3)
  reasons.push('ev/deplasman verisi');
 if(Number.isFinite(h.stats?.xg)&&Number.isFinite(a.stats?.xg))
  reasons.push('ölçülmüş xG');
 if(k.indexOf('Korner')>=0)reasons.push('doğrulanmış korner geçmişi');
 return reasons.slice(0,2).join(' ve ')||'geçmiş maç istatistikleri';
}

function verifiedOdds(h,a,f){
 // Source priority: exact-date externally quoted prices captured today.
 var match=(dailyMarket?.matches||[]).find(function(x){return marketMatches(x,h,a,f.date);});
 if(match&&match.source_url&&match.source_type==='international_bookmaker_median_not_turkish_iddaa')return match;
 // Legacy live-price records are acceptable only when independently sourced and dated.
 var old=getMatchOdds(h,a,f);
 if(old&&old.source_mode!=='user_entry_unverified'&&old.date===f.date&&old.source_url)return old;
 return null;
}
function adjustedProbability(model,market,coverage){
 if(!Number.isFinite(market))return model;
 var weight=coverage>=70?.52:coverage>=50?.37:.24;
 return Math.max(.01,Math.min(.99,weight*model+(1-weight)*market));
}
function runFixture(f){
 var h=team(f.home),a=team(f.away),comp=f.league;
 // API records provide the actual competition; match URLs do not.
 if(comp==='Bugünün fikstürü'){
  var api=(window.FUTSIM_API_FOOTBALL?.fixtures||[]).find(function(x){return marketMatches({date:x.date,home:x.home,away:x.away},h,a,f.date);});
  if(api)comp=api.league;
  else comp=h.competitions?.includes('Şampiyonlar Ligi')&&a.competitions?.includes('Şampiyonlar Ligi')?'Şampiyonlar Ligi':h.league;
 }
 var p=goalRates(h,a,comp),quality=confidenceOf(h,a,p);
 var n=Math.min(h.stats?.matches||0,a.stats?.matches||0);
 if(n<3||quality.value<35){skipped.push(h.name+' – '+a.name+': model geçmişi sınırlı');return null;}
 var r=simulate(p,pattern(h,comp),pattern(a,comp),100000);
 calibrate(r);
 var odds=verifiedOdds(h,a,f);
 var selections=[];
 for(var k of MARKET_KEYS){
  // A market is never priced from a model's theoretical 1/p.
  var rawModel=Number(k==='12'?r.markets['1']+r.markets['2']:k==='3,5 Üst'?100-r.markets['3,5 Alt']:r.markets[k]);
  var quote=Number(odds?.markets?.[k]);
  if(!Number.isFinite(rawModel)||rawModel<12||rawModel>99||!Number.isFinite(quote)||quote<1.03||quote>4.5)continue;
  var marketFair=Number(odds?.market_fair_probabilities?.[k])/100;
  if(!Number.isFinite(marketFair)||marketFair<=0||marketFair>=1)marketFair=null;
  var model=rawModel/100;
  // Conservative market cross-check prevents a low-coverage model from inventing an extreme advantage.
  var blended=adjustedProbability(model,marketFair,quality.value);
  selections.push({key:k,odd:quote,prob:blended,modelProb:model,marketProb:marketFair,
    source:odds.source||'Güncel oran kaydı',sourceURL:odds.source_url,real:true});
 }
 return {f:f,h:h,a:a,p:p,r:r,quality:quality.value,n:n,options:selections,hasQuotes:selections.length>0};
}

function choose(models){
 var min=1.88,max=2.12;
 var beam=[{legs:[],odd:1,prob:1,used:[]}],found=[];
 var entries=models.map(function(m){return {item:m,options:m.options.slice().sort(function(a,b){return b.prob-a.prob;}).slice(0,18)};})
  .filter(function(row){return row.options.length>0;});
 for(var row of entries){
  var next=beam.slice();
  for(var c of beam){
   if(c.legs.length>=6)continue;
   for(var op of row.options){
    var odd=c.odd*op.odd;
    if(odd>2.20)continue;
    var prob=c.prob*op.prob;
    // One market per game; the current fixture enters the state only once.
    var val={legs:c.legs.concat([{...op,item:row.item}]),odd:odd,prob:prob,used:c.used.concat([row.item.f.hid+'|'+row.item.f.aid])};
    next.push(val);
    if(odd>=min&&odd<=max)found.push(val);
   }
  }
  // Retain candidates across odds buckets AND leg counts to allow
  // 1-, 2-, 3-, 4-, 5- and 6-match combinations to compete fairly.
  var buckets=new Map();
  for(var c of next){
   var bucket=Math.floor(Math.log(c.odd)*135);
   var key=c.legs.length+'|'+bucket;
   var arr=buckets.get(key)||[];
   arr.push(c);buckets.set(key,arr);
  }
  beam=[];
  for(var arr of buckets.values()){
   arr.sort(function(a,b){return b.prob-a.prob;});
   beam.push(...arr.slice(0,7));
  }
  beam.sort(function(a,b){return b.prob-a.prob;});
  beam=beam.slice(0,1800);
 }
 if(!found.length){
  // Wider tolerance only if there is no coupon close to 2.00.
  found=beam.filter(function(c){return c.legs.length>0&&c.odd>=1.78&&c.odd<=2.20;});
 }
 if(!found.length)return null;
 found.sort(function(a,b){
  // Maximizing estimated hit rate is primary; leg count never decides risk.
  var score=function(x){return x.prob-.004*Math.abs(2-x.odd)-.0001*x.legs.length;};
  return score(b)-score(a);
 });
 return found[0];
}
function drawNeedle(win){
 var prob=Math.max(0,Math.min(100,Number(win)||0));
 var deg=-90+180*(prob/100);
 var n=$d('dcNeedle');if(n)n.setAttribute('transform','rotate('+deg+' 180 170)');
}
function makeApp(){
 var wrap=document.querySelector('.wrap');if(!wrap)return;
 app=document.createElement('div');app.id='dailyApp';
 app.innerHTML='<header class="dc-head"><div class="dc-logo">FUT<b>SIM</b></div><span class="dc-day" id="dcDay">Günlük analiz</span></header>'+
 '<p class="dc-kicker">2 ORANDAN 1 MİLYONA</p><h1>Günün kuponu.</h1>'+
 '<p class="dc-intro">Bugünün karşılaşmaları arka planda 100.000’er kez simüle edilir. FUTSIM, yaklaşık 2.00 toplam orana en düşük model riskli kombinasyonu arar.</p>'+
 '<section class="dc-card"><div class="dc-card-head"><span class="dc-mark" id="dcStatus">GÜNLÜK SEÇİM</span><span class="dc-pill" id="dcFixtureCount">Veriler okunuyor</span></div>'+
 '<div id="dcTotal" class="dc-total">— <small>toplam oran</small></div><div id="dcChoices" style="margin-top:17px"><div class="dc-state">Bugünün fikstürü inceleniyor…</div></div>'+
 '<p id="dcPriceNote" class="dc-note">Yalnızca tarihli ve kaynaklı fiyatlar gerçek piyasa oranı olarak gösterilir.</p></section>'+
 '<section class="dc-card"><div class="dc-card-head"><span class="dc-mark">KUPONUN MODEL OLASILIĞI</span><span class="dc-pill">0–100</span></div>'+
 '<div class="dc-gauge"><svg viewBox="0 0 360 195" class="dc-meter" aria-label="Kupon tahmini kazanma olasılığı göstergesi">'+
 '<defs><linearGradient id="dcGrad"><stop offset="0%" stop-color="#ff5d67"/><stop offset="52%" stop-color="#f6bd65"/><stop offset="100%" stop-color="#49e6a9"/></linearGradient></defs>'+
 '<path d="M 47 168 A 133 133 0 0 1 313 168" stroke="#1a3d48" stroke-width="26" fill="none" stroke-linecap="round"/>'+
 '<path d="M 47 168 A 133 133 0 0 1 313 168" stroke="url(#dcGrad)" stroke-width="20" fill="none" stroke-linecap="round"/>'+
 '<line id="dcNeedle" x1="180" y1="170" x2="180" y2="57" stroke="#effff8" stroke-width="5" stroke-linecap="round" transform="rotate(-90 180 170)"/>'+
 '<circle cx="180" cy="170" r="11" fill="#eafaf4"/><text x="34" y="192" fill="#a7bdc7" font-size="13">0</text><text x="310" y="192" fill="#a7bdc7" font-size="13">100</text></svg>'+
 '<div class="dc-gauge-text"><div id="dcWin" class="dc-percent">—</div><div class="dc-risklabel">TAHMİNİ KAZANMA İHTİMALİ</div></div></div>'+
 '<div class="dc-sides"><span>Kazanma olasılığı<b id="dcWon">—</b></span><span style="text-align:right">Kaybetme riski<b id="dcLost">—</b></span></div>'+
 '<p class="dc-note" id="dcRiskNote">Bu ibre gerçek maç sonuçlarını garanti etmez. Farklı maçlar bağımsız varsayılmıştır; model geçmiş testlerle tam kalibre edilmiş değildir.</p></section>'+
 '<div class="dc-actions"><button type="button" id="dcRefresh" class="dc-btn">↻ Yeniden hesapla</button><button type="button" id="dcToggleVideo" class="dc-btn main">🎬 Günün videosu</button></div>'+
 '<section id="dcStudio" class="dc-card" style="margin-top:16px" hidden><div class="dc-card-head"><span class="dc-mark">ANLATICI VİDEO STÜDYOSU</span><span class="dc-pill">9:16 · 38 sn</span></div>'+
 '<div class="dc-video"><canvas id="dcCanvas" width="720" height="1280"></canvas><div class="dc-video-side">'+
 '<p class="dc-small">Kupon oluşturulduğunda anlatıcı metni güncellenir. Metni kopyala, Türkçe MP3 seslendirmeyi yükle; sahneler kuponun seçimlerine göre hazırlanır.</p>'+
 '<label class="dc-small">Ses dosyası (isteğe bağlı)<input id="dcVoice" type="file" accept="audio/*" style="display:block;margin-top:8px"></label>'+
 '<div class="dc-actions"><button type="button" id="dcCopy" class="dc-btn">Metni kopyala</button><button type="button" id="dcRecord" class="dc-btn main">Videoyu oluştur</button></div>'+
 '<p id="dcVideoStatus" class="dc-small" role="status">MP3 yoksa sessiz video hazırlanır.</p>'+
 '<a id="dcDownload" class="dc-link" download hidden>Videoyu indir</a></div></div>'+
 '<textarea id="dcScript" class="dc-script" readonly aria-label="Günün anlatıcı metni"></textarea>'+
 '<video id="dcVideoPreview" controls playsinline hidden style="max-width:100%;width:210px;aspect-ratio:9/16;margin-top:12px"></video></section>'+
 '<p class="dc-secondary">Olasılıklar FUTSIM model tahminidir; kesin kazanma, doğrulanmış getiri veya yatırım tavsiyesi değildir. Veri veya güncel fiyat eksikse açıkça belirtilir.</p>';
 wrap.insertBefore(app,wrap.firstChild);
 $d('dcToggleVideo').onclick=function(){var x=$d('dcStudio');x.hidden=!x.hidden;if(!x.hidden)drawFrame(0);};
 $d('dcRefresh').onclick=function(){calculate();};
 $d('dcCopy').onclick=function(){var val=$d('dcScript').value;if(navigator.clipboard&&val){navigator.clipboard.writeText(val).then(function(){setVideoStatus('Metin kopyalandı.');}).catch(function(){fallbackCopy();});}else fallbackCopy();};
 $d('dcRecord').onclick=renderVideo;
 $d('dcDay').textContent=new Intl.DateTimeFormat('tr-TR',{timeZone:'Europe/Istanbul',day:'numeric',month:'long',year:'numeric'}).format(new Date());
 initialized=true;
}
function fallbackCopy(){var x=$d('dcScript');x.focus();x.select();setVideoStatus('Metin seçildi; kopyalamak için uzun bas veya Ctrl+C kullan.');}
function renderResult(fixtures,fresh){
 var count=fixtures.length;
 $d('dcFixtureCount').textContent=count+' maç analiz edildi';
 if(!selected){
  $d('dcStatus').textContent='GERÇEK ORAN ARANIYOR';
  $d('dcTotal').innerHTML='— <small>toplam oran</small>';
  $d('dcChoices').innerHTML='<div class="dc-state">'+escapeText(marketIssue||'Bugünkü kaynaklı oranlarda yaklaşık 2.00 toplam oranlı uygun kombinasyon bulunamadı.')+'</div>';
  $d('dcPriceNote').textContent='Gerçek bahis oranı yoksa yerine 1 / model olasılığı yazılmaz. Bu maçların fiyatları kaynaklı veriyle yeniden aranır.';
  $d('dcWin').textContent='—';$d('dcWon').textContent='—';$d('dcLost').textContent='—';drawNeedle(0);
  $d('dcScript').value='FUTSIM bugün yalnızca güncel maçları inceledi. Doğrulanmış oranlarda uygun bir iki oranlık kupon bulunamadı. Veri eksikliği nedeniyle rastgele seçim yapmıyoruz.';
  $d('dcRecord').disabled=false;
  return;
 }
 var real=selected.legs.every(function(x){return x.real;});
 $d('dcStatus').textContent='GÜNÜN GERÇEK PİYASA KUPONU';
 $d('dcTotal').innerHTML=fix(selected.odd)+' <small>kayıtlı piyasa toplam oranı</small>';
 $d('dcChoices').innerHTML=selected.legs.map(function(x){
  var m=x.item;
  return '<div class="dc-pick"><div class="dc-pick-main"><strong>'+escapeText(m.h.name)+' – '+escapeText(m.a.name)+'</strong>'+
  '<span>'+escapeText(label(x.key))+' · '+escapeText(m.f.time)+' · Ayarlı tahmin '+pct(x.prob*100)+'</span>'+
  '<span>'+escapeText(historyReasons(m.h,m.a,x.key))+'</span>'+ 
  (x.sourceURL?'<span><a href="'+escapeText(x.sourceURL)+'" target="_blank" rel="noopener noreferrer" style="color:#6ce6ba">Piyasa fiyatı kaynağı</a> · Model '+pct(x.modelProb*100)+(x.marketProb!=null?' · Piyasa adil '+pct(x.marketProb*100):'')+'</span>':'')+'</div><div class="dc-odd">'+fix(x.odd)+'</div></div>';
 }).join('');
 $d('dcPriceNote').textContent='Fiyatlar güncel kaynaklı uluslararası piyasa oranlarıdır; Türkiye İddaa oranları değildir ve anlık değişebilir. Adil oranlar ayrı tutulur. Bir maçtan yalnızca bir pazar seçilir.';
 var win=selected.prob*100;
 $d('dcWin').textContent=pct(win);$d('dcWon').textContent=pct(win);$d('dcLost').textContent=pct(100-win);
 $d('dcRiskNote').textContent='FUTSIM model+piyasa olasılığı '+pct(win)+', tahmini kayıp riski '+pct(100-win)+'. Farklı maçlar bağımsız varsayılmıştır. Bu kupon olasılıkları henüz bağımsız geçmiş testle kalibre edilmemiştir.';
 drawNeedle(win);
 buildScript();
 drawFrame(0);
}
function buildScript(){
 var scenes=[];
 if(!selected){$d('dcScript').value='Günlük kupon için yeterli veri yok.';return;}
 var isReal=selected.legs.every(function(x){return x.real;});
 scenes.push('Bugün FUTSIM iki oranlık günlük kuponunu hazırladı. Önce günün karşılaşmaları analiz edildi.');
 scenes.push('Her karşılaşma yüz bin kez simüle edildi ve farklı kupon ihtimalleri karşılaştırıldı.');
 selected.legs.forEach(function(x){
  scenes.push(x.item.h.name+' ve '+x.item.a.name+' maçında seçimimiz '+label(x.key)+'. Piyasa oranı '+fix(x.odd)+'.');
 });
 scenes.push('Toplam kayıtlı piyasa oranı '+fix(selected.odd)+'. FUTSIM model ve piyasa verilerine göre kuponun tahmini gerçekleşme ihtimali yüzde '+Math.round(selected.prob*100)+'.');
 scenes.push('Kaybetme ihtimali yüzde '+Math.round(100-selected.prob*100)+'. Oranlar bahis sitesine göre değişebilir, hiçbir tahmin garanti değildir.');
 scenes.push('FUTSIM. Her gün, tek kupon. Tahminler garanti değildir.');
 $d('dcScript').value=scenes.join('\n\n');
}

async function calculate(){
 if(calculating||typeof data==='undefined'||!data||!Array.isArray(teams)||!teams.length)return;
 calculating=true;selected=null;fixtureModels=[];skipped=[];
 $d('dcStatus').textContent='100.000 SİMÜLASYON / MAÇ';
 $d('dcChoices').innerHTML='<div class="dc-state">Bugünün gerçek fiyatları taranıyor; tüm uygun maç kombinasyonları karşılaştırılıyor…</div>';
 $d('dcRefresh').disabled=true;
 try{
  await loadDailyOdds();
  var source=fixtureList();
  for(var f of source.rows){
   try{var m=runFixture(f);if(m)fixtureModels.push(m);}catch(e){skipped.push(f.home+' – '+f.away+': model hesaplanamadı');}
   await new Promise(function(resolve){setTimeout(resolve,0);});
  }
  genuineQuotes=fixtureModels.filter(function(x){return x.hasQuotes;}).length;
  selected=choose(fixtureModels);
  renderResult(fixtureModels,source.fresh);
  var out=fixtureModels.length+'/'+source.rows.length+' maç incelendi · '+genuineQuotes+' fiyatlı maç';
  if(skipped.length)out+=' · '+skipped.length+' veri eksiği';
  $d('dcFixtureCount').textContent=out;
 }catch(e){
  $d('dcStatus').textContent='ANALİZ TAMAMLANAMADI';
  $d('dcChoices').innerHTML='<div class="dc-state">Kaynak veya hesaplama hatası: '+escapeText(e.message)+'</div>';
 }finally{calculating=false;$d('dcRefresh').disabled=false;}
}
function ready(){
 if(initialized||typeof data==='undefined'||!data||typeof teams==='undefined'||!teams.length)return;
 makeApp();
 calculate();
}
document.addEventListener('DOMContentLoaded',function(){ready();setTimeout(ready,500);setTimeout(ready,1500);});
window.addEventListener('futsim:ready',ready);
if(document.readyState!=='loading')setTimeout(ready,0);
window.FUTSIM_DAILY_DIAGNOSTICS={choose,adjustedProbability,marketMatches};

/* Coupon-driven, original animated narrated short video. Optional uploaded MP3 is mixed in.
   Text is not automatically spoken by the browser: narration must be supplied as an audio file. */
function setVideoStatus(s){if($d('dcVideoStatus'))$d('dcVideoStatus').textContent=s;}
function roundRect(g,x,y,w,h,r,fill){g.fillStyle=fill;g.beginPath();g.roundRect(x,y,w,h,r);g.fill();}
function words(g,text,x,y,maxWidth,lineHeight,maxLines){
 var tokens=$text(text).split(/\s+/),line='',out=0;
 for(var i=0;i<tokens.length;i++){
  var next=(line?line+' ':'')+tokens[i];
  if(g.measureText(next).width>maxWidth&&line){
   g.fillText(line,x,y+out*lineHeight);out++;line=tokens[i];
   if(out>=maxLines)return;
  }else line=next;
 }
 if(line&&out<maxLines)g.fillText(line,x,y+out*lineHeight);
}
function drawFrame(sec,duration){
 var canvas=$d('dcCanvas');if(!canvas)return;
 var g=canvas.getContext('2d');if(!g)return;
 var w=720,h=1280,total=duration||38;
 g.clearRect(0,0,w,h);
 var grad=g.createLinearGradient(0,0,w,h);grad.addColorStop(0,'#071922');grad.addColorStop(1,'#0c3440');g.fillStyle=grad;g.fillRect(0,0,w,h);
 g.fillStyle='#45e3ad';g.fillRect(45,40,115,8);
 g.fillStyle='#f1fff9';g.font='900 52px system-ui';g.fillText('FUTSIM',45,115);
 g.fillStyle='#87b6b8';g.font='600 25px system-ui';g.fillText('2 ORANDAN 1 MİLYONA',45,161);
 g.fillStyle='#263e47';g.fillRect(45,190,630,6);
 g.fillStyle='#47e3b2';g.fillRect(45,190,630*Math.min(1,sec/total),6);
 if(!selected){
  g.fillStyle='#f7fff9';g.font='800 42px system-ui';words(g,'BUGÜN DOĞRULANMIŞ KUPON YOK',45,480,625,60,4);
  g.fillStyle='#b3ccd2';g.font='28px system-ui';words(g,'FUTSIM veri eksikse oran veya kupon uydurmaz.',45,800,620,41,4);
 }else{
  var real=selected.legs.every(function(x){return x.real;});
  var n=selected.legs.length,phase=Math.min(n+3,Math.floor(sec/total*(n+4)));
  g.fillStyle='#5ceabc';g.font='800 24px system-ui';g.fillText('GÜNÜN KUPONU',45,279);
  if(phase===0){g.fillStyle='#e8fff6';g.font='900 66px system-ui';words(g,'BUGÜNÜN SEÇİMİ',45,495,610,85,3);
   g.fillStyle='#c0d8dd';g.font='29px system-ui';words(g,'Günün maçları arka planda analiz edildi.',45,815,610,48,3);}
  else if(phase===1){g.fillStyle='#e8fff6';g.font='900 72px system-ui';g.fillText('100.000',45,522);
   g.fillStyle='#c0d8dd';g.font='29px system-ui';words(g,'Her maç için yüz bin olası senaryo değerlendirildi.',45,610,615,52,4);}
  else if(phase>=2&&phase<2+n){
   var x=selected.legs[phase-2];roundRect(g,37,347,645,455,24,'#112c36');
   g.fillStyle='#e8fff6';g.font='800 42px system-ui';words(g,x.item.h.name+' – '+x.item.a.name,58,430,604,57,3);
   g.fillStyle='#5be4af';g.font='900 51px system-ui';words(g,label(x.key),58,615,605,66,2);
   g.fillStyle='#e8fff6';g.font='800 58px system-ui';g.fillText(fix(x.odd),58,754);
   g.font='24px system-ui';g.fillStyle='#a9c7cf';g.fillText('Model: '+pct(x.prob*100),350,753);
  }else if(phase===n+2){
   g.fillStyle='#f3fff8';g.font='900 45px system-ui';g.fillText('TOPLAM ORAN',45,445);
   g.fillStyle='#65edb8';g.font='900 107px system-ui';g.fillText(fix(selected.odd),45,567);
   g.fillStyle='#a5c9d0';g.font='26px system-ui';words(g,real?'Kaynaklı piyasa fiyatları':'Yalnızca teorik model oranı',45,644,625,40,3);
  }else{
   var prob=Math.round(selected.prob*100),risk=100-prob;
   g.fillStyle='#f2fff9';g.font='900 48px system-ui';g.fillText('MODEL OLASILIĞI',45,446);
   g.fillStyle='#63edb9';g.font='900 120px system-ui';g.fillText('%'+prob,45,610);
   g.fillStyle='#e3ffff';g.font='34px system-ui';g.fillText('Tahmini kayıp riski: %'+risk,45,700);
   g.fillStyle='#a2bdc5';g.font='25px system-ui';words(g,real?'Kesin sonuç değildir.':'Gerçek bahis oranı henüz doğrulanmadı.',45,790,625,40,3);
  }
 }
 g.fillStyle='#90b4c0';g.font='24px system-ui';g.fillText('MODEL TAHMİNİ • GARANTİ DEĞİLDİR',45,1169);
 g.fillStyle='#527985';g.font='21px system-ui';g.fillText(new Intl.DateTimeFormat('tr-TR',{timeZone:'Europe/Istanbul',day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date()),45,1219);
}
async function renderVideo(){
 var canvas=$d('dcCanvas');if(!canvas||!canvas.captureStream||typeof MediaRecorder==='undefined'){setVideoStatus('Bu tarayıcı video kaydını desteklemiyor. Chrome veya Edge kullan.');return;}
 var button=$d('dcRecord');button.disabled=true;setVideoStatus('Video sahneleri hazırlanıyor…');
 var ac=null,audioSource=null,mix=null,buffer=null,voice=$d('dcVoice')?.files?.[0];
 try{
  if(voice){
   var Ctx=window.AudioContext||window.webkitAudioContext;if(!Ctx)throw new Error('Tarayıcı MP3 mikslemeyi desteklemiyor.');
   ac=new Ctx();await ac.resume();
   buffer=await ac.decodeAudioData(await voice.arrayBuffer());
  }
  var stream=canvas.captureStream(30),total=buffer?buffer.duration:38;
  if(buffer){
   audioSource=ac.createBufferSource();audioSource.buffer=buffer;
   mix=ac.createMediaStreamDestination();audioSource.connect(mix);
   stream=new MediaStream([...stream.getVideoTracks(),...mix.stream.getAudioTracks()]);
  }
  var mime=['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm','video/mp4'].find(function(x){return MediaRecorder.isTypeSupported(x);})||'';
  var rec=new MediaRecorder(stream,mime?{mimeType:mime}:undefined),chunks=[];
  rec.ondataavailable=function(e){if(e.data?.size)chunks.push(e.data);};
  rec.onerror=function(){setVideoStatus('Video kayıt hatası.');};
  rec.onstop=function(){
   stream.getTracks().forEach(function(t){t.stop();});if(ac)ac.close().catch(function(){});
   var blob=new Blob(chunks,{type:rec.mimeType||'video/webm'});
   if(videoURL)URL.revokeObjectURL(videoURL);
   videoURL=URL.createObjectURL(blob);
   var link=$d('dcDownload'),preview=$d('dcVideoPreview');
   link.href=videoURL;link.download='FUTSIM_GUNUN_KUPONU_'+whenDay()+((rec.mimeType||'').indexOf('mp4')>=0?'.mp4':'.webm');link.hidden=false;
   preview.src=videoURL;preview.hidden=false;button.disabled=false;
   setVideoStatus('Video hazır. '+(voice?'Sesli':'Sessiz')+' sürüm oluşturuldu. Kaydetmeden önce önizle.');
  };
  drawFrame(0,total);
  rec.start(500);
  var clock=performance.now(),audioStart=ac?ac.currentTime+.1:null;
  if(audioSource)audioSource.start(audioStart);
  function frame(){
   if(rec.state!=='recording')return;
   var elapsed=ac?ac.currentTime-audioStart:(performance.now()-clock)/1000;
   if(elapsed>=total){drawFrame(total,total);rec.stop();return;}
   drawFrame(Math.max(0,elapsed),total);
   if(Math.floor(elapsed)%5===0)setVideoStatus('Video oluşturuluyor: '+Math.floor(elapsed)+' / '+Math.floor(total)+' sn');
   requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
 }catch(e){if(ac)ac.close().catch(function(){});button.disabled=false;setVideoStatus('Video oluşturulamadı: '+e.message);}
}
})();
