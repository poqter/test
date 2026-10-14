"""Observed usage and versioned price estimates; missing price is never zero."""
from datetime import datetime, timezone
import json
import math
import os


def estimate_cost(payload):
    try:
        prices=json.loads(os.getenv('BRIEFING_PRICE_TABLE_JSON','{}'))
        rate=prices.get(payload.get('model_name'))
        if not isinstance(rate,dict):return None
        required=('input_per_million','cached_input_per_million','output_per_million','search_per_thousand')
        values={k:float(rate[k]) for k in required}
        if any(not math.isfinite(v) or v<0 for v in values.values()):return None
        if not str(rate.get('source_url') or '').startswith('https://') or not rate.get('checked_at'):return None
        input_tokens=max(0,int(payload.get('input_tokens') or 0));cached=max(0,min(input_tokens,int(payload.get('cached_input_tokens') or 0)))
        cost=(max(0,input_tokens-cached)*values['input_per_million']+cached*values['cached_input_per_million']
              +int(payload.get('output_tokens') or 0)*values['output_per_million'])/1_000_000
        cost+=int(payload.get('search_actions') or 0)*values['search_per_thousand']/1000
        return round(cost,6)
    except (ValueError,TypeError,KeyError,OverflowError):return None


def usage_summary(rows):
    actual=sum(float(r.get('actual_cost_usd') or 0) for r in rows if r.get('actual_cost_usd') is not None)
    estimates=sum(float(r.get('estimated_cost_usd') or 0) for r in rows if r.get('estimated_cost_usd') is not None)
    return {'requests':len(rows),'search_actions':sum(int(r.get('search_actions') or 0) for r in rows),
            'input_tokens':sum(int(r.get('input_tokens') or 0) for r in rows),
            'output_tokens':sum(int(r.get('output_tokens') or 0) for r in rows),
            'actual_known_usd':actual,'estimated_known_usd':estimates,
            'accounted_known_usd':sum(float(r.get('actual_cost_usd') if r.get('actual_cost_usd') is not None else r.get('estimated_cost_usd') or 0) for r in rows),
            'purpose_requests':{purpose:sum((r.get('metadata') or {}).get('execution_purpose','legacy')==purpose for r in rows) for purpose in ('operation','validation','recovery','legacy')},
            'unknown_cost_requests':sum(r.get('actual_cost_usd') is None and r.get('estimated_cost_usd') is None for r in rows),
            'charge_uncertain_requests':sum(bool((r.get('metadata') or {}).get('charge_uncertain')) for r in rows)}


def cost_summary_label(summary):
    """Do not present the empty known subtotal as a zero total bill."""
    requests = int(summary.get('requests') or 0)
    unknown = int(summary.get('unknown_cost_requests') or 0)
    uncertain = int(summary.get('charge_uncertain_requests') or 0)
    known = float(summary.get('accounted_known_usd') or 0)
    if not requests:
        text = 'API 요청 없음 · 집계 비용 $0.0000'
    elif unknown >= requests:
        text = f'총비용 확인 필요 · 비용 미확인 요청 {unknown}회'
    elif unknown:
        text = f'총비용 확인 필요 · 확인된 비용 합계 ${known:.4f} (일부 기록) · 비용 미확인 요청 {unknown}회'
    else:
        text = f'기록 기준 비용 합계 ${known:.4f} · 추정 비용 포함'
    return text + (f' · 응답 미확인 {uncertain}회' if uncertain else '')
