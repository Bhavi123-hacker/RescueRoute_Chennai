/* Real-life field helpers: navigation, call, share, notes, SOS, recent pickups. */
(function(){
const KEY='rescueroute-field-v1';
function load(){try{return JSON.parse(localStorage.getItem(KEY)||'{}');}catch{return {};}}
function save(patch){const data={...load(),...patch};try{localStorage.setItem(KEY,JSON.stringify(data));}catch{}}
function activeHospital(){
  const id=$('destination-hospital')?.value||streetPlan?.selected_hospital||streetPlan?.top_hospitals?.[0]?.hospital_id||currentPlan?.best?.hospital_id;
  const fromDir=cityDirectory.find(h=>h.id===id);
  if(fromDir)return fromDir;
  if(streetPlan?.hospital)return streetPlan.hospital;
  if(id&&world?.state?.hospitals?.[id]){const h=world.state.hospitals[id];return{id,name:h.name,lat:h.lat,lon:h.lon,address:'',phone:''};}
  return null;
}
function activePickup(){return streetPlan?.pickup||sourceLocation||(world?world.nodes[$('pickup').value]:null);}
function tripMinutes(){return streetPlan?.legs?.transport?.minutes??currentPlan?.best?.arrival_min??null;}
function tripKm(){return streetPlan?.legs?.transport?.distance_km??null;}
function mapsUrl(){
  const src=activePickup(),h=activeHospital();if(!src||!h)return null;
  return `https://www.google.com/maps/dir/?api=1&origin=${src.lat},${src.lon}&destination=${h.lat},${h.lon}&travelmode=driving`;
}
function summaryText(){
  const src=activePickup(),h=activeHospital(),mins=tripMinutes(),km=tripKm();
  const notes=$('scene-notes')?.value?.trim()||'';
  const phone=$('callback-phone')?.value?.trim()||'';
  const lines=[
    'RescueRoute Chennai · Emergency trip',
    `Pickup: ${src?`${Number(src.lat).toFixed(5)}, ${Number(src.lon).toFixed(5)}`:'—'}${src?.label||src?.name?` (${src.label||src.name})`:''}`,
    `Hospital: ${h?.name||'—'}`,
    h?.address?`Address: ${h.address}`:null,
    h?.phone?`Hospital phone: ${h.phone}`:null,
    mins!=null?`ETA: ${Number(mins).toFixed(1)} min${km!=null?` · ${Number(km).toFixed(1)} km`:''}`:null,
    phone?`Callback: ${phone}`:null,
    notes?`Notes: ${notes}`:null,
    mapsUrl()?`Navigate: ${mapsUrl()}`:null,
    'Confirm hospital capacity by phone before arrival.',
  ].filter(Boolean);
  return lines.join('\n');
}
function renderTurns(){
  const list=$('turn-list');if(!list)return;
  const streets=streetPlan?.legs?.transport?.streets||[];
  list.replaceChildren();
  if(!streets.length){list.append(element('li','small-muted','Street-by-street guide appears after a successful map route.'));return;}
  streets.slice(0,18).forEach((s,i)=>{
    const li=element('li','');
    li.append(document.createTextNode(`${i+1}. ${s.name||'Unnamed road'} · ${(s.distance_km||0).toFixed(2)} km${s.oneway?' · one-way':''}`));
    list.append(li);
  });
  if(streets.length>18)list.append(element('li','small-muted',`+ ${streets.length-18} more segments`));
}
function renderFieldMeta(){
  const box=$('field-meta'),actions=$('field-actions'),h=activeHospital(),src=activePickup(),mins=tripMinutes(),km=tripKm();
  if(!box)return;
  box.replaceChildren();
  if(!src||!h){box.append(element('p','small-muted','Plan a route to unlock navigation, call and share actions.'));if(actions)actions.hidden=true;if($('eta-live'))$('eta-live').textContent='ETA —';return;}
  if(actions)actions.hidden=false;
  if($('eta-live'))$('eta-live').textContent=mins!=null?`ETA ${Number(mins).toFixed(1)} min`:'ETA —';
  box.append(element('p','',`From pickup → ${h.name}`));
  box.append(element('p','small-muted',[mins!=null?`${Number(mins).toFixed(1)} min`:null,km!=null?`${Number(km).toFixed(1)} km`:null,h.address||null].filter(Boolean).join(' · ')));
  if(h.phone)box.append(element('p','',`☎ ${h.phone}`));
  else box.append(element('p','small-muted','No phone in OSM record — confirm from hospital board/directory.'));
  renderTurns();
}
function rememberPickup(){
  const src=activePickup();if(!src||!Number.isFinite(Number(src.lat)))return;
  const data=load();const recent=Array.isArray(data.recent)?data.recent:[];
  const item={lat:Number(src.lat),lon:Number(src.lon),label:src.label||src.name||'Pickup',at:Date.now()};
  const next=[item,...recent.filter(r=>Math.hypot(r.lat-item.lat,r.lon-item.lon)>0.0008)].slice(0,5);
  save({recent:next,notes:$('scene-notes')?.value||'',callback:$('callback-phone')?.value||'',hospital:$('destination-hospital')?.value||''});
  renderRecent();
}
function renderRecent(){
  const host=$('recent-pickups');if(!host)return;
  const recent=load().recent||[];host.replaceChildren();
  if(!recent.length)return;
  host.append(element('div','small-muted','Recent pickups'));
  for(const r of recent){
    const b=element('button','recent-chip',r.label||`${r.lat.toFixed(3)}, ${r.lon.toFixed(3)}`);
    b.type='button';
    b.addEventListener('click',()=>setSource(r.lat,r.lon,r.label||'Recent pickup'));
    host.append(b);
  }
}
function refreshField(){renderFieldMeta();rememberPickup();}

async function ensurePlanAndDispatch(autoDispatch){
  if(typeof sourceTimer!=='undefined'&&sourceTimer){clearTimeout(sourceTimer);sourceTimer=null;}
  // A* first (hospital + ambulance + path), then street geometry overlay.
  if(typeof calculate==='function')await calculate();
  if(window.paintMapRoutes)paintMapRoutes();
  if(typeof requestStreetPlan==='function'){
    try{await requestStreetPlan(true);}catch(e){/* A* path already painted */}
  }
  if(window.paintMapRoutes)paintMapRoutes();
  refreshField();
  if(autoDispatch){
    if(typeof dispatchAmbulance==='function')await dispatchAmbulance();
    else if(currentPlan?.best){
      const request={...currentPlan.request,expected_revision:state().revision};
      const r=await mutate('dispatch',request,'Mission started. Active journey is live.');
      if(r){selectedMission=r.result.mission_id;currentPlan=null;render();if(window.paintMapRoutes)paintMapRoutes();if(!feedTimer)$('run-feed')?.click();}
    }
  }
  controls();
}

$('nav-google')?.addEventListener('click',()=>{const url=mapsUrl();if(!url){status('Set pickup and hospital first.',true);return;}window.open(url,'_blank','noopener');});
$('call-hospital')?.addEventListener('click',()=>{
  const h=activeHospital();
  if(!h?.phone){status('No phone number on this hospital record. Open City directory or call manually.',true);return;}
  const tel='tel:'+String(h.phone).split(/[;,]/)[0].replace(/[^\d+]/g,'');
  window.location.href=tel;
});
$('copy-summary')?.addEventListener('click',async()=>{
  const text=summaryText();
  try{await navigator.clipboard.writeText(text);status('Emergency summary copied.');}
  catch{
    const ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();
    try{document.execCommand('copy');status('Emergency summary copied.');}catch{status('Copy failed — select text from Print card instead.',true);}
    ta.remove();
  }
});
$('share-trip')?.addEventListener('click',async()=>{
  const text=summaryText(),url=mapsUrl();
  if(navigator.share){try{await navigator.share({title:'RescueRoute emergency trip',text,url:url||undefined});return;}catch{}}
  window.open('https://wa.me/?text='+encodeURIComponent(text),'_blank','noopener');
});
$('print-card')?.addEventListener('click',()=>{
  const sheet=$('print-sheet');if(!sheet){status('Print sheet missing. Hard-refresh the page (Ctrl+F5).',true);return;}
  const text=summaryText();
  if(!activeHospital()||!activePickup()){status('Set pickup and hospital before printing.',true);return;}
  sheet.hidden=false;
  sheet.textContent=text;
  sheet.setAttribute('aria-hidden','false');
  const done=()=>{sheet.hidden=true;sheet.setAttribute('aria-hidden','true');window.removeEventListener('afterprint',done);};
  window.addEventListener('afterprint',done);
  setTimeout(()=>{window.print();setTimeout(done,500);},100);
});
$('sos-now')?.addEventListener('click',async()=>{
  if(busy)return;
  $('emergency').value='critical';$('category').value='trauma';$('needs-icu').checked=true;$('destination-hospital').value='';$('allow-alternative').checked=true;
  const run=async()=>{status('SOS: routing to nearest suitable hospital and starting mission…');await ensurePlanAndDispatch(true);};
  if(sourceLocation||$('pickup').value){await run();return;}
  if(!navigator.geolocation){status('Click the map to set pickup, then press SOS again.',true);return;}
  status('SOS: getting your location…');
  navigator.geolocation.getCurrentPosition(async p=>{
    if(typeof sourceTimer!=='undefined'){clearTimeout(sourceTimer);sourceTimer=null;}
    setSource(p.coords.latitude,p.coords.longitude,'SOS my location','BROWSER_LOCATION');
    await run();
  },e=>status('Location failed: '+e.message+'. Click map then SOS.',true),{enableHighAccuracy:true,timeout:10000});
});
$('find-shortest')?.addEventListener('click',async()=>{
  if(busy)return;
  if(!activePickup()){status('Click the map (or pick a neighborhood) to set pickup first.',true);return;}
  status('Finding shortest traffic-aware route…');
  await ensurePlanAndDispatch(false);
  if(currentPlan?.best)status('Route ready. Click Dispatch ambulance to start Active journey.');
});
$('scene-notes')?.addEventListener('change',()=>save({notes:$('scene-notes').value}));
$('callback-phone')?.addEventListener('change',()=>save({callback:$('callback-phone').value}));

const data=load();
if($('scene-notes')&&data.notes)$('scene-notes').value=data.notes;
if($('callback-phone')&&data.callback)$('callback-phone').value=data.callback;
renderRecent();

const prevStreetTrip=typeof renderStreetTrip==='function'?renderStreetTrip:null;
if(prevStreetTrip){renderStreetTrip=function(){prevStreetTrip();refreshField();};}
const prevChoose=chooseHospital;
chooseHospital=function(id,calculateNow=true){prevChoose(id,calculateNow);save({hospital:id});setTimeout(refreshField,300);};
const prevSet=setSource;
setSource=function(lat,lon,label,source){prevSet(lat,lon,label,source);setTimeout(refreshField,400);};

window.refreshFieldKit=refreshField;
})();
