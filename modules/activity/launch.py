"""Exchange the existing one-time workspace ticket for a separate Auth session.

Only a consumed server-issued ticket supplies the identity. Neither user IDs nor
Auth credentials are accepted from URL parameters. Calendar data still uses RLS.
"""
import time
from modules.shared.hwarang_auth import HwarangAuthError


def accept_launch(auth, ticket, current=None):
    identity = auth.consume_launch_ticket(ticket, "workspace")
    uid = str(identity["profile"]["id"])
    if "workspace.sales_activity" not in identity.get("feature_permissions", []):
        raise HwarangAuthError("영업활동 관리 이용 권한을 확인해 주세요.")
    if current:
        if str(current.get("profile", {}).get("id")) != uid:
            raise HwarangAuthError("다른 계정으로 캘린더를 사용 중입니다. 로그아웃 후 WORKSPACE에서 다시 열어 주세요.")
        return auth.refresh(current)

    user = auth._auth_user_by_id(uid)
    if str(user.get("id")) != uid or not user.get("email") or not user.get("email_confirmed_at"):
        raise HwarangAuthError("계정 인증정보를 확인하지 못했습니다. 캘린더에서 직접 로그인해 주세요.")
    if any(factor.get("status") == "verified" for factor in user.get("factors", []) or []):
        raise HwarangAuthError("추가 인증이 설정된 계정입니다. 캘린더에서 직접 로그인해 주세요.")
    link = auth._request("POST", "/auth/v1/admin/generate_link", admin=True,
                         json={"type": "magiclink", "email": user["email"]})
    # REST returns properties at the top level (SDKs wrap them in properties).
    if not isinstance(link, dict) or str(link.get("id")) != uid or not link.get("hashed_token"):
        raise HwarangAuthError("캘린더 연결 인증정보를 확인하지 못했습니다.")
    token = auth._request("POST", "/auth/v1/verify",
                          json={"type": "magiclink", "token_hash": link["hashed_token"]})
    if not isinstance(token, dict) or not token.get("access_token") or not token.get("refresh_token"):
        raise HwarangAuthError("캘린더 로그인 정보를 확인하지 못했습니다.")
    try:
        if str((token.get("user") or {}).get("id")) != uid:
            raise HwarangAuthError("캘린더 계정 인증정보가 일치하지 않습니다.")
        context = auth._complete_workspace_login(uid)
        if not context.get("profile", {}).get("is_active") or "workspace.sales_activity" not in context.get("feature_permissions", []):
            raise HwarangAuthError("영업활동 관리 이용 권한을 확인해 주세요.")
    except Exception:
        auth.sign_out(token)
        raise
    return {**context, "access_token": token["access_token"], "refresh_token": token["refresh_token"],
            "expires_at": int(token.get("expires_at") or (time.time() + int(token.get("expires_in") or 3600))),
            "profile_checked_at": int(time.time()), "authenticated_at": time.time()}
