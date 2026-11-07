"""Recipient group controls and Excel download for briefing sharing."""
from __future__ import annotations

import streamlit as st
from modules.shared.hwarang_auth import HwarangAuthError
from .kakao_groups import KakaoGroups, load_template
from .kakao_recipients import Recipient, assess_recipients
from .kakao_workbook import make_workbook
from .repository import BriefingRepositoryError


def render_kakao(repo, uid, day, url, sender):
    st.divider()
    st.subheader('카카오톡 발송 엑셀')
    st.caption('명단을 한 번 저장해 두면 공유할 때마다 같은 그룹을 선택할 수 있습니다.')
    try:
        groups_api = KakaoGroups(st.secrets, st.session_state.get('hwarang_auth'))
        groups = groups_api.list()
    except (HwarangAuthError, ValueError):
        st.warning('발송 명단을 불러오지 못했습니다. 다시 로그인하거나 잠시 후 이용해 주세요.')
        return
    with st.expander('발송 대상 명단 관리', expanded=not groups):
        with st.form('kakao_new_group_' + uid, clear_on_submit=True):
            new_name = st.text_input('새 그룹 이름', max_chars=80, placeholder='예: VIP 고객')
            create = st.form_submit_button('그룹 만들기')
            if create:
                try:
                    name = new_name.strip()
                    if not name:
                        raise ValueError('그룹 이름을 입력해 주세요.')
                    groups_api.create(name)
                    st.rerun()
                except (HwarangAuthError, ValueError) as exc:
                    st.error(str(exc))
        if groups:
            st.caption('카카오톡 친구 목록에 저장된 검색 이름을 한 줄에 한 명씩 입력하세요. 동명이인은 친구 이름을 다르게 저장해 주세요.')
    if not groups:
        st.info('먼저 발송 대상 그룹을 만들어 주세요.')
        return
    group_map = {g['id']: g for g in groups}
    group_id = st.selectbox('발송 대상 그룹', list(group_map),
        format_func=lambda value: group_map[value]['name'], key='kakao_selected_' + uid)
    group = group_map[group_id]
    existing = group.get('recipients') or []
    names = [str(x.get('search_name') or '') for x in existing if isinstance(x, dict) and x.get('enabled', True)]
    with st.expander('선택한 그룹의 친구 이름 수정'):
        with st.form('kakao_edit_' + uid + '_' + group_id + '_' + str(group['version'])):
            edited = st.text_area('카카오톡 친구 검색 이름', value='\n'.join(names), height=200,
                help='한 줄에 한 명씩 입력하세요. 최대 200명입니다.')
            save = st.form_submit_button('명단 저장')
            if save:
                try:
                    rows = [x.strip() for x in edited.splitlines() if x.strip()]
                    if len(rows) > 200:
                        raise ValueError('한 그룹에는 최대 200명까지 등록할 수 있습니다.')
                    items = [Recipient(name, name) for name in rows]
                    errors = [a for a in assess_recipients(items) if a.state == 'needs_review']
                    if errors:
                        raise ValueError('같은 검색 이름이 있거나 사용할 수 없는 이름이 있습니다. 명단을 확인해 주세요.')
                    groups_api.save(group, [{'display_name': r.display_name, 'search_name': r.search_name, 'enabled': True} for r in items])
                    st.rerun()
                except (HwarangAuthError, ValueError) as exc:
                    st.error(str(exc))
        confirm = st.checkbox('이 그룹을 삭제합니다', key='kakao_confirm_' + uid + '_' + group_id)
        if st.button('선택한 그룹 삭제', disabled=not confirm, key='kakao_delete_' + uid + '_' + group_id):
            try:
                groups_api.delete(group)
                st.session_state.pop('kakao_selected_' + uid, None)
                st.rerun()
            except (HwarangAuthError, ValueError) as exc:
                st.error(str(exc))
    recipients = [Recipient(str(x.get('display_name') or ''), str(x.get('search_name') or ''), bool(x.get('enabled', True)))
                  for x in existing if isinstance(x, dict)]
    assessments = assess_recipients(recipients)
    errors = [a for a in assessments if a.state == 'needs_review']
    count = sum(a.state == 'unverified' for a in assessments)
    st.caption(f'저장된 발송 대상 {count}명 · 엑셀은 매번 지정된 전용 폴더에 저장해 주세요.')
    if errors:
        st.warning('같은 검색 이름 또는 잘못된 이름이 있습니다. 명단을 수정해 주세요.')
    if not url:
        st.info('위에서 통합 공유 링크를 만들면 엑셀을 내려받을 수 있습니다.')
        return
    default_message = f"{sender.get('name', '')} {sender.get('position', '')}이 전하는 오늘의 브리핑\n{day}"
    message = st.text_area('발송 문구', value=default_message.strip(), max_chars=3000,
        key='kakao_message_' + uid + '_' + day)
    if not count or errors or not message.strip():
        st.button('발송 엑셀 내려받기', disabled=True, key='kakao_disabled_' + uid)
        return
    try:
        workbook = make_workbook(load_template(repo), day=day, group_name=group['name'],
            message=message, url=url, recipients=recipients)
        st.download_button('발송 엑셀 내려받기', workbook,
            file_name=f'briefing_kakao_{day}.xlsm',
            mime='application/vnd.ms-excel.sheet.macroEnabled.12',
            key='kakao_download_' + uid, type='primary')
        st.caption('전용 폴더에 저장한 파일을 Windows용 Excel에서 열어 발송 버튼을 누르세요.')
    except (BriefingRepositoryError, ValueError, OSError):
        st.warning('발송 엑셀을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.')
