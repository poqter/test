"""Account-scoped analyzer preferences stored in Supabase Auth user metadata."""
import math
import streamlit as st
from modules.consultation.analyzer_model import DEFAULT_COVERAGES
from modules.consultation.analyzer_limits import DEFAULT_LIMITS
from modules.shared.hwarang_auth import HwarangAuthService, SupabaseConfig

FIELD = "hwarang_coverage_preferences"

def request(method, **kwargs):
    service = HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))
    return service._request(method, "/auth/v1/user",
                            access_token=st.session_state["hwarang_auth"]["access_token"], **kwargs)

def preferences():
    auth = st.session_state.get("hwarang_auth") or {}
    owner = str(auth.get("user_id") or (auth.get("profile") or {}).get("id") or "")
    base = {"selected": list(DEFAULT_COVERAGES), "limits": dict(DEFAULT_LIMITS)}
    if not owner or not auth.get("access_token"):
        return base, ""
    key = "coverage_preferences_" + owner
    if key not in st.session_state:
        try:
            user = request("GET")
            source = (user.get("user_metadata") or {}).get(FIELD) or {}
            if isinstance(source.get("selected"), list):
                base["selected"] = [x for x in source["selected"] if isinstance(x,str)]
            for label, v in (source.get("limits") or {}).items():
                if v is None or isinstance(v,(int,float)) and math.isfinite(v) and v > 0:
                    base["limits"][label] = v
            st.session_state[key] = base
        except Exception:
            st.warning("저장된 기준을 불러오지 못해 기본 기준을 표시합니다.")
            return base, ""
    return st.session_state[key], owner

def save_preferences(owner, selected, limits):
    payload = {"selected": selected, "limits": limits}
    try:
        request("PUT", json={"data": {FIELD: payload}})
    except Exception:
        st.error("기준 저장에 실패했습니다. 다시 시도해 주세요.")
        return
    st.session_state["coverage_preferences_" + owner] = payload
    st.success("내 자동정리 기준을 저장했습니다.")
