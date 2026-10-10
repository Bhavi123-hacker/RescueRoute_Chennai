/* Simple pickup → hospital shortest-path map (free OSM tiles, no API key). */
let streetMap=null,streetData=null,streetPlan=null,streetKey='',streetPendingKey='',streetTimer=null,streetGeneration=0;
let hospitalLayer=null,roadLayer=null,tripLayer=null,endpointLayer=null,arrowLayer=null,labelLayer=null,roadLayers=new Map();
let streetLeg='transport',compareReturn=false,streetClosed=new Set(),streetPlayback=null,playbackMarker=null,ambulanceMarker=null,basemap=null,roadsReady=false,lastFitKey='';
let ambDrive=null,ambRaf=0,savedAstarPath=[];
const legColors={response:'#f5f5f5',transport:'#f5c451',return:'#a3a3a3'},legNames={response:'Ambulance → pickup',transport:'Pickup → hospital',return:'Hospital → return'};
function latlng(p){return[p[1],p[0]];}
function streetTheme(){return document.documentElement.dataset.theme!=='light';}
function pin(label,type=''){const amb=type==='pin-ambulance';return L.divIcon({className:'map-pin'+(amb?' amb-marker':''),html:`<span class="pin-core ${type}">${label}</span>`,iconSize:amb?[48,48]:[36,36],iconAnchor:amb?[24,24]:[18,18]});}
function haversineKm(a,b){const R=6371,dLat=(b.lat-a.lat)*Math.PI/180,dLon=(b.lon-a.lon)*Math.PI/180;const x=Math.sin(dLat/2)**2+Math.cos(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.min(1,Math.sqrt(x)));}
function pickupPoint(){return streetPlan?.pickup||sourceLocation||(world?world.nodes[$('pickup').value]:null);}
function nearbyHospitals(limit=8){const src=pickupPoint();if(!src||!cityDirectory.length)return [];const prefer=cityDirectory.filter(h=>state().hospitals[h.id]?.status_source!=='UNKNOWN');const pool=prefer.length?prefer:cityDirectory;return [...pool].map(h=>({h,d:haversineKm(src,h)})).sort((a,b)=>a.d-b.d).slice(0,limit).map(x=>x.h);}
function updateRouteSteps(){const steps=document.querySelectorAll('.route-steps .step');if(!steps.length)return;const hasPickup=!!pickupPoint(),hasHospital=!!($('destination-hospital')?.value||streetPlan?.selected_hospital||streetPlan?.top_hospitals?.[0]||currentPlan?.best?.hospital_id),hasRoute=!!(streetPlan?.legs?.transport||currentPlan?.best);steps[0]?.classList.toggle('on',true);steps[1]?.classList.toggle('on',hasPickup);steps[2]?.classList.toggle('on',hasRoute||hasHospital);}
function extendToHospital(pts,hospitalId){
  if(!pts.length||!hospitalId||!world)return pts;
  const h=state().hospitals[hospitalId]||cityDirectory.find(x=>x.id===hospitalId);
  if(!h)return pts;
  const end=[h.lat,h.lon];
  if(Math.hypot(pts.at(-1)[0]-end[0],pts.at(-1)[1]-end[1])>0.0004)pts.push(end);
  return pts;
}
function rememberAstarPath(best){
  if(!best||!world)return;
  const ids=[];
  for(const id of best.pickup_route?.nodes||[])if(!ids.length||ids.at(-1)!==id)ids.push(id);
  for(const id of best.hospital_route?.nodes||[])if(!ids.length||ids.at(-1)!==id)ids.push(id);
  let pts=ids.map(id=>world.nodes[id]).filter(Boolean).map(n=>[n.lat,n.lon]);
  // Prefer street pickup→hospital geometry so cyan continues past the pickup pin.
  if(streetPlan?.legs?.transport?.coordinates?.length>1){
    const street=[];appendTrack(street,streetPlan.legs.response?.coordinates);appendTrack(street,streetPlan.legs.transport.coordinates);
    if(street.length>pts.length)pts=street;
  }
  pts=extendToHospital(pts,best.hospital_id);
  if(pts.length>1)savedAstarPath=pts;
}
function astarLatLngs(){
  if(!world)return savedAstarPath.slice();
  const best=currentPlan?.best;const m=mission();
  if(best)rememberAstarPath(best);
  const pickupNodes=best?.pickup_route?.nodes||m?.pickup_route?.nodes||(!m?.picked_up&&m?.remaining_route?.nodes)||[];
  const hospitalNodes=best?.hospital_route?.nodes||m?.hospital_route?.nodes||[];
  const ids=[];
  for(const id of pickupNodes)if(!ids.length||ids.at(-1)!==id)ids.push(id);
  for(const id of hospitalNodes)if(!ids.length||ids.at(-1)!==id)ids.push(id);
  let pts=ids.map(id=>world.nodes[id]).filter(Boolean).map(n=>[n.lat,n.lon]);
  if(streetPlan?.legs?.transport?.coordinates?.length>1){
    const street=[];appendTrack(street,streetPlan.legs.response?.coordinates);appendTrack(street,streetPlan.legs.transport.coordinates);
    if(street.length>=Math.max(2,pts.length))pts=street;
  }
  pts=extendToHospital(pts,best?.hospital_id||m?.hospital_id);
  if(pts.length>1){savedAstarPath=pts;return pts;}
  if(savedAstarPath.length>1)return savedAstarPath.slice();
  const street=[];
  appendTrack(street,streetPlan?.legs?.response?.coordinates);
  appendTrack(street,streetPlan?.legs?.transport?.coordinates);
  return extendToHospital(street,m?.hospital_id||$('destination-hospital')?.value);
}
function appendTrack(track,coords){for(const p of coords||[]){const ll=Array.isArray(p[0])?p:latlng(p);if(!track.length||track.at(-1)[0]!==ll[0]||track.at(-1)[1]!==ll[1])track.push(ll);}return track;}
function fullMissionTrack(){
  // Dispatch starts at pickup → hospital (gold street path).
  const track=[];
  appendTrack(track,streetPlan?.legs?.transport?.coordinates);
  if(track.length>1)return track;
  const m=mission(),p=pickupPoint(),h=m&&(state().hospitals[m.hospital_id]||streetPlan?.hospital);
  const hospNodes=(m?.hospital_route?.nodes||currentPlan?.best?.hospital_route?.nodes||[]).map(id=>world.nodes[id]).filter(Boolean).map(n=>[n.lat,n.lon]);
  if(hospNodes.length>1)return extendToHospital(hospNodes,m?.hospital_id);
  const pts=[];
  if(p)pts.push([p.lat,p.lon]);
  if(h)pts.push([h.lat,h.lon]);
  return pts;
}
function pointOnTrack(track,t){
  if(!track?.length)return null;
  if(track.length===1)return track[0];
  const u=Math.min(1,Math.max(0,t))*(track.length-1),i=Math.floor(u),f=u-i,a=track[i],b=track[Math.min(track.length-1,i+1)];
  return[a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f];
}
function stopAmbulanceDrive(){if(ambRaf){cancelAnimationFrame(ambRaf);ambRaf=0;}ambDrive=null;}
function startAmbulanceDrive(missionId){
  const track=fullMissionTrack();
  if(track.length<2)return;
  stopAmbulanceDrive();
  // ~18s visual drive so the red marker is obvious even when the graph only has 1–2 GPS hops.
  ambDrive={missionId,track,started:performance.now(),duration:18000};
  const tick=now=>{
    if(!ambDrive||ambDrive.missionId!==missionId)return;
    const m=mission();
    if(!m||m.id!==missionId){stopAmbulanceDrive();paintAmbulance();return;}
    paintAmbulance();
    const t=(now-ambDrive.started)/ambDrive.duration;
    if(t<1||!['ARRIVED','COMPLETED'].includes(m.phase))ambRaf=requestAnimationFrame(tick);
    else{ambDrive.done=true;paintAmbulance();}
  };
  ambRaf=requestAnimationFrame(tick);
  paintAmbulance();
  streetMap?.fitBounds(track,{padding:[50,60],maxZoom:14,animate:true});
  status('Red ✚ starts at your pickup and drives to the hospital.');
}
function ambulanceLatLng(){
  const m=mission();if(!m||!world)return null;
  const a=state().fleet[m.ambulance_id];if(!a)return null;
  const n=world.nodes[a.current_node];
  // Prefer smooth visual drive along streets (ambulance → pickup → hospital).
  if(ambDrive&&ambDrive.missionId===m.id&&ambDrive.track.length>1){
    const t=Math.min(1,(performance.now()-ambDrive.started)/ambDrive.duration);
    return pointOnTrack(ambDrive.track,t);
  }
  if(!n)return null;
  const track=fullMissionTrack();
  if(track.length>1&&['TO_PICKUP','ON_SCENE','TO_HOSPITAL','ARRIVED'].includes(m.phase)){
    const total=Math.max(m.original_eta_min||1,.1),rem=Math.max(0,m.remaining_min||0);
    let p=m.phase==='ARRIVED'?1:m.phase==='ON_SCENE'?.42:Math.min(.98,Math.max(0.02,1-rem/total));
    if(m.phase==='TO_PICKUP')p=Math.min(.4,p);
    if(m.phase==='TO_HOSPITAL')p=Math.max(.45,p);
    return pointOnTrack(track,p);
  }
  return[n.lat,n.lon];
}
function paintAmbulance(){
  if(!streetMap)return;
  const at=ambulanceLatLng();const m=mission();
  if(!at||!m||!['TO_PICKUP','ON_SCENE','TO_HOSPITAL','ARRIVED'].includes(m.phase)){
    if(ambulanceMarker){streetMap.removeLayer(ambulanceMarker);ambulanceMarker=null;}
    if(m?.phase==='COMPLETED')stopAmbulanceDrive();
    return;
  }
  const driving=ambDrive&&ambDrive.missionId===m.id&&!ambDrive.done;
  const t=driving?Math.min(1,(performance.now()-ambDrive.started)/ambDrive.duration):1;
  const label=m.phase==='ARRIVED'&&(!driving||t>=1)?'✓':'✚';
  // Own layer on the map (not endpointLayer) so pin redraws cannot erase the red ambulance.
  if(!ambulanceMarker){
    ambulanceMarker=L.marker(at,{icon:pin(label,'pin-ambulance'),zIndexOffset:5000,interactive:false}).addTo(streetMap);
    ambulanceMarker.bindTooltip(`${m.ambulance_id} · from pickup`,{permanent:true,direction:'top',offset:[0,-18],className:'amb-tip'});
  }else{
    ambulanceMarker.setLatLng(at);
    ambulanceMarker.setIcon(pin(label,'pin-ambulance'));
    ambulanceMarker.setTooltipContent(`${m.ambulance_id} · ${driving?'pickup → hospital':m.phase.replaceAll('_',' ')}`);
  }
  if($('map-coordinate'))$('map-coordinate').textContent=`RED ✚ ${m.ambulance_id} from pickup · ${at[0].toFixed(5)}, ${at[1].toFixed(5)}`;
}
window.startAmbulanceDrive=startAmbulanceDrive;
window.stopAmbulanceDrive=stopAmbulanceDrive;
function paintMapRoutes(){
  if(!streetMap||!tripLayer)return;
  tripLayer.clearLayers();arrowLayer.clearLayers();
  const street=streetPlan?.legs?.transport;
  const astar=astarLatLngs();
  const m=mission();
  const pickup=pickupPoint();
  const pickupName=pickup?.label||pickup?.name||world?.nodes?.[$('pickup')?.value]?.name||'pickup';
  // Gold = the dispatched trip: pickup → hospital
  if(street?.coordinates?.length>1){
    addRoadRoute(street,legColors.transport,'transport');
    renderRouteArrows();
  }
  // Cyan = A* pickup → hospital junctions (same trip, graph view)
  const tripPath=street?.coordinates?.length>1?street.coordinates.map(latlng):(astar.length>1?astar:fullMissionTrack());
  if(tripPath.length>1){
    tripLayer.addLayer(L.polyline(tripPath,{renderer:L.svg(),color:'#000',weight:14,opacity:.35,interactive:false}));
    tripLayer.addLayer(L.polyline(tripPath,{renderer:L.svg(),color:'#5eead4',weight:5,opacity:.85,interactive:false,dashArray:'10 8',className:'astar-route'}));
  }
  if(tripPath.length>1){
    const fitKey=JSON.stringify(tripPath[0])+JSON.stringify(tripPath.at(-1))+(m?.id||'plan')+(m?.phase||'');
    if(fitKey!==lastFitKey){streetMap.fitBounds(tripPath,{padding:[50,60],maxZoom:14,animate:true});lastFitKey=fitKey;}
    $('map-source').textContent=`FROM ${pickupName.toUpperCase()} → HOSPITAL`;
    const name=streetPlan?.hospital?.name||currentPlan?.best?.hospital_name||state().hospitals[m?.hospital_id]?.name||'hospital';
    const mins=street?.minutes??currentPlan?.best?.arrival_min??m?.remaining_min;
    const km=street?.distance_km;
    if(!$('trip-summary').classList.contains('routing')){
      $('trip-summary').classList.remove('street-error');
      const phaseNote=`Dispatch: red ✚ starts at ${pickupName} and follows this path to ${name}.`;
      $('trip-summary').textContent=mins!=null?`${phaseNote} ETA ${Number(mins).toFixed(1)} min${km!=null?` · ${Number(km).toFixed(1)} km`:''}.`:`${phaseNote}`;
    }
  }
  paintAmbulance();
  updateRouteSteps();
}
function initializeStreetMap(){if(streetMap)return;streetMap=L.map('street-map',{zoomControl:false,preferCanvas:true,attributionControl:true,minZoom:11,maxZoom:17,zoomAnimation:true,markerZoomAnimation:true,fadeAnimation:true});streetMap.fitBounds([[12.97,80.16],[13.14,80.29]]);streetMap.attributionControl.setPrefix('');streetMap.attributionControl.addAttribution('© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>');streetMap.resize=()=>streetMap.invalidateSize();roadLayer=L.layerGroup().addTo(streetMap);hospitalLayer=L.layerGroup().addTo(streetMap);tripLayer=L.layerGroup().addTo(streetMap);arrowLayer=L.layerGroup().addTo(streetMap);endpointLayer=L.layerGroup().addTo(streetMap);labelLayer=L.layerGroup().addTo(streetMap);streetMap.on('zoomend moveend',()=>{renderStreetHospitals();renderStreetRoads();renderStreetLabels();renderRouteArrows();});streetMap.on('click',e=>{setSource(e.latlng.lat,e.latlng.lng,'Map pickup');$('map-source').textContent='PICKUP SET · FINDING ROUTE…';updateRouteSteps();});new ResizeObserver(()=>streetMap.invalidateSize()).observe($('street-map'));$('graph-map').hidden=true;ensureBasemap(true);}
function hospitalPopup(h){const box=element('div');box.append(element('strong','',h.name),element('p','',h.address||'Address not recorded'),element('p','','Tap to set as destination'));const a=element('button','button primary','Go here →');a.addEventListener('click',()=>{chooseHospital(h.id);streetMap.closePopup();requestStreetPlan(true);});box.append(a);return box;}
function hospitalSubset(){const filter=$('map-hospital-filter')?.value||'nearby';if(filter==='nearby')return nearbyHospitals(8);if(filter==='configured')return cityDirectory.filter(h=>state().hospitals[h.id]?.status_source!=='UNKNOWN');if(filter==='top'){const ids=new Set((streetPlan?.top_hospitals||[]).map(h=>h.hospital_id));return cityDirectory.filter(h=>ids.has(h.id));}return cityDirectory;}
function renderStreetHospitals(){if(!streetMap||!world||!cityDirectory.length)return;hospitalLayer.clearLayers();const rows=hospitalSubset(),chosenId=$('destination-hospital').value||streetPlan?.selected_hospital||streetPlan?.top_hospitals?.[0]?.hospital_id;let shown=0;for(const h of rows){shown++;const configured=state().hospitals[h.id]?.status_source!=='UNKNOWN',chosen=h.id===chosenId;const m=L.circleMarker([h.lat,h.lon],{radius:chosen?10:configured?7:5,color:chosen?'#f5c451':'#111',weight:chosen?3:1.5,fillColor:chosen?'#f5c451':configured?'#f0f0f0':'#666',fillOpacity:chosen?.98:.9,className:chosen?'hospital-glow':''});m.bindTooltip((chosen?'★ ':'✚ ')+h.name,{direction:'top',opacity:.96}).bindPopup(()=>hospitalPopup(h));hospitalLayer.addLayer(m);}$('map-hospital-count').textContent=rows.length?`${rows.length} nearby hospitals shown`:'Set a pickup to see nearby hospitals';$('street-map').dataset.hospitalRecords=String(shown);updateRouteSteps();}
function roadStyle(road){const major=/motorway|trunk|primary/.test(road.kind),secondary=/secondary|tertiary/.test(road.kind),closed=streetClosed.has(road.id);return{color:closed?'#ff5555':major?'#d4d4d4':secondary?'#8a8a8a':'#4a4a4a',weight:closed?3.5:major?2.4:secondary?1.5:0.9,opacity:closed?.95:basemap?(major?.55:.35):(major?.85:.65),dashArray:closed?'5 5':null};}
function basemapUrl(){return streetTheme()?'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png':'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';}
function ensureBasemap(on=true){if(!streetMap)return;if(!on){if(basemap){streetMap.removeLayer(basemap);basemap=null;}document.getElementById('street-map')?.classList.remove('dark-tiles');$('map-source').textContent='STREETS ONLY';renderStreetRoads(true);return;}if(basemap){streetMap.removeLayer(basemap);basemap=null;}basemap=L.tileLayer(cfg.tileUrl||basemapUrl(),{maxZoom:19,subdomains:'abc',keepBuffer:2,opacity:1,attribution:'© OpenStreetMap'}).addTo(streetMap);document.getElementById('street-map')?.classList.toggle('dark-tiles',streetTheme());basemap.on('tileerror',()=>{$('map-source').textContent='TILES OFFLINE · BUNDLED STREETS';});$('toggle-basemap')?.setAttribute('aria-pressed','true');$('map-source').textContent='CLICK MAP TO SET PICKUP';renderStreetRoads(true);}
function roadPopup(road){const box=element('div');box.append(element('strong','',road.name),element('p','','Click map empty area to set pickup'));return box;}
function renderStreetRoads(restyle=false){if(!streetData||!streetMap)return;const zoom=streetMap.getZoom();for(const road of streetData.roads){const visible=zoom>=12||/motorway|trunk|primary|secondary/.test(road.kind);let layer=roadLayers.get(road.id);if(!layer&&visible){layer=L.polyline(road.coordinates.map(latlng),{...roadStyle(road),interactive:false,smoothFactor:1.2});roadLayers.set(road.id,layer);}if(layer){if(visible&&!roadLayer.hasLayer(layer))roadLayer.addLayer(layer);else if(!visible&&roadLayer.hasLayer(layer))roadLayer.removeLayer(layer);if(restyle)layer.setStyle(roadStyle(road));}}}
function renderStreetLabels(){if(!streetMap||!labelLayer||!world)return;labelLayer.clearLayers();const bounds=streetMap.getBounds(),zoom=streetMap.getZoom();if(zoom<12)return;for(const n of Object.values(world.nodes)){if(!bounds.contains([n.lat,n.lon]))continue;const marker=L.marker([n.lat,n.lon],{interactive:false,icon:L.divIcon({className:'area-name',html:'',iconSize:[100,18],iconAnchor:[50,-10]})}).addTo(labelLayer);const el=marker.getElement();if(el)el.textContent=n.name;}}
function streetPayload(){if(!world)return null;const m=mission(),active=m&&activePhases.includes(m.phase);const req=currentPlan?.request||(active?m.request:{pickup:$('pickup').value,category:$('category').value,emergency:$('emergency').value,needs_icu:$('needs-icu').checked,...cityRequest()});return{...req,hospital_id:req.preferred_hospital||currentPlan?.best?.hospital_id||(active?m.hospital_id:null),ambulance_id:currentPlan?.best?.ambulance_id||(active?m.ambulance_id:null),directional_traffic:$('directional-traffic').value||'balanced',return_to:$('return-destination').value||'pickup',closed_streets:[...streetClosed].sort(),simple:true};}
function desiredStreetKey(){const body=streetPayload();return body?JSON.stringify([body,world.state.revision]):'';}
async function requestStreetPlan(force=false){if(!world||!roadsReady)return;const body=streetPayload(),key=desiredStreetKey();if(!force&&(streetKey===key||streetPendingKey===key))return;const generation=++streetGeneration;streetPendingKey=key;stopStreetPlayback();if($('street-recalculate'))$('street-recalculate').disabled=true;$('trip-summary').textContent='Running A* + street shortest path…';$('trip-summary').classList.add('routing');try{const result=await api('street-plan',body);if(generation!==streetGeneration||key!==desiredStreetKey())return;streetPlan=result;streetKey=key;if(!$('destination-hospital').value&&result.top_hospitals?.[0]){/* visual only */}renderStreetTrip();renderStreetPins();renderStreetHospitals();paintMapRoutes();const m=mission();if(m&&activePhases.includes(m.phase)&&(!ambDrive||ambDrive.missionId!==m.id||ambDrive.track.length<5))startAmbulanceDrive(m.id);if(!livePreview)displayStreetRankings();if(window.refreshFieldKit)refreshFieldKit();}catch(e){if(generation!==streetGeneration)return;streetPlan=null;streetKey='';$('trip-summary').textContent='Street overlay failed ('+e.message+'). Showing A* path if available.';$('trip-summary').classList.add('street-error');paintMapRoutes();}finally{$('trip-summary').classList.remove('routing');if(generation===streetGeneration){streetPendingKey='';if($('street-recalculate'))$('street-recalculate').disabled=false;}}}
function scheduleStreetPlan(){if(!world||!roadsReady)return;clearTimeout(streetTimer);streetTimer=setTimeout(()=>requestStreetPlan(),200);}
function displayStreetRankings(){if(!streetPlan)return;oldRecommendations(streetPlan.top_hospitals);$('ranking-mode').textContent='A* + STREETS';$('ranking-source').textContent='A* chooses ambulance/hospital; map highlights the shortest traffic-aware path';$('traffic-source-chip').textContent=state().settings.use_ml?'A* + ML':'A* TRAFFIC';}
function renderStreetTrip(){const parent=$('trip-legs');if(!parent)return;parent.replaceChildren();$('trip-summary').classList.remove('street-error');const t=streetPlan?.legs?.transport;if($('street-play'))$('street-play').disabled=!t;updateRouteSteps();}
function addRoadRoute(r,color,key){if(!r?.coordinates?.length)return;const coords=r.coordinates.map(latlng);tripLayer.addLayer(L.polyline(coords,{renderer:L.svg(),color:'#000',weight:12,opacity:.5,interactive:false}));tripLayer.addLayer(L.polyline(coords,{renderer:L.svg(),color:color,weight:6,opacity:.98,interactive:false,className:'street-route route-pulse'}));for(const c of [r.source_connector,r.destination_connector].filter(Boolean)){if(c?.length)tripLayer.addLayer(L.polyline(c.map(latlng),{color:'#f5c451',weight:2,dashArray:'3 6',opacity:.75,interactive:false}));}}
function drawStreetTrip(){paintMapRoutes();}
function renderRouteArrows(){if(!arrowLayer||!streetPlan?.legs?.transport)return;arrowLayer.clearLayers();const r=streetPlan.legs.transport;let last=null,count=0;for(let i=1;i<r.coordinates.length&&count<20;i++){const a=streetMap.latLngToLayerPoint(latlng(r.coordinates[i-1])),b=streetMap.latLngToLayerPoint(latlng(r.coordinates[i]));if(!last||b.distanceTo(last)>110){if(a.distanceTo(b)<2)continue;const angle=Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI;arrowLayer.addLayer(L.marker(latlng(r.coordinates[i]),{interactive:false,icon:L.divIcon({className:'direction-arrow',html:`<span style="display:block;transform:rotate(${angle}deg);color:#f5c451">➤</span>`,iconSize:[18,18],iconAnchor:[9,9]})}));last=b;count++;}}}
function renderStreetPins(){if(!streetMap||!world)return;endpointLayer.clearLayers();const src=pickupPoint();if(src)endpointLayer.addLayer(L.marker([src.lat,src.lon],{icon:pin('P','pin-pickup')}).bindTooltip('Pickup'));const hid=$('destination-hospital').value||streetPlan?.selected_hospital||streetPlan?.top_hospitals?.[0]?.hospital_id||currentPlan?.best?.hospital_id||mission()?.hospital_id;const h=streetPlan?.hospital||cityDirectory.find(x=>x.id===hid)||(hid&&state().hospitals[hid]);if(h)endpointLayer.addLayer(L.marker([h.lat,h.lon],{icon:pin('H','pin-hospital')}).bindTooltip(h.name));paintAmbulance();}
function fitStreetTrip(){paintMapRoutes();}
function stopStreetPlayback(){if(streetPlayback){clearInterval(streetPlayback);streetPlayback=null;}if(playbackMarker){streetMap.removeLayer(playbackMarker);playbackMarker=null;}}
function movePreview(progress){if(!streetPlan?.legs?.transport)return;const r=streetPlan.legs.transport,coords=r.coordinates,lengths=[0];for(let i=1;i<coords.length;i++)lengths.push(lengths[i-1]+L.latLng(latlng(coords[i-1])).distanceTo(L.latLng(latlng(coords[i]))));const target=lengths.at(-1)*progress/100;let i=1;while(i<lengths.length-1&&lengths[i]<target)i++;const f=(target-lengths[i-1])/Math.max(.001,lengths[i]-lengths[i-1]);const a=coords[Math.max(0,i-1)],b=coords[Math.min(i,coords.length-1)],at=[a[1]+(b[1]-a[1])*f,a[0]+(b[0]-a[0])*f];if(!playbackMarker)playbackMarker=L.marker(at,{icon:pin('+','pin-preview'),interactive:false}).addTo(streetMap);else playbackMarker.setLatLng(at);}
const oldRecommendations=renderRecommendations;renderRecommendations=function(rows){if(streetPlan&&streetKey===desiredStreetKey()&&!livePreview)displayStreetRankings();else oldRecommendations(rows);};
const previousDraw=drawGraph;drawGraph=function(){if(!streetMap)return;renderStreetPins();renderStreetHospitals();renderStreetLabels();paintMapRoutes();updateRouteSteps();};
const previousExtras=renderCityExtras;renderCityExtras=function(){previousExtras();if(!streetMap)return;renderStreetPins();renderStreetHospitals();paintMapRoutes();if(streetPlan&&!livePreview&&streetKey===desiredStreetKey())displayStreetRankings();updateRouteSteps();};
const previousView=view;view=function(name){previousView(name);if(name==='dispatch'&&streetMap)setTimeout(()=>streetMap.invalidateSize(),0);};
const previousChoose=chooseHospital;chooseHospital=function(id,calculateNow=true){streetPlan=null;streetKey='';previousChoose(id,calculateNow);scheduleStreetPlan();updateRouteSteps();};
focusHospital=function(id){const h=cityDirectory.find(h=>h.id===id);if(!h)return;$('map-hospital-filter').value='nearby';streetMap.setView([h.lat,h.lon],15);renderStreetHospitals();showHospitalSelection(id);};
const previousClear=clearLivePreview;clearLivePreview=function(){previousClear();streetGeneration++;streetPendingKey='';streetKey='';streetPlan=null;if(tripLayer)tripLayer.clearLayers();if(arrowLayer)arrowLayer.clearLayers();scheduleStreetPlan();};
const previousReset=resetCitySelections;resetCitySelections=function(){stopStreetPlayback();stopAmbulanceDrive();savedAstarPath=[];if(ambulanceMarker&&streetMap){streetMap.removeLayer(ambulanceMarker);ambulanceMarker=null;}streetClosed.clear();if($('directional-traffic'))$('directional-traffic').value='balanced';if($('return-destination'))$('return-destination').value='pickup';streetPlan=null;streetKey='';streetGeneration++;previousReset();renderStreetRoads(true);updateRouteSteps();};
for(const id of ['zoom-in','zoom-out','map-fit','map-reset','city-3d']){const old=$(id);if(!old)continue;const copy=old.cloneNode(true);old.replaceWith(copy);}
$('zoom-in')?.addEventListener('click',()=>streetMap.zoomIn());$('zoom-out')?.addEventListener('click',()=>streetMap.zoomOut());$('map-fit')?.addEventListener('click',fitStreetTrip);$('map-reset')?.addEventListener('click',()=>streetMap.fitBounds([[12.97,80.16],[13.14,80.29]]));
$('city-3d')?.addEventListener('click',()=>{});
$('graph-mode')?.addEventListener('click',()=>{$('street-map').hidden=false;$('graph-map').hidden=true;$('geo-map').hidden=true;streetMap.invalidateSize();});
$('aws-map-mode')?.addEventListener('click',()=>{$('street-map').hidden=true;});
$('map-hospital-filter')?.addEventListener('change',()=>{renderStreetHospitals();if(($('map-hospital-filter').value==='nearby'||$('map-hospital-filter').value==='top'))scheduleStreetPlan();});
$('show-all-hospitals')?.addEventListener('click',()=>{$('map-hospital-filter').value='all';streetMap.fitBounds(cityDirectory.map(h=>[h.lat,h.lon]),{padding:[35,45]});renderStreetHospitals();});
$('map-hospital-search')?.addEventListener('change',()=>{const text=$('map-hospital-search').value.toLowerCase().trim(),h=cityDirectory.find(h=>h.name.toLowerCase()===text)||cityDirectory.find(h=>h.name.toLowerCase().includes(text));if(h&&text){chooseHospital(h.id,false);focusHospital(h.id);requestStreetPlan(true);}else if(text)status('No hospital match. Try another name.',true);});
$('street-recalculate')?.addEventListener('click',()=>requestStreetPlan(true));
window.paintMapRoutes=paintMapRoutes;window.requestStreetPlan=requestStreetPlan;window.paintAmbulance=paintAmbulance;window.rememberAstarPath=rememberAstarPath;
for(const id of ['directional-traffic','return-destination'])$(id)?.addEventListener('change',()=>{streetKey='';requestStreetPlan(true);});
$('clear-street-incidents')?.addEventListener('click',()=>{streetClosed.clear();renderStreetRoads(true);streetKey='';requestStreetPlan(true);});
$('street-play')?.addEventListener('click',()=>{if(streetPlayback){stopStreetPlayback();return;}if(!streetPlan?.legs?.transport)return;let progress=0;streetPlayback=setInterval(()=>{progress=Math.min(100,progress+2);if($('street-progress'))$('street-progress').value=progress;movePreview(progress);if(progress===100)stopStreetPlayback();},120);});
$('toggle-basemap')?.addEventListener('click',()=>ensureBasemap(!basemap));
$('theme-toggle')?.addEventListener('click',()=>{ensureBasemap(!!basemap);renderStreetRoads(true);drawStreetTrip();});
initializeStreetMap();
(async()=>{try{const r=await fetch('assets/chennai_streets.json');if(!r.ok)throw new Error('Street snapshot missing.');streetData=await r.json();renderStreetRoads();roadsReady=true;$('graph-info').textContent='Mapped Chennai corridors ready';scheduleStreetPlan();}catch(e){$('graph-info').textContent=e.message;status(e.message,true);}let tries=0;const timer=setInterval(()=>{if(cityDirectory.length){clearInterval(timer);for(const h of cityDirectory)$('map-hospital-options')?.append(new Option(h.name,h.name));renderStreetHospitals();}else if(++tries>60)clearInterval(timer);},200);})();
drawGeo=function(){if(!geoReady||!geoMap||!world)return;};
$('aws-map-mode')?.addEventListener('click',()=>{$('map-source').textContent='AWS MAP';});
