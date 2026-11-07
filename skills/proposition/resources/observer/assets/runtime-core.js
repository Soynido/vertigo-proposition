/* Public native activity only; CLI spans are not agents or business validation. */
(function(scope){
 'use strict';
 function project(s={},now){
  const agents=s.agents||[],tools=s.tools||[],byId=new Map(agents.map(a=>[a.id,a]));
  const starts=agents.map(a=>a.started_at).filter(Number.isFinite),origin=starts.length?Math.min(...starts):0;
  const active=agents.some(a=>a.status==='RUNNING'||a.status==='STARTING');
  const ends=agents.map(a=>a.ended_at??a.last_activity_at).filter(Number.isFinite);
  const current=Number.isFinite(now)?now:s.observed_at||origin;
  const horizon=origin?(active?Math.min(current,s.disconnected_at??current):Math.max(origin,...ends)):0;
  const full=origin?Math.max(0,horizon-origin):0;
  const levels=new Map();function depth(a,seen=new Set()){
   if(levels.has(a.id))return levels.get(a.id);if(seen.has(a.id))return 1;seen.add(a.id);
   const p=byId.get(a.parent_id),n=p?depth(p,seen)+1:1;levels.set(a.id,n);return n;
  }
  const tasks=[];
  function add(a){
   if(tasks.some(t=>t.agent_id===a.id))return;const p=byId.get(a.parent_id);if(p)add(p);
   const start=origin?Math.max(0,(a.started_at??a.last_activity_at)-origin):0;
   const end=origin?Math.max(start,(a.ended_at??horizon)-origin):0;
   tasks.push({id:'agent-'+a.id,agent_id:a.id,parent:p?'agent-'+p.id:'root',level:depth(a),
    name:a.role||(!a.parent_id?'Agent principal':'Agent '+a.id.slice(-8)),owner:'Codex',group:agents.some(x=>x.parent_id===a.id),
    start,end,duration:a.started_at===null?null:Math.max(0,(a.ended_at??horizon)-a.started_at),status:a.status,
    provider:'code',icon:'aperture',kind:'type',role_id:'proposition',error:a.status==='FAILED'?end:null,
    detail:'Agent '+a.id+' · '+a.status+' · dernière activité '+new Date(a.last_activity_at*1000).toLocaleTimeString()+'. '+(a.last_output||'Aucune sortie publique reçue.')+' Opérations observées : '+(tools.filter(t=>t.agent_id===a.id).slice(-8).map(t=>t.label+' : '+t.status).join('; ')||'aucune')+'. Validation métier non déduite.'});
  }
  for(const a of agents)add(a);
  return {origin:origin*1000,full,time:full,totalTasks:agents.length,truncated:false,
   tasks:[{id:'root',name:agents.length?'Activité des agents':'En attente de Codex',owner:'Flux natif',level:0,start:0,end:full,group:true,provider:'code',icon:'aperture',kind:'type',role_id:'proposition',detail:'Messages publics et outils du véritable arbre d’agents. Temps actif et qualité métier non déduits.'},...tasks],
   metrics:{commands:tools.length,errors:(s.metrics?.failed||0)+(s.metrics?.blocked||0)+(s.metrics?.failed_agents||0),cost:null,ai:null,tools:tools.length},
   nativeAgentsObserved:agents.length>0,sourceConnected:s.source_connected===true,businessQuality:'NOT_ASSESSED',rootStatus:active?'RUNNING':s.status||'WAITING_FOR_HOST'};
 }
 const api={project};if(typeof module!=='undefined'&&module.exports)module.exports=api;else scope.VertigoRuntimeCore=api;
})(typeof window==='undefined'?globalThis:window);
