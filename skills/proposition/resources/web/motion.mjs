// Portable mechanism, not a scene design. Native scroll remains the only clock.
// Lifecycle derived from the pinned Vertigo homepage scope; see PROVENANCE.json.
export function createScope(host=window) {
  const controller=new AbortController(), frames=new Map();
  return {
    signal:controller.signal,
    on(target,type,callback,options={}) {
      if(!controller.signal.aborted)
        target.addEventListener(type,callback,{...options,signal:controller.signal});
    },
    frame(key,callback) {
      if(controller.signal.aborted)return;
      if(frames.has(key))host.cancelAnimationFrame(frames.get(key));
      frames.set(key,host.requestAnimationFrame(time=>{
        frames.delete(key);
        if(!controller.signal.aborted)callback(time);
      }));
    },
    dispose() {
      if(controller.signal.aborted)return;
      controller.abort();
      frames.forEach(id=>host.cancelAnimationFrame(id));frames.clear();
    },
  };
}

export function createScrollScene(section,{layers=[],onUpdate=()=>{}}={}) {
  if(!(section instanceof HTMLElement))throw new TypeError('An actual scene element is required');
  const scope=createScope(), reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let animations=[],progress=0,disposed=false;
  const clamp=value=>Math.max(0,Math.min(1,value));
  function configure() {
    animations.forEach(animation=>animation.cancel());animations=[];
    // Cancel the effects to restore readable underlying HTML/CSS. The author
    // still supplies the scene's reduced-motion layout and meaningful poster.
    if(!reduced.matches) {
      animations=layers.map(layer=>{
        if(!(layer.element instanceof Element))throw new TypeError('A layer element is required');
        const animation=layer.element.animate(layer.keyframes,
          {...layer.options,duration:1000,iterations:1,fill:'both'});
        animation.pause();animation.currentTime=0;
        return animation;
      });
    }
    schedule();
  }
  function render() {
    const rect=section.getBoundingClientRect(),distance=Math.max(1,section.offsetHeight-innerHeight);
    progress=clamp(-rect.top/distance);
    animations.forEach(animation=>{animation.currentTime=progress*1000;});
    onUpdate({progress,reducedMotion:reduced.matches,active:rect.bottom>0&&rect.top<innerHeight,
      width:innerWidth,height:innerHeight});
  }
  function schedule(){scope.frame('scene',render);}
  scope.on(window,'scroll',schedule,{passive:true});
  scope.on(window,'resize',schedule,{passive:true});
  scope.on(reduced,'change',configure);
  const observer=new ResizeObserver(schedule);observer.observe(section);
  scope.signal.addEventListener('abort',()=>observer.disconnect(),{once:true});
  configure();
  return {
    get progress(){return progress;},
    refresh:schedule,
    goTo(value,{behavior='auto'}={}) {
      if(disposed)return;
      if(!Number.isFinite(value))throw new TypeError('Scene position must be finite');
      const top=section.getBoundingClientRect().top+scrollY;
      scrollTo({top:top+clamp(value)*Math.max(0,section.offsetHeight-innerHeight),
        behavior:reduced.matches?'instant':behavior});
      schedule();
    },
    destroy() {
      if(disposed)return;
      disposed=true;scope.dispose();animations.forEach(animation=>animation.cancel());animations=[];
    },
  };
}
