"""Bounded provider adapters. No model quotes, ETFs or silently changed bases."""
from datetime import datetime, time, timedelta, timezone
import json
import math
import os
from urllib.parse import quote
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
import requests

SYMBOLS = {"KOSPI":"^KS11", "KOSDAQ":"^KQ11", "SP500":"^GSPC",
           "NASDAQ_COMPOSITE":"^IXIC", "USDKRW":"USDKRW"}
INDEXES = {"KOSPI", "KOSDAQ", "SP500", "NASDAQ_COMPOSITE"}


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


def eod_observation(code, rows, as_of, *, provider="fmp", source_url="", external=False, license_reference=""):
    zone=ZoneInfo("Asia/Seoul" if code in {"KOSPI","KOSDAQ"} else "America/New_York")
    close=time(15,30) if code in {"KOSPI","KOSDAQ"} else time(16) if code in INDEXES else time(17)
    points={}
    for row in rows if isinstance(rows,list) else []:
        try:
            at=datetime.combine(datetime.fromisoformat(row["date"]).date(),close,zone)
            value=float(row["close"])
            if at<=as_of and math.isfinite(value) and value>0:points[at]=value
        except (ValueError,TypeError,KeyError):continue
    ordered=sorted(points.items(),reverse=True)
    if len(ordered)<2:return None
    (observed,value),(previous_at,previous)=ordered[:2]
    return {"code":code,"instrument_code":code,"value":value,"previous_value":previous,
        "observed_at":observed.isoformat(),"previous_observed_at":previous_at.isoformat(),
        "market_timezone":str(zone),"retrieved_at":datetime.now(timezone.utc).isoformat(),
        "unit":"pt" if code in INDEXES else "KRW","source_name":"FMP 지수 종가" if code in INDEXES else "FMP 일간 환율",
        "source_url":source_url,"provider":provider,"data_type":"official_close" if code in INDEXES else "official_daily",
        "reference_definition":"해당 지수 정규장 종가" if code in INDEXES else "FMP USDKRW 일간 EOD 기준",
        "observation_kind":"closing_index" if code in INDEXES else "spot_exchange_rate",
        "display_allowed":True,"external_allowed":external,"license_reference":license_reference}


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


def ecos_observation(data, as_of):
    points=[]
    for row in (data.get("StatisticSearch") or {}).get("row",[]):
        try:
            if str(row.get("ITEM_CODE1"))!="0000001":continue
            day=datetime.strptime(row["TIME"],"%Y%m%d").date()
            # Use the complete preceding Korean statistical day, never relabel it.
            if day>=as_of.astimezone(ZoneInfo("Asia/Seoul")).date():continue
            value=float(row["DATA_VALUE"])
            if math.isfinite(value) and value>0:points.append((day,value))
        except (KeyError,TypeError,ValueError):continue
    points=sorted(dict(points).items(),reverse=True)
    if len(points)<2:return None
    (day,value),(previous_day,previous)=points[:2];zone=ZoneInfo("Asia/Seoul")
    external,reference=_rights()
    return {"code":"USDKRW","instrument_code":"USDKRW","value":value,"previous_value":previous,
        "observed_at":datetime.combine(day,time(),zone).isoformat(),"as_of_precision":"date",
        "previous_observed_at":datetime.combine(previous_day,time(),zone).isoformat(),
        "market_timezone":"Asia/Seoul","retrieved_at":datetime.now(timezone.utc).isoformat(),
        "unit":"KRW","source_name":"한국은행 ECOS","source_url":"https://ecos.bok.or.kr/",
        "provider":"bok_ecos","data_type":"official_daily","reference_definition":"ECOS 731Y001 / 0000001 원/미국달러 일간 매매기준율",
        "observation_kind":"spot_exchange_rate","display_allowed":True,"external_allowed":external,"license_reference":reference}


def collect_provider_observations(as_of, *, http=None):
    mode=os.getenv("BRIEFING_MARKET_PROVIDER","").strip().lower()
    if mode not in {"fmp_treasury","fmp_ecos_treasury"}:return [],{"status":"not_configured"}
    key=os.getenv("FMP_API_KEY","").strip();ecos_key=os.getenv("ECOS_API_KEY","").strip()
    if not key or mode=="fmp_ecos_treasury" and not ecos_key:return [],{"status":"configuration_required"}
    external,reference=_rights();rows=[];details={}
    start=(as_of-timedelta(days=20)).date().isoformat()
    try:
        # Validate real instrument identity against the provider's index catalog.
        indexes=json.loads(_download("https://financialmodelingprep.com/stable/index-list",params={"apikey":key},http=http))
        available={str(x.get("symbol")):str(x.get("name") or "").lower() for x in indexes if isinstance(x,dict)}
    except (requests.RequestException,ValueError,TypeError):return [],{"status":"provider_catalog_failed"}
    for code,symbol in SYMBOLS.items():
        if code=="USDKRW" and mode=="fmp_ecos_treasury":continue
        expected={"KOSPI":"kospi","KOSDAQ":"kosdaq","SP500":"500","NASDAQ_COMPOSITE":"nasdaq"}.get(code)
        if expected and (symbol not in available or expected not in available[symbol]):
            details[code]="instrument_not_verified";continue
        try:
            data=json.loads(_download("https://financialmodelingprep.com/stable/historical-price-eod/full",
                params={"apikey":key,"symbol":symbol,"from":start,"to":as_of.date().isoformat()},http=http))
            data=[r for r in data if isinstance(r,dict) and r.get("symbol")==symbol]
            row=eod_observation(code,data,as_of,source_url="https://site.financialmodelingprep.com/developer/docs/stable/index-historical-price-eod-full" if expected else "https://site.financialmodelingprep.com/developer/docs/stable/forex-historical-price-eod-full",external=external,license_reference=reference)
            if row:rows.append(row)
            details[code]="collected" if row else "insufficient_observations"
        except (requests.RequestException,ValueError,TypeError):details[code]="provider_failed"
    if mode=="fmp_ecos_treasury":
        try:
            url=f"https://ecos.bok.or.kr/api/StatisticSearch/{quote(ecos_key,safe='')}/json/kr/1/40/731Y001/D/{(as_of-timedelta(days=20)):%Y%m%d}/{as_of:%Y%m%d}/0000001"
            row=ecos_observation(json.loads(_download(url,http=http)),as_of)
            if row:rows.append(row)
            details["USDKRW"]="collected" if row else "insufficient_observations"
        except (requests.RequestException,ValueError,TypeError):details["USDKRW"]="provider_failed"
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
    return rows,{"status":"collected" if len(rows)==6 else "partial","provider":mode,"metrics":details,
                 "customer_display_configured":external}
