/* Native public activity; no execution/configuration/approval endpoint. */
(()=>{'use strict';
 const key='vertigo-native-observer-session';let token=location.hash.slice(1)||sessionStorage.getItem(key)||'';
 if(token){sessionStorage.setItem(key,token);history.replaceState(null,'',location.pathname);}
 const initial={agents:[],tools:[],events:[],metrics:{},status:'WAITING_FOR_HOST'},subs=new Set();let latest=initial,received=performance.now();
 const bridge={events:[],snapshot:initial,cursor:0,live:true,connected:false,runId:null,diagnostics:[],model:VertigoRuntimeCore.project(initial),
  subscribe(fn){subs.add(fn);fn(this.model);return()=>subs.delete(fn);},notify(){for(const fn of subs)fn(this.model);},
  seek(){this.live=false;return this.model;},pause(){this.live=false;return this.model;},
  resume(){this.live=true;this.snapshot=latest;tick();},replay(){return this.pause();}};
 window.vertigoTrace=bridge;window.openai={widgetState:null,async setWidgetState(){}};
 function tick(){if(!bridge.live)return;const now=(latest.observed_at||0)+(performance.now()-received)/1000;
  bridge.model=VertigoRuntimeCore.project(latest,now);bridge.notify();}
 async function poll(){try{
  const res=await fetch('/api/activity?after='+bridge.cursor,{headers:{Authorization:'Bearer '+token},cache:'no-store'});
  if(res.status===400){bridge.cursor=0;}else if(!res.ok)throw Error('Session unavailable');else{
   latest=await res.json();received=performance.now();bridge.connected=true;bridge.cursor=latest.cursor;bridge.runId=latest.root_id;bridge.diagnostics=latest.diagnostics;
   bridge.events=latest.events;bridge.snapshot=latest;if(bridge.live)tick();
  }
 }catch{bridge.connected=false;bridge.notify();}setTimeout(poll,document.hidden?4000:1000);}
 async function ack(){try{await fetch('/api/ui-ready',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({view:'native-public-activity',version:1})});}catch{}}
 window.addEventListener('load',()=>{for(const e of document.querySelectorAll('[data-action=restart],.vm-speed select,.vm-axis input')){e.disabled=true;e.title='Relecture native non qualifiée';}ack();});
 setInterval(()=>{if(!document.hidden)tick();},250);poll();
})();
