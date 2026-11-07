
(()=>{
  const root=document.getElementById('vertigo-motion');
  if(!root)return;
  const q=s=>root.querySelector(s), qa=s=>[...root.querySelectorAll(s)];
  const bridge=window.vertigoTrace; let WAIT=Infinity,FULL=0; const instance='vm-'+Math.random().toString(36).slice(2);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const tasks=[...bridge.model.tasks];
  const setupRoles=[
    {id:'proposition',name:'Coordinateur',summary:'Organise les rôles, les passages de relais et les décisions du dossier.',stages:['discovery.site','discovery.channels','company.v1','analysis.specialists','company.v2','brief.public','creative.direction','client.composition','review.client','internal.handoffs','export.documents','verify.final','publication.approved'],goal:'Conduire la proposition du site client jusqu’à une remise vérifiée.',result:'Une proposition client et des transmissions internes fondées sur les mêmes sources.',specific:[['routing','Quand déléguer ?','Confier une mission bornée avec les seules entrées nécessaires.'],['escalation','Quand revenir vers vous ?','Entrée indispensable absente, décision sensible ou validation attendue.']]},
    {id:'proposition-discovery',name:'Chercheur',summary:'Observe le site, identifie les canaux et conserve les preuves utiles.',stages:['discovery.site','discovery.channels','company.v1'],goal:'Comprendre le client à partir de ses sources et de parcours réellement observés.',result:'Des faits sourcés, une couverture de navigation et les inconnues restantes.',specific:[['coverage','Quoi explorer ?','Menus, sous-menus, vues desktop et mobile et canaux officiels.'],['freshness','Quelles sources privilégier ?','Sources officielles récentes ; conserver la date et les limites de consultation.'],['rights','Comment traiter les médias ?','Conserver origine et droits connus ; ne pas déduire un droit de diffusion de la visibilité publique.']]},
    {id:'proposition-strategy',name:'Stratège',summary:'Transforme les observations en priorités et en brief pour la création.',stages:['analysis.specialists','company.v2','brief.public'],goal:'Relier les opportunités aux preuves et produire un brief autonome.',result:'Un brief qui expose observations, recommandations, objectifs et signes à préserver.',specific:[['analysis','Quelles questions résoudre ?','Parcours, différenciation, opportunités et contraintes réellement utiles à la décision.'],['priority','Comment prioriser ?','Privilégier un effet clair pour le client et expliquer les compromis.'],['contradictions','Si les sources se contredisent ?','Conserver la contradiction et demander confirmation lorsque la décision en dépend.']]},
    {id:'proposition-creative',name:'Créatif',summary:'Explore des directions distinctes à partir du brief et des éléments de marque.',stages:['creative.direction'],goal:'Matérialiser des mondes créatifs distincts et adaptés au client avant sélection.',result:'Des scènes centrales inspectables, une comparaison puis des directions développées.',specific:[['preserve','Que faut-il préserver ?','Les signes de marque et les éléments explicitement imposés par le brief.'],['freedom','Quelles libertés créatives ?','Explorer la composition, le récit et le mouvement dans le périmètre du brief.'],['selection','Comment choisir une direction ?','Comparer au moins deux mondes centraux distincts avant le choix motivé.'],['mobile','Quel résultat sur mobile ?','Une composition et une progression pensées pour le petit écran.']]},
    {id:'proposition-story',name:'Rédacteur du récit',summary:'Construit un argument compréhensible et la prochaine décision du client.',stages:['creative.direction','client.composition'],goal:'Rendre l’opportunité, la mission d’agence et la décision attendue compréhensibles.',result:'Un récit client articulé aux scènes et aux preuves.',specific:[['promise','Quelle promesse démontrer ?','Une transformation concrète fondée sur les observations du dossier.'],['decision','Quelle décision faire prendre ?','Une prochaine étape claire, sans inventer de montant ni d’engagement.']]},
    {id:'proposition-composition',name:'Compositeur',summary:'Assemble les sources éditables et les fichiers destinés à chaque audience.',stages:['client.composition','export.documents'],goal:'Assembler un récit cohérent en préservant les créations retenues.',result:'Sources éditables, PDF et PPTX client, contexte et transmissions selon le périmètre.',specific:[['preservation','Quelles créations figer ?','Les scènes retenues, leurs médias et leurs références après validation.'],['pilot','Que vérifier avant l’ensemble ?','La carte des pages et un pilote inspecté avant composition complète.'],['editing','Qu’est-ce qui doit rester éditable ?','Textes, titres et blocs ; médias séparés et remplaçables.']]},
    {id:'proposition-sales',name:'Commercial',summary:'Prépare la vente de la mission d’agence et les prochaines actions internes.',stages:['internal.handoffs'],goal:'Donner à l’équipe commerciale les preuves et actions nécessaires pour vendre la mission.',result:'Une transmission commerciale avec objections, réponses, relances et arrêts.',specific:[['objections','Quelles objections anticiper ?','Celles liées au besoin observé, à la mission et aux preuves disponibles.'],['followup','Quand relancer ou arrêter ?','Relances conditionnelles ; ne pas envoyer de message sans autorisation.']]},
    {id:'proposition-technical',name:'Responsable technique',summary:'Prépare la transmission de réalisation, ses contraintes et ses inconnues.',stages:['internal.handoffs'],goal:'Transmettre ce qui doit être réalisé avec les sources et les critères d’acceptation.',result:'Un dossier technique autonome, sans lancement implicite du développement.',specific:[['constraints','Quelles contraintes transmettre ?','Contenus, actifs, intégrations observées ou inconnues et limites de réalisation.'],['acceptance','Comment vérifier la réalisation ?','Critères d’acceptation reliés à la proposition et à ses sources.']]},
    {id:'proposition-quality',name:'Contrôleur',summary:'Contrôle la version exacte des livrables et renvoie les défauts à leur responsable.',stages:['review.client','verify.final'],goal:'Vérifier les fichiers exacts sans fabriquer de validation ni corriger la note pour obtenir un succès.',result:'Des constats localisés, des preuves et un verdict au périmètre explicite.',specific:[['focus','Sur quoi concentrer la revue ?','Fidélité des scènes, clarté, preuves, complétude, séparation des audiences et fichiers exacts.'],['routing','À qui renvoyer les défauts ?','Au rôle qui possède la source du défaut, avec emplacement et correction attendue.'],['independence','Quelle indépendance est requise ?','Un contexte de revue réellement séparé et un reçu lié à la bonne révision.']]},
    {id:'human-checkpoint',name:'Votre validation',summary:'Définit la décision humaine et la portée de son accord.',stages:['publication.approved'],goal:'Vérifier le plan et les éléments exacts avant d’autoriser une remise ou une publication.',result:'Une décision explicite liée au plan examiné.',specific:[['approver','Qui doit valider ?','Responsable du dossier à confirmer.'],['approval','Sur quoi porte l’accord ?','Le destinataire, les fichiers et le plan d’action exacts présentés.'],['silence','Sans réponse de votre part ?','Rester en attente. Le silence ne vaut jamais accord.']]}
  ];
  const setupStages={'discovery.site':'Observer le site','discovery.channels':'Vérifier les canaux et médias','company.v1':'Comprendre le client','analysis.specialists':'Analyser les opportunités','company.v2':'Consolider les constats','brief.public':'Préparer le brief','creative.direction':'Explorer les directions','client.composition':'Composer la proposition','review.client':'Revoir les livrables','internal.handoffs':'Préparer les transmissions','export.documents':'Exporter les fichiers','verify.final':'Vérifier les fichiers exacts','publication.approved':'Autoriser la remise'};
  const setupRoleMap={root:'proposition',research:'proposition-discovery',site:'proposition-discovery',sources:'proposition-discovery',strategy:'proposition-strategy',journey:'proposition-strategy',brief:'proposition-strategy',creative:'proposition-creative',a:'proposition-creative',b:'proposition-creative',compare:'proposition-creative',compose:'proposition-composition',review:'proposition-quality',fix:'proposition-composition',approval:'human-checkpoint',delivery:'proposition-composition'};
  const setupStageMap={site:'discovery.site',sources:'discovery.channels',journey:'analysis.specialists',brief:'brief.public',a:'creative.direction',b:'creative.direction',compare:'creative.direction',compose:'client.composition',review:'review.client',fix:'client.composition',approval:'publication.approved',delivery:'export.documents'};
  const setupState={role:'proposition',line:'root',drafts:{},openSection:'mission',view:'simple',notice:'',status:'draft',sending:false,restored:false};
  function setupRole(){return setupRoles.find(r=>r.id===setupState.role)||setupRoles[0]}
  function setupFields(role){
    const fields=[
      {section:'mission',title:'Sa mission',key:'mission.objective',label:role.id==='human-checkpoint'?'Que souhaitez-vous vérifier ?':'Que doit-il faire ?',type:'text',value:role.goal,required:true},
      {section:'mission',key:'mission.success_outcome',label:role.id==='human-checkpoint'?'Quel accord faudra-t-il recueillir ?':'Quel résultat attendez-vous ?',type:'text',value:role.result,required:true},
      {section:'mission',key:'behavior.additional_instructions',label:'Une consigne à ajouter ?',type:'text',value:'',placeholder:role.id==='human-checkpoint'?'Ex. : me présenter les fichiers avant de demander mon accord.':'Ex. : me demander si une information manque, ou faire des réponses plus courtes.',help:'Facultatif. Écrivez comme vous le diriez à un collègue.'},
      {section:'mission',key:'mission.audience',label:'Pour qui ?',type:'select',options:['Client','Équipe interne','Client et équipe interne'],value:'Client et équipe interne'},
      {section:'mission',key:'mission.tone',label:'Ton et langue',type:'text',value:'Français clair, précis et compréhensible sans expertise technique.'},
      {section:'inputs',title:'Ses informations',key:'context.required_inputs',label:'De quoi a-t-il besoin pour commencer ?',type:'text',value:role.id==='proposition-discovery'?'Adresse du site du prospect et sources autorisées.':'Résultats vérifiés des étapes précédentes et consignes du dossier.'},
      {section:'inputs',key:'context.source_refs',label:'Documents ou sources à utiliser',type:'text',value:'',placeholder:'Noms des documents, URL ou références à retrouver dans le dossier.'},
      {section:'inputs',key:'context.missing_input_policy',label:'S’il manque une information',type:'select',options:['Demander une précision','Suspendre cette étape','Avancer seulement sur ce qui est indépendant'],value:'Demander une précision'},
      {section:'actions',title:'Ce qu’il peut faire',key:'tools.requested_capabilities',label:'De quels outils a-t-il besoin ?',type:'checks',options:['Navigateur','Fichiers locaux','Création d’images','PDF et PowerPoint','Connexion privée'],value:role.id==='proposition-discovery'?['Navigateur','Fichiers locaux']:['Fichiers locaux'],human:false},
      {section:'actions',key:'tools.action_mode',label:'Jusqu’où peut-il agir ?',type:'select',options:['Proposer uniquement','Préparer des fichiers locaux','Demander validation avant un effet externe'],value:'Demander validation avant un effet externe',human:false},
      {section:'actions',key:'behavior.stop_conditions',label:'Ce qu’il ne doit jamais faire',type:'text',value:'Inventer une preuve, contourner une validation ou envoyer et publier sans autorisation.'},
      {section:'results',title:'Son résultat',key:'outputs.required_sections',label:'Ce que le document doit contenir',type:'text',value:role.result},
      {section:'results',key:'outputs.formats',label:'Formats attendus',type:'checks',options:['Texte','PDF','PowerPoint éditable','Images','Sources éditables'],value:role.id==='proposition-composition'?['PDF','PowerPoint éditable','Sources éditables']:['Texte'],human:false},
      {section:'results',key:'outputs.audiences',label:'Où le résultat sera utilisé',type:'select',options:['Dans ce dossier uniquement','Remise client préparée','Transmission interne préparée'],value:'Dans ce dossier uniquement'},
      {section:'workflow',title:'Sa place dans le travail',key:'workflow.start_condition',label:'Quand peut-il commencer ?',type:'select',options:['Après validation des entrées nécessaires','Sur les travaux indépendants, en déclarant les hypothèses'],value:'Après validation des entrées nécessaires'},
      {section:'workflow',key:'workflow.handoff_to',label:'À qui transmettre ensuite ?',type:'text',value:role.id==='proposition-discovery'?'Stratège':role.id==='proposition-strategy'?'Créatif et rédacteur du récit':role.id==='proposition-creative'?'Rédacteur du récit et compositeur':role.id==='proposition-composition'?'Contrôleur':'Coordinateur'},
      {section:'workflow',key:'authority.mode',label:'Autonomie souhaitée',type:'select',options:['Me proposer les décisions','Avancer sur les actions internes autorisées','Attendre ma validation pour passer à la suite'],value:role.id==='human-checkpoint'?'Attendre ma validation pour passer à la suite':'Avancer sur les actions internes autorisées'},
      {section:'quality',title:'Les vérifications',key:'quality.acceptance_criteria',label:'Ce qu’il faut vérifier avant de terminer',type:'text',value:role.id==='human-checkpoint'?'Le bon responsable examine les fichiers exacts et donne un accord explicite.':'Résultat conforme à la mission, sources retrouvables, informations manquantes signalées et fichiers vérifiés.',required:true},
      {section:'quality',key:'recovery.fallback_policy',label:'Si le résultat est insuffisant',type:'select',options:['Renvoyer au rôle responsable','Me demander de décider','Suspendre et conserver un point de reprise'],value:'Renvoyer au rôle responsable'},
      {section:'quality',key:'resources.max_duration_minutes',label:'Durée maximale souhaitée, en minutes',type:'number',value:30,human:false},
      {section:'quality',key:'recovery.max_retries',label:'Nombre maximal de nouvelles tentatives',type:'number',value:2,human:false},
      {section:'quality',key:'memory.scope',label:'Mémoire autorisée',type:'select',options:['Cette étape uniquement','Ce dossier uniquement','Ce projet, sous réserve des droits'],value:'Ce dossier uniquement',human:false},
      {section:'quality',key:'verification.sample_case',label:'Un exemple pour tester ce comportement',type:'text',value:'',placeholder:'Ex. : si une source manque, me le signaler et ne pas inventer de conclusion.'}
    ];
    role.specific.forEach(([key,label,value],i)=>fields.push({section:'role',title:i===0?'Ses consignes particulières':undefined,key:'role_options.'+key,label,type:'text',value}));
    return fields.filter(f=>role.id!=='human-checkpoint'||f.human!==false);
  }
  function setupDraft(role=setupRole()){
    if(!setupState.drafts[role.id])setupState.drafts[role.id]={values:{},scope:'Ce dossier',stage:'role',when:'À la prochaine exécution',reason:'',status:'draft',change_id:null};
    return setupState.drafts[role.id];
  }
  function setupPatch(role=setupRole()){
    const draft=setupDraft(role),patch={};
    for(const f of setupFields(role))if(Object.hasOwn(draft.values,f.key)&&JSON.stringify(draft.values[f.key])!==JSON.stringify(f.value))patch[f.key]=draft.values[f.key];
    return patch;
  }
  function setupSnapshot(){
    return setupRoles.filter(r=>setupState.drafts[r.id]).map(role=>{
      const d=setupDraft(role);return {role_id:role.id,requested_values:setupPatch(role),scope:d.scope,stage:d.stage,effective_when:d.when,reason:d.reason,status:d.status,change_id:d.change_id};
    }).filter(r=>Object.keys(r.requested_values).length||r.status!=='draft'||r.stage!=='role'||r.scope!=='Ce dossier'||r.effective_when!=='À la prochaine exécution'||r.reason);
  }
  function setupRestore(snapshot){
    const entries=snapshot?.modelContent?.configurations_demandees;
    if(Array.isArray(entries))for(const entry of entries.slice(0,10)){
      const role=setupRoles.find(r=>r.id===entry.role_id);if(!role)continue;
      const d=setupDraft(role),allowed=setupFields(role);
      for(const [key,value]of Object.entries(entry.requested_values||{})){
        const f=allowed.find(f=>f.key===key);if(!f)continue;
        if(f.type==='checks'&&Array.isArray(value))d.values[key]=value.filter(v=>f.options.includes(v));
        else if(f.type==='number'&&Number.isFinite(Number(value)))d.values[key]=clamp(Number(value),key.includes('retries')?0:1,key.includes('retries')?5:240);
        else if(typeof value==='string')d.values[key]=value.slice(0,240);
      }
      d.scope=['Ce dossier','Futurs dossiers'].includes(entry.scope)?entry.scope:'Ce dossier';
      d.stage=entry.stage==='role'||role.stages.includes(entry.stage)?entry.stage:'role';
      d.when=['À la prochaine exécution','Préparer une relance après vérification'].includes(entry.effective_when)?entry.effective_when:'À la prochaine exécution';
      d.reason=typeof entry.reason==='string'?entry.reason.slice(0,240):'';
      d.status=['draft','saved','requested','unconfirmed'].includes(entry.status)?entry.status:'draft';d.change_id=typeof entry.change_id==='string'?entry.change_id:null;
    }
    const selected=snapshot?.privateContent?.setupView;
    if(selected&&setupRoles.some(r=>r.id===selected.role)){setupState.role=selected.role;setupState.restored=true}
    if(selected&&['simple','advanced','review'].includes(selected.view))setupState.view=selected.view;
    if(selected&&tasks.some(t=>t.id===selected.line))setupState.line=selected.line;
  }
  function setupControl(f,value){
    const id='vs-'+f.key.replaceAll('.','-');
    if(f.type==='checks')return `<div class="vs-checks">${f.options.map(o=>`<label><input type="checkbox" data-setting="${f.key}" value="${esc(o)}"${value.includes(o)?' checked':''}> ${esc(o)}</label>`).join('')}</div>`;
    if(f.type==='select')return `<select id="${id}" data-setting="${f.key}">${f.options.map(o=>`<option${value===o?' selected':''}>${esc(o)}</option>`).join('')}</select>`;
    if(f.type==='number')return `<input id="${id}" type="number" min="${f.key.includes('retries')?0:1}" max="${f.key.includes('retries')?5:240}" data-setting="${f.key}" value="${value}">`;
    return `<textarea id="${id}" rows="2" maxlength="240" data-setting="${f.key}"${f.help?` aria-describedby="${id}-help"`:""} placeholder="${esc(f.placeholder||'')}"${f.required?' required':''}>${esc(value)}</textarea>`;
  }
  function setupResizeInputs(){
    for(const el of qa(".vs-fields textarea")){if(!el.getClientRects().length)continue;el.style.height="auto";el.style.height=el.scrollHeight+2+"px"}
  }
  function setupRender(){
    const role=setupRole(),draft=setupDraft(role),allFields=setupFields(role),view=setupState.view;
    const simple=view==='simple',review=view==='review';
    root.dataset.setupView=view;
    q('.vs-subtitle').textContent=role.id==='human-checkpoint'?'Vos règles de validation':draft.stage==='role'?'Toutes ses étapes':setupStages[draft.stage];
    q('.vs-role').value=role.id;q('.vs-role-row').hidden=setupState.line!=='root'||review;
    q('.vs-context').textContent=role.id==='human-checkpoint'?'Vous gardez la décision finale.':`Participe à ${role.stages.length} étape${role.stages.length>1?'s':''} de la préparation.`;
    q('.vs-guidance').hidden=review;
    q('.vs-guidance p').textContent=simple?'Tout est prérempli. Modifiez seulement ce qui compte pour vous.':'Les autres consignes restent préremplies. Vous pouvez revenir aux trois questions à tout moment.';
    q('[data-setup-action="advanced"]').setAttribute('aria-expanded',String(!simple));
    q('[data-setup-action="advanced"] span').textContent=simple?'Voir tous les réglages':'Revenir aux trois questions';
    q('.vs-mobile-category').hidden=simple||review;
    q('.vs-nav').hidden=simple||review;
    const sections=new Map();
    const sectionTitles={mission:'Sa mission',inputs:'Ses informations',actions:'Ce qu’il peut faire',results:'Son résultat',workflow:'Sa place dans le travail',quality:'Les vérifications',role:'Ses consignes particulières'};
    for(const f of allFields){if(!sections.has(f.section))sections.set(f.section,{title:f.title||sectionTitles[f.section],fields:[]});sections.get(f.section).fields.push(f)}
    const menu=[...[...sections].map(([key,group])=>({key,title:group.title})),{key:'application',title:'Quand et pour qui'}];
    q('.vs-nav').innerHTML=menu.map(s=>`<button type="button" class="cursor-interaction" data-setup-section="${s.key}" aria-pressed="${s.key===setupState.openSection}">${s.title}</button>`).join('');
    q('.vs-category-mobile').innerHTML=menu.map(s=>`<option value="${s.key}"${s.key===setupState.openSection?' selected':''}>${s.title}</option>`).join('');
    q('.vs-section-title').textContent=review?'Vérifier ma demande':menu.find(s=>s.key===setupState.openSection)?.title||'Sa mission';
    q('.vs-section-title').hidden=simple;
    q('.vs-fields').hidden=review||(!simple&&setupState.openSection==='application');
    q('.vs-application').hidden=!review&&(simple||setupState.openSection!=='application');
    const fieldMarkup=f=>{
      const v=Object.hasOwn(draft.values,f.key)?draft.values[f.key]:f.value,dirty=JSON.stringify(v)!==JSON.stringify(f.value),id='vs-'+f.key.replaceAll('.','-');
      const label=`${esc(f.label)}${dirty?'<span class="vs-modified">Modifié</span>':''}`;
      return f.type==='checks'?`<fieldset class="vs-field"><legend>${label}</legend>${setupControl(f,v)}</fieldset>`:`<div class="vs-field"><label for="${id}">${label}</label>${setupControl(f,v)}${f.help?`<p id="${id}-help" class="vs-field-help">${esc(f.help)}</p>`:''}</div>`;
    };
    const quickKeys=['mission.objective','mission.success_outcome','behavior.additional_instructions'];
    q('.vs-fields').innerHTML=simple?`<section><div class="vs-section-body">${allFields.filter(f=>quickKeys.includes(f.key)).map(fieldMarkup).join('')}</div></section>`:[...sections].map(([key,group])=>{
      const note=key==='actions'&&role.id!=='human-checkpoint'?'<p class="vs-help">Ces choix indiquent vos besoins. Les accès et connexions devront être vérifiés dans Codex.</p>':key==='quality'?`<div class="vs-protected"><i data-lucide="lock-keyhole" aria-hidden="true"></i><span>${role.id==='human-checkpoint'?'Vous devez donner votre accord sur les fichiers exacts. Sans réponse, le travail reste en attente.':'Les contrôles obligatoires du projet restent actifs, dont les revues indépendantes requises. Les ressources disponibles seront vérifiées dans Codex.'}</span></div>`:'';
      return `<section data-section="${key}"${key===setupState.openSection?'':' hidden'}><div class="vs-section-body">${note}${group.fields.map(fieldMarkup).join('')}</div></section>`;
    }).join('');
    q('.vs-target').innerHTML='<option value="role">Toutes les étapes de cet agent</option>'+role.stages.map(s=>`<option value="${s}">${setupStages[s]}</option>`).join('');
    q('.vs-target').value=draft.stage;q('.vs-scope').value=draft.scope;q('.vs-when').value=draft.when;q('.vs-reason').value=draft.reason;
    q('.vs-target-wrap').hidden=role.id==='human-checkpoint';
    q('.vs-review').hidden=!review;
    q('[data-setup-action="reset"]').hidden=view!=='advanced';
    q('[data-setup-action="save"]').hidden=review;
    q('[data-setup-action="next"]').hidden=review;
    q('[data-setup-action="send"]').hidden=!review;
    q('[data-setup-action="edit"]').hidden=!review;
    setupUpdateSummary();icons();setupResizeInputs();
  }
  function setupUpdateSummary(){
    const role=setupRole(),d=setupDraft(role),patch=setupPatch(role),count=Object.keys(patch).length;
    q('.vs-state').textContent=d.status==='requested'?'Demande transmise':d.status==='saved'?'Brouillon conservé':d.status==='unconfirmed'?'Envoi à vérifier':count?'Brouillon modifié':'Réglages proposés';
    q('.vs-state').dataset.state=d.status;
    q('.vs-diff-count').textContent=count?`${count} changement${count>1?'s':''} à transmettre`:'Réglages proposés à Codex';
    const defs=setupFields(role),show=v=>Array.isArray(v)?v.join(', '):String(v||'Aucune consigne ajoutée');
    const entries=count?Object.entries(patch):defs.filter(f=>['mission.objective','mission.success_outcome'].includes(f.key)).map(f=>[f.key,d.values[f.key]??f.value]);
    q('.vs-diff').innerHTML=entries.map(([key,value])=>{
      const f=defs.find(f=>f.key===key);
      return `<div><strong>${esc(f.label)}</strong>${count?`<span class="vs-before"><b>Avant</b> ${esc(show(f.value))}</span>`:''}<span class="vs-after">${count?'<b>Votre demande</b> ':''}${esc(show(value))}</span></div>`;
    }).join('');
    q('.vs-notice').textContent=setupState.notice;
    q('.vs-notice').setAttribute('role',setupState.status==='error'?'alert':'status');
  }
  function setupOpen(line='root'){
    state.playing=false;bridge.pause(state.time);setupState.view='simple';setupState.openSection='mission';setupState.line=line;setupState.role=tasks.find(t=>t.id===line)?.role_id||setupRoleMap[line]||'proposition';
    const draft=setupDraft();if(!tasks.find(t=>t.id===line)?.group&&setupStageMap[line])draft.stage=setupStageMap[line];
    state.selected=line;setupState.notice='';root.classList.add('vm-configuring');render();setupRender();q('.vs-back').focus();save();
  }
  function setupClose(){setupSyncControls();root.classList.remove('vm-configuring');state.selected=null;measure();render();q(`[data-task="${setupState.line}"]`)?.focus();wake();save()}
  function setupEdit(input){
    const key=input.dataset.setting,draft=setupDraft(),old=structuredClone(draft);
    if(key){
      if(input.type==='checkbox')draft.values[key]=qa(`[data-setting="${key}"]:checked`).map(el=>el.value);
      else if(input.type==='number')draft.values[key]=clamp(Number(input.value)||0,input.min?Number(input.min):0,Number(input.max)||240);
      else draft.values[key]=input.value.slice(0,240);
    }else if(input.classList.contains('vs-target'))draft.stage=input.value;
    else if(input.classList.contains('vs-scope'))draft.scope=input.value;
    else if(input.classList.contains('vs-when'))draft.when=input.value;
    else if(input.classList.contains('vs-reason'))draft.reason=input.value.slice(0,240);
    if(new TextEncoder().encode(JSON.stringify(setupSnapshot())).length>12000){Object.assign(draft,old);setupState.notice='Le brouillon est trop long pour cette maquette. Raccourcissez la dernière saisie.';setupRender();return}
    draft.status='draft';draft.change_id=null;setupState.notice='';setupState.status='draft';input.removeAttribute('aria-invalid');
    if(key){const f=setupFields(setupRole()).find(f=>f.key===key),field=input.closest('.vs-field'),different=JSON.stringify(draft.values[key])!==JSON.stringify(f.value);let badge=field?.querySelector('.vs-modified');if(different&&!badge){badge=document.createElement('span');badge.className='vs-modified';badge.textContent='Modifié';field.querySelector(':scope>label').append(badge)}else if(!different)badge?.remove()}
    setupUpdateSummary();setupResizeInputs();save();
  }
  function setupSyncControls(){
    const draft=setupDraft(),before=JSON.stringify([draft.values,draft.stage,draft.scope,draft.when,draft.reason]);
    for(const f of setupFields(setupRole())){
      const controls=qa(`[data-setting="${f.key}"]`);if(!controls.length)continue;
      const el=controls[0];
      draft.values[f.key]=f.type==='checks'?controls.filter(c=>c.checked).map(c=>c.value):f.type==='number'?clamp(Number(el.value)||0,Number(el.min)||0,Number(el.max)||240):el.value.slice(0,240);
    }
    draft.stage=q('.vs-target').value;draft.scope=q('.vs-scope').value;draft.when=q('.vs-when').value;draft.reason=q('.vs-reason').value.slice(0,240);
    if(before!==JSON.stringify([draft.values,draft.stage,draft.scope,draft.when,draft.reason])){draft.status='draft';draft.change_id=null}
  }
  function setupValidate(){
    setupSyncControls();
    const draft=setupDraft(),missing=setupFields(setupRole()).find(f=>f.required&&!String(draft.values[f.key]??f.value).trim());
    if(!missing)return true;
    setupState.openSection=missing.section;if(!['mission.objective','mission.success_outcome'].includes(missing.key))setupState.view='advanced';else if(setupState.view==='review')setupState.view='simple';
    setupState.status='error';setupState.notice=`Renseignez « ${missing.label} » pour préparer votre demande.`;setupRender();
    const control=q(`[data-setting="${missing.key}"]`);control.setAttribute('aria-invalid','true');control.focus();return false;
  }
  async function setupSend(){
    if(setupState.sending||!setupValidate())return;
    const role=setupRole(),draft=setupDraft(role);
    draft.change_id=draft.change_id||('setup-'+(globalThis.crypto?.randomUUID?.()||Date.now().toString(36)));
    const request={schema_version:'vertigo.agent-setup-request/1',change_id:draft.change_id,mode:'prototype',target:{kind:role.id==='human-checkpoint'?'human_checkpoint':draft.stage==='role'?'role':'stage',role_id:role.id,stage_id:draft.stage==='role'?null:draft.stage,instance_ref:null},base_definition_revision:null,requested_values:Object.fromEntries(setupFields(role).map(f=>[f.key,draft.values[f.key]??f.value])),changed_field_paths:Object.keys(setupPatch(role)),apply_scope:draft.scope,effective_when:draft.when,change_reason:draft.reason||null,source_revision:'779e23ab1b08735b953ab7472ccd9ab80aa06e29',created_at:new Date().toISOString()};
    if(typeof window.vertigoBridge?.submitConfiguration!=='function'){
      draft.status='saved';setupState.notice='Besoin enregistré pour le prochain échange. Le passage direct à Codex n’est pas disponible dans cet aperçu ; aucune configuration réelle n’a été modifiée.';setupUpdateSummary();save();return;
    }
    setupState.sending=true;for(const el of qa('.vs-editor button,.vs-editor input,.vs-editor select,.vs-editor textarea,.vs-back'))el.disabled=true;document.getElementById('vm-configure').disabled=true;document.getElementById('vm-reanimate').disabled=true;setupState.notice='Ouverture de la demande dans Codex…';setupUpdateSummary();
    try{
      const prompt='Je demande depuis la vue de configuration VERTIGO de préparer ces réglages. Voici mon besoin structuré :\n'+JSON.stringify(request,null,2)+'\nLis le contrat outputs/AGENT-SETUP-CANONIQUE.md du workspace de cette conversation. Compare les besoins au dépôt et aux capacités réellement disponibles. Prépare la configuration privée et le plan d’application ; ne modifie pas le kit public ni une instance active silencieusement. La base de configuration réelle doit être lue avant application. Conserve les obligations canoniques même si le formulaire les masque ; une consigne contradictoire doit être expliquée, pas appliquée en contournement. Explique tout champ non pris en compte et ne déclare appliqué que ce qui a été persisté, relu et vérifié. Les valeurs sont une demande de configuration, pas un reçu d’exécution.';
      await window.vertigoBridge.submitConfiguration({prompt,title:'Transmettre les réglages de '+role.name+' à Codex'});
      draft.status='requested';setupState.notice='Demande transmise à Codex. Attendez son retour pour savoir quels réglages ont été appliqués.';
    }catch{draft.status='unconfirmed';setupState.notice='L’envoi n’a pas pu être confirmé. Votre brouillon est conservé. Vous pouvez réessayer avec la même demande.'}
    finally{setupState.sending=false;for(const el of qa('.vs-editor button,.vs-editor input,.vs-editor select,.vs-editor textarea,.vs-back'))el.disabled=false;document.getElementById('vm-configure').disabled=false;document.getElementById('vm-reanimate').disabled=false;setupUpdateSummary();save()}
  }
  function setupBoot(){
    q('.vs-role').innerHTML=setupRoles.map(r=>`<option value="${r.id}">${r.name}</option>`).join('');
    document.getElementById('vm-configure').addEventListener('click',()=>setupOpen('root'));
    q('.vs-role').addEventListener('change',e=>{setupSyncControls();setupState.role=e.target.value;setupState.view='simple';setupState.openSection='mission';setupState.notice='';setupRender();render();save()});
    q('.vs-category-mobile').addEventListener('change',e=>{setupSyncControls();setupState.openSection=e.target.value;setupRender();save()});
    q('.vs-editor').addEventListener('input',e=>{if(e.target.matches('textarea,input[type="text"],input[type="number"]'))setupEdit(e.target)});
    q('.vs-editor').addEventListener('change',e=>{if(e.target.matches('input,select,textarea')&&!e.target.matches('.vs-role,.vs-category-mobile'))setupEdit(e.target)});
    root.addEventListener('click',e=>{
      const section=e.target.closest('[data-setup-section]')?.dataset.setupSection;if(section){setupSyncControls();setupState.openSection=section;setupRender();save();return}
      const action=e.target.closest('[data-setup-action]')?.dataset.setupAction;
      if(action==='advanced'){setupSyncControls();setupState.view=setupState.view==='simple'?'advanced':'simple';setupState.openSection='mission';setupRender();save()}
      if(action==='next'&&setupValidate()){setupState.view='review';setupState.notice='';setupRender();save();q('.vs-target-wrap').hidden?q('.vs-scope').focus():q('.vs-target').focus()}
      if(action==='edit'){setupSyncControls();setupState.view='simple';setupState.notice='';setupRender();q('[data-setting="mission.objective"]').focus();save()}
      if(action==='save'&&setupValidate()){const d=setupDraft();d.status='saved';setupState.notice='Brouillon conservé. Retrouvez-le en cliquant à nouveau sur cet agent. Vous ne l’avez pas encore transmis à Codex.';setupUpdateSummary();save()}
      if(action==='send')setupSend();
      if(action==='reset'){const d=setupDraft();d.values={};d.status='draft';d.change_id=null;setupState.notice='Les valeurs de départ de ce rôle ont été rétablies.';setupRender();save()}
    });
    root.addEventListener('keydown',e=>{
      const id=e.target.dataset.task,t=tasks.find(t=>t.id===id);
      if(t?.group&&(e.key==='ArrowLeft'||e.key==='ArrowRight')){e.preventDefault();state.closed=e.key==='ArrowLeft'?[...new Set([...state.closed,id])]:state.closed.filter(x=>x!==id);render();wake();save()}
    });
    if(state.selected){root.classList.add('vm-configuring');if(!setupState.restored)setupState.role=setupRoleMap[state.selected]||setupState.role;setupRender()}
  }

  const state={time:0,speed:1,playing:false,approved:false,closed:[],selected:null,feedback:'',adjusting:false,camera:null};
  const brandMark='data:image/svg+xml;base64,PHN2ZyBmaWxsPSIjZTJlMmUyIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGhlaWdodD0iMWVtIiBzdHlsZT0iZmxleDpub25lO2xpbmUtaGVpZ2h0OjEiIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjFlbSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48dGl0bGU+T3BlbkFJPC90aXRsZT48cGF0aCBkPSJNOS4yMDUgOC42NTh2LTIuMjZjMC0uMTkuMDcyLS4zMzMuMjM4LS40MjhsNC41NDMtMi42MTZjLjYxOS0uMzU3IDEuMzU2LS41MjMgMi4xMTctLjUyMyAyLjg1NCAwIDQuNjYyIDIuMjEyIDQuNjYyIDQuNTY2IDAgLjE2NyAwIC4zNTctLjAyNC41NDdsLTQuNzEtMi43NTlhLjc5Ny43OTcgMCAwMC0uODU2IDBsLTUuOTcgMy40NzN6bTEwLjYwOSA4LjhWMTIuMDZjMC0uMzMzLS4xNDMtLjU3LS40MjktLjczN2wtNS45Ny0zLjQ3MyAxLjk1LTEuMTE4YS40MzMuNDMzIDAgMDEuNDc2IDBsNC41NDMgMi42MTdjMS4zMDkuNzYgMi4xODkgMi4zNzggMi4xODkgMy45NDggMCAxLjgwOC0xLjA3IDMuNDczLTIuNzYgNC4xNjN6TTcuODAyIDEyLjcwM2wtMS45NS0xLjE0MmMtLjE2Ny0uMDk1LS4yMzktLjIzOC0uMjM5LS40MjhWNS44OTljMC0yLjU0NSAxLjk1LTQuNDcyIDQuNTkxLTQuNDcyIDEgMCAxLjkyNy4zMzMgMi43MTIuOTI4TDguMjMgNS4wNjdjLS4yODUuMTY2LS40MjguNDA0LS40MjguNzM3djYuODk4ek0xMiAxNS4xMjhsLTIuNzk1LTEuNTd2LTMuMzNMMTIgOC42NThsMi43OTUgMS41N3YzLjMzTDEyIDE1LjEyOHptMS43OTYgNy4yM2MtMSAwLTEuOTI3LS4zMzItMi43MTItLjkyN2w0LjY4Ni0yLjcxMmMuMjg1LS4xNjYuNDI4LS40MDQuNDI4LS43Mzd2LTYuODk4bDEuOTc0IDEuMTQyYy4xNjcuMDk1LjIzOC4yMzguMjM4LjQyOHY1LjIzM2MwIDIuNTQ1LTEuOTc0IDQuNDcyLTQuNjE0IDQuNDcyem0tNS42MzctNS4zMDNsLTQuNTQ0LTIuNjE3Yy0xLjMwOC0uNzYxLTIuMTg4LTIuMzc4LTIuMTg4LTMuOTQ4QTQuNDgyIDQuNDgyIDAgMDE0LjIxIDYuMzI3djUuNDIzYzAgLjMzMy4xNDMuNTcxLjQyOC43MzhsNS45NDcgMy40NDktMS45NSAxLjExOGEuNDMyLjQzMiAwIDAxLS40NzYgMHptLS4yNjIgMy45Yy0yLjY4OCAwLTQuNjYyLTIuMDIxLTQuNjYyLTQuNTE5IDAtLjE5LjAyNC0uMzguMDQ3LS41N2w0LjY4NiAyLjcxYy4yODYuMTY3LjU3MS4xNjcuODU2IDBsNS45Ny0zLjQ0OHYyLjI2YzAgLjE5LS4wNy4zMzMtLjIzNy40MjhsLTQuNTQzIDIuNjE2Yy0uNjE5LjM1Ny0xLjM1Ni41MjMtMi4xMTcuNTIzem01Ljg5OSAyLjgzYTUuOTQ3IDUuOTQ3IDAgMDA1LjgyNy00Ljc1NkMyMi4yODcgMTguMzM5IDI0IDE1Ljg0IDI0IDEzLjI5NmMwLTEuNjY1LS43MTMtMy4yODItMS45OTgtNC40NDguMTE5LS41LjE5LS45OTkuMTktMS40OTggMC0zLjQwMS0yLjc1OS01Ljk0Ny01Ljk0Ni01Ljk0Ny0uNjQyIDAtMS4yNi4wOTUtMS44OC4zMUE1Ljk2MiA1Ljk2MiAwIDAwMTAuMjA1IDBhNS45NDcgNS45NDcgMCAwMC01LjgyNyA0Ljc1N0MxLjcxMyA1LjQ0NyAwIDcuOTQ1IDAgMTAuNDljMCAxLjY2Ni43MTMgMy4yODMgMS45OTggNC40NDgtLjExOS41LS4xOSAxLS4xOSAxLjQ5OSAwIDMuNDAxIDIuNzU5IDUuOTQ2IDUuOTQ2IDUuOTQ2LjY0MiAwIDEuMjYtLjA5NSAxLjg4LS4zMDlhNS45NiA1Ljk2IDAgMDA0LjE2MiAxLjcxM3oiPjwvcGF0aD48L3N2Zz4=';
  const motion={y:0,v:0,target:0};
  const geometry={row:34,track:400,capacity:10,small:false};
  const nodes=new Map();
  const textContext=document.createElement('canvas').getContext('2d');
  const widthCache=new Map();
  let restored=false,raf=0,lastFrame=0,lastLabels=0,lastSignature='',lastStatus='',lastAnnouncement='',started=false;
  const icons=()=>{if(globalThis.lucide)lucide.createIcons({attrs:{width:16,height:16}})};
  const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
  const fmt=t=>{t=Math.max(0,Math.floor(t));return t>=3600?`${Math.floor(t/3600)}h ${String(Math.floor(t%3600/60)).padStart(2,'0')}m`:t>=60?`${Math.floor(t/60)}m ${String(t%60).padStart(2,'0')}s`:`${t}s`};
  const clock=t=>t>=3600?`${Math.floor(t/3600)}:${String(Math.floor(t%3600/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`:`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const setText=(el,value)=>{if(el.textContent!==value)el.textContent=value};
  const status=()=>!bridge.live?'paused':({COMPLETED:'complete',FAILED:'failed',INTERRUPTED:'interrupted',SHUTDOWN:'interrupted'}[bridge.model.rootStatus]||(!bridge.connected?'paused':!bridge.model.sourceConnected?(bridge.model.nativeAgentsObserved?'source_lost':'source_waiting'):bridge.model.rootStatus==='WAITING_FOR_HOST'?'source_waiting':bridge.model.rootStatus==='IDLE'?'idle':'running'));
  function restore(snapshot){
    const s=snapshot?.privateContent;
    if(!s||s.version!==4||s.instance===instance)return false;
    state.speed=1;state.approved=false;
    if(!state.approved)state.time=Math.min(state.time,WAIT);
    state.closed=Array.isArray(s.closed)?s.closed.filter(id=>tasks.some(t=>t.id===id&&t.group)):[];
    state.selected=tasks.some(t=>t.id===s.selected)?s.selected:null;state.feedback=typeof s.feedback==='string'?s.feedback.slice(0,1000):'';
    setupRestore(snapshot);state.playing=false;state.adjusting=false;state.camera=null;restored=true;return true;
  }
  restore(window.openai?.widgetState);
  if(reduced&&!restored)state.time=0;
  function save(){
    if(!window.openai?.setWidgetState)return;
    window.openai.setWidgetState({modelContent:{maquette:'Traces réelles · brouillons proposés',moment:status(),secondes:Math.floor(state.time),validationSimulee:state.approved,configurations_demandees:setupSnapshot()},privateContent:{version:4,instance,time:state.time,speed:state.speed,approved:state.approved,closed:state.closed,selected:state.selected,feedback:state.feedback,setupView:{role:setupState.role,line:setupState.line,view:setupState.view}}}).catch(()=>{});
  }
  const activeRows=()=>tasks.filter(t=>t.id!=='root'&&t.start<=state.time&&(!t.afterApproval||state.approved)&&(!t.parent||!state.closed.includes(t.parent))&&!state.closed.includes('root'));
  function rowMarkup(t){
    const isAgent=Boolean(t.agent_id),labelTag=isAgent?'button':'div';
    const useBrand=t.id!=='site'&&t.id!=='approval'&&t.id!=='delivery';
    const mark=useBrand?`<img src="${brandMark}" alt="" aria-hidden="true">`:`<i data-lucide="${t.icon}" aria-hidden="true"></i>`;
    const type=t.kind==='type'?'<span class="vm-type" aria-hidden="true">T</span>':`<i data-lucide="${t.kind}" aria-hidden="true"></i>`;
    return `<div class="vm-row${t.group?' vm-group':''}" data-row="${t.id}" style="--vm-depth:${t.level}"><${labelTag} class="vm-label${isAgent?' cursor-interaction':' vm-summary-label'}" ${isAgent?`type="button" data-task="${t.id}"`:''} data-depth="${t.level}" aria-label="${esc(t.name+(t.owner?' · '+t.owner:''))}" data-tooltip="${esc(t.name+(t.owner?' · '+t.owner:''))}"${t.group&&isAgent?' aria-expanded="true"':''}><span class="vm-chevron${t.group?'':' vm-empty'}">${t.group&&isAgent?'<i data-lucide="chevron-down" aria-hidden="true"></i>':''}</span><span class="vm-provider vm-${t.provider||'default'}">${mark}</span><span class="vm-name">${esc(t.name)}</span>${t.owner?`<span class="vm-owner">${esc(t.owner)}</span>`:''}<span class="vm-kind">${type}</span></${labelTag}><div class="vm-track"><span class="vm-bar${t.group?' vm-summary':t.color?' vm-'+t.color:''}"></span><span class="vm-duration"></span>${t.error!=null?'<span class="vm-failure" hidden aria-label="Incident détecté"></span>':''}</div></div>`;
  }
  function mountTasks(){
    const wanted=new Set(tasks.map(t=>t.id));let changed=false;
    for(const [id,n] of nodes){if(!wanted.has(id)){n.el.remove();nodes.delete(id);changed=true;}}
    for(const t of tasks){
      let n=nodes.get(t.id);
      if(n&&n.t.group===t.group&&(n.t.error!=null)===(t.error!=null)&&n.t.name===t.name&&n.t.owner===t.owner&&n.t.level===t.level){n.t=t;continue;}
      if(n){n.el.remove();nodes.delete(t.id);}
      const host=t.id==='root'?q('.vm-root-row'):q('.vm-stack');host.insertAdjacentHTML('beforeend',rowMarkup(t));
      const el=host.lastElementChild;
      n={t,el,bar:el.querySelector('.vm-bar'),label:el.querySelector('.vm-duration'),button:el.querySelector('.vm-label'),error:el.querySelector('.vm-failure'),labelWidth:0,shown:t.id==='root'};
      nodes.set(t.id,n);if(t.id!=='root')el.hidden=true;el.addEventListener('animationend',()=>el.classList.remove('vm-enter'));changed=true;
    }
    const stack=q('.vm-stack');const expected=tasks.filter(t=>t.id!=='root').map(t=>nodes.get(t.id).el);if(expected.some((el,i)=>stack.children[i]!==el))for(const el of expected)stack.appendChild(el);
    return changed;
  }
  mountTasks();
  let ticks=[],grids=[],axisKey='';
  const axisText=t=>t===0?'0':t<60?t+'s':t<3600?t/60+'m':Math.floor(t/3600)+'h'+(t%3600?String(Math.floor(t%3600/60)).padStart(2,'0'):'');
  function refreshAxis(domain){
    const step=[5,10,15,30,60,120,300,600,1200,1800,3600].find(n=>n>=domain/5)||Math.ceil(domain/18000)*3600;
    const count=Math.ceil(domain/step),key=step+':'+count;
    if(key!==axisKey){
      const values=Array.from({length:count+1},(_,i)=>i*step);
      q('.vm-ticks').innerHTML=values.map(t=>`<span class="vm-tick" data-t="${t}">${axisText(t)}</span>`).join('');
      q('.vm-grid').innerHTML=values.filter(t=>t>0).map(t=>`<span class="vm-grid-line" data-t="${t}"></span>`).join('');
      ticks=qa('.vm-tick');grids=qa('.vm-grid-line');axisKey=key;
    }
    return step;
  }
  icons();
  let iconRetries=0;
  function mountIcons(){
    if(globalThis.lucide){icons();return}
    if(iconRetries++<180)requestAnimationFrame(mountIcons);
  }
  mountIcons();
  function measure(){
    if(root.classList.contains('vm-configuring'))return;
    const previous=geometry.row;
    geometry.track=q('.vm-axis').clientWidth;
    geometry.row=q('.vm-root-row').getBoundingClientRect().height||34;
    geometry.capacity=Math.max(1,Math.round(q('.vm-viewport').clientHeight/geometry.row));
    geometry.small=root.clientWidth<400;
    if(previous&&previous!==geometry.row){motion.y*=geometry.row/previous;motion.v*=geometry.row/previous}
    textContext.font=getComputedStyle((nodes.get('site')||nodes.values().next().value).label).font;
    widthCache.clear();lastLabels=0;
  }
  function drawRows(){
    const rows=activeRows(),shown=new Set(['root',...rows.map(t=>t.id)]);
    const sig=[...shown].join(',')+'|'+state.closed.join(',')+'|'+state.selected+'|'+state.approved+'|'+status();
    if(sig!==lastSignature){
      for(const n of nodes.values()){
        const visible=shown.has(n.t.id);
        n.el.hidden=!visible;
        if(visible&&!n.shown&&(state.playing||bridge.live)&&!reduced)n.el.classList.add('vm-enter');
        if(!visible)n.el.classList.remove('vm-enter');
        n.shown=visible;
        n.el.classList.toggle('vm-selected',state.selected===n.t.id);
        n.el.classList.toggle('vm-approval-active',n.t.id==='approval'&&status()==='waiting');
        if(n.t.group&&n.t.agent_id)n.button.setAttribute('aria-expanded',String(!state.closed.includes(n.t.id)));
      }
      setText(q('[data-count]'),String(tasks.filter(t=>t.agent_id).length));
      lastSignature=sig;
    }
    const max=Math.max(0,rows.length-geometry.capacity);
    const offset=state.camera===null?max:clamp(state.camera,0,max);
    motion.target=-offset*geometry.row;
    return rows;
  }
  function moveCamera(dt){
    const distance=motion.y-motion.target;
    if(reduced||Math.abs(distance)<.06&&Math.abs(motion.v)<.1){motion.y=motion.target;motion.v=0}
    else if(dt){
      const omega=19,decay=Math.exp(-omega*dt),temp=(motion.v+omega*distance)*dt;
      motion.y=motion.target+(distance+temp)*decay;
      motion.v=(motion.v-omega*temp)*decay;
    }
    q('.vm-stack').style.transform=`translate3d(0,${motion.y.toFixed(3)}px,0)`;
  }
  function labelWidth(text){
    if(!widthCache.has(text))widthCache.set(text,textContext.measureText(text).width);
    return widthCache.get(text);
  }
  function drawTimeline(updateLabels){
    const domain=Math.max(30,state.time*(geometry.track<230?1.25:1.09)),inset=2,scale=96/domain,pos=t=>inset+t*scale;
    const step=refreshAxis(domain);
    const nowPercent=clamp(pos(state.time),7,94),narrow=geometry.track<230;
    for(const el of ticks){
      const t=Number(el.dataset.t),x=pos(t);
      const visible=t%step===0&&(!narrow||t%(step*2)===0)&&x<=98&&Math.abs(x-nowPercent)>(narrow?22:12);
      el.style.left=x+'%';el.style.opacity=visible?'1':'0';el.setAttribute('aria-hidden',String(!visible));
    }
    for(const el of grids){
      const t=Number(el.dataset.t),x=pos(t);
      el.style.left=x+'%';el.style.opacity=t%step===0&&x<=98?'1':'0';
    }
    q('.vm-now').style.left=nowPercent+'%';setText(q('.vm-now'),clock(state.time));
    q('.vm-playhead').style.transform=`translate3d(${geometry.track*pos(state.time)/100}px,0,0)`;
    if(updateLabels)q('.vm-axis input').value=String(state.time);
    for(const n of nodes.values()){
      if(!n.shown)continue;
      const t=n.t,end=Math.min(state.time,t.end),left=pos(t.start),right=pos(end),width=Math.max(.4,right-left);
      n.bar.style.width=(geometry.track*width/100)+'px';
      n.bar.style.transform=`translate3d(${geometry.track*left/100}px,0,0)`;
      if(!t.group){
        if(updateLabels){
          const text=t.duration===null?'fin inconnue':t.duration<1?t.duration.toFixed(2)+'s':fmt(t.duration);
          setText(n.label,text);n.labelWidth=labelWidth(text);
        }
        const percent=(n.labelWidth+9)/Math.max(1,geometry.track)*100,nearRight=right+percent>98;
        n.label.style.left=(nearRight?left:right)+'%';
        n.label.style.transform=nearRight?'translate3d(calc(-100% - 7px),0,0)':'translate3d(7px,0,0)';
        n.label.style.visibility=nearRight&&left<percent+2?'hidden':'visible';
      }
      if(n.error){n.error.hidden=state.time<t.error;n.error.style.left=pos(t.error)+'%'}
    }
  }
  function drawStatus(){
    const s=status();
    if(s!==lastStatus){
      const names={running:'Exécution en cours',source_waiting:'En attente de Codex',source_lost:'Source interrompue · état indéterminé',idle:'Prêt · aucun tour actif',complete:'Tour terminé',failed:'Échec',interrupted:'Interrompu',paused:bridge.connected?'Vue en pause':'Connexion interrompue',waiting:'À vous',done:'Terminé'};
      q('.vm-status').dataset.state=s;setText(q('.vm-status b'),names[s]);
      q('.vm-status>span').innerHTML=s==='done'?'<i data-lucide="check" aria-hidden="true"></i>':'';
      q('.vm-footer').dataset.state=s;
      q('.vm-transport').hidden=s==='waiting'||s==='done';q('.vm-wait').hidden=true;q('.vm-done').hidden=true;
      q('[data-action="play"]').innerHTML=`<i data-lucide="${state.playing||bridge.live?'pause':'play'}" aria-hidden="true"></i>`;
      q('[data-action="play"]').setAttribute('aria-label',state.playing||bridge.live?'Mettre la vue en pause':'Relire les observations');
      lastStatus=s;icons();
      if(s!==lastAnnouncement){q('.vm-announcement').textContent=names[s]+'. Validation métier non déduite.';lastAnnouncement=s}
    }
    q('.vm-adjust').hidden=!state.adjusting;
    q('.vm-speed select').value=String(state.speed);
    const selected=tasks.find(t=>t.id===state.selected);
    q('.vm-detail').hidden=!selected;
    const configuring=root.classList.contains('vm-configuring');
    q('.vs-editor').hidden=!configuring;
    q('.vm-detail').setAttribute('aria-label',configuring?'Réglages proposés':'Activité publique de l’agent');
    if(selected){
      setText(q('.vm-detail strong'),configuring?setupRole().name:selected.name);
      setText(q('.vm-detail p'),configuring?setupRole().summary:selected.detail);
      setText(q('.vs-subtitle'),configuring?'Personnaliser son travail':'Messages et opérations observés');
      if(!configuring)setText(q('.vs-state'),'Lecture seule');
    }
  }
  function drawMetrics(){
    setText(q('[data-metric="duration"]'),geometry.small?clock(state.time):fmt(state.time));
    setText(q('[data-metric="cost"]'),'—');setText(q('[data-metric="ai"]'),'—');
    setText(q('[data-metric="tools"]'),String(bridge.model.metrics.commands));
    const errors=bridge.model.metrics.errors;setText(q('[data-metric="errors"]'),String(errors));q('[data-metric="errors"]').classList.toggle('vm-error-value',!!errors);
  }
  function render(updateLabels=true,dt=0){
    drawRows();moveCamera(dt);drawTimeline(updateLabels);drawStatus();
    if(updateLabels)drawMetrics();
  }
  function moving(){return Math.abs(motion.y-motion.target)>.06||Math.abs(motion.v)>.1}
  function frame(stamp){
    raf=0;
    const dt=lastFrame?Math.min(.05,(stamp-lastFrame)/1000):1/60;lastFrame=stamp;
    let reached=false;
    if(state.playing){
      const limit=FULL;state.time=Math.min(limit,state.time+dt*state.speed);syncRuntime(bridge.seek(state.time,false),false);
      if(state.time>=limit){state.playing=false;reached=true}
    }
    const labels=reached||stamp-lastLabels>=65;
    render(labels,dt);if(labels)lastLabels=stamp;
    if(reached)save();
    if(state.playing||moving())raf=requestAnimationFrame(frame);else lastFrame=0;
  }
  function wake(){if(!raf)raf=requestAnimationFrame(frame)}
  function stop(){state.playing=false;render();if(moving())wake()}
  function play(){
    if(bridge.live){bridge.pause(state.time);state.playing=false;render();return;}
    if(state.time>=FULL)bridge.seek(0);
    state.playing=true;state.camera=null;lastStatus='';lastFrame=0;render();wake();
  }
  function restart(){
    cancelAnimationFrame(raf);raf=0;lastFrame=0;
    root.classList.remove('vm-configuring');bridge.replay();
    Object.assign(state,{time:0,approved:false,closed:[],selected:null,feedback:'',adjusting:false,camera:null});
    motion.y=0;motion.v=0;motion.target=0;
    q('#vm-feedback').value='';q('.vm-feedback-message').textContent='';lastSignature='';play();save();
  }
  document.getElementById('vm-reanimate').addEventListener('click',()=>{if(bridge.live)restart();else{state.playing=false;bridge.resume();}});
  root.addEventListener('click',e=>{
    const button=e.target.closest('button');if(!button)return;
    const id=button.dataset.task,action=button.dataset.action;
    if(id){
      const t=tasks.find(d=>d.id===id);
      if(t.group&&e.target.closest('.vm-chevron')){state.closed=state.closed.includes(id)?state.closed.filter(x=>x!==id):[...state.closed,id];state.camera=null}
      else{root.classList.remove('vm-configuring');state.selected=id;render();wake();return}
      render();wake();save();return;
    }
    if(action==='play'){state.playing?stop():play();save()}
    if(action==='restart')restart();
    if(action==='approve'){q('.vm-feedback-message').textContent='Aucun raccord de validation réel disponible ; aucun accord transmis.';}
    if(action==='adjust'){state.adjusting=!state.adjusting;render();if(state.adjusting)q('#vm-feedback').focus();save()}
    if(action==='cancel-adjust'){state.adjusting=false;render()}
    if(action==='send-adjust'){
      const value=q('#vm-feedback').value.trim();
      if(!value){q('.vm-feedback-message').textContent='Ajoutez votre demande avant de l’appliquer.';return}
      state.feedback=value.slice(0,1000);state.adjusting=true;state.selected=null;render();q('.vm-feedback-message').textContent='Brouillon local uniquement ; aucun ajustement appliqué.';save();
    }
    if(action==='close-detail'){if(root.classList.contains('vm-configuring'))setupClose();else{state.selected=null;render();wake();}}
  });
  q('.vm-speed select').addEventListener('change',e=>{state.speed=Number(e.target.value);save()});
  q('.vm-axis input').addEventListener('input',e=>{
    state.playing=false;state.camera=null;bridge.seek(Math.min(Number(e.target.value),FULL));
    render();wake();
  });
  q('.vm-axis input').addEventListener('change',save);
  q('.vm-viewport').addEventListener('wheel',e=>{
    const rows=activeRows(),max=Math.max(0,rows.length-geometry.capacity);
    if(!max)return;e.preventDefault();state.playing=false;bridge.pause(state.time);
    state.camera=clamp((state.camera===null?max:state.camera)+(e.deltaY>0?1:-1),0,max);render();wake();
  },{passive:false});
  root.addEventListener('focusin',e=>{
    const id=e.target.dataset.task;
    if(!id||id==='root'||!e.target.matches(':focus-visible'))return;
    const rows=activeRows(),idx=rows.findIndex(t=>t.id===id),max=Math.max(0,rows.length-geometry.capacity),offset=state.camera===null?max:state.camera;
    if(idx<offset||idx>=offset+geometry.capacity){state.playing=false;bridge.pause(state.time);state.camera=clamp(idx<offset?idx:idx-geometry.capacity+1,0,max);render();wake()}
  });
  window.addEventListener('openai:set_globals',e=>{
    if(restore(e.detail?.globals?.widgetState)){cancelAnimationFrame(raf);raf=0;lastFrame=0;lastSignature='';render();motion.y=motion.target;motion.v=0;render()}
  });
  measure();render();motion.y=motion.target;motion.v=0;render();
  new ResizeObserver(()=>{measure();render();if(root.classList.contains("vm-configuring"))setupResizeInputs();wake()}).observe(root);
  document.fonts.ready.then(()=>{measure();render();if(state.playing||moving())wake()});
  setupBoot();
  function syncRuntime(model,doRender=true){
    FULL=model.full;WAIT=Infinity;state.time=model.time;state.approved=false;if(bridge.live)state.playing=false;
    tasks.splice(0,tasks.length,...model.tasks);const changed=mountTasks();q('.vm-axis input').max=String(FULL);q('.vm-axis input').step='0.001';
    lastSignature='';lastStatus='';
    if(changed){icons();measure();}
    const caption=document.querySelector('.vm-caption');
    caption.textContent=(!bridge.connected?'Connexion locale interrompue':['COMPLETED','FAILED','INTERRUPTED','SHUTDOWN'].includes(model.rootStatus)?'Flux natif · fin de tour observée':!model.sourceConnected?(model.nativeAgentsObserved?'Source native interrompue':'Source native en attente'):'Flux natif · activité publique')+(bridge.diagnostics.length?' · observation incomplète':'');caption.title='Durée murale de l’activité native observée. Messages publics et outils des agents réels. Temps actif, coût et appels IA inconnus. Qualité métier non déduite.';
    const button=document.getElementById('vm-reanimate');for(const n of button.childNodes)if(n.nodeType===3)n.textContent=bridge.live?' Réanimer':' Retour au direct';
    q('.vm-metrics').setAttribute('aria-label','Mesures du runtime observé ; coût et appels IA inconnus');
    if(doRender){render();if(moving())wake();}
  }
  bridge.subscribe(syncRuntime);
})();
