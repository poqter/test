"""Read exact observations from approved source files; never generate prices."""
from datetime import datetime, timezone, timedelta
import json
import math
import os
from pathlib import Path
from .normalize import is_safe_url

METRICS={"KOSPI":("코스피","pt"),"KOSDAQ":("코스닥","pt"),"SP500":("S&P 500","pt"),
         "NASDAQ_COMPOSITE":("나스닥 종합","pt"),"USDKRW":("원/달러","KRW"),"US10Y":("미국 10년 국채 금리","%")}


def validated_metrics(rows, as_of):
    accepted={}
    for row in rows if isinstance(rows,list) else []:
        try:
            code=row["code"]; value=float(row["value"])
            observed=datetime.fromisoformat(str(row["observed_at"]).replace("Z","+00:00"))
            if code not in METRICS or not math.isfinite(value) or value<0 or observed.tzinfo is None: continue
            if observed>as_of or as_of-observed>timedelta(days=10): continue
            if row.get("unit") != METRICS[code][1] or not is_safe_url(row.get("source_url", "")): continue
            if not row.get("source_name") or not row.get("observation_kind") or row.get("display_allowed") is not True: continue
            expected_kind = 'nominal_treasury_yield' if code == 'US10Y' else 'spot_exchange_rate' if code == 'USDKRW' else 'closing_index'
            if row.get('instrument_code') != code or row.get('observation_kind') != expected_kind: continue
            previous=row.get("previous_value")
            previous=float(previous) if previous is not None else None
            if previous is not None and (not math.isfinite(previous) or previous<=0): continue
            normalized={"code":code,"label":METRICS[code][0],"unit":row["unit"],"value":value,
               "previous_value":previous,"change":value-previous if previous is not None else None,
               "change_percent":(value/previous-1)*100 if previous else None,
               "observed_at":observed.isoformat(),"source_name":str(row["source_name"]),"source_url":str(row["source_url"]),
               "observation_kind":str(row["observation_kind"]),"external_allowed":row.get("external_allowed") is True}
            if code not in accepted or datetime.fromisoformat(accepted[code]["observed_at"]) < observed: accepted[code]=normalized
        except (KeyError,TypeError,ValueError,OverflowError): continue
    return {"complete":len(accepted)==6,"items":[accepted.get(code,{"code":code,"label":label,"status":"unavailable"}) for code,(label,_) in METRICS.items()],
            "missing":[code for code in METRICS if code not in accepted]}


def collect_metrics(as_of):
    # The feed must be a deployment-configured, approved source, never an LLM
    # quote. Public endpoints may be polled without adding a paid API contract.
    raw=os.getenv("BRIEFING_MARKET_OBSERVATIONS_JSON", "")
    path=os.getenv("BRIEFING_MARKET_OBSERVATIONS_FILE", "")
    url=os.getenv("BRIEFING_MARKET_OBSERVATIONS_URL", "")
    status='not_configured'
    try:
        if url:
            import requests
            from .publication import _public_destination
            if not url.startswith('https://') or not is_safe_url(url) or not _public_destination(url):raise ValueError('Invalid feed URL')
            with requests.get(url,timeout=10,stream=True,allow_redirects=False) as response:
                if response.status_code!=200:raise ValueError('Feed unavailable')
                chunks=[];size=0
                for chunk in response.iter_content(65536):
                    size+=len(chunk)
                    if size>256000:raise ValueError('Feed too large')
                    chunks.append(chunk)
                rows=json.loads(b''.join(chunks))
            status='collected'
        else:
            rows=json.loads(raw) if raw else json.loads(Path(path).read_text()) if path else []
            status='collected' if raw or path else 'not_configured'
    except Exception:
        rows=[];status='collection_failed'
    result=validated_metrics(rows,as_of)
    result['collection_status']=status
    return result
