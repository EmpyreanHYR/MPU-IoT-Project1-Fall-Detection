'use strict';
const notes=window.FALLGUARD_NOTES, byId=id=>document.getElementById(id);
const params=new URLSearchParams(location.search);
let targetSession=params.get('session')||'', current=Math.max(0,notes.findIndex(n=>n.id===params.get('slide')));
let lastStateAt=0,lastStamp=0,commandStamp=0,blanked=false,notesSize=24;
let channel=null;try{channel=new BroadcastChannel('fallguard-presenter-v1')}catch(_){/* Local-storage fallback below. */}
const clock={running:false,started:0,total:0,slideStarted:0,slideTotal:0};
const format=seconds=>`${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`;
function send(action,extra={}){
  commandStamp=Math.max(Date.now(),commandStamp+1);
  const message={type:'command',action,targetSession,...extra,stamp:commandStamp};
  if(channel)channel.postMessage(message);
  try{localStorage.setItem('fallguard-presenter-command',JSON.stringify(message))}catch(_){/* Storage may be disabled. */}
}
function resetSlideClock(){clock.slideTotal=0;clock.slideStarted=performance.now()}
function render(){
  const n=notes[current];byId('position').textContent=current<12?`${String(current+1).padStart(2,'0')} / 12`:`附录 ${current-11}`;
  byId('sectionLabel').textContent=n.label;byId('slideTitle').textContent=n.title;
  byId('notes').textContent=n[byId('language').value];byId('notes').lang=byId('language').value==='zh'?'zh-CN':'en';
  byId('budget').textContent=n.seconds?`/ ${n.seconds} 秒`:'/ 答辩附录';
  byId('nextTitle').textContent=notes[current+1]?.title||'已到最后一页';
  byId('jump').value=String(current);byId('previous').disabled=current===0;byId('next').disabled=current===notes.length-1;
  byId('blank').textContent=blanked?'恢复画面':'黑屏';
  byId('audienceLink').href='index.html?present=1#'+n.id;
}
function receive(message){
  if(message?.type!=='state'||(targetSession&&message.session!==targetSession)||message.stamp<=lastStamp)return;
  const next=notes.findIndex(n=>n.id===message.slideId);if(next<0)return;
  targetSession=message.session;lastStamp=message.stamp;lastStateAt=Date.now();blanked=message.blank;
  if(next!==current){current=next;resetSlideClock()}
  byId('connection').textContent='已连接观众页面 · 翻页与黑屏同步';render();
}
if(channel)channel.onmessage=event=>receive(event.data);
window.addEventListener('storage',event=>{if(event.key==='fallguard-presenter-state'&&event.newValue){try{receive(JSON.parse(event.newValue))}catch(_){}}});
notes.forEach((n,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=`${i<12?String(i+1).padStart(2,'0'):'A'+(i-11)} · ${n.label}`;byId('jump').append(option)});
byId('previous').onclick=()=>send('navigate',{slideId:notes[Math.max(0,current-1)].id});
byId('next').onclick=()=>send('navigate',{slideId:notes[Math.min(notes.length-1,current+1)].id});
byId('jump').onchange=()=>send('navigate',{slideId:notes[Number(byId('jump').value)].id});
byId('blank').onclick=()=>send('blank',{value:!blanked});
byId('language').onchange=render;
function resizeNotes(delta){notesSize=Math.max(18,Math.min(36,notesSize+delta));document.documentElement.style.setProperty('--notes-size',notesSize+'px')}
byId('fontDown').onclick=()=>resizeNotes(-2);byId('fontUp').onclick=()=>resizeNotes(2);
byId('timerToggle').onclick=()=>{
  const now=performance.now();
  if(clock.running){clock.total+=(now-clock.started)/1000;clock.slideTotal+=(now-clock.slideStarted)/1000}
  else{clock.started=now;clock.slideStarted=now}
  clock.running=!clock.running;byId('timerToggle').textContent=clock.running?'暂停计时':'继续计时';updateClock();
};
byId('timerReset').onclick=()=>{clock.total=clock.slideTotal=0;clock.started=clock.slideStarted=performance.now();byId('timerToggle').textContent=clock.running?'暂停计时':'开始计时';updateClock()};
function updateClock(){
  const now=performance.now(),total=clock.total+(clock.running?(now-clock.started)/1000:0),slide=clock.slideTotal+(clock.running?(now-clock.slideStarted)/1000:0);
  byId('elapsed').textContent=format(total);byId('slideElapsed').textContent=format(slide);
  byId('elapsed').classList.toggle('over-budget',total>480);
  byId('slideElapsed').classList.toggle('over-budget',notes[current].seconds>0&&slide>notes[current].seconds);
}
document.addEventListener('keydown',event=>{
  if(event.ctrlKey||event.metaKey||event.altKey||event.target.closest('input,select,textarea'))return;
  if(event.key===' '&&event.target.closest('button'))return;
  if(['ArrowRight','PageDown',' '].includes(event.key)){event.preventDefault();byId('next').click()}
  if(['ArrowLeft','PageUp'].includes(event.key)){event.preventDefault();byId('previous').click()}
  if(event.key.toLowerCase()==='b')byId('blank').click();
  if(event.key.toLowerCase()==='t')byId('timerToggle').click();
});
render();updateClock();send('request-state');
setInterval(updateClock,250);
setInterval(()=>{send('request-state');if(Date.now()-lastStateAt>7000)byId('connection').textContent='未连接观众页面 · 点击“打开观众页面”后再试'},3000);
