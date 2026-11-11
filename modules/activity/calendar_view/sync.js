/* One authorized subscription while this calendar is visible. Polling remains
 * as a fallback, and visible-range stamps avoid unrelated payload reloads. */
let realtimeClient=null,realtimeKey='',realtimeToken='',realtimeReady=false,signalTimer=null,signalPending=false;
function stopRealtime(){
 const old=realtimeClient;realtimeClient=null;realtimeReady=false;realtimeKey='';realtimeToken='';signalPending=false;clearTimeout(signalTimer);signalTimer=null;
 clearTimeout(syncTimer);syncTimer=null;
 if(old)old.removeAllChannels().then(()=>old.disconnect()).catch(()=>old.disconnect());
}
function configureRealtime(a){
 const session=a?.mobileSession;
 if(document.hidden||!parentVisible||!a?.fast||!session?.token||!a.syncUnit){stopRealtime();return}
 const key=[session.url,session.uid,a.syncUnit].join('|');
 if(realtimeClient&&realtimeKey===key){if(realtimeToken!==session.token){realtimeToken=session.token;realtimeClient.setAuth(session.token).catch(()=>{realtimeReady=false})}return}
 stopRealtime();realtimeKey=key;realtimeToken=session.token;
 const client=realtimeClient=new HwarangRealtime.RealtimeClient(session.url+'/realtime/v1',{params:{apikey:session.key},accessToken:async()=>syncConfig?.mobileSession?.token||null});
 client.channel('calendar:'+a.syncUnit).on('postgres_changes',{event:'*',schema:'public',table:'sales_calendar_signals',filter:'unit=eq.'+a.syncUnit},()=>{
  signalPending=true;if(signalTimer)return;signalTimer=setTimeout(()=>{signalTimer=null;if(client===realtimeClient)checkSync()},500);
 }).on('postgres_changes',{event:'*',schema:'public',table:'sales_activity_signals',filter:'owner=eq.'+session.uid},payload=>{
  if(payload.new?.topic==='scope'){calendarCache.clear();calendarBoot.supportRecipients=null;calendarAction('reauth')}
 }).subscribe(status=>{
  if(client!==realtimeClient)return;
  realtimeReady=status==='SUBSCRIBED';scheduleSync();
  if(realtimeReady)checkSync();
 });
}
addEventListener('pagehide',stopRealtime);
