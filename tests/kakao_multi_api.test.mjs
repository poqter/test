import test from 'node:test';
import assert from 'node:assert/strict';
import {refreshToken,sendMemo,ReauthenticationRequired} from '../supabase/functions/hwarang-kakao/kakao-api.mjs';
test('refresh revoked token is reauth only for confirmed KOE322',async()=>{
 const config={clientId:'app',clientSecret:'secret'},previous={refresh_token:'r'};
 await assert.rejects(refreshToken(async()=>Response.json({error:'invalid_grant',error_code:'KOE322'},{status:400}),config,previous),ReauthenticationRequired);
 for(const payload of [{error:'invalid_client'},{error:'invalid_grant',error_code:'KOE320'}]){
  await assert.rejects(refreshToken(async()=>Response.json(payload,{status:401}),config,previous),e=>!(e instanceof ReauthenticationRequired));
 }
});
test('memo transient401/timeout does not purge consent',async()=>{
 await assert.rejects(sendMemo(async()=>Response.json({code:-401},{status:401}),'token',{}),e=>!(e instanceof ReauthenticationRequired));
 await assert.rejects(sendMemo(async()=>{throw Error('timeout')},'token',{}),e=>!(e instanceof ReauthenticationRequired));
});
