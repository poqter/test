"""Saved-content readiness labels shared by the reading and manager screens."""
from .runtime import body_quality_ready


def publication_blockers(bundle):
    revision = bundle.get('revision') or {}
    snapshot = bundle.get('snapshot') or {}
    qa = snapshot.get('qa_payload') or {}
    content = snapshot.get('content_payload') or {}
    reasons = []
    if revision.get('publication_status') == 'hidden':
        reasons.append('공개가 중단된 판본입니다.')
    if revision.get('validation_status') != 'ok':
        reasons.append('본문 확인이 필요한 항목이 남아 있습니다.')
    if revision.get('coverage_status') != 'healthy' or not body_quality_ready(content):
        reasons.append('게시 기준을 충족할 기사·출처가 충분하지 않습니다.')
    if not qa.get('internal_body_ready'):
        reasons.append('직원용 본문의 게시 조건이 충족되지 않았습니다.')
    return reasons


def sharing_blockers(bundle, policy, profile, *, reader_configured=True):
    revision = bundle.get('revision') or {}
    snapshot = bundle.get('snapshot') or {}
    qa = snapshot.get('qa_payload') or {}
    reasons = []
    if not policy.get('external_sharing_approved'):
        reasons.append('고객 공유 사용 설정을 켜 주세요.')
    if revision.get('publication_status') != 'published':
        reasons.append('이 브리핑을 직원 화면에 먼저 게시해 주세요.')
    if not qa.get('public_body_ready'):
        reasons.append('고객에게 제공할 본문이 아직 준비되지 않았습니다.')
    if not revision.get('external_share_allowed') or not revision.get('external_qa_passed'):
        reasons.append('이 판본이 고객 공유 품질 기준을 충족하지 못했습니다.')
    if not str(profile.get('position_name') or '').strip():
        reasons.append('계정의 실제 직책을 등록해 주세요.')
    if not reader_configured:
        reasons.append('고객 읽기 페이지 주소를 연결해 주세요.')
    return reasons


def selection_summary(snapshot):
    content = snapshot.get('content_payload') or {}
    qa = snapshot.get('qa_payload') or {}
    counts = qa.get('selection_diagnostics') or {}
    result = {'기사': len(content.get('issues') or [])}
    for key, label in [('routed_events', '수집 사건'), ('analyzed_events', '분석 완료'),
                       ('eligible_events', '선정 기준 통과')]:
        if counts.get(key) is not None:
            result[label] = int(counts[key])
    return result
