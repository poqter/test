/* One authorized subscription while this calendar is visible. Polling remains
 * as a fallback, and visible-range stamps avoid unrelated payload reloads. */
let realtimeClient=null,realtimeKey='',realtimeToken='',realtimeReady=false,signalTimer=null,signalPending=false;
function stopRealtime(){
 const old=realtimeClient;realtimeClient=null;realtimeReady=false;realtimeKey='';realtimeToken='';signalPending=false;clearTimeout(signalTimer);signalTimer=null;
 clearTimeout(syncTimer);syncTimer=null;
 if(old)old.removeAllChannels().then(()=>old.disconnect()).catch(()=>old.disconnect());
}
function calendarSyncUnits(a){
 const scope=a?.mobileSession?.viewScope||'daily';
 if(!scope.startsWith('{'))return [a.syncUnit];
 // Use the authenticated bootstrap scope, never user-entered organization IDs.
 const members=JSON.parse(calendarBoot.access);
 return [...new Set([a.syncUnit,...Object.values(members).map(r=>r.unit)].filter(Boolean))].sort();
}
let realtimeLibraryFlight=null;
function loadRealtimeLibrary(){
 if(realtimeLibraryFlight)return;
 const script=document.createElement('script');script.src='realtime.js';script.async=true;
 realtimeLibraryFlight=script;
 script.onload=()=>{if(typeof HwarangRealtime!=='undefined')configureRealtime(syncConfig)};
 script.onerror=()=>{script.remove();realtimeLibraryFlight=null;};
 document.head.append(script);
}
function configureRealtime(a){
 const session=a?.mobileSession;
 if(document.hidden||!parentVisible||(typeof navigator!=='undefined'&&navigator.onLine===false)||!a?.fast||!session?.token||!a.syncUnit){stopRealtime();return}
 if(!a.syncStamp)return;
 if(typeof HwarangRealtime==='undefined'){loadRealtimeLibrary();return}
 const units=calendarSyncUnits(a),key=[session.url,session.uid,...units].join('|');
 if(realtimeClient&&realtimeKey===key){if(realtimeToken!==session.token){realtimeToken=session.token;realtimeClient.setAuth(session.token).catch(()=>{realtimeReady=false})}return}
 stopRealtime();realtimeKey=key;realtimeToken=session.token;
 const client=realtimeClient=new HwarangRealtime.RealtimeClient(session.url+'/realtime/v1',{params:{apikey:session.key},accessToken:async()=>syncConfig?.mobileSession?.token||null});
 const channel=client.channel('calendar:'+a.syncUnit);
 for(const unit of units)channel.on('postgres_changes',{event:'*',schema:'public',table:'sales_calendar_signals',filter:'unit=eq.'+unit},()=>{
  signalPending=true;if(signalTimer)return;signalTimer=setTimeout(()=>{signalTimer=null;if(client===realtimeClient)checkSync()},500);
 });
 channel.on('postgres_changes',{event:'*',schema:'public',table:'sales_activity_signals',filter:'topic=eq.scope'},payload=>{
  if(payload.new?.topic==='scope'&&payload.new.owner===session.uid){if(typeof resetCalendarSearch==='function')resetCalendarSearch();calendarCache.clear();calendarBoot.supportRecipients=null;calendarAction('reauth')}
 }).subscribe(status=>{
  if(client!==realtimeClient)return;
  realtimeReady=status==='SUBSCRIBED';scheduleSync();
  if(realtimeReady)checkSync();
 });
}
addEventListener('pagehide',stopRealtime);
