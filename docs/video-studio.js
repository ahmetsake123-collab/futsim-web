/* FUTSIM Video Studio | Rendered in the browser. No server or paid service. */
(function(){
'use strict';
var duration=49, lastUrl=null, working=false;
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

function matchup(a){
 var m=a.r.markets,home=m['1'],away=m['2'],d=Math.abs(home-away);
 if(d>=8&&Math.max(home,away)>=40)return {favori:home>away?a.home:a.away,headline:(home>away?a.home:a.away)+' FAVORİ',spoken:'Bu maçın favorisi '+(home>away?a.home:a.away)+'.'};
 return {favori:null,headline:'DENGELİ MAÇ · NET FAVORİ YOK',spoken:'İki takımın galibiyet ihtimali birbirine yakın. Bu maçta net bir favori yok.'};
}
function opening(a){
 var today=typeof istanbulDay==='function'?istanbulDay():null;
 return a.date&&a.date===today?'Bugün '+a.home+' ve '+a.away+' karşı karşıya.':a.home+' ve '+a.away+' karşı karşıya.';
}
function spokenScore(s){return String(s||'').replace('-', ' - ');}
function speech(a){
 var m=a.r.markets,top=a.r.allScores.slice(0,6),close=matchup(a);
 var others=top.filter(function(x){return x.score!==a.chosen.modal.score;});
 var first=others[0],second=others[1],half=(a.r.halves||[])[0];
 return opening(a)+'\n\n'+
  'FUTSIM bu maç için yüz bin simülasyon çalıştırdı. '+a.home+' galibiyeti yüzde '+Math.round(m['1'])+
  ', beraberlik yüzde '+Math.round(m.X)+', '+a.away+' galibiyeti yüzde '+Math.round(m['2'])+'. '+
  close.spoken+'\n\nEn sık görülen skor '+spokenScore(a.chosen.modal.score)+', ihtimali yüzde '+Math.round(a.chosen.modal.p)+
  '. Diğer olası skorlar '+spokenScore(first?.score||a.chosen.modal.score)+' yüzde '+Math.round(first?.p||0)+
  ', ve '+spokenScore(second?.score||a.chosen.modal.score)+' yüzde '+Math.round(second?.p||0)+'. '+
  'Yapay zekânın tercih ettiği skor '+spokenScore(a.chosen.representative.score)+'.\n\n'+
  'İki buçuk gol üstü yüzde '+Math.round(m['2,5 Üst'])+', altı yüzde '+Math.round(m['2,5 Alt'])+
  '. Karşılıklı gol ihtimali yüzde '+Math.round(m['KG Var'])+'. '+
  (half?'En sık ilk yarı skoru '+spokenScore(half.score)+'. ':'')+
  '\nFUTSIM. Her maçın bir olasılığı var.';
}
function details(a){
 var m=a.r.markets;
 el('studioDigest').innerHTML='<b>'+escapeHTML(a.home)+' – '+escapeHTML(a.away)+'</b><br>'+
 '100.000 simülasyon · 1: '+percent(m['1'])+' · X: '+percent(m.X)+' · 2: '+percent(m['2'])+
 '<br>En sık skor: '+escapeHTML(a.chosen.modal.score)+' ('+percent(a.chosen.modal.p)+')'+
 ' · Yapay zekânın tercih ettiği skor: '+escapeHTML(a.chosen.representative.score)+
 '<br>En olası 6 skor: '+a.r.allScores.slice(0,6).map(function(x){return escapeHTML(x.score)+' ('+percent(x.p)+')';}).join(' · ')+
 '<br>'+escapeHTML(matchup(a).spoken)+
 '<br>2,5 Alt: '+percent(m['2,5 Alt'])+' · Üst: '+percent(m['2,5 Üst'])+' · KG Var: '+percent(m['KG Var'])+
 (!a.date?'<br><small>Bu eşleşmenin önümüzdeki 7 günlük fikstürdeki tarihi doğrulanmadı; özel karşılaştırma.</small>':'');
 el('studioScript').value=speech(a);el('studioTextControls').hidden=false;
 el('studioSaveText').onclick=function(){save(new Blob([el('studioScript').value],{type:'text/plain;charset=utf-8'}),'FUTSIM_'+clean(a.home)+'_'+clean(a.away)+'_metin.txt');};
 el('studioCopyText').onclick=async function(){try{await navigator.clipboard.writeText(el('studioScript').value);status('Seslendirme metni kopyalandı.');}catch(e){el('studioScript').select();status('Metin seçildi. Ctrl+C ile kopyalayabilirsin.');}};
 el('studioSaveData').onclick=function(){
  var result={home:a.home,away:a.away,competition:a.competition,fixture_date:a.date,asof:a.asof,
   generated_at:a.created,engine:'FUTSIM two-half Monte Carlo',simulations:100000,
   model_goal_parameters:{home:a.p.lh,away:a.p.la},markets:m,matchup_classification:matchup(a).headline,
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
 g.setTransform(W/1080,0,0,H/1920,0,0);
 background(g,t);
 var z=a.r.markets,ch=a.chosen,judgement=matchup(a);
 function part(start,end,draw){
  var alpha=ease((t-start)/.58)*ease((end-t)/.58);
  if(alpha<=0)return;
  g.save();g.globalAlpha=alpha;draw(ease((t-start)/(end-start)),t-start);g.restore();
 }
 function bar(x,y,w,h,value,col,progress){
  rect(g,x,y,w,h,h/2,'#21404c');
  var amount=Math.max(0,w*Math.max(0,Math.min(100,value))/100*ease(progress));
  if(amount>0.5)rect(g,x,y,amount,h,Math.min(h/2,amount/2),col);
 }
 function progressBox(x,y,w,h,title,value,col,stagger){
  rect(g,x,y,w,h,22,'#102a35','#35616a');
  label(g,title,x+27,y+34,27,'#e5f6fb','left',700);
  label(g,percent(value),x+w-28,y+37,32,col,'right',850);
  bar(x+28,y+81,w-56,11,value,col,stagger);
 }
 part(0,4,function(f,u){
  label(g,'MAÇ GÜNÜ',540,354,40,'#6ff0c8');
  label(g,a.home.toLocaleUpperCase('tr-TR'),540,633,Math.min(92,1160/Math.max(12,a.home.length)),'#f4ffff');
  label(g,'V S',540,798,52,'#8cacba');
  label(g,a.away.toLocaleUpperCase('tr-TR'),540,967,Math.min(92,1160/Math.max(12,a.away.length)),'#f4ffff');
  ring(g,540,798,341+8*Math.sin(u),.15,6.1,'rgba(88,230,205,.3)',4);
  label(g,'100.000 SİMÜLASYON / GERÇEK FUTSIM MOTORU',540,1255,29,'#78d5bd');
 });
 part(4,10,function(f,u){
  label(g,'100.000 MAÇ SENARYOSU',540,345,46,'#a5c9d0');
  label(g,Math.round(100000*ease(f)).toLocaleString('tr-TR'),540,584,137,'#58efc7');
  label(g,'İKİ DEVRELİ MONTE CARLO',540,704,33,'#e0f6f1');
  rect(g,99,852,882,482,30,'#0f2731','#2b5962');
  for(var i=0;i<135;i++){
   var angle=i*2.39996+u*.1,r=34+184*Math.sqrt(i/135),x=540+Math.cos(angle)*r,y=1086+Math.sin(angle)*r;
   g.fillStyle=i%6===0?'#9db0ff':'#5ceacb';g.beginPath();g.arc(x,y,3.7,0,7);g.fill();
  }
  bar(131,1448,820,20,100,'#64ffcf',f);
  label(g,'100.000 OLASI KARŞILAŞMA ÜRETİLDİ',540,1542,27,'#a1d6d5');
 });
 part(10,17,function(f,u){
  label(g,'MAÇ SONUCU OLASILIKLARI',540,329,42,'#6cf4cf');
  [{key:'1',name:a.home,val:z['1'],color:'#56edbf'},
   {key:'X',name:'BERABERLİK',val:z.X,color:'#c1d3df'},
   {key:'2',name:a.away,val:z['2'],color:'#9ba9ff'}].forEach(function(v,i){
    var y=483+i*282;
    rect(g,82,y,916,243,28,'#102938','#2c5761');
    label(g,v.name.toLocaleUpperCase('tr-TR'),114,y+64,Math.min(41,670/Math.max(8,v.name.length)),'#ecffff','left');
    label(g,percent(v.val),963,y+65,50,v.color,'right');
    bar(114,y+154,848,19,v.val,v.color,(u-i*.35)/2.2);
  });
  rect(g,95,1404,890,114,25,'#14343f','#3e666c');
  label(g,judgement.headline,540,1461,Math.min(36,870/Math.max(14,judgement.headline.length)),'#a1efd9');
 });
 part(17,27,function(f,u){
  label(g,'EN OLASI SKORLAR',540,300,51,'#62f8ca');
  label(g,'EN SIK GÖRÜLEN SONUÇ',540,413,28,'#a6bfca');
  label(g,ch.modal.score.replace('-', ' : '),540,575,127,'#f5ffff');
  label(g,percent(ch.modal.p)+' OLASILIK',540,686,43,'#70f8cc');
  label(g,'DİĞER EN OLASI 5 SKOR',540,828,33,'#a2bdca');
  a.r.allScores.filter(function(x){return x.score!==ch.modal.score;}).slice(0,5).forEach(function(x,i){
   var y=899+i*116,reveal=ease((u-.55-i*.24)/1.2);
   g.save();g.globalAlpha*=reveal;
   rect(g,134,y,812,98,19,'#102c3b','#294b61');
   label(g,'0'+(i+2),172,y+49,30,'#638898','left');
   label(g,x.score.replace('-', ' : '),264,y+49,47,'#effaff','left');
   label(g,percent(x.p),898,y+49,41,i%2?'#aab7ff':'#5af5d0','right');
   g.restore();
  });
 });
 part(27,33,function(f,u){
  label(g,'YAPAY ZEKÂNIN TERCİH ETTİĞİ SKOR',540,409,37,'#91c1d3');
  rect(g,106,617,868,505,38,'#142c41','#416c7c');
  label(g,ch.representative.score.replace('-', ' : '),540,860,145,'#bdc0ff');
  label(g,percent(ch.representative.p)+' SKOR OLASILIĞI',540,1040,35,'#8cf3cb');
  label(g,judgement.headline,540,1354,35,'#79eecb');
  label(g,'MODELİN EN GÜÇLÜ SONUÇ GRUBUNDAN',540,1464,27,'#9dbcc9');
 });
 part(33,40,function(f,u){
  label(g,'GOL DAĞILIMI',540,348,46,'#62f2c9');
  label(g,'2,5 ALT / ÜST',540,458,69,'#ffffff');
  var under=z['2,5 Alt'],over=z['2,5 Üst'],start=-Math.PI/2;
  ring(g,540,1000,247,0,Math.PI*2,'#274652',58);
  ring(g,540,1000,247,start,start+Math.PI*2*under/100*ease(u/2),'#62efd1',58);
  ring(g,540,1000,247,start+Math.PI*2*under/100,start+Math.PI*2*(under+over)/100*ease(u/2),'#aab1ff',58);
  label(g,'100.000',540,980,81,'#ffffff');label(g,'SENARYO',540,1079,30,'#a5c0ce');
  label(g,'ALT '+percent(under),272,1488,47,'#63f6c8');
  label(g,'ÜST '+percent(over),810,1488,47,'#aab6ff');
 });
 part(40,45,function(f,u){
  var half=(a.r.halves||[])[0];
  label(g,'EK SENARYOLAR',540,346,48,'#6eefd1');
  rect(g,97,536,886,348,32,'#123240','#396274');
  label(g,'KARŞILIKLI GOL VAR',540,632,34,'#afcad3');
  label(g,percent(z['KG Var']),540,774,114,'#64f4c9');
  rect(g,97,959,886,370,32,'#182e47','#426478');
  label(g,'EN SIK İLK YARI SKORU',540,1061,33,'#b1ced7');
  label(g,half?half.score.replace('-', ' : '):'—',540,1197,107,'#b7c0ff');
  if(half)label(g,percent(half.p)+' OLASILIK',540,1404,37,'#a9b5fc');
 });
 part(45,49,function(f,u){
  label(g,'FUTSIM',540,767,145,'#f5ffff');
  g.fillStyle='#55dbc2';g.fillRect(216,903,648,4);
  label(g,'HER MAÇIN BİR OLASILIĞI VAR',540,1032,38,'#a5f1df');
  label(g,a.home.toLocaleUpperCase('tr-TR')+'   •   '+a.away.toLocaleUpperCase('tr-TR'),540,1276,30,'#9ab7c4');
 });
 label(g,'F U T S I M',73,120,39,'#6cf5cf','left');
 g.fillStyle='#1d444e';g.fillRect(70,187,940,2);
 g.fillStyle='#1a4a4b';g.fillRect(70,1785,940,3);
 g.fillStyle='#5bffce';g.fillRect(70,1785,940*limit(t/duration),4);
 label(g,'Yatırım tavsiyesi değildir.',1007,1849,27,'#b2c2cb','right',550);
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