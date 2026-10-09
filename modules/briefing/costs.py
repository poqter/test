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
            'unknown_cost_requests':sum(r.get('actual_cost_usd') is None and r.get('estimated_cost_usd') is None for r in rows),
            'charge_uncertain_requests':sum(bool((r.get('metadata') or {}).get('charge_uncertain')) for r in rows)}
