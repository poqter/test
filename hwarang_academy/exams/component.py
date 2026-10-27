"""Stable browser-owned CBT surface; credentials and grading remain server-side."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_surface = components.declare_component('hwarang_cbt_v2', path=str(Path(__file__).parent / 'frontend'))


def process(repo, event, attempt):
    """Optimistic revision and lost-response recovery, never silently overwrite."""
    action = event.get('action')
    if action not in ('save', 'submit', 'poll', 'check'):
        raise ValueError('INVALID_ACTION')
    current = repo.call('get', id=attempt['id'])
    if action == 'poll' or current['status'] == 'submitted':
        return current
    payload = event.get('payload') or {}
    revision = payload.get('revision')
    if action == 'save':
        fields = {k: payload[k] for k in ('answers', 'flags', 'cursor')}
        # A previous write may have committed although its response was lost.
        if all(current[k] == v for k, v in fields.items()):
            return current
        if current['revision'] != revision:
            raise ValueError('CONFLICT')
        return repo.call('save', id=attempt['id'], revision=revision, **fields)
    if current['revision'] != revision:
        if action == 'check' and payload.get('number') in current.get('review_checked', []):
            return current
        raise ValueError('CONFLICT')
    return repo.call(action, id=attempt['id'], revision=revision,
                     **({'number': payload['number']} if action == 'check' else {}))


@st.fragment
def active(repo, initial):
    key = '_academy_exam_wire_' + initial['id']
    state = st.session_state.setdefault(key, {'attempt': initial, 'ack': None, 'error': ''})
    if not state['error'] and str(initial.get('server_now','')) > str(state['attempt'].get('server_now','')):
        state['attempt'] = initial
    event = _surface(attempt=state['attempt'], ack=state['ack'], error=state['error'],
                     key='cbt_surface_' + initial['id'], default=None)
    if not event or event.get('id') == state['ack']:
        return
    state['ack'] = event.get('id')
    try:
        state['attempt'] = process(repo, event, state['attempt'])
        state['error'] = ''
        if state['attempt']['status'] == 'submitted':
            st.session_state.pop(key, None)
            st.rerun()
    except Exception as exc:
        state['error'] = ('다른 화면에서 답안이 변경되었습니다. 저장된 답안으로 다시 불러오세요.'
                          if str(exc) == 'CONFLICT' else '저장을 확인하지 못했습니다. 선택한 답은 화면에 보관 중입니다.')
    st.rerun(scope='fragment')
