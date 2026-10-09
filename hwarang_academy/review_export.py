"""Server-generated review HTML downloaded through Streamlit's native control."""
from html import escape


def review_html(payload: dict) -> str:
    s, r = payload.get('session') or {}, payload.get('report') or {}
    if not s.get('ended'):
        raise ValueError('상담 종료 후 복기 파일을 저장할 수 있습니다.')
    def e(value):
        return escape(str(value if value is not None else ''))
    parts = [f'<h1>화랑 상담 훈련 복기</h1><p>{e(s.get("title"))} · {e(s.get("mode"))} · {e(s.get("session_length"))}</p>',
             '<p>규칙 기반 잠정 평가 · 공식 인증 아님</p>',
             f'<p>역량 평가: {"판정 유보 · 아래 항목별 사유 확인" if r.get("unresolved") or r.get("lower") != r.get("upper") else e(r.get("lower")) + "점 · 잠정"}</p>']
    mission = r.get('mission_outcome') or {}
    parts.append(f'<h2>미션 결과</h2><p>{"최종 목표 달성" if mission.get("final_complete") else "미완료"}</p><p>{e(mission.get("followup_schedule"))}</p>')
    for row in r.get('rows', []):
        parts.append(f'<section><h3>{e(row.get("name"))}</h3><p>{e(row.get("gate"))}</p><p>{e(row.get("reason"))}</p><p>{e(row.get("next_action"))}</p></section>')
    parts.append('<h2>대화 복기</h2>')
    for turn in payload.get('review', []):
        parts.append(f'<section><h3>TURN {e(turn.get("turn"))}</h3><p>상담사: {e(turn.get("text"))}</p><blockquote>고객: {e(turn.get("customer"))}</blockquote></section>')
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>화랑 상담 훈련 복기</title><style>body{font-family:system-ui,"Malgun Gothic",sans-serif;'
            'max-width:900px;margin:32px auto;padding:20px;color:#183750;line-height:1.8}'
            'section{border-bottom:1px solid #d6e0e9;padding:12px 0}blockquote{background:#f5f8fc;padding:12px}'
            '@media print{body{margin:0;max-width:none}section{break-inside:avoid}}</style></head><body>'
            + ''.join(parts) + '</body></html>')
