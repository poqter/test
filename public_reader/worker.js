// First HTTP response contains the full reader and sender-specific Open Graph tags.
// Every asset read goes through the same live policy/revision/revocation gate.
                                                                                        
const headers = {
  "Cache-Control": "private, no-store, max-age=0", "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow",
  "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
};
function message(status        , text        )           {
  return new Response('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>브리핑 안내</title><body style="font:18px/1.8 sans-serif;margin:48px auto;max-width:600px;padding:20px">'+text+'</body></html>', {status, headers:{...headers,"Content-Type":"text/html; charset=utf-8"}});
}
export async function handle(request         , deps              )                    {
  if (request.method !== "GET" && request.method !== "HEAD") return message(405,"읽기 전용 페이지입니다.");
  const url = new URL(request.url);
  if (url.searchParams.get("health") === "1") {
    const configured=Boolean(deps.env("SUPABASE_URL") && deps.env("SUPABASE_SERVICE_ROLE_KEY"));
    return new Response(JSON.stringify({status:configured?"ok":"configuration_required",schema:"hwarang-share-v3",configured}), {status:configured?200:503,headers:{...headers,"Content-Type":"application/json"}});
  }
  const token = url.searchParams.get("token") || "";
  const asset = url.searchParams.get("asset");
  if (!/^[A-Za-z0-9_-]{32,64}$/.test(token) || asset && !["pdf","preview"].includes(asset)) return message(404,"공유 링크를 확인해 주세요.");
  const base = (deps.env("SUPABASE_URL") || "").replace(/\/$/, "");
  const key = deps.env("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!base || !key) return message(503,"잠시 후 다시 확인해 주세요.");
  const auth = {apikey:key, ...(key.startsWith("sb_secret_") ? {} : {Authorization:"Bearer "+key})};
  try {
    const response = await deps.fetcher(base+"/rest/v1/rpc/hwarang_read_public_briefing", {method:"POST", headers:{...auth,"Content-Type":"application/json"},body:JSON.stringify({p_token:token}),signal:AbortSignal.timeout(10000)});
    if (!response.ok) return message(503,"잠시 후 다시 확인해 주세요.");
    const packet = await response.json();
    if (!packet || packet.schema !== "hwarang-share-v3" || !/^[a-f0-9]{24}$/.test(packet.asset_version || "")) return message(410,"이 공유 링크는 만료됐거나 공개가 중단됐습니다. 보내주신 설계사에게 새 링크를 요청해 주세요.");
    if (!asset) {
      if (typeof packet.rendered_html !== "string" || packet.rendered_html.length > 500000) return message(503,"브리핑 본문을 확인하고 있습니다.");
      return new Response(request.method === "HEAD" ? null : packet.rendered_html,{headers:{...headers,"Content-Type":"text/html; charset=utf-8"}});
    }
    const filename = asset === "pdf" ? "briefing.pdf" : "preview.png";
    const type = asset === "pdf" ? "application/pdf" : "image/png";
    const stored = await deps.fetcher(base+"/storage/v1/object/briefing-share-assets/"+token+"/"+packet.asset_version+"/"+filename,{headers:auth,signal:AbortSignal.timeout(10000)});
    if (!stored.ok) return message(503,"파일을 준비하고 있습니다. 잠시 후 다시 확인해 주세요.");
    const buffer = await stored.arrayBuffer();
    if (buffer.byteLength > 4000000 || (stored.headers.get("Content-Type") || "").split(";")[0] !== type) return message(503,"파일을 확인하고 있습니다.");
    return new Response(request.method === "HEAD" ? null : buffer,{headers:{...headers,"Content-Type":type,...(asset === "pdf" ? {"Content-Disposition":'inline; filename="hwarang_briefing.pdf"'} : {})}});
  } catch { return message(503,"잠시 후 다시 확인해 주세요."); }
}
// Portable Cloudflare Worker; credentials are server secrets, never client data.
export default {
  fetch(request         , env                       )                    {
    return handle(request,{env:(key       )=>env[key],fetcher:fetch});
  }
};
