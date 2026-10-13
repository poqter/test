// First HTTP response contains the full reader and sender-specific Open Graph tags.
// Every asset read goes through the same live policy/revision/revocation gate.
type Dependencies = { env: (key: string) => string | undefined; fetcher: typeof fetch };
const headers = {
  "Cache-Control": "private, no-store, max-age=0", "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow",
  "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline' https://cdn.jsdelivr.net; font-src https://cdn.jsdelivr.net; script-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
};
function message(status: number, text: string): Response {
  return new Response('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>브리핑 안내</title><body style="font:18px/1.8 sans-serif;margin:48px auto;max-width:600px;padding:20px">'+text+'</body></html>', {status, headers:{...headers,"Content-Type":"text/html; charset=utf-8"}});
}
// Log only bounded classifications. Never log URLs, headers, keys, tokens or upstream bodies.
const READER_RELEASE = "reader-20261014-readable";
function cleanSetting(value: string | undefined) {
  let text = String(value || "").trim();
  if (text.length >= 2 && ((text.startsWith('"') && text.endsWith('"')) || (text.startsWith("'") && text.endsWith("'")))) text = text.slice(1, -1).trim();
  return text;
}
function logFailure(stage: string, code: string, upstreamStatus: number | null = null) {
  console.error(JSON.stringify({event:"briefing_reader_failure",release:READER_RELEASE,stage,code,upstream_status:upstreamStatus}));
}
function settings(deps: Dependencies) {
  const base = cleanSetting(deps.env("SUPABASE_URL")).replace(/\/$/, "");
  const key = cleanSetting(deps.env("SUPABASE_SERVICE_ROLE_KEY"));
  if (!base || !key) return {base,key,error:"missing_setting"};
  try {
    const parsed = new URL(base);
    if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== "/") return {base,key,error:"invalid_project_url"};
  } catch { return {base,key,error:"invalid_project_url"}; }
  if (/[^\x21-\x7e]/.test(key)) return {base,key,error:"invalid_key_header"};
  return {base,key,error:null};
}
const READER_DESIGN_CSS = "\n@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');\n:root{color-scheme:light;--ink:#182c46;--muted:#607087;--brand:#172e4d;--line:#e4eaf1;--soft:#f1f5fa}*{box-sizing:border-box}body{font-family:Pretendard,'Malgun Gothic',sans-serif;margin:0;background:#eef2f6;color:var(--ink);font-size:16px;line-height:1.9;overflow-wrap:anywhere}.wrap{max-width:736px;margin:24px auto 48px;background:#fff;padding:0 36px 30px;border-radius:12px;overflow:hidden}header{margin:0 -36px 30px;padding:30px 36px 0;background:var(--brand);color:#f7f9fc}.brand{display:flex;align-items:center;gap:12px;font-size:13px;font-weight:600;letter-spacing:1.5px;color:#cdd8e7;margin-bottom:28px}.brand:before{content:'H';font-family:Georgia,serif;font-weight:400;font-size:30px;line-height:42px;text-align:center;width:44px;height:44px;border:1px solid #77869c;flex-shrink:0}h1{font-size:32px;line-height:1.35;letter-spacing:-1.2px;margin:0 0 14px;font-weight:700}h2{font-size:23px;line-height:1.45;letter-spacing:-.7px;margin:0 0 15px;font-weight:700}h3{font-size:14px;line-height:1.7;margin:0 0 7px;font-weight:600}.meta,.source{font-size:13px;color:var(--muted)}header .meta{color:#c5d2e4;font-size:14px;line-height:1.8}.controls{display:flex;gap:8px;flex-wrap:wrap;margin:24px -36px 0;padding:17px 36px;background:#fff;border-bottom:1px solid var(--line)}button,.button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);padding:9px 14px;font:inherit;font-size:13px;text-decoration:none;cursor:pointer}button[aria-pressed=true]{background:var(--soft);border-color:var(--muted)}article{background:#fff;border:0;border-radius:0;padding:0 0 28px;margin:0 0 28px;border-bottom:1px solid var(--line)}article.lead{border-top:0}.panel{background:var(--soft);border:0;border-radius:8px;padding:21px 23px;margin:0 0 32px}.panel h2{font-size:16px}.panel p{margin-bottom:8px}.explanation{border-left:3px solid #9aaec8;padding:2px 0 2px 17px;margin:20px 0}.explanation p{font-size:15px;color:var(--muted);line-height:1.8}p{margin:8px 0 19px}.tag{font-size:12px;color:var(--muted);font-weight:600;display:block;margin-bottom:10px}a{color:#365d85;text-underline-offset:4px}summary{cursor:pointer;color:var(--brand);font-weight:600;padding:8px 0}.source{font-size:12px;margin:10px 0;line-height:1.8}.source a{color:var(--muted)}.section-title{font-size:14px;color:var(--muted);font-weight:500;display:flex;align-items:center;gap:10px;margin:30px 0 20px}.section-title:after{content:'';height:1px;flex:1;background:var(--line)}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.metric{padding:16px;background:var(--soft);border-radius:8px}.value{font-size:24px;font-weight:700}.delta{font-size:16px}.up{color:#b52638}.down{color:#145eb0}.flat{color:var(--muted)}.big{font-size:19px}.big h2{font-size:26px}.big .panel h2{font-size:19px}.big .explanation p{font-size:18px}.reader-footer{background:var(--soft);margin:30px -36px -30px;padding:25px 36px;font-size:12px;color:var(--muted);line-height:1.8}.reader-footer strong{color:var(--ink);font-size:14px;font-weight:600}@media(max-width:600px){.wrap{margin:0;border-radius:0;padding:0 22px 24px}header{margin:0 -22px 26px;padding:24px 22px 0}.controls{margin:22px -22px 0;padding:15px 22px}h1{font-size:28px}h2{font-size:21px}.panel{padding:18px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.reader-footer{margin:26px -22px -24px;padding:23px 22px}}@media(max-width:350px){.metrics{grid-template-columns:1fr}}@media print{body{background:white}.wrap{max-width:none;margin:0;padding:0;border-radius:0}header{background:white;color:var(--ink);margin:0;padding:0 0 16px}header .meta,.brand{color:var(--muted)}.controls{display:none}article,.panel{break-inside:avoid}.reader-footer{margin:20px 0 0}details{display:block}}\n.briefing-section{font-size:22px;font-weight:700;color:var(--ink);margin:42px 0 24px;padding:14px 0;border-top:2px solid var(--line)}article h2{font-size:25px}article>p{font-size:17px;line-height:1.95}.explanation{background:var(--soft);border-left:0;border-radius:8px;padding:17px 20px}.explanation p{color:#40546d;font-size:16px}.source{font-size:13px}.big article>p{font-size:20px}@media(max-width:600px){article h2{font-size:22px}.briefing-section{font-size:20px}}\n";
function applyReaderDesign(document: string): string {
  document = document.replace(/<br\s*\/?>(?:\s*)수집 기준[^<]*/gi, "")
    .replace(/<h2 class="section-title">오늘의 소식 <span class="meta">\d+개<\/span><\/h2>/g, "")
    .replace(/<a class="button" href="[^"]*">PDF 저장<\/a>/g, "")
    .replace(/<h2 class="section-title">(경제·금융[^<]*|종합[^<]*|보험[^<]*)<\/h2>/g, '<h2 class="section-title briefing-section">$1</h2>');
  const style = "<style data-hwarang-reader-design=\"20261014\">" + READER_DESIGN_CSS + "</style>";
  return /<\/head\s*>/i.test(document) ? document.replace(/<\/head\s*>/i, style + "</head>") : style + document;
}
export async function handle(request: Request, deps: Dependencies): Promise<Response> {
  if (request.method !== "GET" && request.method !== "HEAD") return message(405,"읽기 전용 페이지입니다.");
  const url = new URL(request.url);
  if (url.searchParams.get("health") === "1") {
    const config=settings(deps); const configured=!config.error;
    return new Response(JSON.stringify({status:configured?"ok":"configuration_required",schema:"hwarang-share-v3",configured,release:READER_RELEASE}), {status:configured?200:503,headers:{...headers,"Content-Type":"application/json"}});
  }
  const token = url.searchParams.get("token") || "";
  const asset = url.searchParams.get("asset");
  if (!/^[A-Za-z0-9_-]{32,64}$/.test(token) || asset && !["pdf","preview"].includes(asset)) return message(404,"공유 링크를 확인해 주세요.");
  const config=settings(deps); const {base,key}=config;
  if (config.error) { logFailure("configuration",config.error); return message(503,"잠시 후 다시 확인해 주세요."); }
  const auth = {apikey:key, ...(key.startsWith("sb_secret_") ? {} : {Authorization:"Bearer "+key})};
  let stage = "packet_lookup";
  try {
    const response = await deps.fetcher(base+"/rest/v1/rpc/hwarang_read_public_briefing", {method:"POST", headers:{...auth,"Content-Type":"application/json"},body:JSON.stringify({p_token:token}),signal:AbortSignal.timeout(10000)});
    if (!response.ok) { logFailure(stage,"upstream_http_error",response.status); return message(503,"잠시 후 다시 확인해 주세요."); }
    stage = "packet_decode";
    const packet = await response.json();
    if (!packet || packet.schema !== "hwarang-share-v3" || !/^[a-f0-9]{24}$/.test(packet.asset_version || "")) return message(410,"이 공유 링크는 만료됐거나 공개가 중단됐습니다. 보내주신 설계사에게 새 링크를 요청해 주세요.");
    if (!asset) {
      if (typeof packet.rendered_html !== "string" || packet.rendered_html.length > 500000) { logFailure("body_validation","invalid_body"); return message(503,"브리핑 본문을 확인하고 있습니다."); }
      return new Response(request.method === "HEAD" ? null : applyReaderDesign(packet.rendered_html),{headers:{...headers,"Content-Type":"text/html; charset=utf-8"}});
    }
    const filename = asset === "pdf" ? "briefing.pdf" : "preview.png";
    const type = asset === "pdf" ? "application/pdf" : "image/png";
    stage = "asset_lookup";
    const stored = await deps.fetcher(base+"/storage/v1/object/briefing-share-assets/"+token+"/"+packet.asset_version+"/"+filename,{headers:auth,signal:AbortSignal.timeout(10000)});
    if (!stored.ok) { logFailure(stage,"upstream_http_error",stored.status); return message(503,"파일을 준비하고 있습니다. 잠시 후 다시 확인해 주세요."); }
    const buffer = await stored.arrayBuffer();
    if (buffer.byteLength > 4000000 || (stored.headers.get("Content-Type") || "").split(";")[0] !== type) return message(503,"파일을 확인하고 있습니다.");
    return new Response(request.method === "HEAD" ? null : buffer,{headers:{...headers,"Content-Type":type,...(asset === "pdf" ? {"Content-Disposition":'inline; filename="hwarang_briefing.pdf"'} : {})}});
  } catch (error) {
    const name = error instanceof Error ? error.name : "UnknownError";
    logFailure(stage, ["TimeoutError","AbortError","TypeError","SyntaxError"].includes(name) ? name : "request_exception");
    return message(503,"잠시 후 다시 확인해 주세요.");
  }
}
// Portable Cloudflare Worker; credentials are server secrets, never client data.
export default {
  fetch(request: Request, env: Record<string,string>): Promise<Response> {
    return handle(request,{env:(key:string)=>env[key],fetcher:(input,init)=>globalThis.fetch(input,init)});
  }
};
