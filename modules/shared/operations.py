"""Read-only operational evidence and append-only administrator review records.

No workflow dispatch, code changes, settings writes or operational-data mutations.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import requests

REPO = 'poqter/test'
AUDIT_ACTION = 'operations_review_v1'
SCOPES = ('원인 분석만', '수정·검증까지', '수정·검증·배포까지')
CHECKS = ('발생 위치와 근거 확인', '사용자 영향과 미확인 범위 확인', '요청 범위 확인')
KST = ZoneInfo('Asia/Seoul')
ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = ('modules/shared/operations.py', 'modules/shared/operations_ui.py', 'modules/shared/admin_center_ui.py')


def release_id():
    return hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in SOURCE_FILES)).hexdigest()[:16]


def now():
    return datetime.now(timezone.utc).isoformat()


def display_time(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(KST).strftime('%Y-%m-%d %H:%M KST')
    except (ValueError, TypeError):
        return '미확인'


def redact(value):
    text = str(value or '')
    text = re.sub(r'(?i)(authorization\s*[:=]\s*|bearer\s+)\S+', r'\1[가림]', text)
    text = re.sub(r'(?i)((?:password|passwd|secret|token|api[_-]?key|비밀번호|고객명|성명|이름|주소)\s*[\"\']?\s*[:=]\s*)[^\n,;]+', r'\1[가림]', text)
    text = re.sub(r'(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)', '[가림]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[이메일 가림]', text)
    text = re.sub(r'(?<!\d)(?:01[016789][- .]?\d{3,4}[- .]?\d{4}|\d{6}[- ]?[1-4]\d{6})(?!\d)', '[개인정보 가림]', text)
    text = re.sub(r'https?://[^\s<>]+', lambda m: m[0].split('?')[0].split('#')[0], text)
    return text


def github_get(path, params=None):
    # Fixed public repository, GET only, bounded timeouts; no credentials needed.
    response = requests.get(f'https://api.github.com/repos/{REPO}/{path}', params=params,
                            headers={'Accept': 'application/vnd.github+json'}, timeout=(3, 12))
    if response.status_code != 200:
        raise RuntimeError(f'GitHub 조회 실패 (HTTP {response.status_code})')
    return response.json()


def github_overview():
    runs = github_get('actions/runs', {'branch': 'main', 'per_page': 40}).get('workflow_runs', [])
    # Workflow identity is stable even if its display name changes.
    latest = {}
    for run in runs:
        latest.setdefault(str(run['workflow_id']), run)
    commits = github_get('commits', {'sha': 'main', 'per_page': 6})
    return {'runs': list(latest.values()), 'history': runs, 'commits': commits, 'collected_at': now()}


def state(status, conclusion):
    if status != 'completed':
        return '진행 중' if status in ('queued','in_progress','waiting','pending','requested') else '확인 불가'
    return {'success':'통과', 'failure':'실패', 'timed_out':'실패', 'cancelled':'취소', 'skipped':'미실행', 'neutral':'미확인', 'action_required':'확인 필요'}.get(conclusion, '미확인')


def area(name):
    name = name.lower()
    if any(w in name for w in ('pip install', 'npm ci', 'setup-python', 'setup-node', 'install from clean')):
        return '검사 환경 준비'
    for words, label in [ (('mobile','webkit','device'), '모바일'), (('check_install','home screen','홈 화면','pwa'), '홈 화면 설치'),
                         (('academy','cbt','learning'), 'ACADEMY'), (('briefing',), '브리핑'),
                         (('calendar','activity','daily','support'), '일정·영업활동'),
                         (('deploy','release'), '배포'), (('foundation','shell','login'), '공통 기반') ]:
        if any(w in name for w in words): return label
    return '공통 검사'


def run_issue(run, history=()):
    key = 'github:' + str(run['workflow_id'])
    previous = next((r for r in history if r.get('workflow_id') == run['workflow_id'] and r.get('id') != run['id'] and r.get('status') == 'completed'), None)
    result = state(run.get('status'), run.get('conclusion'))
    change = '신규 확인'
    if previous:
        old = state(previous.get('status'), previous.get('conclusion'))
        change = '해결 확인 (검사 범위)' if result == '통과' and old == '실패' else '재발 후보' if result == '실패' and old == '통과' else '계속 확인' if result != '통과' else '변화 없음'
    return dict(id=key, evidence=f"{run['id']}:{run.get('run_attempt',1)}", title=redact(run['name']), area=area(run['name']),
                result=result, impact='확인 범위 정상' if result=='통과' else '영향 미확인', classification='원인 미확정',
                fact=f"GitHub Actions 실행 결과: {result}. 개별 단계는 상세 조회에서 확인합니다.",
                cause='미확인', next='실패 단계와 검사 대상 버전을 확인하고 실제 기능 오류 여부를 구분합니다.',
                first=run.get('created_at'), last=run.get('updated_at'), sha=run.get('head_sha'),
                url=run.get('html_url'), change=change, run_id=run['id'], files=[], reproduction='실제 사용자 재현 절차 미확인',
                expected='해당 검사 단계 통과', minimum='원인 확인 후 최소 변경안 결정', checks=[])


def run_details(run_id, sha):
    jobs = github_get(f'actions/runs/{int(run_id)}/jobs', {'per_page':100})
    steps = []
    for job in jobs.get('jobs',[]):
        for step in job.get('steps',[]):
            steps.append({'영역':area(step['name']+' '+job['name']), '작업':redact(job['name']), '단계':redact(step['name']),
                          '결과':state(step.get('status'),step.get('conclusion')), '원본 결과':step.get('conclusion'), '시작':display_time(step.get('started_at'))})
    commit = github_get(f'commits/{sha}') if re.fullmatch('[a-f0-9]{40}', str(sha)) else {}
    return {'steps':steps, 'files':[f['filename'] for f in commit.get('files',[])],
            'truncated':jobs.get('total_count',0)>100, 'collected_at':now()}


def require(auth, actor):
    if not actor: raise ValueError('최고관리자 인증이 필요합니다.')
    auth._require_super_admin(actor)


def briefing_overview(auth, actor):
    require(auth, actor)
    def rows(table, select, order, limit):
        value=auth._request('GET','/rest/v1/'+table,admin=True,params={'select':select,'order':order,'limit':str(limit)})
        if not isinstance(value,list): raise ValueError('브리핑 조회 결과 확인 불가')
        return value
    return {'jobs':rows('hwarang_briefing_jobs','profile_code,briefing_date,job_status,failure_code,started_at,finished_at','created_at.desc',60),
            'publications':rows('hwarang_briefings','profile_code,briefing_date,current_published_revision_id','briefing_date.desc,created_at.desc',90),
            'runs':rows('hwarang_briefing_daily_runs','run_key,briefing_date,group_code,status,attempts,updated_at','updated_at.desc',40),
            'collected_at':now()}


def briefing_issues(data):
    out=[]
    today=datetime.now(KST).date().isoformat()
    for code,label in [('NEWS','종합'),('INSURANCE','보험'),('MARKET','경제')]:
        job=next((j for j in data['jobs'] if j['profile_code']==code),{})
        pub=next((p for p in data['publications'] if p['profile_code']==code and p.get('current_published_revision_id')), {})
        published=pub.get('briefing_date')
        failed=job.get('job_status')=='failed' and job.get('briefing_date','')>=str(published or '')
        result='실패' if failed else '통과' if published==today else '확인 필요'
        fact=f"최근 게시일: {published or '미확인'} / 최근 작업: {job.get('job_status','미확인')} / 작업일: {job.get('briefing_date','미확인')}"
        out.append(dict(id='briefing:'+code,evidence=f"{job.get('started_at','unknown')}:{job.get('job_status')}:{published}",title=label+' 브리핑',area='브리핑',result=result,
                        impact='영향 미확인' if result!='통과' else '게시 기록 확인',classification='원인 미확정',fact=fact,cause='미확인',
                        next='예정일·운영 정책과 게시 결과를 대조합니다. 최근 게시일만으로 지연을 확정하지 않습니다.',
                        first=job.get('started_at'),last=job.get('finished_at') or job.get('started_at'),sha='',url='',change='현재 기록',files=[],
                        reproduction='해당 날짜의 브리핑 조회 및 게시 상태 확인',expected='운영 정책에 맞는 게시',minimum='원인 확인 후 결정',
                        error=redact(job.get('failure_code')),checks=[]))
    return out


def studio_report_overview(auth, actor):
    require(auth, actor)
    incidents = auth._request('POST', '/rest/v1/rpc/hwarang_studio_report_incidents',
                              admin=True, json={'p_actor': actor})
    return {'collected_at': now(), 'incidents': incidents or []}


def studio_report_issues(data):
    reasons = {
        'duplicate_criterion': '평가 항목 중복',
        'criterion_set_mismatch': '평가 항목 구성 불일치',
        'invalid_evidence_turn': '근거 회차 불일치',
        'evidence_quote_mismatch': '학습자 원문과 인용 불일치',
        'missing_evidence': '평가 근거 누락',
    }
    issues = []
    for row in data['incidents']:
        session = str(row['session_id'])
        reason = reasons.get(row['reason'], '미분류')
        mode = '공식 평가' if row['purpose'] == 'EVALUATOR' else '연습 피드백'
        credit = '정산 미확인'
        charged = row.get('credits_charged')
        if charged is not None:
            if row['credit_status'] == 'failed' and charged == 0:
                credit = '예약 해제 · 0 Credit'
            elif row['credit_status'] == 'expired' and charged == 0:
                credit = '예약 만료 · 0 Credit'
            elif row['credit_status'] == 'completed':
                credit = f'{charged} Credit 차감'
        cost = '원장 기록 확인' if row.get('cost_status') == 'known' else '금액 미확인'
        issues.append({
            'id': 'studio-report:' + session, 'evidence': row['recorded_at'],
            'title': mode + ' 근거 검증 실패 · ' + session[:8],
            'area': 'ACADEMY / 상담 Studio / ' + mode,
            'result': '실패', 'impact': '사용 가능한 피드백이 생성되지 않음',
            'change': '운영 기록', 'classification': '평가 결과 검증 실패',
            'fact': f'세션 {session[:8]} · {display_time(row["recorded_at"])} · {reason} · 학습자 정산 {credit} · 공급자 비용 {cost}',
            'cause': reason, 'error': reason,
            'source': '관리자센터 운영 점검의 ACADEMY 평가 진단',
            'reproduction': '같은 실패 사유를 넣은 모의 평가 응답으로 검증한다.',
            'expected': '실패를 기록하고 예약을 해제하며, 공급자 사용 기록을 보존한다.',
            'minimum': '결과 구조와 근거 검증을 대조하여 원인을 확인한다.',
            'next': '실패 사유와 Credit 원장 상태를 대조한다.',
            'first': row['recorded_at'], 'last': row['recorded_at'],
        })
    return issues


def review_history(auth, actor, issue_id=None):
    require(auth,actor)
    params={'select':'id,actor_user_id,details,created_at','action':'eq.'+AUDIT_ACTION,'order':'id.desc','limit':'100'}
    if issue_id: params['details->>issue_id']='eq.'+issue_id
    rows=auth._request('GET','/rest/v1/hwarang_admin_audit_log',admin=True,params=params)
    if not isinstance(rows,list): raise ValueError('점검 기록 조회 실패')
    return rows


def save_review(auth,actor,issue,status,checks,note,request_id):
    require(auth,actor)
    if status not in ('미확인','확인 중','검토 완료','보완 필요'): raise ValueError('잘못된 점검 상태')
    if status=='검토 완료' and not all(checks.get(c) for c in CHECKS): raise ValueError('필수 점검 항목을 확인해 주세요.')
    # Append-only audit records preserve older evidence/reviews and concurrent reviewers.
    # A request ID permits reconciliation after an ambiguous network response.
    payload={'actor_user_id':actor,'action':AUDIT_ACTION,'details':{'issue_id':issue['id'],'evidence':issue['evidence'],
        'status':status,'checks':{c:bool(checks.get(c)) for c in CHECKS},'note':redact(note)[:2000],'request_id':request_id}}
    existing=auth._request('GET','/rest/v1/hwarang_admin_audit_log',admin=True,params={
        'action':'eq.'+AUDIT_ACTION,'details->>request_id':'eq.'+request_id,'select':'id','limit':'1'})
    if existing:return existing
    return auth._request('POST','/rest/v1/hwarang_admin_audit_log',admin=True,json=payload,prefer='return=representation')


def request_text(issues, scope=SCOPES[1], runtime='', generated=None):
    if scope not in SCOPES: raise ValueError('잘못된 요청 범위')
    blocks=[f'화랑 WORKSPACE 운영 점검 요청\n요청 범위: {scope}\n생성 시각: {display_time(generated or now())}\n운영 점검 코드 표식: {runtime or "미확인"}']
    for item in issues:
        steps=item.get('steps',[])
        failures=[f"{s['작업']} → {s['단계']}: {s['결과']}" for s in steps if s['결과']!='통과']
        blocks.append('\n'.join([f"\n[문제 {item['id']}] {item['title']}",f"근거 ID: {item['evidence']}",
            f"발생 위치: {item['area']}",f"발견 시각(해당 실행): {display_time(item.get('first'))} / 최근: {display_time(item.get('last'))}",
            f"확인 사실: {item['fact']}",f"사용자 영향: {item['impact']}",f"원인 분류: {item['classification']} / 추정 원인: {item['cause']}",
            f"재현 절차: {item.get('reproduction','미확인')}",f"기대 결과: {item.get('expected','미확인')}",
            f"검사 대상 커밋: {item.get('sha') or '미확인'} / 해당 커밋의 운영 반영: 미확인",
            f"실패·미실행 단계: {'; '.join(failures) or '상세 미확인 또는 없음'}",
            f"오류: {item.get('error') or '오류 원문 미수집 — 실행 링크에서 확인 필요'}",
            f"근거 링크: {item.get('url') or item.get('source', '관리자센터 브리핑 조회 기록')}",
            f"해당 커밋 변경 파일(원인 파일 확정 아님): {', '.join(item.get('files',[])) or '미확인'}",
            f"최소 변경안: {item.get('minimum','원인 확인 후 결정')}", f"다음 확인: {item['next']}",
            '재검증 순서: 원인 구분 → 해당 실패 검사 → 관련 기능 회귀 → 운영 확인(승인 범위 내)']))
    blocks.append('\n[작업 기준]\n최신 적용본과 기존 확정 정책을 먼저 확인해줘. 실제 기능 오류·검사 문제·실행 타이밍을 구분하고 미확인 내용을 단정하지 말아줘. 기존 로그인·세션·조직 권한과 정상 기능을 보존해줘.')
    if scope==SCOPES[0]:blocks.append('원인과 최소 수정안만 제시하고 코드·DB 수정이나 배포는 하지 말아줘.')
    else:
        blocks.append('확인된 원인에 필요한 부분만 수정하고 관련 검사를 실행해줘. 소스 검증과 실제 운영 UI 확인을 구분해서 보고해줘.')
        blocks.append('검증 후 저장소 반영·운영 배포와 결과 확인까지 진행해줘.' if scope==SCOPES[2] else '이번 요청에서는 운영 반영·배포를 진행하지 말아줘.')
        blocks.append('DB 변경이 필요하면 대상과 영향을 먼저 설명하고 별도 승인을 받아줘.')
    return redact('\n\n'.join(blocks))


def schedules(at=None):
    """Show checked-out workflow schedules; unsupported expressions stay explicit."""
    from datetime import timedelta
    at=at or datetime.now(timezone.utc)
    result=[]
    for path in sorted((ROOT/'.github/workflows').glob('*.yml')):
        source=path.read_text()
        for cron in re.findall(r"cron:\s*['\"]([^'\"]+)['\"]",source):
            fields=cron.split(); upcoming=None
            if len(fields)==5 and fields[2:]==['*','*','*']:
                try:
                    minutes=[int(x) for x in fields[0].split(',')];hours=[int(x) for x in fields[1].split(',')]
                    candidates=[(at+timedelta(days=d)).replace(hour=h,minute=m,second=0,microsecond=0) for d in (0,1) for h in hours for m in minutes]
                    upcoming=min(x for x in candidates if x>at)
                except (ValueError,OverflowError):pass
            result.append({'자동 작업':path.stem,'예약식 (UTC)':cron,'다음 예정 (KST)':display_time(upcoming.isoformat()) if upcoming else '예약식 직접 확인 필요'})
    return result


def enrich(item, detail):
    item=dict(item);item.update(steps=detail.get('steps',[]),files=detail.get('files',[]))
    failed=[s for s in item['steps'] if s['결과']=='실패']
    if failed:
        item['fact']+=' 실패 단계: '+' / '.join(s['단계'] for s in failed)
        if any(s.get('원본 결과')=='timed_out' for s in failed):
            item['classification']='타이밍 문제 (추정)';item['cause']='실행 제한시간 초과 확인. 응답 지연·교착·검사 대기 원인은 추가 확인 필요'
            item['minimum']='지연 구간과 대기 조건부터 확인하고 해당 구간만 수정'
        elif any('browser' in s['단계'].lower() or 'mobile' in s['단계'].lower() for s in failed):
            item['cause']='기능 오류·UI 검사 불일치·타이밍 문제 중 미확정'
            item['minimum']='최신 UI와 실패 선택자·대기 조건을 대조한 후 기능 또는 검사 코드만 최소 수정'
    return item
