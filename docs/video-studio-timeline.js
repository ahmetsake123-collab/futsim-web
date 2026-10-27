/* FUTSIM Scene Studio: script-first scenes, audio-guided timeline, browser capture.
   No external API. The match simulator stays in the main FUTSIM script. */
(function(){
'use strict';
const $=id=>document.getElementById(id);
let sceneData=[],active=null,voice=null,voiceURL='',audioBuffer=null,voiceContext=null;
let timing=[],rendering=false,previewFrame=0,api=null,dirty=false;
const chapters=[
 {id:'intro',label:'Maç açılışı',window:[0,2]},
 {id:'engine',label:'100.000 simülasyon',window:[2,6]},
 {id:'result',label:'Maç sonucu ve favori',window:[6,13]},
 {id:'scores',label:'En olası altı skor',window:[13,23]},
 {id:'ai-score',label:'Skor tercihi',window:[23,29]},
 {id:'goals',label:'2,5 alt / üst',window:[29,35]},
 {id:'btts',label:'KG var / yok',window:[35,40]},
 {id:'bet',label:'Bahis tercihi',window:[40,46]},
 {id:'outro',label:'FUTSIM kapanışı',window:[46,49]}
];
const r1=x=>Math.round(x*10)/10;
const clamp=(v,min,max)=>Math.min(max,Math.max(min,v));
function st(s){if($('studioStatus'))$('studioStatus').textContent=s;}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function pct(x){return '%'+Number(x).toLocaleString('tr-TR',{maximumFractionDigits:1,minimumFractionDigits:1});}
function score(x){return String(x||'').replace('-', ' - ');}
function sceneScript(a){
 const m=a.r.markets,bet=api.bestMarket(a),fav=api.matchup(a),scores=a.r.allScores||[];
 const modal=a.chosen.modal,rep=a.chosen.representative;
 const other=scores.filter(x=>x.score!==modal.score);
 return [
  api.opening(a),
  'FUTSIM bu maçı tam yüz bin kez simüle etti.',
  a.home+' yüzde '+Math.round(m['1'])+', beraberlik yüzde '+Math.round(m.X)+', '+a.away+' yüzde '+Math.round(m['2'])+'. '+(fav.favori?fav.favori+' favori.':fav.spoken),
  'En sık skor '+score(modal.score)+', yüzde '+Math.round(modal.p)+'. Alternatifler '+other.slice(0,2).map(x=>score(x.score)+' yüzde '+Math.round(x.p)).join(', ')+'.',
  'Yapay zekânın tercih ettiği skor '+score(rep.score)+'.',
  'İki buçuk gol üstü yüzde '+Math.round(m['2,5 Üst'])+', altı yüzde '+Math.round(m['2,5 Alt'])+'.',
  'Karşılıklı gol var yüzde '+Math.round(m['KG Var'])+', yok yüzde '+Math.round(100-m['KG Var'])+'.',
  bet?'Yapay zekânın tercih ettiği bahis: '+bet.spoken+', yüzde '+Math.round(bet.p)+'. Bu, garanti değil, model olasılığıdır.':'Bahis seçimi için yeterli veri yok.',
  'FUTSIM. Her maçın bir olasılığı var.'
 ];
}
function speechText(){return sceneData.map(x=>x.text.trim()).filter(Boolean).join('\n\n');}
function refreshScript(){
 if($('studioScript')){$('studioScript').value=speechText();$('studioScript').readOnly=true;}
}
function weights(){return sceneData.map(s=>{let t=s.text,words=t.trim().split(/\s+/).length;return Math.max(1.3,words*.36+(t.match(/[,.;:]/g)||[]).length*.16+.25);});}
function weightedTimes(duration){
 const w=weights(),total=w.reduce((v,x)=>v+x,0);
 let t=0;return w.map((v,i)=>{const start=t;t+=v/total*duration;return i===0?0:r1(start);});
}
function detectPauses(buffer){
 let samples=buffer.getChannelData(0),rate=buffer.sampleRate,hop=Math.max(128,Math.floor(rate*.025));
 const rms=[];for(let p=0;p<samples.length;p+=hop){let sum=0,len=Math.min(hop,samples.length-p);
   for(let i=0;i<len;i+=3){let x=samples[p+i];sum+=x*x;}rms.push(Math.sqrt(sum/Math.max(1,Math.ceil(len/3))));}
 const sorted=[...rms].sort((a,b)=>a-b);
 const p95=sorted[Math.floor(sorted.length*.95)]||.01;
 const threshold=Math.max(.0017,Math.min(.028,p95*.09));
 let groups=[],start=-1;for(let i=0;i<=rms.length;i++){
  if(i<rms.length&&rms[i]<=threshold){if(start<0)start=i;}
  else if(start>=0){if((i-start)*hop/rate>=.09)groups.push({t:(start+i)*.5*hop/rate,length:(i-start)*hop/rate});
    start=-1;}
 }
 return groups;
}
function alignTimes(){
 if(!sceneData.length)return;
 const total=audioBuffer?audioBuffer.duration:Math.max(36,Math.min(59,weights().reduce((x,y)=>x+y,0)*1.07));
 const predicted=weightedTimes(total);
 let starts=[...predicted];
 if(audioBuffer){
  // Global alignment: prefer meaningful MP3 pauses near the expected scene
  // positions, while keeping all boundaries strictly ordered. This avoids
  // local decisions drifting into the following sentence.
  const pauses=detectPauses(audioBuffer).filter(p=>p.t>.5&&p.t<total-.5&&p.length>=.105)
    .sort((a,b)=>a.t-b.t);
  const stages=[];
  const n=sceneData.length,window=Math.max(5.5,total*.16);
  stages.push([{t:0,cost:0,prev:-1}]);
  for(let i=1;i<n;i++){
   const minLeft=i*.48,maxRight=total-(n-i)*.48;
   const matches=pauses.filter(p=>p.t>=minLeft&&p.t<=maxRight&&Math.abs(p.t-predicted[i])<window)
    .map(p=>({t:r1(p.t),pause:p.length}));
   matches.push({t:predicted[i],pause:0});
   const unique=[...new Map(matches.map(c=>[c.t,c])).values()].sort((a,b)=>a.t-b.t);
   const stage=[];
   for(const c of unique){
    let best=null;
    for(let j=0;j<stages[i-1].length;j++){
     const prior=stages[i-1][j];
     const gap=c.t-prior.t,expected=predicted[i]-predicted[i-1];
     if(gap<.48)continue;
     const penalty=.065*Math.pow(c.t-predicted[i],2)+.04*Math.pow(gap-expected,2)-
       Math.min(.8,c.pause)*3.1+(c.pause===0?.48:0);
     const cost=prior.cost+penalty;
     if(!best||cost<best.cost)best={t:c.t,pause:c.pause,cost,prev:j};
    }
    if(best)stage.push(best);
   }
   // Always provide a fallback when speech has no detectable pauses.
   if(!stage.length){
    const prev=stages[i-1].reduce((v,x,j)=>x.cost<v.item.cost?{item:x,index:j}:v,
      {item:{cost:Infinity},index:-1});
    const fallback=clamp(Math.max(predicted[i],prev.item.t+.48),minLeft,maxRight);
    stage.push({t:r1(fallback),cost:prev.item.cost+10,prev:prev.index,pause:0});
   }
   stages.push(stage);
  }
  const last=stages[n-1];
  let index=0,bestCost=Infinity;
  for(let j=0;j<last.length;j++){
   const remaining=total-last[j].t,expected=total-predicted[n-1];
   const cost=last[j].cost+.055*Math.pow(remaining-expected,2);
   if(cost<bestCost){bestCost=cost;index=j;}
  }
  for(let i=n-1;i>=1;i--){
   const node=stages[i][index];starts[i]=node.t;index=node.prev;
  }
 }
 timing=starts;updateEditorTimes();
}
function spanFor(i){
 const end=i+1<sceneData.length?timing[i+1]:totalDuration();
 return Math.max(.1,end-timing[i]);
}
function totalDuration(){return audioBuffer?audioBuffer.duration+.3:Math.max(36,Math.min(59,weights().reduce((x,y)=>x+y,0)*1.07));}
function currentScene(t){
 let i=0;for(let j=1;j<timing.length;j++)if(t>=timing[j])i=j;
 return i;
}
function renderCanvas(g,a,t,w,h){
 const i=currentScene(t),sc=chapters[i],st=Math.max(0,t-timing[i]),span=spanFor(i);
 const u=clamp(st/Math.max(.1,span),0,.999);
 const mapped=sc.window[0]+(sc.window[1]-sc.window[0])*(.05+.90*u);
 api.frame(g,a,mapped,w,h);
 g.setTransform(w/1080,0,0,h/1920,0,0);
 // A shared caption is authored directly from the selected scene paragraph.
 const text=sceneData[i]?.text||'',lines=[];
 const words=text.split(/\s+/);let line='';
 for(const word of words){if((line+' '+word).trim().length>49&&line){lines.push(line);line=word;}else line=(line+' '+word).trim();}
 if(line)lines.push(line);
 g.save();g.globalAlpha=.94;g.fillStyle='#061824';g.beginPath();g.roundRect(95,1581,890,Math.min(174,53+lines.slice(0,3).length*39),22);g.fill();g.restore();
 g.save();g.textAlign='center';g.textBaseline='middle';g.fillStyle='#e7fafa';g.font='600 28px system-ui,Arial';
 lines.slice(0,3).forEach((txt,j)=>g.fillText(txt,540,1624+j*38,836));
 g.restore();
}
function drawNow(t){
 if(!active||!api)return;
 const c=$('studioCanvas');if(!c)return;
 const g=c.getContext('2d',{alpha:false});if(!g)return;
 renderCanvas(g,active,t,c.width,c.height);
 const indicator=$('studioActiveScene');if(indicator)indicator.textContent=(currentScene(t)+1)+' / '+sceneData.length+' · '+chapters[currentScene(t)].label;
 const fill=$('studioSyncProgress');if(fill)fill.value=t;
}
function updateEditorTimes(){
 if(!sceneData.length)return;
 const box=$('studioSceneList');if(!box)return;
 box.innerHTML=sceneData.map((s,i)=>'<div class="scene-row" data-sceneno="'+i+'">'+
   '<div class="scene-row-head"><b>'+('0'+(i+1)).slice(-2)+' · '+esc(chapters[i].label)+'</b>'+
   '<label>Başlangıç (sn) <input type="number" step="0.1" min="0" data-scenestart="'+i+'" value="'+timing[i].toFixed(1)+'" '+(i===0?'disabled':'')+'></label></div>'+
   '<textarea rows="2" data-scenetext="'+i+'" aria-label="'+esc(chapters[i].label)+' metni">'+esc(s.text)+'</textarea></div>').join('');
 box.querySelectorAll('input[data-scenestart]').forEach(inp=>inp.addEventListener('change',()=>{
  let i=Number(inp.dataset.scenestart),max=i===timing.length-1?totalDuration()-.3:timing[i+1]-.3;
  let min=timing[i-1]+.3;
  timing[i]=r1(clamp(Number(inp.value)||min,min,Math.max(min,max)));
  inp.value=timing[i].toFixed(1);drawNow(timing[i]);
 }));
 box.querySelectorAll('textarea[data-scenetext]').forEach(txt=>txt.addEventListener('input',()=>{
  sceneData[Number(txt.dataset.scenetext)].text=txt.value;dirty=true;refreshScript();
 }));
 const duration=totalDuration();if($('studioSyncProgress')){$('studioSyncProgress').max=duration;$('studioSyncProgress').step=.05;}
 drawNow(0);
}
function setup(a,external){
 if(external)api=external;
 if(!api)return;
 active=a;sceneData=sceneScript(a).map((t,i)=>({...chapters[i],text:t}));
 dirty=false;refreshScript();alignTimes();
 const list=$('studioTimelinePanel');if(list)list.hidden=false;
 st('Sahneler metne göre oluşturuldu. '+(audioBuffer?'MP3 için yaklaşık zamanlar hesaplandı. Dinleyerek sınırları kontrol et.':'MP3 yükleyince sahne başlangıçlarını sese göre ayarlayacağım.'));
}
async function loadVoice(file){
 if(!file)return;
 if(voiceURL)URL.revokeObjectURL(voiceURL);
 voice=file;voiceURL=URL.createObjectURL(file);
 if($('studioAudioPlayer'))$('studioAudioPlayer').src=voiceURL;
 try{
  const AC=window.AudioContext||window.webkitAudioContext;
  if(!AC)throw Error('Ses çözümleme için Chrome veya Edge kullan.');
  if(!voiceContext)voiceContext=new AC();
  const bytes=await file.arrayBuffer();
  audioBuffer=await voiceContext.decodeAudioData(bytes);
  if(sceneData.length)alignTimes();
  st('MP3 yüklendi ('+r1(audioBuffer.duration)+' sn). Sessizliklerden yaklaşık sahne sınırları bulundu. Önizleyip gerekirse saniyeleri düzenle.');
 }catch(e){audioBuffer=null;st('MP3 okunamadı: '+e.message);}
}
function preview(){
 const player=$('studioAudioPlayer');if(!player||!voiceURL){st('Önce MP3 yükle.');return;}
 if(!sceneData.length){st('Önce 100.000 simülasyonu ve metni oluştur.');return;}
 if(player.paused){player.play().catch(e=>st('Ses oynatılamadı: '+e.message));}else player.pause();
}
function watchPreview(){
 const player=$('studioAudioPlayer');if(!player||player.paused||!active)return;
 drawNow(player.currentTime);
 previewFrame=requestAnimationFrame(watchPreview);
}
function syncData(){
 return {model:'FUTSIM 100000',home:active?.home,away:active?.away,date:active?.date,
  voice_name:voice?.name||null,voice_duration:audioBuffer?.duration||null,
  duration:totalDuration(),source:'Approximate pause detection, manual timestamps allowed',
  scenes:sceneData.map((s,i)=>({id:s.id,title:s.label,start:timing[i],end:i+1<timing.length?timing[i+1]:totalDuration(),narration:s.text}))};
}
async function prepare(external){
 api=external;
 try{
  st('FUTSIM 100.000 simülasyon hesaplıyor...');
  await new Promise(resolve=>setTimeout(resolve,30));
  const a=api.analyze();api.details(a);setup(a,api);
 }catch(e){st('Analiz hazırlanamadı: '+e.message);}
}
async function create(external,forceSynced){
 if(rendering)return;
 api=external;
 try{
  if(!active||!forceSynced){
   st('FUTSIM 100.000 maç hesaplıyor; sahne metinleri hazırlanıyor...');
   await new Promise(resolve=>setTimeout(resolve,40));
   const a=api.analyze();api.details(a);setup(a,external);
  }
  if(!active)throw Error('Önce analiz oluştur.');
  if(forceSynced&&!audioBuffer)throw Error('Sesli video için MP3 dosyası yükle.');
  const button=$('studioGenerate'),soundButton=$('studioRenderSynced');
  const c=$('studioCanvas'),quality=$('studioQuality').value;c.width=quality==='hd'?1080:720;c.height=quality==='hd'?1920:1280;
  let g=c.getContext('2d',{alpha:false});if(!g||!c.captureStream)throw Error('Tarayıcıda canvas video kayıt desteği yok.');
  const visual=c.captureStream(30);let stream=visual,ctx=null,source=null,speaker=null,startAt=0;
  if(forceSynced&&audioBuffer){
   const AC=window.AudioContext||window.webkitAudioContext;
   ctx=new AC();await ctx.resume();
   source=ctx.createBufferSource();source.buffer=audioBuffer;speaker=ctx.createMediaStreamDestination();
   source.connect(speaker);source.connect(ctx.destination);
   stream=new MediaStream([...visual.getVideoTracks(),...speaker.stream.getAudioTracks()]);
  }
  const recorder=api.buildRecorder(stream);
  if(!recorder)throw Error('Bu tarayıcı video kaydedemiyor. Chrome veya Edge dene.');
  let chunks=[];const video=$('studioVideoPreview'),down=$('studioVideoDownload');
  video.hidden=true;down.hidden=true;rendering=true;
  button.disabled=true;if(soundButton)soundButton.disabled=true;
  recorder.ondataavailable=e=>{if(e.data&&e.data.size)chunks.push(e.data);};
  const total=totalDuration();
  recorder.onerror=e=>st('Kayıt hatası. Format desteğini kontrol et.');
  recorder.onstop=()=>{
   rendering=false;button.disabled=false;if(soundButton)soundButton.disabled=false;
   stream.getTracks().forEach(x=>x.stop());
   if(source){try{source.disconnect();}catch(e){}}
   if(ctx)ctx.close().catch(()=>{});
   const mime=recorder.mimeType||'video/webm',ext=mime.includes('mp4')?'mp4':'webm';
   const blob=new Blob(chunks,{type:mime});
   if(!blob.size){st('Kayıt boş; başka tarayıcı veya 720p dene.');return;}
   if(window._futsimPrevUrl)URL.revokeObjectURL(window._futsimPrevUrl);
   window._futsimPrevUrl=URL.createObjectURL(blob);
   video.src=window._futsimPrevUrl;video.hidden=false;down.href=video.src;
   down.download='FUTSIM_'+api.clean(active.home)+'_'+api.clean(active.away)+'_100K_'+(forceSynced?'SESLI':'SESSIZ')+'.'+ext;down.hidden=false;
   st('Tamamlandı: '+r1(total)+' sn '+(forceSynced?'sesli':'sessiz')+' video. Sahneler metin sırasına göre kuruldu. Önizlemede zamanları kontrol et.');
  };
  drawNow(0);
  recorder.start(500);
  const startWall=performance.now()+150;
  if(source){startAt=ctx.currentTime+.15;source.start(startAt);}
  let last=-1;
  function tick(){
   if(!rendering)return;
   const t=source?ctx.currentTime-startAt:(performance.now()-startWall)/1000;
   const clamped=clamp(t,0,total);
   renderCanvas(g,active,clamped,c.width,c.height);
   if(Math.floor(clamped)!==last){last=Math.floor(clamped);st('Video dışa aktarılıyor: '+last+' / '+Math.round(total)+' sn. Sekmeyi açık tut.');}
   if(t>=total){recorder.stop();return;}
   requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
 }catch(e){rendering=false;if($('studioGenerate'))$('studioGenerate').disabled=false;if($('studioRenderSynced'))$('studioRenderSynced').disabled=false;st('Video oluşturma hatası: '+e.message);}
}
function init(){
 const file=$('studioVoiceFile');if(file)file.addEventListener('change',()=>loadVoice(file.files?.[0]));
 $('studioRenderSynced')?.addEventListener('click',()=>{if(!api)st('Önce FUTSIM analizi oluştur.');else create(api,true);});
 $('studioPreviewSync')?.addEventListener('click',preview);
 $('studioAudioPlayer')?.addEventListener('play',()=>{cancelAnimationFrame(previewFrame);watchPreview();});
 $('studioAudioPlayer')?.addEventListener('pause',()=>cancelAnimationFrame(previewFrame));
 $('studioAudioPlayer')?.addEventListener('seeked',()=>drawNow($('studioAudioPlayer').currentTime));
 $('studioSyncProgress')?.addEventListener('input',e=>{const t=Number(e.target.value);drawNow(t);if($('studioAudioPlayer')&&voiceURL)$('studioAudioPlayer').currentTime=t;});
 $('studioSaveTimeline')?.addEventListener('click',()=>{
  if(!active){st('Önce analiz üret.');return;}
  const a=document.createElement('a'),blob=new Blob([JSON.stringify(syncData(),null,2)],{type:'application/json'});
  a.href=URL.createObjectURL(blob);a.download='FUTSIM_sahne_zamanlari.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),60000);
 });
}
window.FUTSIM_STUDIO_SYNC={init,setup,prepare,create,syncData,speechText,bestScene:()=>sceneData};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();