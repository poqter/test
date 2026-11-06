from streamlit.testing.v1 import AppTest


def test_device_sync_survives_lost_module_lookup_after_registration():
    at=AppTest.from_string('''
import streamlit as st
from modules.activity import device
from streamlit.components.v1 import component_registry
from unittest.mock import patch
# Reproduce the framework failure raised when an older callback's module
# cannot be resolved after hot reload. Synchronization must not re-register.
with patch.object(component_registry,"_get_module_name",side_effect=RuntimeError("module is None. This should never happen.")):
    device.synchronize(None,lambda *args:None)
st.text_input("WORKSPACE 아이디")
''',default_timeout=20).run()
    assert not at.exception
    assert at.text_input[0].label=='WORKSPACE 아이디'
    assert len(at.get('component_instance'))==1


def test_device_store_and_clear_handshake_still_work():
    at=AppTest.from_string('''
import streamlit as st
from modules.activity import device
from unittest.mock import patch
st.session_state["device_action"]="store"
st.session_state["device_handle"]="a"*54
with patch.object(device,"_bridge",return_value={"action":"store","token":"a"*54}) as bridge:
    device.synchronize(None,lambda *args:None)
    assert bridge.call_args.kwargs["token"]=="a"*54
assert "device_action" not in st.session_state
st.session_state["device_action"]="clear"
with patch.object(device,"_bridge",return_value={"action":"clear","token":""}) as bridge:
    device.synchronize(None,lambda *args:None)
    assert bridge.call_args.kwargs["token"]==""
assert "device_action" not in st.session_state
st.success("동기화 완료")
''',default_timeout=20).run()
    assert not at.exception
    assert at.success[0].value=='동기화 완료'
