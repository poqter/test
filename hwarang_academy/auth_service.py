"""Supabase-backed authentication for HWARANG ACADEMY.

The browser never receives the Supabase secret key.  All admin operations are
performed by the Streamlit server.  End users sign in with the Academy
``login_id`` while Supabase Auth continues to use email/password internally.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any

import requests


_ID_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AcademyAuthError(RuntimeError):
    """User-safe authentication error."""


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    publishable_key: str
    secret_key: str

    @classmethod
    def from_mapping(cls, secrets: Any) -> "SupabaseConfig":
        """Read flat Streamlit secrets, with a nested fallback for portability."""
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
            raise AcademyAuthError("Supabase 연결 정보가 설정되지 않았습니다.")
        if not url.startswith(("https://", "http://")):
            raise AcademyAuthError("Supabase URL 형식을 확인해 주세요.")
        return cls(url=url.rstrip("/"), publishable_key=publishable, secret_key=secret)


class AcademyAuthService:
    """Thin HTTP client around Supabase Auth + Data API.

    ``sb_secret_*`` keys are sent only through the ``apikey`` header, matching
    Supabase's current opaque-key guidance. User access tokens are sent as
    Authorization bearer JWTs alongside the publishable key.
    """

    def __init__(self, config: SupabaseConfig, timeout: float = 12.0):
        self.config = config
        self.timeout = timeout
        self.http = requests.Session()

    # ---------- low-level helpers ----------
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
            raise AcademyAuthError("인증 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.") from exc

        if response.ok:
            if response.status_code == 204 or not response.content:
                return None
            try:
                return response.json()
            except ValueError:
                return response.text

        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text}
        message = str(
            payload.get("msg")
            or payload.get("message")
            or payload.get("error_description")
            or payload.get("error")
            or ""
        )
        raise AcademyAuthError(self._friendly_error(response.status_code, message))

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
        if "password" in low and ("weak" in low or "short" in low or "length" in low):
            return "비밀번호가 보안 기준을 충족하지 않습니다. 더 길고 복잡하게 입력해 주세요."
        if status == 429:
            return "요청이 잠시 많습니다. 잠시 후 다시 시도해 주세요."
        if status >= 500:
            return "인증 서버 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
        return message or "요청을 처리하지 못했습니다. 입력 내용을 확인해 주세요."

    # ---------- profile / organization ----------
    def _profile_by_login_id(self, login_id: str) -> dict[str, Any] | None:
        target = login_id.strip().casefold()
        rows = self._request(
            "GET",
            "/rest/v1/profiles",
            admin=True,
            params={
                "select": "id,login_id,display_name,role,is_active,position_code,organization_unit_id",
                "login_id": f"ilike.{login_id.strip()}",
            },
        )
        if not isinstance(rows, list):
            return None
        return next(
            (row for row in rows if str(row.get("login_id") or "").casefold() == target),
            None,
        )

    def _enrich_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        result = dict(profile)
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
        # GoTrue may return the user object directly or under ``user`` depending on endpoint/client.
        if isinstance(data, dict) and isinstance(data.get("user"), dict):
            return data["user"]
        return data if isinstance(data, dict) else {}

    def sign_in(self, login_id: str, password: str) -> dict[str, Any]:
        login_id = login_id.strip()
        if not login_id or not password:
            raise AcademyAuthError("아이디와 비밀번호를 입력해 주세요.")
        profile = self._profile_by_login_id(login_id)
        if not profile or not profile.get("is_active"):
            # Same message for unknown and disabled accounts to avoid account enumeration.
            raise AcademyAuthError("아이디 또는 비밀번호를 확인해 주세요.")
        auth_user = self._auth_user_by_id(str(profile["id"]))
        email = str(auth_user.get("email") or "").strip()
        if not email:
            raise AcademyAuthError("계정 인증정보를 확인할 수 없습니다. 관리자에게 문의해 주세요.")

        token = self._request(
            "POST",
            "/auth/v1/token",
            admin=False,
            params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
        if not isinstance(token, dict) or not token.get("access_token"):
            raise AcademyAuthError("로그인 정보를 확인하지 못했습니다.")
        expires_in = int(token.get("expires_in") or 3600)
        return {
            "access_token": token["access_token"],
            "refresh_token": token.get("refresh_token", ""),
            "expires_at": int(token.get("expires_at") or (time.time() + expires_in)),
            "profile": self._enrich_profile(profile),
        }

    def refresh(self, auth_state: dict[str, Any]) -> dict[str, Any]:
        refresh_token = str(auth_state.get("refresh_token") or "")
        if not refresh_token:
            return auth_state
        if int(auth_state.get("expires_at") or 0) > int(time.time()) + 120:
            return auth_state
        token = self._request(
            "POST",
            "/auth/v1/token",
            admin=False,
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
        )
        if not isinstance(token, dict) or not token.get("access_token"):
            raise AcademyAuthError("로그인 시간이 만료되었습니다. 다시 로그인해 주세요.")
        updated = dict(auth_state)
        updated.update(
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token") or refresh_token,
            expires_at=int(token.get("expires_at") or (time.time() + int(token.get("expires_in") or 3600))),
        )
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
            raise AcademyAuthError("아이디는 영문·숫자·점·밑줄·하이픈으로 3~32자까지 사용할 수 있습니다.")
        if not (1 <= len(display_name) <= 60):
            raise AcademyAuthError("이름을 입력해 주세요.")
        if not _EMAIL_RE.fullmatch(email):
            raise AcademyAuthError("이메일 주소를 확인해 주세요.")
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise AcademyAuthError("비밀번호는 8자 이상이며 영문과 숫자를 포함해 주세요.")
        if not self.login_id_available(login_id):
            raise AcademyAuthError("이미 사용 중인 아이디입니다.")

        branches = self.joinable_branches(join_code)
        if not branches:
            raise AcademyAuthError("가입코드를 확인해 주세요.")
        if organization_code not in {b["code"] for b in branches}:
            raise AcademyAuthError("가입코드로 선택할 수 없는 소속입니다.")

        # The Streamlit server owns the secret key, so it can create and auto-confirm
        # an internal Academy user without exposing admin credentials to the browser.
        self._request(
            "POST",
            "/auth/v1/admin/users",
            admin=True,
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
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
        except AcademyAuthError:
            # Local logout must still succeed if the remote session is already expired.
            pass
