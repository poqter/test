"""URL routing only: existing login, device sessions and permissions stay in app.py."""
import streamlit as st


def workspace_route():
    pass


def calendar_route():
    pass


def select_entry():
    calendar=st.Page(calendar_route,title="화랑 캘린더",url_path="calendar")
    route=st.navigation([st.Page(workspace_route,title="화랑 WORKSPACE",default=True),calendar],position="hidden")
    route.run()
    if route.url_path=="calendar":
        if st.query_params.get("view")!="mobile-calendar":st.query_params["view"]="mobile-calendar"
    elif st.query_params.get("view")=="mobile-calendar":
        st.switch_page(calendar)
    return route.url_path
