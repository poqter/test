"""Read the approved design data without editing or inventing customer facts."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import json
from .coverage_master import validate_master

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'data' / 'source'

@lru_cache(maxsize=16)
def load(name: str) -> dict:
    allowed = {p.stem for p in SOURCE.glob('*.json')}
    if name not in allowed:
        raise ValueError('Unknown content file')
    return json.loads((SOURCE / (name + '.json')).read_text(encoding='utf-8'))

MAP = load('map_v1')
INTENTS = {i['intent_id']: i for i in load('intent_dictionary')['intents']}
RESPONSES = {r['response_id']: r for r in load('response_library')['responses']}
SCENARIOS = {s['scenario_id']: s for s in load('worked_scenario_rules')['scenarios']}
CATEGORIES = {c['id']: c for c in MAP['categories']}
MODES = {m['id']: m for m in load('mode_contracts')['modes']}
CRITERIA = {c['criterion_id']: c for c in load('evaluation_policy')['criteria']}
BUILD_ID = 'hwarang-academy-5.2-world-scroll'
# Supplemental implementation lines live outside immutable V1/V1.1 sources.
INTERACTION_RESPONSES = json.loads((ROOT / 'data' / 'interaction_responses.json').read_text(encoding='utf-8'))
for _response in INTERACTION_RESPONSES['responses']:
    if _response['response_id'] in RESPONSES:
        raise ValueError('Duplicate interaction response ID')
    RESPONSES[_response['response_id']] = _response
AXES = {'Q': '질문력', 'L': '경청·연결', 'N': '니즈 파악', 'E': '설명력', 'F': '상담 흐름', 'X': '다음 단계'}

# Visual labels only. No age, income, family or policy facts are created here.
SCENE_LABELS = {
    'A01-S01': ('첫 연결', '소개 고객에게 첫 연락', '연락 목적과 허용 범위를 합의합니다.'),
    'C07-S01': ('문제 발견', '보험료 부담의 실제 원인 찾기', '금액·부담 계기·유지할 조건을 나눠 확인합니다.'),
    'D08-S01': ('조건 비교', '실손 전환을 고민하는 고객', '가격만으로 판단하지 않고 비교할 범위를 정합니다.'),
    'F07-S01': ('선택 존중', '배우자와 상의하겠다는 고객', '공동 검토와 고객의 연락 의사를 존중합니다.'),
    'G10-S01': ('확인과 안내', '보험금 지급을 확답해 달라는 고객', '확정할 수 없는 내용과 확인 절차를 구분합니다.'),
    'H10-S01': ('전문 검토', '가업승계를 문의하는 대표', '경영·소유·가족 목표와 필요한 자료를 정리합니다.'),
}


def validate_content() -> None:
    validate_master()
    assert len(MAP['training_types']) == 97
    assert len(MAP['scenario_plan_slots']) == 194
    assert len(INTENTS) == 110 and len(SCENARIOS) == 6
    for s in SCENARIOS.values():
        for b in s['new_branch_rules']:
            if b['response_id'] not in RESPONSES:
                raise ValueError('Missing response: ' + b['response_id'])
            if not set(b['trigger_intents']) <= INTENTS.keys():
                raise ValueError('Unknown intent')
