"""Shared Supabase authentication for the HWARANG platform.

WORKSPACE is the primary sign-in surface. Other HWARANG apps receive a short-
lived, one-time launch ticket and never receive a password or Supabase secret.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


_ID_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_LOGGER = logging.getLogger("hwarang.auth")
_PROFILE_REFRESH_SECONDS = 60


class HwarangAuthError(RuntimeError):
    """User-safe authentication error."""


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    publishable_key: str
    secret_key: str

    @classmethod
    def from_mapping(cls, secrets: Any) -> "SupabaseConfig":
        try:
            nested = secrets.get("supabase", {}) if hasattr(secrets, "get") else {}
            url = str(secrets.get("SUPABASE_URL", nested.get("url", ""))).strip()
            publishable = str(
                secrets.get("SUPABASE_PUBLISHABLE_KEY", nested.get("publishable_key", ""))
            ).strip()
            secret = str(secrets.get("SUPABASE_SECRET_KEY", nested.get("secret_key", ""))).strip()
        except (FileNotFoundError, KeyError):
            url = publishable = secret = ""
        if not (url and publishable and secret):
            raise HwarangAuthError("HWARANG 계정 연결 정보가 설정되지 않았습니다.")
        if not url.startswith(("https://", "http://")):
            raise HwarangAuthError("Supabase URL 형식을 확인해 주세요.")
        return cls(url=url.rstrip("/"), publishable_key=publishable, secret_key=secret)


class HwarangAuthService:
    """Server-side client for Supabase Auth, profile data and app handoff."""

    def __init__(self, config: SupabaseConfig, timeout: float = 12.0):
        self.config = config
        self.timeout = timeout
        self.http = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        admin: bool = False,
        access_token: str | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        key = self.config.secret_key if admin else self.config.publishable_key
        headers = {"apikey": key, "Accept": "application/json"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = self.http.request(
                method,
                self.config.url + path,
                headers=headers,
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise HwarangAuthError("계정 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.") from exc
        if 200 <= response.status_code < 300:
            if not response.content:
                return None
            try:
                return response.json()
            except ValueError:
                return response.text
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text}
        message = ""
        if isinstance(payload, dict):
            message = str(
                payload.get("msg")
                or payload.get("message")
                or payload.get("error_description")
                or payload.get("error")
                or ""
            )
        # Keep infrastructure details in server logs, not in the user-facing UI.
        # Never log request headers/body because they can contain credentials.
        _LOGGER.warning(
            "Supabase request failed: method=%s path=%s status=%s message=%s",
            method,
            path,
            response.status_code,
            message[:500],
        )
        raise HwarangAuthError(self._friendly_error(response.status_code, message))

    @staticmethod
    def _friendly_error(status: int, message: str) -> str:
        low = message.lower()
        if "invalid login credentials" in low or "invalid_credentials" in low:
            return "아이디 또는 비밀번호를 확인해 주세요."
        if "email" in low and ("already" in low or "registered" in low or "exists" in low):
            return "이미 가입된 이메일입니다. 로그인하거나 다른 이메일을 사용해 주세요."
        if "login_id_already_exists" in low or "duplicate" in low:
            return "이미 사용 중인 아이디입니다."
        if "invalid_join_code" in low or "organization_not_allowed" in low:
            return "가입코드 또는 선택한 소속을 확인해 주세요."
        if "super_admin_required" in low:
            return "계정·권한 관리는 최고관리자만 이용할 수 있습니다."
        if "cannot_demote_or_disable_self" in low or "cannot_disable_own_workspace" in low:
            return "현재 최고관리자 계정의 로그인 권한은 해제할 수 없습니다."
        if "last_super_admin_required" in low:
            return "최소 한 명의 활성 최고관리자 계정이 필요합니다."
        if "invalid_permission_code" in low or "invalid_app_code" in low:
            return "권한 설정 정보를 확인해 주세요."
        if "password" in low and ("weak" in low or "short" in low or "length" in low):
            return "비밀번호가 보안 기준을 충족하지 않습니다. 더 길고 복잡하게 입력해 주세요."
        if status == 401:
            return "계정 인증 연결을 확인해 주세요."
        if status == 403:
            return "계정 서버 접근 권한을 확인해 주세요."
        if status == 404:
            return "계정 서버 설정을 확인해 주세요."
        if status == 429:
            return "요청이 잠시 많습니다. 잠시 후 다시 시도해 주세요."
        if status >= 500:
            return "계정 서버 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
        if any(token in low for token in ("column ", "relation ", "schema ", "permission denied", "pgrst")):
            return "계정 서버 설정을 확인해 주세요."
        return message or "요청을 처리하지 못했습니다. 입력 내용을 확인해 주세요."

    # ---------- profile / organization ----------
    def _profile_by_login_id(self, login_id: str) -> dict[str, Any] | None:
        target = login_id.strip().casefold()
        rows = self._request(
            "GET",
            "/rest/v1/profiles",
            admin=True,
            params={
                "select": (
                    "id,login_id,auth_email,display_name,role,is_active,position_code,"
                    "organization_unit_id"
                ),
                "login_id": f"ilike.{login_id.strip()}",
            },
        )
        if not isinstance(rows, list):
            return None
        return next(
            (row for row in rows if str(row.get("login_id") or "").casefold() == target),
            None,
        )

    def _profile_by_id(self, uid: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "/rest/v1/profiles",
            admin=True,
            params={
                "select": (
                    "id,login_id,auth_email,display_name,role,is_active,position_code,"
                    "organization_unit_id"
                ),
                "id": f"eq.{uid}",
                "limit": "1",
            },
        )
        return rows[0] if isinstance(rows, list) and rows else None

    @staticmethod
    def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
        """Strip server-only fields before the profile enters Streamlit session state."""
        result = dict(profile)
        result.pop("auth_email", None)
        return result

    def _enrich_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        result = self._public_profile(profile)
        position_code = profile.get("position_code")
        org_id = profile.get("organization_unit_id")
        if position_code:
            rows = self._request(
                "GET",
                "/rest/v1/positions",
                admin=True,
                params={"select": "display_name", "code": f"eq.{position_code}", "limit": "1"},
            )
            result["position_name"] = rows[0]["display_name"] if rows else None
        if org_id:
            rows = self._request(
                "GET",
                "/rest/v1/organization_units",
                admin=True,
                params={"select": "name,code,parent_id", "id": f"eq.{org_id}", "limit": "1"},
            )
            if rows:
                result["organization_name"] = rows[0]["name"]
                result["organization_code"] = rows[0]["code"]
        return result

    @staticmethod
    def workspace_permission_role(profile: dict[str, Any]) -> str:
        """Bridge HWARANG Fresh v1 accounts to the current WORKSPACE registry.

        Fresh v1 deliberately removed the legacy ``profiles.workspace_role`` column.
        System administrators receive the WORKSPACE Admin bundle; other users use
        the conservative Basic bundle until feature-level permissions are migrated.
        """
        system_role = str(profile.get("role") or "").strip().lower()
        if system_role in {"super_admin", "admin"}:
            return "Admin"
        return "Basic"

    def app_access_for_user(self, user_id: str) -> dict[str, bool]:
        rows = self._request(
            "GET",
            "/rest/v1/hwarang_app_access",
            admin=True,
            params={"select": "app_code,is_enabled", "user_id": f"eq.{user_id}"},
        )
        result = {"workspace": False, "calculator": False, "academy": False}
        if isinstance(rows, list):
            for row in rows:
                code = str(row.get("app_code") or "")
                if code in result:
                    result[code] = bool(row.get("is_enabled"))
        return result

    def effective_permissions(self, user_id: str) -> set[str]:
        rows = self._request(
            "POST",
            "/rest/v1/rpc/get_hwarang_effective_permissions",
            admin=True,
            json={"p_user_id": user_id},
        )
        if not isinstance(rows, list):
            return set()
        return {
            str(row.get("permission_code") or "")
            for row in rows
            if isinstance(row, dict) and row.get("permission_code")
        }

    def authorization_for_user(self, user_id: str) -> dict[str, Any]:
        return {
            "app_access": self.app_access_for_user(user_id),
            "feature_permissions": sorted(self.effective_permissions(user_id)),
        }

    def refresh_launch_identity(
        self, identity: dict[str, Any], target_app: str, *, max_age_seconds: int = 60
    ) -> dict[str, Any]:
        updated = dict(identity or {})
        profile = updated.get("profile") if isinstance(updated.get("profile"), dict) else {}
        user_id = str(profile.get("id") or "")
        if not user_id:
            raise HwarangAuthError("로그인 정보를 확인할 수 없습니다. WORKSPACE에서 다시 열어 주세요.")
        now = int(time.time())
        if now - int(updated.get("identity_checked_at") or 0) < max_age_seconds:
            return updated
        latest = self._profile_by_id(user_id)
        if not latest or not latest.get("is_active"):
            raise HwarangAuthError("사용할 수 없는 계정입니다. WORKSPACE에서 다시 로그인해 주세요.")
        authorization = self.authorization_for_user(user_id)
        if not authorization["app_access"].get(target_app, False):
            raise HwarangAuthError("이 계정은 해당 HWARANG 앱 이용 권한이 없습니다.")
        updated["profile"] = self._enrich_profile(latest)
        updated.update(authorization)
        updated["identity_checked_at"] = now
        return updated

    def _require_super_admin(self, actor_user_id: str) -> dict[str, Any]:
        actor = self._profile_by_id(actor_user_id)
        if not actor or not actor.get("is_active") or actor.get("role") != "super_admin":
            raise HwarangAuthError("계정·권한 관리는 최고관리자만 이용할 수 있습니다.")
        return actor

    def admin_list_users(self, actor_user_id: str) -> list[dict[str, Any]]:
        self._require_super_admin(actor_user_id)
        rows = self._request(
            "GET", "/rest/v1/profiles_admin_view", admin=True,
            params={"select": "*", "order": "display_name.asc.nullslast,login_id.asc"},
        )
        return rows if isinstance(rows, list) else []

    def admin_reference_data(self, actor_user_id: str) -> dict[str, list[dict[str, Any]]]:
        self._require_super_admin(actor_user_id)
        positions = self._request(
            "GET", "/rest/v1/positions", admin=True,
            params={"select": "code,display_name,rank_order,is_active", "order": "rank_order.desc"},
        )
        organizations = self._request(
            "GET", "/rest/v1/organization_units", admin=True,
            params={"select": "id,code,name,unit_type,parent_id,is_active,sort_order", "order": "sort_order.asc,name.asc"},
        )
        permissions = self._request(
            "GET", "/rest/v1/hwarang_permissions", admin=True,
            params={"select": "permission_code,app_code,group_label,display_name,description,sort_order,default_granted,is_active", "is_active": "eq.true", "order": "sort_order.asc"},
        )
        return {
            "positions": positions if isinstance(positions, list) else [],
            "organizations": organizations if isinstance(organizations, list) else [],
            "permissions": permissions if isinstance(permissions, list) else [],
        }

    def admin_user_snapshot(self, actor_user_id: str, target_user_id: str) -> dict[str, Any]:
        self._require_super_admin(actor_user_id)
        profile = self._profile_by_id(target_user_id)
        if not profile:
            raise HwarangAuthError("사용자 정보를 찾을 수 없습니다.")
        authz = self.authorization_for_user(target_user_id)
        return {"profile": self._enrich_profile(profile), **authz}

    def admin_apply_user_changes(
        self, *, actor_user_id: str, target_user_id: str, display_name: str, role: str,
        is_active: bool, organization_unit_id: str | None, position_code: str,
        app_access: dict[str, bool], permissions: dict[str, bool],
    ) -> dict[str, Any]:
        self._require_super_admin(actor_user_id)
        self._request(
            "POST",
            "/rest/v1/rpc/admin_apply_hwarang_user",
            admin=True,
            json={
                "p_actor_user_id": actor_user_id,
                "p_target_user_id": target_user_id,
                "p_display_name": display_name.strip(),
                "p_role": role,
                "p_is_active": bool(is_active),
                "p_organization_unit_id": organization_unit_id,
                "p_position_code": position_code,
                "p_app_access": app_access,
                "p_permissions": permissions,
            },
        )
        return self.admin_user_snapshot(actor_user_id, target_user_id)

    def admin_audit_log(self, actor_user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        self._require_super_admin(actor_user_id)
        rows = self._request(
            "GET", "/rest/v1/hwarang_admin_audit_log", admin=True,
            params={
                "select": "id,actor_user_id,target_user_id,action,details,created_at",
                "order": "created_at.desc",
                "limit": str(max(1, min(int(limit), 200))),
            },
        )
        return rows if isinstance(rows, list) else []

    def login_id_available(self, login_id: str) -> bool:
        login_id = login_id.strip()
        if not _ID_RE.fullmatch(login_id):
            return False
        return self._profile_by_login_id(login_id) is None

    def joinable_branches(self, join_code: str) -> list[dict[str, str]]:
        code = join_code.strip()
        if not code:
            return []
        rows = self._request(
            "POST",
            "/rest/v1/rpc/get_joinable_branches",
            admin=False,
            json={"p_code": code},
        )
        if not isinstance(rows, list):
            return []
        return [
            {
                "code": str(row.get("organization_code", "")),
                "name": str(row.get("organization_name", "")),
                "parent": str(row.get("parent_name", "")),
            }
            for row in rows
            if row.get("organization_code") and row.get("organization_name")
        ]

    # ---------- authentication ----------
    def _auth_user_by_id(self, uid: str) -> dict[str, Any]:
        data = self._request("GET", f"/auth/v1/admin/users/{uid}", admin=True)
        if isinstance(data, dict) and isinstance(data.get("user"), dict):
            return data["user"]
        return data if isinstance(data, dict) else {}

    def _mark_login(self, uid: str) -> None:
        """Best-effort operational metadata update; never block a valid login."""
        try:
            self._request(
                "PATCH",
                "/rest/v1/profiles",
                admin=True,
                params={"id": f"eq.{uid}"},
                json={"last_login_at": datetime.now(timezone.utc).isoformat()},
                prefer="return=minimal",
            )
        except HwarangAuthError:
            # The optimization migration may not be installed yet. Authentication
            # itself is more important than this optional management timestamp.
            _LOGGER.info("Could not update last_login_at for user %s", uid)

    def sign_in(self, login_id: str, password: str) -> dict[str, Any]:
        login_id = login_id.strip()
        if not login_id or not password:
            raise HwarangAuthError("아이디와 비밀번호를 입력해 주세요.")
        profile = self._profile_by_login_id(login_id)
        if not profile or not profile.get("is_active"):
            raise HwarangAuthError("아이디 또는 비밀번호를 확인해 주세요.")
        # Fresh HWARANG schema keeps the Auth email in a server-only profile
        # column, avoiding an extra Auth Admin request on every login.  The
        # admin lookup remains as a compatibility fallback for older rows.
        email = str(profile.get("auth_email") or "").strip()
        if not email:
            auth_user = self._auth_user_by_id(str(profile["id"]))
            email = str(auth_user.get("email") or "").strip()
        if not email:
            raise HwarangAuthError("계정 인증정보를 확인할 수 없습니다. 관리자에게 문의해 주세요.")
        token = self._request(
            "POST",
            "/auth/v1/token",
            admin=False,
            params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
        if not isinstance(token, dict) or not token.get("access_token"):
            raise HwarangAuthError("로그인 정보를 확인하지 못했습니다.")
        expires_in = int(token.get("expires_in") or 3600)
        user_id = str(profile["id"])
        authorization = self.authorization_for_user(user_id)
        if not authorization["app_access"].get("workspace", False):
            raise HwarangAuthError("이 계정은 HWARANG WORKSPACE 이용 권한이 없습니다.")
        self._mark_login(user_id)
        return {
            "access_token": token["access_token"],
            "refresh_token": token.get("refresh_token", ""),
            "expires_at": int(token.get("expires_at") or (time.time() + expires_in)),
            "profile_checked_at": int(time.time()),
            "profile": self._enrich_profile(profile),
            **authorization,
        }

    def refresh(self, auth_state: dict[str, Any]) -> dict[str, Any]:
        """Refresh the Auth token and periodically revalidate account access.

        Profile revalidation lets role, organization and active-state changes
        take effect without requiring a server restart while avoiding a DB call
        on every Streamlit rerun.
        """
        updated = dict(auth_state)
        now = int(time.time())
        refresh_token = str(updated.get("refresh_token") or "")

        if refresh_token and int(updated.get("expires_at") or 0) <= now + 120:
            token = self._request(
                "POST",
                "/auth/v1/token",
                admin=False,
                params={"grant_type": "refresh_token"},
                json={"refresh_token": refresh_token},
            )
            if not isinstance(token, dict) or not token.get("access_token"):
                raise HwarangAuthError("로그인 시간이 만료되었습니다. 다시 로그인해 주세요.")
            updated.update(
                access_token=token["access_token"],
                refresh_token=token.get("refresh_token") or refresh_token,
                expires_at=int(
                    token.get("expires_at")
                    or (time.time() + int(token.get("expires_in") or 3600))
                ),
            )

        last_check = int(updated.get("profile_checked_at") or 0)
        profile = updated.get("profile") if isinstance(updated.get("profile"), dict) else {}
        uid = str(profile.get("id") or "")
        if uid and now - last_check >= _PROFILE_REFRESH_SECONDS:
            latest = self._profile_by_id(uid)
            if not latest or not latest.get("is_active"):
                raise HwarangAuthError("사용할 수 없는 계정입니다. 관리자에게 문의해 주세요.")
            authorization = self.authorization_for_user(uid)
            if not authorization["app_access"].get("workspace", False):
                raise HwarangAuthError("이 계정은 HWARANG WORKSPACE 이용 권한이 없습니다.")
            updated["profile"] = self._enrich_profile(latest)
            updated.update(authorization)
            updated["profile_checked_at"] = now

        return updated

    def sign_up(
        self,
        *,
        login_id: str,
        password: str,
        display_name: str,
        email: str,
        join_code: str,
        organization_code: str,
    ) -> dict[str, Any]:
        login_id = login_id.strip()
        display_name = display_name.strip()
        email = email.strip().lower()
        join_code = join_code.strip()
        organization_code = organization_code.strip()
        if not _ID_RE.fullmatch(login_id):
            raise HwarangAuthError("아이디는 영문·숫자·점·밑줄·하이픈으로 3~32자까지 사용할 수 있습니다.")
        if not (1 <= len(display_name) <= 60):
            raise HwarangAuthError("이름을 입력해 주세요.")
        if not _EMAIL_RE.fullmatch(email):
            raise HwarangAuthError("이메일 주소를 확인해 주세요.")
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise HwarangAuthError("비밀번호는 8자 이상이며 영문과 숫자를 포함해 주세요.")
        if not self.login_id_available(login_id):
            raise HwarangAuthError("이미 사용 중인 아이디입니다.")
        branches = self.joinable_branches(join_code)
        if not branches:
            raise HwarangAuthError("가입코드를 확인해 주세요.")
        if organization_code not in {b["code"] for b in branches}:
            raise HwarangAuthError("가입코드로 선택할 수 없는 소속입니다.")
        self._request(
            "POST",
            "/auth/v1/admin/users",
            admin=True,
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "signup_mode": "hwarang_self_signup",
                    "login_id": login_id,
                    "display_name": display_name,
                    "organization_code": organization_code,
                    "join_code": join_code,
                },
            },
        )
        return self.sign_in(login_id, password)

    def sign_out(self, auth_state: dict[str, Any] | None) -> None:
        if not auth_state:
            return
        token = str(auth_state.get("access_token") or "")
        if not token:
            return
        try:
            self._request("POST", "/auth/v1/logout", access_token=token)
        except HwarangAuthError:
            pass

    # ---------- one-time cross-app launch ----------
    def create_launch_ticket(
        self,
        *,
        user_id: str,
        target_app: str,
        target_url: str,
        ttl_seconds: int = 60,
    ) -> str:
        """Issue a one-time launch ticket through the Fresh-v1 database RPC.

        The database owns the TTL (60 seconds). ``ttl_seconds`` is retained only
        for compatibility with existing callers and is intentionally ignored.
        """
        if not target_url.startswith(("https://", "http://")):
            raise HwarangAuthError("연결할 앱 주소가 설정되지 않았습니다.")

        target_app = target_app.strip().lower()
        if target_app not in {"academy", "calculator", "workspace"}:
            raise HwarangAuthError("지원하지 않는 연결 대상입니다.")

        data = self._request(
            "POST",
            "/rest/v1/rpc/issue_hwarang_app_launch_ticket",
            admin=True,
            json={
                "p_user_id": user_id,
                "p_target_app": target_app,
            },
        )

        raw_token = ""
        if isinstance(data, str):
            raw_token = data.strip()
        elif isinstance(data, dict):
            raw_token = str(
                data.get("issue_hwarang_app_launch_ticket")
                or data.get("ticket")
                or data.get("token")
                or ""
            ).strip()
        elif isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, str):
                raw_token = first.strip()
            elif isinstance(first, dict):
                raw_token = str(
                    first.get("issue_hwarang_app_launch_ticket")
                    or first.get("ticket")
                    or first.get("token")
                    or ""
                ).strip()

        if not raw_token:
            raise HwarangAuthError("앱 연결용 인증정보를 발급하지 못했습니다.")

        parts = urlsplit(target_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["launch"] = raw_token
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    def consume_launch_ticket(self, raw_token: str, target_app: str) -> dict[str, Any]:
        raw_token = raw_token.strip()
        target_app = target_app.strip().lower()

        if not raw_token:
            raise HwarangAuthError("연결 정보가 없습니다.")

        data = self._request(
            "POST",
            "/rest/v1/rpc/consume_hwarang_app_launch_ticket",
            admin=True,
            json={
                "p_ticket": raw_token,
                "p_target_app": target_app,
            },
        )

        user_id = ""
        if isinstance(data, str):
            user_id = data.strip()
        elif isinstance(data, dict):
            user_id = str(
                data.get("consume_hwarang_app_launch_ticket")
                or data.get("user_id")
                or ""
            ).strip()
        elif isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, str):
                user_id = first.strip()
            elif isinstance(first, dict):
                user_id = str(
                    first.get("consume_hwarang_app_launch_ticket")
                    or first.get("user_id")
                    or ""
                ).strip()

        if not user_id:
            raise HwarangAuthError(
                "연결 시간이 만료되었거나 이미 사용된 접근입니다. WORKSPACE에서 다시 열어 주세요."
            )

        profile = self._profile_by_id(user_id)
        if not profile or not profile.get("is_active"):
            raise HwarangAuthError("사용할 수 없는 계정입니다.")
        authorization = self.authorization_for_user(user_id)
        if not authorization["app_access"].get(target_app, False):
            raise HwarangAuthError("이 계정은 해당 HWARANG 앱 이용 권한이 없습니다.")

        return {
            "profile": self._enrich_profile(profile),
            "launch_authenticated": True,
            "identity_checked_at": int(time.time()),
            **authorization,
        }

