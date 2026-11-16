/** Send one already-claimed part. Storage implements atomic reservation and fresh authorization.
 * Not wired into the deployed handler until RPC transaction and quota tests pass.
 */
export async function dispatchOne({store,api,job}) {
  if (!job || !Number.isInteger(job.part) || job.part<1 || typeof job.body!=='string' || !job.body || job.body.length>200) throw Error('Invalid job');
  let attempted=false;
  try {
    // Store checks current live account, membership/scope, subscription consent, generation,
    // pending prior part accepted, owner/day uniqueness and reserved free budget.
    const permit=await store.authorize(job);
    if (!permit?.allowed) {await store.cancel(job,'authorization_changed');return {status:'cancelled'};}
    // Any token refresh and rotated-token persistence must be serialized per connection.
    const token=await store.validToken(job);
    const ready=await store.beginAttempt(job); // atomic reserved->sending; revalidates authorization
    if (!ready) return {status:'cancelled'};
    attempted=true;
    const result=await api.sendMemo(token,job.body);
    if(result?.result_code!==0)throw Error('API did not accept');
    await store.accept(job);
    return {status:'accepted'};
  } catch {
    // Never retry uncertain transport or persistence; next part remains blocked.
    await store.fail(job,attempted?'uncertain':'failed').catch(()=>{});
    return {status:attempted?'uncertain':'failed'};
  }
}
