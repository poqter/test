const url = Deno.env.get("SUPABASE_URL")!;
const admin = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const anon = Deno.env.get("SUPABASE_ANON_KEY")!;
const headers = { "Content-Type": "application/json", "Cache-Control": "no-store" };
const deny = () => new Response('{"error":"로그인 정보를 확인해 주세요."}', { status: 401, headers });
async function rpc(name: string, body: object) {
  const response = await fetch(url + "/rest/v1/rpc/" + name, {
    method: "POST", headers: { ...headers, apikey: admin, Authorization: "Bearer " + admin }, body: JSON.stringify(body)
  });
  if (!response.ok) throw Error("Account service unavailable");
  return (await response.json())[0];
}
Deno.serve(async req => {
  if (req.method !== "POST") return new Response(null, { status: 405 });
  try {
    const { login_id, password } = await req.json();
    if (typeof login_id !== "string" || !login_id.trim() || login_id.length > 150 ||
        typeof password !== "string" || !password || password.length > 4096) return deny();
    const account = await rpc("get_hwarang_login_bootstrap", { p_login_id: login_id.trim() });
    if (!account?.is_active) return deny();
    let email = account.auth_email;
    if (!email) {
      const profile = await fetch(url + "/auth/v1/admin/users/" + encodeURIComponent(account.user_id),
        { headers: { apikey: admin, Authorization: "Bearer " + admin } });
      if (!profile.ok) return deny();
      email = (await profile.json()).email;
    }
    const response = await fetch(url + "/auth/v1/token?grant_type=password", {
      method: "POST", headers: { ...headers, apikey: anon }, body: JSON.stringify({ email, password })
    });
    if (!response.ok) return deny();
    const session = await response.json();
    if (session.user?.id !== account.user_id) return deny();
    const context = await rpc("complete_hwarang_workspace_login", { p_user_id: account.user_id });
    if (!context?.is_active || !context.app_access?.workspace) return deny();
    return Response.json(session, { headers });
  } catch {
    return new Response('{"error":"로그인을 처리하지 못했습니다."}', { status: 400, headers });
  }
});
