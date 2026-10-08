"""Private, versioned checkpoints for the bounded rule-training engine."""
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import json
from uuid import UUID

from .content import SCENARIOS, MODES
from .dialogue_context import DialogueMemory
from .dialogue_v5 import DialogueStateV5, PendingQuestionV5
from .engine import Session, Turn, Draft
from .language import Hit, Interpretation
from .scenario_v2 import SESSION_LENGTHS
from .service import AppState, present

SCHEMA_VERSION = 1
MAX_CHECKPOINT_BYTES = 2_000_000
_TYPES = {c.__name__: c for c in (
    Session, Turn, Draft, Hit, Interpretation, DialogueMemory,
    DialogueStateV5, PendingQuestionV5,
)}


def _encode(value):
    if is_dataclass(value):
        if type(value).__name__ not in _TYPES:
            raise ValueError('저장할 수 없는 상담 상태입니다.')
        return {'kind': 'record', 'type': type(value).__name__,
                'fields': {f.name: _encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, dict):
        return {'kind': 'map', 'items': [[str(k), _encode(v)] for k, v in value.items()]}
    if isinstance(value, (list, tuple, set)):
        kind = 'set' if isinstance(value, set) else 'tuple' if isinstance(value, tuple) else 'list'
        values = sorted(value) if isinstance(value, set) else value
        return {'kind': kind, 'items': [_encode(v) for v in values]}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError('저장할 수 없는 상담 값입니다.')


def _decode(value, depth=0):
    if depth > 48:
        raise ValueError('상담 기록 구조를 확인해 주세요.')
    if not isinstance(value, dict):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise ValueError('상담 기록 형식을 확인해 주세요.')
    kind = value.get('kind')
    if kind == 'record':
        cls = _TYPES.get(value.get('type'))
        data = value.get('fields')
        if cls is None or not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValueError('지원하지 않는 상담 기록 버전입니다.')
        return cls(**{k: _decode(v, depth + 1) for k, v in data.items()})
    items = value.get('items')
    if not isinstance(items, list):
        raise ValueError('상담 기록 형식을 확인해 주세요.')
    if kind == 'map':
        return {k: _decode(v, depth + 1) for k, v in items if isinstance(k, str)}
    if kind in ('list', 'tuple', 'set'):
        values = [_decode(v, depth + 1) for v in items]
        return set(values) if kind == 'set' else tuple(values) if kind == 'tuple' else values
    raise ValueError('지원하지 않는 상담 기록 형식입니다.')


def checkpoint(session: Session, user_id: str) -> dict:
    owner = str(UUID(user_id))
    if session.user_id is not None and str(UUID(session.user_id)) != owner:
        raise ValueError('본인의 상담 기록만 저장할 수 있습니다.')
    session.user_id = owner
    wire = {'schema': SCHEMA_VERSION, 'session': _encode(session)}
    if len(json.dumps(wire, ensure_ascii=False).encode()) > MAX_CHECKPOINT_BYTES:
        raise ValueError('상담 기록 크기를 확인해 주세요. 복기 파일을 먼저 저장해 주세요.')
    view = present(AppState(session=session, independent=True))
    return {
        'id': str(UUID(session.session_id)), 'scenario_id': session.scenario_id,
        'mode': session.mode, 'session_length': session.session_length,
        'stage': view['session']['stage'], 'ended': session.ended,
        'end_reason': session.end_reason, 'turn_count': len(session.turns),
        'engine_version': view['engine_version'], 'wire': wire,
        'transcript': view['session']['messages'], 'report': view.get('report', {}),
    }


def restore(wire: dict, user_id: str) -> Session:
    if not isinstance(wire, dict) or wire.get('schema') != SCHEMA_VERSION:
        raise ValueError('저장된 상담의 버전을 확인해 주세요.')
    if len(json.dumps(wire, ensure_ascii=False).encode()) > MAX_CHECKPOINT_BYTES:
        raise ValueError('상담 기록 크기를 확인해 주세요.')
    try:
        session = _decode(wire['session'])
        if not isinstance(session, Session) or session.user_id != str(UUID(user_id)):
            raise ValueError('본인의 상담 기록만 이어볼 수 있습니다.')
        UUID(session.session_id)
        if session.scenario_id not in SCENARIOS or session.mode not in MODES or session.session_length not in SESSION_LENGTHS:
            raise ValueError('저장된 훈련 설정을 확인해 주세요.')
        if not isinstance(session.turns, list) or len(session.turns) > 40:
            raise ValueError('상담 회차를 확인해 주세요.')
        if not isinstance(session.v5_state, DialogueStateV5) or not isinstance(session.dialogue_memory, DialogueMemory):
            raise ValueError('상담 상태를 확인해 주세요.')
        if any(not isinstance(t, Turn) or not isinstance(t.text, str) or len(t.text) > 2400 for t in session.turns):
            raise ValueError('상담 발화를 확인해 주세요.')
        if session.draft is not None and not isinstance(session.draft, Draft):
            raise ValueError('상담 초안을 확인해 주세요.')
        return session
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('저장된 상담 기록을 읽지 못했습니다.') from exc


class TrainingHistory:
    """Server-side owner-scoped access; no credentials/state enter the UI model."""
    def __init__(self, auth, user_id):
        self.auth = auth
        self.user_id = str(UUID(user_id))

    def rows(self):
        result = self.auth._request('GET', '/rest/v1/academy_sessions', admin=True, params={
            'select': 'id,user_id,scenario_id,mode,status,last_turn_no,updated_at,metadata',
            'user_id': 'eq.' + self.user_id, 'metadata->>training_engine': 'eq.rules',
            'order': 'updated_at.desc,id.desc', 'limit': '20',
        })
        return result if isinstance(result, list) else []

    def summary(self):
        return self.auth._request('POST', '/rest/v1/rpc/get_hwarang_rule_learning_summary',
                                  admin=True, json={'p_user_id': self.user_id}) or {}

    def load(self, session_id):
        session_id = str(UUID(session_id))
        rows = self.auth._request('GET', '/rest/v1/academy_sessions', admin=True, params={
            'select': 'id,user_id,session_state,metadata', 'id': 'eq.' + session_id,
            'user_id': 'eq.' + self.user_id, 'metadata->>training_engine': 'eq.rules', 'limit': '1',
        })
        if not rows or rows[0].get('user_id') != self.user_id:
            raise ValueError('본인의 상담 기록을 찾지 못했습니다.')
        row = rows[0]
        session = restore(row['session_state'], self.user_id)
        if str(UUID(session.session_id)) != session_id:
            raise ValueError('상담 기록의 회차 정보가 일치하지 않습니다.')
        return session, int((row.get('metadata') or {}).get('history_version') or 0)

    def save(self, session, version):
        return self.auth._request('POST', '/rest/v1/rpc/save_hwarang_rule_training', admin=True, json={
            'p_user_id': self.user_id, 'p_record': checkpoint(session, self.user_id),
            'p_expected_version': version,
        })


def history_header(session: Session, version: int) -> dict:
    return {'id': str(UUID(session.session_id)), 'scenario_id': session.scenario_id,
            'mode': session.mode, 'status': 'completed' if session.ended else 'in_progress',
            'last_turn_no': len(session.turns), 'updated_at': datetime.now(timezone.utc).isoformat(),
            'metadata': {'history_version': version, 'training_engine': 'rules'}}


def public_history(state: dict) -> dict:
    return {'available': bool(state.get('available')), 'summary': state.get('summary') or {},
            'error': state.get('error') or '', 'saved_at': state.get('saved_at') or '',
            'records': [{k: row.get(k) for k in ('id', 'scenario_id', 'mode', 'status', 'last_turn_no', 'updated_at')}
                        for row in state.get('rows', [])]}


def initialize_history(app: AppState, client: TrainingHistory) -> dict:
    state = {'available': False, 'rows': [], 'summary': {}, 'error': '',
             'session_id': '', 'version': 0, 'saved_at': ''}
    try:
        state['rows'] = client.rows()
        state['summary'] = client.summary()
        state['available'] = True
        if state['rows'] and app.session is None:
            row = state['rows'][0]
            session, version = client.load(row['id'])
            app.session = session
            app.selection, app.mode, app.session_length = session.scenario_id, session.mode, session.session_length
            state.update(session_id=session.session_id, version=version)
    except (RuntimeError, ValueError, TypeError, KeyError):
        state['error'] = '학습 기록을 연결하지 못했습니다. 현재 상담은 이 접속에서 유지됩니다. 종료 후 복기 파일을 저장해 주세요.'
    return state


def save_history(app: AppState, client: TrainingHistory, state: dict) -> bool:
    if not app.session:
        return False
    session = app.session
    version = state.get('version', 0) if state.get('session_id') == session.session_id else 0
    try:
        result = client.save(session, version)
        new_version = int(result['version'])
        state.update(available=True, error='', session_id=session.session_id,
                     version=new_version, summary=result.get('summary') or {},
                     saved_at=datetime.now(timezone.utc).isoformat())
        head = history_header(session, new_version)
        state['rows'] = [head] + [r for r in state.get('rows', []) if r.get('id') != head['id']]
        state['rows'] = state['rows'][:20]
        return True
    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
        state['error'] = ('다른 접속에서' in str(exc) and str(exc)) or '학습 기록 저장을 완료하지 못했습니다. 현재 대화는 유지됩니다. 기록 연결을 다시 확인하거나 복기 파일을 저장해 주세요.'
        return False
