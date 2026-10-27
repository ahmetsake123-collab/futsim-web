/* FUTSIM Video Studio | Rendered in the browser. No server or paid service. */
(function(){
'use strict';
var duration=40, lastUrl=null, working=false;
var el=function(id){return document.getElementById(id);};
var limit=function(x){return Math.max(0,Math.min(1,x));};
var ease=function(x){x=limit(x);return x*x*(3-2*x);};
var percent=function(v){return '%'+Number(v).toLocaleString('tr-TR',{minimumFractionDigits:1,maximumFractionDigits:1});};
var clean=function(s){return String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9_-]/g,'_').slice(0,30);};
function status(s){el('studioStatus').textContent=s;}
function escapeHTML(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function save(blob,name){var url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url);},60000);}
function analyze(){
 if(typeof data==='undefined'||!data)throw Error('FUTSIM verileri henüz yüklenmedi.');
 if(typeof busy!=='undefined'&&busy)throw Error('Mevcut analiz tamamlanmadan video oluşturulamaz.');
 var h=byId[el('home').value],a=byId[el('away').value],c=el('competition').value;
 if(!h||!a||h.id===a.id)throw Error('Önce farklı iki takım seç.');
 var p=goalRates(h,a,c);
 var r=simulate(p,pattern(h,c),pattern(a,c),100000);
 var b=data.backtest||{};
 if(b.status==='gelişti'&&b.temperature&&b.temperature!==1){
  var keys=['1','X','2'],t=Number(b.temperature),adjust=keys.map(function(k){return Math.pow(r.markets[k]/100,1/t);});
  var sum=adjust.reduce(function(x,y){return x+y;},0);
  keys.forEach(function(k,i){r.markets[k]=adjust[i]/sum*100;});
  r.markets['1X']=r.markets['1']+r.markets.X;r.markets.X2=r.markets.X+r.markets['2'];
 }
 reconcileScoreOutcome(r);
 return {home:h.name,away:a.name,competition:c,date:(getChosenFixture(h,a)||{}).date||null,asof:data.asof,
  created:new Date().toISOString(),p:p,r:r,chosen:resultAlignedScore(r),sample:100000,coverage:Math.min(h.stats?.matches||0,a.stats?.matches||0)};
}
function speech(a){
 var m=a.r.markets,modal=a.chosen.modal.score.replace('-',' - '),rep=a.chosen.representative.score.replace('-',' - ');
 var fav=a.chosen.favorite==='1'?a.home:a.chosen.favorite==='2'?a.away:'beraberlik';
 var tight=Math.abs(m['1']-m['2'])<3?'İki takımın kazanma ihtimali birbirine çok yakın. ':'';
 return 'FUTSIM analizine hoş geldiniz. '+a.home+' ve '+a.away+' karşı karşıya.\n\n'+
  'Bu maçı FUTSIM motorunda tam yüz bin kez simüle ettik. '+a.home+' için yüzde '+Math.round(m['1'])+
  ', beraberlik için yüzde '+Math.round(m.X)+', '+a.away+' için yüzde '+Math.round(m['2'])+' ihtimal oluştu. '+tight+
  '\nEn sık skor '+modal+'. Ancak modelin öne çıkardığı sonuç '+fav+'; bu sonuç grubunun temsilî skoru '+rep+
  '.\nİki buçuk gol üstü yüzde '+Math.round(m['2,5 Üst'])+', altı yüzde '+Math.round(m['2,5 Alt'])+
  '. Karşılıklı gol olasılığı yüzde '+Math.round(m['KG Var'])+
  '.\n\nBu sayılar kesin sonuç değil, olasılıktır. FUTSIM. Her maçın bir olasılığı var.';
}
function details(a){
 var m=a.r.markets;
 el('studioDigest').innerHTML='<b>'+escapeHTML(a.home)+' – '+escapeHTML(a.away)+'</b><br>'+
 '100.000 simülasyon · 1: '+percent(m['1'])+' · X: '+percent(m.X)+' · 2: '+percent(m['2'])+
 '<br>En sık skor: '+escapeHTML(a.chosen.modal.score)+' ('+percent(a.chosen.modal.p)+')'+
 ' · Temsilî skor: '+escapeHTML(a.chosen.representative.score)+
 '<br>2,5 Alt: '+percent(m['2,5 Alt'])+' · Üst: '+percent(m['2,5 Üst'])+' · KG Var: '+percent(m['KG Var'])+
 (!a.date?'<br><small>Bu eşleşmenin önümüzdeki 7 günlük fikstürdeki tarihi doğrulanmadı; özel karşılaştırma.</small>':'');
 el('studioScript').value=speech(a);el('studioTextControls').hidden=false;
 el('studioSaveText').onclick=function(){save(new Blob([el('studioScript').value],{type:'text/plain;charset=utf-8'}),'FUTSIM_'+clean(a.home)+'_'+clean(a.away)+'_metin.txt');};
 el('studioCopyText').onclick=async function(){try{await navigator.clipboard.writeText(el('studioScript').value);status('Seslendirme metni kopyalandı.');}catch(e){el('studioScript').select();status('Metin seçildi. Ctrl+C ile kopyalayabilirsin.');}};
 el('studioSaveData').onclick=function(){
  var result={home:a.home,away:a.away,competition:a.competition,fixture_date:a.date,asof:a.asof,
   generated_at:a.created,engine:'FUTSIM two-half Monte Carlo',simulations:100000,
   model_goal_parameters:{home:a.p.lh,away:a.p.la},markets:m,
   modal_score:a.chosen.modal,representative_score:a.chosen.representative,
   most_frequent_scores:a.r.scores,all_scores:a.r.allScores,
   narration:el('studioScript').value};
  save(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),'FUTSIM_'+clean(a.home)+'_'+clean(a.away)+'_analiz.json');
 };
}
function label(g,s,x,y,sz,color,align,weight){
 g.save();g.textBaseline='middle';g.textAlign=align||'center';g.fillStyle=color||'#e9faff';
 g.font=(weight||800)+' '+sz+'px system-ui,Arial,sans-serif';g.fillText(String(s),x,y);g.restore();
}
function rect(g,x,y,w,h,r,fill,stroke){
 g.beginPath();g.roundRect(x,y,w,h,r);g.fillStyle=fill;g.fill();
 if(stroke){g.lineWidth=2;g.strokeStyle=stroke;g.stroke();}
}
function ring(g,x,y,r,start,end,color,lw){
 g.beginPath();g.arc(x,y,r,start,end);g.strokeStyle=color;g.lineWidth=lw;g.stroke();
}
function background(g,t){
 var grad=g.createLinearGradient(0,0,1080,1920);grad.addColorStop(0,'#07141e');grad.addColorStop(.52,'#091d27');grad.addColorStop(1,'#040810');
 g.fillStyle=grad;g.fillRect(0,0,1080,1920);
 g.strokeStyle='rgba(80,208,190,.09)';g.lineWidth=1;
 for(var i=0;i<23;i++){g.beginPath();g.moveTo(i*100-580,1000);g.lineTo(i*100-300,1920);g.stroke();}
 for(var j=1080;j<1940;j+=80){g.beginPath();g.moveTo(0,j);g.lineTo(1080,j);g.stroke();}
 for(var k=0;k<38;k++){var x=(k*227.7)%1000+40,y=(k*433.5)%1680+40;g.fillStyle='rgba(112,250,215,'+(.12+.10*Math.sin(t*.7+k))+')';g.beginPath();g.arc(x,y,2,0,7);g.fill();}
}
function frame(g,a,t,W,H){
 g.setTransform(W/1080,0,0,H/1920,0,0);background(g,t);
 var z=a.r.markets,ch=a.chosen;
 function part(start,end,draw){var alpha=ease((t-start)/.75)*ease((end-t)/.75);if(alpha<=0)return;g.save();g.globalAlpha=alpha;draw(ease((t-start)/(end-start)),t-start);g.restore();}
 part(0,5,function(f,u){
   label(g,'MATCH INTELLIGENCE',540,365,39,'#67e6ca');
   label(g,a.home.toLocaleUpperCase('tr-TR'),540,630,Math.min(94,1150/Math.max(12,a.home.length)),'#f4ffff');
   label(g,'V S',540,790,48,'#91b2c1');
   label(g,a.away.toLocaleUpperCase('tr-TR'),540,960,Math.min(94,1150/Math.max(12,a.away.length)),'#f4ffff');
   rect(g,205,1155,670,117,34,'#123a40','#376b66');label(g,'FUTSIM VIDEO STÜDYOSU',540,1214,34,'#72f5d6');
   ring(g,540,790,335+8*Math.sin(u),.2,6.05,'rgba(88,230,205,.3)',4);
 });
 part(5,12,function(f,u){
   label(g,'SİMÜLASYON MOTORU',540,358,41,'#92c4cc');
   label(g,Math.round(100000*ease(f)).toLocaleString('tr-TR'),540,605,138,'#5bf8c9');
   label(g,'İKİ DEVRELİ 100.000 MAÇ',540,718,36,'#ecffff');
   rect(g,95,863,890,505,31,'rgba(13,37,47,.92)','#235c66');
   for(var i=0;i<90;i++){var angle=i*2.39996+u*.12,r=34+175*Math.sqrt(i/90),x=540+Math.cos(angle)*r,y=1110+Math.sin(angle)*r;
     g.fillStyle=i%7===0?'#a6bcff':'#55e4c6';g.beginPath();g.arc(x,y,3.5,0,7);g.fill();}
   rect(g,130,1470,820,15,7,'#1b3d45');g.fillStyle='#67ffd0';g.fillRect(130,1470,820*f,15);
   label(g,'OLASI GOL SENARYOLARI HESAPLANIYOR',540,1560,26,'#86aabb');
 });
 part(12,21,function(f,u){
   label(g,'MODEL SONUÇLARI',540,351,43,'#68efcf');
   var items=[{name:a.home,val:z['1'],color:'#5cf0c5'},{name:'BERABERLİK',val:z.X,color:'#acc4d1'},{name:a.away,val:z['2'],color:'#999fff'}];
   items.forEach(function(v,i){var y=555+i*276;rect(g,81,y,918,225,31,'#102938','#2d5162');
     label(g,v.name.toLocaleUpperCase('tr-TR'),116,y+54,36,'#edf7ff','left');
     label(g,percent(v.val),956,y+54,54,v.color,'right');
     rect(g,112,y+141,840,19,9,'#214252');g.fillStyle=v.color;g.fillRect(112,y+141,840*v.val/100*ease((u-i*.45)/2.8),19);
   });
   label(g,Math.abs(z['1']-z['2'])<3?'İKİ TAKIM BİRBİRİNE ÇOK YAKIN':'GALİBİYET DAĞILIMI',540,1525,30,'#a7dacc');
 });
 part(21,29,function(f,u){
   label(g,'SKOR LABORATUVARI',540,342,44,'#62e9c7');
   label(g,'EN SIK GERÇEKLEŞEN SKOR',540,509,29,'#aac4d1');
   label(g,ch.modal.score.replace('-', ' : '),540,692,160,'#f5fdff');
   label(g,'ORAN '+percent(ch.modal.p),540,839,40,'#64f8d0');
   rect(g,100,1035,880,348,38,'#17283c','#38596b');
   label(g,'FAVORİ SONUCUN TEMSİLÎ SKORU',540,1133,29,'#acc2d4');
   label(g,ch.representative.score.replace('-', ' : '),540,1262,113,'#a5b7ff');
   label(g,'En sık skor ile favori sonuç farklı olabilir',540,1508,27,'#a1b5c4');
 });
 part(29,35,function(f,u){
   label(g,'TOPLAM GOL',540,340,44,'#64eccb');label(g,'2,5 ALT / ÜST',540,448,69,'#ecfaff');
   var under=z['2,5 Alt'],over=z['2,5 Üst'],st=-Math.PI/2;
   ring(g,540,1000,243,0,Math.PI*2,'#244253',58);
   ring(g,540,1000,243,st,st+Math.PI*2*under/100*ease(u/2),'#64f5cb',58);
   ring(g,540,1000,243,st+Math.PI*2*under/100,st+Math.PI*2*(under+over)/100*ease(u/2),'#a6a8ff',58);
   label(g,'100.000',540,983,81,'#fff');label(g,'MAÇ',540,1075,30,'#92b6c2');
   label(g,'ALT '+percent(under),260,1470,48,'#64f5cb');
   label(g,'ÜST '+percent(over),815,1470,48,'#b5b5ff');
 });
 part(35,40,function(f,u){
   label(g,'KARŞILIKLI GOL',540,430,46,'#b3ccd8');
   label(g,percent(z['KG Var']),540,649,155,'#64ffd2');
   label(g,'FUTSIM',540,1041,131,'#fbffff');
   g.fillStyle='#5ad7bd';g.fillRect(220,1153,640,4);
   label(g,'HER MAÇIN BİR OLASILIĞI VAR',540,1234,37,'#9fe6d5');
   label(g,'Simülasyon tahminidir, kesin sonuç değildir',540,1432,25,'#91abb9');
 });
 // Fixed visual identity / progress.
 label(g,'F U T S I M',71,114,38,'#6cf9d3','left');
 label(g,'// VIDEO STUDIO',73,161,23,'#779da9','left',650);
 label(g,'100K  /  DATA DRIVEN',1008,119,22,'#87b2bd','right',700);
 g.fillStyle='#1e4654';g.fillRect(70,205,940,2);g.fillRect(70,1850,940,3);
 g.fillStyle='#5efad0';g.fillRect(70,1850,940*limit(t/duration),4);
 label(g,a.date||a.asof||'FUTSIM',74,1812,24,'#8aaebb','left',650);
 label(g,'40 SEC  ·  9:16  ·  100.000',1009,1812,23,'#8aaebb','right',650);
}
function buildRecorder(stream){if(!window.MediaRecorder)return null;
 var options=['video/mp4;codecs=avc1.42E01E','video/mp4','video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'];
 for(var i=0;i<options.length;i++){try{if(MediaRecorder.isTypeSupported(options[i]))return new MediaRecorder(stream,{mimeType:options[i],videoBitsPerSecond:7000000});}catch(e){}}
 try{return new MediaRecorder(stream,{videoBitsPerSecond:7000000});}catch(e){return null;}
}
async function create(){
 if(working)return;
 try{
  status('FUTSIM 100.000 yeni maç simülasyonu çalıştırıyor…');
  await new Promise(function(resolve){setTimeout(resolve,30);});
  var a=analyze();details(a);
  var canvas=el('studioCanvas'),quality=el('studioQuality').value;
  canvas.width=quality==='hd'?1080:720;canvas.height=quality==='hd'?1920:1280;
  var g=canvas.getContext('2d',{alpha:false});if(!g||!canvas.captureStream)throw Error('Bu tarayıcı video kaydını desteklemiyor. Chrome veya Edge dene.');
  frame(g,a,0,canvas.width,canvas.height);
  var stream=canvas.captureStream(30),rec=buildRecorder(stream);
  if(!rec){stream.getTracks().forEach(function(t){t.stop();});throw Error('Tarayıcı MediaRecorder desteklemiyor.');}
  var chunks=[],btn=el('studioGenerate'),video=el('studioVideoPreview'),download=el('studioVideoDownload');
  working=true;btn.disabled=true;download.hidden=true;video.hidden=true;
  rec.ondataavailable=function(e){if(e.data&&e.data.size)chunks.push(e.data);};
  rec.onerror=function(){status('Video kaydında hata oluştu.');};
  rec.onstop=function(){
   working=false;btn.disabled=false;stream.getTracks().forEach(function(t){t.stop();});
   var typ=rec.mimeType||'video/webm',ext=typ.indexOf('mp4')>=0?'mp4':'webm';
   var blob=new Blob(chunks,{type:typ});if(!blob.size){status('Video kaydı boş geldi, tekrar dene.');return;}
   if(lastUrl)URL.revokeObjectURL(lastUrl);lastUrl=URL.createObjectURL(blob);
   video.src=lastUrl;video.hidden=false;download.href=lastUrl;download.download='FUTSIM_'+clean(a.home)+'_'+clean(a.away)+'_100K_sessiz.'+ext;download.hidden=false;
   status('Video hazır! '+duration+' saniye sessiz '+ext.toUpperCase()+'. Metni indirip seslendirdikten sonra video ve MP3 dosyasını ChatGPT’ye yükle.');
  };
  rec.start(500);
  var begin=performance.now(),lastSecond=-1;
  function tick(now){
   if(!working)return;var t=Math.min(duration,(now-begin)/1000);
   frame(g,a,t,canvas.width,canvas.height);
   var s=Math.floor(t);if(s!==lastSecond){lastSecond=s;status('FUTSIM video oluşturuluyor: '+s+'/'+duration+' saniye. Bu sekmeyi açık ve görünür tut.');}
   if(t>=duration){rec.stop();return;}
   requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
 }catch(e){working=false;el('studioGenerate').disabled=false;status('Video oluşturulamadı: '+(e.message||e));}
}
function init(){if(!el('studioGenerate'))return;
 el('studioGenerate').addEventListener('click',create);
 el('studioJump').addEventListener('click',function(){el('videoStudio').scrollIntoView({behavior:'smooth'});});
 status('Maçı yukarıdan seç. Butona basınca FUTSIM 100.000 yeni simülasyon çalıştırır.');
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();