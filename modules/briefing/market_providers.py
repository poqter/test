"""Bounded provider adapters. No model quotes, ETFs or silently changed bases."""
from datetime import datetime, time, timedelta, timezone
import math
import os
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
import requests

def _download(url, *, params=None, http=None):
    session = http or requests.Session()
    session.trust_env = False
    with session.get(url, params=params, timeout=8, stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        raw=bytearray()
        for chunk in response.iter_content(16384):
            raw.extend(chunk)
            if len(raw)>2_000_000:raise ValueError("provider_response_too_large")
        return bytes(raw)


def _rights():
    # Contract/reference is explicit, and is never inferred from API-key presence.
    reference=os.getenv("BRIEFING_MARKET_LICENSE_REFERENCE", "").strip()[:500]
    enabled=os.getenv("BRIEFING_MARKET_EXTERNAL_ALLOWED", "false").lower()=="true"
    return enabled and bool(reference), reference


def treasury_observation(raw, as_of):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():raise ValueError("invalid_xml")
    root=ET.fromstring(raw);points={}
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        values={n.tag.split("}")[-1]:n.text for n in entry.iter()}
        try:
            day=datetime.fromisoformat(str(values["NEW_DATE"]).replace("Z","+00:00")).date()
            # Treasury publishes a daily observation date, not an exchange close.
            at=datetime.combine(day,time(),ZoneInfo("America/New_York"))
            value=float(values["BC_10YEAR"])
            if at<=as_of and math.isfinite(value) and value>=0:points[at]=value
        except (KeyError,ValueError,TypeError):continue
    points=sorted(points.items(),reverse=True)
    if len(points)<2:return None
    (at,value),(previous_at,previous)=points[:2]
    return {"code":"US10Y","instrument_code":"US10Y","value":value,"previous_value":previous,
        "observed_at":at.isoformat(),"previous_observed_at":previous_at.isoformat(),"as_of_precision":"date",
        "market_timezone":"America/New_York","retrieved_at":datetime.now(timezone.utc).isoformat(),
        "unit":"%","source_name":"미 재무부 일간 명목 10년 CMT",
        "source_url":"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve",
        "provider":"us_treasury","data_type":"official_daily","reference_definition":"미 재무부 일간 명목 10년 Constant Maturity Treasury 수익률",
        "observation_kind":"nominal_treasury_yield","display_allowed":True,"external_allowed":_rights()[0],
        "license_reference":_rights()[1]}


def collect_provider_observations(as_of, *, http=None):
    """Optional public Treasury feed; no commercial index or FX adapters."""
    mode = os.getenv("BRIEFING_MARKET_PROVIDER", "").strip().lower()
    if mode != "treasury":
        return [], {"status": "not_configured"}
    external, reference = _rights()
    rows = []
    details = {}
    try:
        years=sorted({as_of.year,(as_of-timedelta(days=20)).year});entries=[]
        for year in years:
            raw=_download("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml",params={"data":"daily_treasury_yield_curve","field_tdr_date_value":str(year)},http=http)
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():raise ValueError("invalid_xml")
            entries.extend(ET.fromstring(raw).findall("{http://www.w3.org/2005/Atom}entry"))
        merged=ET.Element("{http://www.w3.org/2005/Atom}feed");merged.extend(entries)
        row=treasury_observation(ET.tostring(merged),as_of)
        if row:rows.append(row)
        details["US10Y"]="collected" if row else "insufficient_observations"
    except (requests.RequestException,ValueError,ET.ParseError):details["US10Y"]="provider_failed"
    return rows,{"status":"partial" if rows else "provider_failed","provider":mode,"metrics":details,
                 "customer_display_configured":external}
