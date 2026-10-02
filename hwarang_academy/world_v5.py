"""V5 fictional customer world model.

No external API calls. The data in this module is training-only, fictional and
kept separate from legal/medical/product truth.  The purpose is to give the
conversation engine a coherent world to query instead of inventing facts turn by
turn.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import re
from typing import Any
from .coverage_master import COVERAGE_MASTER, find_code as master_find_code, find_codes as master_find_codes

WORLD_VERSION = "5.2-world"

# Coverage names are intentionally generic training constructs. They are not an
# attempt to copy any live insurer product or policy wording.
_POLICY_BLUEPRINTS: dict[str, list[dict[str, Any]]] = {
    "C07-BASE": [
        {"id":"WL1","name":"종신보험","insurer":"가상생명 A","product_type":"일반 종신보험","premium_won":200000,"start_year":2018,"payment_term":"20년납","coverage_term":"종신","renewal":"비갱신","purpose":"가족 사망보장","memory_premium_won":200000,"memory_level":"partial","coverages":[
            {"id":"death","name":"일반사망","amount_won":100000000,"kind":"사망"},
            {"id":"cancer","name":"암진단비","amount_won":20000000,"kind":"진단"},
            {"id":"surgery","name":"수술 관련 특약","amount_won":1000000,"kind":"수술"},
        ]},
        {"id":"HL1","name":"건강보험","insurer":"가상손해 B","product_type":"종합건강보험","premium_won":120000,"start_year":2021,"payment_term":"20년납","coverage_term":"90세","renewal":"일부 갱신","purpose":"3대질환·수술 대비","memory_premium_won":None,"memory_level":"exists","coverages":[
            {"id":"cancer","name":"암진단비","amount_won":30000000,"kind":"진단"},
            {"id":"brain","name":"뇌혈관질환 진단비","amount_won":20000000,"kind":"진단"},
            {"id":"heart","name":"허혈성심장질환 진단비","amount_won":20000000,"kind":"진단"},
            {"id":"surgery","name":"질병수술비","amount_won":1000000,"kind":"수술"},
        ]},
        {"id":"MI1","name":"실손의료보험","insurer":"가상손해 C","product_type":"실손의료비","premium_won":38000,"start_year":2022,"payment_term":"갱신형","coverage_term":"계약 조건 확인","renewal":"갱신","purpose":"실제 의료비 대비","memory_premium_won":None,"memory_level":"exists","coverages":[
            {"id":"medical","name":"실손의료비","amount_won":None,"kind":"실손"},
        ]},
        {"id":"DR1","name":"운전자보험","insurer":"가상손해 D","product_type":"운전자보험","premium_won":22000,"start_year":2023,"payment_term":"20년납","coverage_term":"80세","renewal":"일부 갱신","purpose":"운전자 관련 비용 대비","memory_premium_won":None,"memory_level":"unknown","coverages":[
            {"id":"driver","name":"운전자 관련 보장","amount_won":None,"kind":"운전자"},
        ]},
        {"id":"ET1","name":"기타 보장성보험","insurer":"가상손해 E","product_type":"상해·질병 보장","premium_won":50000,"start_year":2019,"payment_term":"20년납","coverage_term":"80세","renewal":"비갱신","purpose":"기타 보장","memory_premium_won":None,"memory_level":"unknown","coverages":[
            {"id":"injury","name":"상해 관련 보장","amount_won":10000000,"kind":"상해"},
        ]},
    ],
    "C07-CASHFLOW": [
        {"id":"WL1","name":"종신보험","insurer":"가상생명 A","product_type":"일반 종신보험","premium_won":180000,"start_year":2017,"payment_term":"20년납","coverage_term":"종신","renewal":"비갱신","purpose":"사망보장","memory_premium_won":180000,"memory_level":"exact","coverages":[
            {"id":"death","name":"일반사망","amount_won":80000000,"kind":"사망"},
            {"id":"cancer","name":"암진단비","amount_won":10000000,"kind":"진단"},
        ]},
        {"id":"HL1","name":"건강보험","insurer":"가상손해 B","product_type":"종합건강보험","premium_won":160000,"start_year":2020,"payment_term":"20년납","coverage_term":"90세","renewal":"일부 갱신","purpose":"질병 보장","memory_premium_won":None,"memory_level":"unknown","coverages":[
            {"id":"cancer","name":"암진단비","amount_won":40000000,"kind":"진단"},
            {"id":"brain","name":"뇌혈관질환 진단비","amount_won":20000000,"kind":"진단"},
            {"id":"heart","name":"허혈성심장질환 진단비","amount_won":20000000,"kind":"진단"},
            {"id":"surgery","name":"질병수술비","amount_won":2000000,"kind":"수술"},
        ]},
        {"id":"MI1","name":"실손의료보험","insurer":"가상손해 C","product_type":"실손의료비","premium_won":45000,"start_year":2021,"payment_term":"갱신형","coverage_term":"계약 조건 확인","renewal":"갱신","purpose":"의료비 대비","memory_premium_won":None,"memory_level":"exists","coverages":[{"id":"medical","name":"실손의료비","amount_won":None,"kind":"실손"}]},
        {"id":"DR1","name":"운전자보험","insurer":"가상손해 D","product_type":"운전자보험","premium_won":25000,"start_year":2024,"payment_term":"20년납","coverage_term":"80세","renewal":"일부 갱신","purpose":"운전자 보장","memory_premium_won":None,"memory_level":"unknown","coverages":[{"id":"driver","name":"운전자 관련 보장","amount_won":None,"kind":"운전자"}]},
        {"id":"AN1","name":"연금보험","insurer":"가상생명 E","product_type":"연금보험","premium_won":100000,"start_year":2019,"payment_term":"10년납","coverage_term":"연금개시 조건 확인","renewal":"해당 없음","purpose":"노후자금","memory_premium_won":100000,"memory_level":"partial","coverages":[]},
    ],
    "C07-FAMILY": [
        {"id":"WL1","name":"종신보험","insurer":"가상생명 A","product_type":"일반 종신보험","premium_won":160000,"start_year":2016,"payment_term":"20년납","coverage_term":"종신","renewal":"비갱신","purpose":"가족 사망보장","memory_premium_won":150000,"memory_level":"approx","coverages":[
            {"id":"death","name":"일반사망","amount_won":100000000,"kind":"사망"},
            {"id":"cancer","name":"암진단비","amount_won":20000000,"kind":"진단"},
            {"id":"surgery","name":"수술 관련 특약","amount_won":1000000,"kind":"수술"},
        ]},
        {"id":"HL1","name":"건강보험","insurer":"가상손해 B","product_type":"종합건강보험","premium_won":120000,"start_year":2020,"payment_term":"20년납","coverage_term":"90세","renewal":"일부 갱신","purpose":"암·뇌·심장과 수술 대비","memory_premium_won":None,"memory_level":"exists","coverages":[
            {"id":"cancer","name":"암진단비","amount_won":30000000,"kind":"진단"},
            {"id":"brain","name":"뇌혈관질환 진단비","amount_won":20000000,"kind":"진단"},
            {"id":"heart","name":"허혈성심장질환 진단비","amount_won":20000000,"kind":"진단"},
            {"id":"surgery","name":"질병수술비","amount_won":1000000,"kind":"수술"},
        ]},
        {"id":"MI1","name":"실손의료보험","insurer":"가상손해 C","product_type":"실손의료비","premium_won":40000,"start_year":2022,"payment_term":"갱신형","coverage_term":"계약 조건 확인","renewal":"갱신","purpose":"실제 의료비 대비","memory_premium_won":None,"memory_level":"exists","coverages":[{"id":"medical","name":"실손의료비","amount_won":None,"kind":"실손"}]},
        {"id":"DR1","name":"운전자보험","insurer":"가상손해 D","product_type":"운전자보험","premium_won":20000,"start_year":2021,"payment_term":"20년납","coverage_term":"80세","renewal":"일부 갱신","purpose":"운전자 관련 비용 대비","memory_premium_won":20000,"memory_level":"partial","coverages":[{"id":"driver","name":"운전자 관련 보장","amount_won":None,"kind":"운전자"}]},
        {"id":"CH1","name":"자녀보험","insurer":"가상손해 E","product_type":"자녀보험","premium_won":40000,"start_year":2015,"payment_term":"20년납","coverage_term":"30세","renewal":"혼합","purpose":"자녀 보장","memory_premium_won":None,"memory_level":"unknown","insured":"자녀","coverages":[
            {"id":"child_disease","name":"자녀 질병 관련 보장","amount_won":20000000,"kind":"질병"},
        ]},
    ],
    "C07-RENEWAL": [
        {"id":"HL1","name":"갱신형 건강보험","insurer":"가상손해 A","product_type":"갱신형 건강보험","premium_won":230000,"start_year":2014,"payment_term":"갱신형","coverage_term":"80세","renewal":"갱신","purpose":"질병·수술 대비","memory_premium_won":230000,"memory_level":"exact","coverages":[
            {"id":"cancer","name":"암진단비","amount_won":30000000,"kind":"진단"},
            {"id":"brain","name":"뇌 관련 진단비","amount_won":10000000,"kind":"진단"},
            {"id":"heart","name":"심장 관련 진단비","amount_won":10000000,"kind":"진단"},
            {"id":"surgery","name":"질병수술비","amount_won":1000000,"kind":"수술"},
        ]},
        {"id":"WL1","name":"종신보험","insurer":"가상생명 B","product_type":"CI 종신보험","premium_won":170000,"start_year":2012,"payment_term":"20년납","coverage_term":"종신","renewal":"비갱신","purpose":"사망보장과 중대한 질병 대비로 설명받음","memory_premium_won":None,"memory_level":"exists","coverages":[
            {"id":"death","name":"사망보장","amount_won":100000000,"kind":"사망"},
            {"id":"ci","name":"중대한 질병 관련 급부","amount_won":50000000,"kind":"CI"},
        ]},
        {"id":"MI1","name":"실손의료보험","insurer":"가상손해 C","product_type":"실손의료비","premium_won":50000,"start_year":2017,"payment_term":"갱신형","coverage_term":"계약 조건 확인","renewal":"갱신","purpose":"의료비 대비","memory_premium_won":None,"memory_level":"exists","coverages":[{"id":"medical","name":"실손의료비","amount_won":None,"kind":"실손"}]},
        {"id":"DR1","name":"운전자보험","insurer":"가상손해 D","product_type":"운전자보험","premium_won":25000,"start_year":2023,"payment_term":"20년납","coverage_term":"80세","renewal":"일부 갱신","purpose":"운전자 관련 비용 대비","memory_premium_won":None,"memory_level":"unknown","coverages":[{"id":"driver","name":"운전자 관련 보장","amount_won":None,"kind":"운전자"}]},
        {"id":"HL2","name":"기타 건강보험","insurer":"가상손해 E","product_type":"건강보험","premium_won":75000,"start_year":2025,"payment_term":"20년납","coverage_term":"100세","renewal":"비갱신","purpose":"진단비 추가 보완","memory_premium_won":None,"memory_level":"unknown","coverages":[
            {"id":"cancer","name":"암진단비","amount_won":20000000,"kind":"진단"},
            {"id":"brain","name":"뇌혈관질환 진단비","amount_won":10000000,"kind":"진단"},
        ]},
    ],
}

_PROFILE_CONTEXT = {
    "C07-BASE": {"family":"배우자와 자녀 1명","health":["최근 특이 병력은 이번 과제에서 다루지 않음"],"claims":[],"attitude":{"insurance_knowledge":"낮음","premium_sensitivity":"높음","change_resistance":"보통","existing_agent_relation":"보통"},"document":{"access":"mobile","location":"휴대폰에 저장된 증권","can_open_now":True,"can_send":True}},
    "C07-CASHFLOW": {"family":"배우자 있음","health":["건강 정보는 이번 과제에서 공개 전 미확인"],"claims":[],"attitude":{"insurance_knowledge":"낮음","premium_sensitivity":"매우 높음","change_resistance":"보통","existing_agent_relation":"강함"},"document":{"access":"partial_mobile","location":"휴대폰에 일부 계약 자료","can_open_now":True,"can_send":True}},
    "C07-FAMILY": {"family":"배우자와 자녀 2명","health":["건강 정보는 이번 과제에서 공개 전 미확인"],"claims":[{"year":2024,"summary":"간단한 실손 청구 경험","detail_state":"memory_only"}],"attitude":{"insurance_knowledge":"보통 이하","premium_sensitivity":"높음","change_resistance":"높음","existing_agent_relation":"보통"},"document":{"access":"file_available","location":"휴대폰에 저장된 증권 파일","can_open_now":True,"can_send":True}},
    "C07-RENEWAL": {"family":"배우자 있음","health":["최근 혈압약 복용 시작 · 상세는 C07 과제에서 자동 공개하지 않음"],"claims":[],"attitude":{"insurance_knowledge":"보통","premium_sensitivity":"높음","change_resistance":"높음","existing_agent_relation":"보통"},"document":{"access":"spouse_managed","location":"배우자가 전체 증권 관리","can_open_now":False,"can_send":False}},
}

_ALIASES = {
    "종신보험": ["종신","종신보험"],
    "갱신형 건강보험": ["갱신형건강보험","갱신건강보험","건강보험"],
    "건강보험": ["건강보험","건강"],
    "기타 건강보험": ["기타건강보험","추가건강보험"],
    "실손의료보험": ["실손","실비","실손보험","실손의료보험","의료실비"],
    "운전자보험": ["운전자","운전자보험"],
    "자녀보험": ["자녀보험","아이보험","어린이보험"],
    "연금보험": ["연금보험","연금"],
    "기타 보장성보험": ["기타보험","보장성보험"],
}

_COVERAGE_ALIASES = {
    "cancer": ["암","암진단","암진단비"],
    "brain": ["뇌","뇌혈관","뇌혈관질환"],
    "heart": ["심장","허혈성","허혈성심장질환"],
    "death": ["사망","사망보장","사망보험금"],
    "surgery": ["수술","수술비"],
    "medical": ["실손","실비","의료비"],
    "ci": ["ci","중대한질병","중대한 질병"],
}


# V5.2 deep document schema. Values are fictional training data and intentionally
# detached from live insurer products/terms.
_DETAILED_COVERAGE_TEMPLATES = {
    "실손의료보험": [
        {"id":"medical_d_in","master_code":"INDEMNITY_DISEASE_IN","name":"질병입원(실손)","kind":"실손","amount_won":50000000,"limit_text":"훈련용 가상 증권상 연간 5천만원 한도","detail":{"입원한도":"연간 5천만원(훈련용 가상값)","자기부담":"세부 조건 페이지 확인"}},
        {"id":"medical_d_out","master_code":"INDEMNITY_DISEASE_OUT","name":"질병통원(실손)","kind":"실손","amount_won":250000,"limit_text":"훈련용 가상 증권상 회당 25만원 한도","detail":{"통원한도":"회당 25만원(훈련용 가상값)","자기부담":"세부 조건 페이지 확인"}},
        {"id":"medical_a_in","master_code":"INDEMNITY_ACCIDENT_IN","name":"상해입원(실손)","kind":"실손","amount_won":50000000,"limit_text":"훈련용 가상 증권상 연간 5천만원 한도","detail":{"입원한도":"연간 5천만원(훈련용 가상값)","자기부담":"세부 조건 페이지 확인"}},
        {"id":"medical_a_out","master_code":"INDEMNITY_ACCIDENT_OUT","name":"상해통원(실손)","kind":"실손","amount_won":250000,"limit_text":"훈련용 가상 증권상 회당 25만원 한도","detail":{"통원한도":"회당 25만원(훈련용 가상값)","자기부담":"세부 조건 페이지 확인"}},
    ],
    "운전자보험": [
        {"id":"driver_settle","master_code":"DRIVER_SETTLEMENT","name":"교통사고처리지원금","kind":"운전자","amount_won":200000000},
        {"id":"driver_under6","master_code":"DRIVER_SETTLEMENT_UNDER6","name":"교통사고처리지원금(6주미만)","kind":"운전자","amount_won":10000000},
        {"id":"driver_lawyer","master_code":"DRIVER_LAWYER","name":"변호사선임비용","kind":"운전자","amount_won":50000000},
        {"id":"driver_fine_person","master_code":"DRIVER_FINE_PERSON","name":"운전자벌금(대인)","kind":"운전자","amount_won":30000000},
        {"id":"driver_fine_property","master_code":"DRIVER_FINE_PROPERTY","name":"운전자벌금(대물)","kind":"운전자","amount_won":5000000},
        {"id":"driver_injury","master_code":"DRIVER_INJURY","name":"자동차사고부상위로금","kind":"운전자","amount_won":None,"limit_text":"상해등급별 지급(훈련용 상세표 미전개)"},
    ],
    "자녀보험": [
        {"id":"child_cancer","master_code":"CANCER_GENERAL","name":"일반암","kind":"진단","amount_won":20000000},
        {"id":"child_minor","master_code":"CANCER_MINOR","name":"유사암","kind":"진단","amount_won":10000000},
        {"id":"child_surgery","master_code":"SURGERY_DISEASE","name":"질병수술","kind":"수술","amount_won":500000},
        {"id":"child_injury_surgery","master_code":"SURGERY_ACCIDENT","name":"상해수술","kind":"수술","amount_won":500000},
        {"id":"child_fracture","master_code":"DIAG_FRACTURE","name":"골절진단비","kind":"진단","amount_won":500000},
    ],
    "기타 보장성보험": [
        {"id":"etc_acc_death","master_code":"DEATH_ACCIDENT","name":"재해(상해)사망","kind":"사망","amount_won":50000000},
        {"id":"etc_fracture","master_code":"DIAG_FRACTURE","name":"골절진단비","kind":"진단","amount_won":300000},
        {"id":"etc_burn","master_code":"DIAG_BURN","name":"화상진단비","kind":"진단","amount_won":300000},
        {"id":"etc_surgery","master_code":"SURGERY_ACCIDENT","name":"상해수술","kind":"수술","amount_won":500000},
    ],
}

_LEGACY_MASTER_MAP = {
    "death":"DEATH_DISEASE","cancer":"CANCER_GENERAL","brain":"BRAIN_VASCULAR",
    "heart":"HEART_ISCHEMIC","surgery":"SURGERY_DISEASE","medical":"INDEMNITY_DISEASE_IN",
    "ci":"CANCER_GENERAL",
}

def _enrich_policies(ps:list[dict], profile_key:str)->None:
    for policy in ps:
        template=_DETAILED_COVERAGE_TEMPLATES.get(policy.get("name"))
        if template:
            policy["coverages"]=deepcopy(template)
        elif "실손" in str(policy.get("product_type","")):
            policy["coverages"]=deepcopy(_DETAILED_COVERAGE_TEMPLATES["실손의료보험"])
        elif "운전자" in str(policy.get("product_type","")):
            policy["coverages"]=deepcopy(_DETAILED_COVERAGE_TEMPLATES["운전자보험"])
        for c in policy.get("coverages",[]):
            if not c.get("master_code"):
                code=master_find_code(c.get("name","")) or _LEGACY_MASTER_MAP.get(str(c.get("id")))
                if code:c["master_code"]=code
            code=c.get("master_code")
            if code in COVERAGE_MASTER:
                c.setdefault("group",COVERAGE_MASTER[code]["group"])
                c.setdefault("value_type",COVERAGE_MASTER[code]["value_type"])
            c.setdefault("document_depth","coverage_detail")
            c.setdefault("detail",{})

def _hash_index(seed:int,key:str,size:int)->int:
    if size <= 0:return 0
    return int(sha256(f"{seed}:{key}".encode()).hexdigest()[:12],16)%size

def _normalize(s:str)->str:
    return re.sub(r"\s+","",str(s or "").lower())

def build_customer_world(scenario_id:str, profile_id:str, facts:dict, seed:int) -> dict:
    """Build a coherent fictional world for one session.

    V5 currently deepens C07. Other executable scenarios receive a minimal world
    shell so the shared dialogue/event log schema can be used without inventing
    unreviewed insurance facts.
    """
    base={
        "version":WORLD_VERSION,
        "scenario_id":scenario_id,
        "profile_id":profile_id,
        "seed":int(seed),
        "personal":{"job":facts.get("job"),"customer":facts.get("customer")},
        "family":None,"financial":{},"health":[],"claims":[],"attitude":{},
        "insurance":{"total_monthly_premium_won":facts.get("total_monthly_premium_won"),"policies":[]},
        "document":{"access":"unknown","location":"미확인","can_open_now":False,"can_send":False,"opened":False,"shared":False,"depth":"portfolio","cursor":{}},
        "knowledge":{"total_premium":{"truth":facts.get("total_monthly_premium_won"),"memory":facts.get("total_monthly_premium_won"),"memory_state":"customer_statement","document_state":"unseen"}},
    }
    if scenario_id!="C07-S01":
        return base
    key=profile_id if profile_id in _POLICY_BLUEPRINTS else "C07-BASE"
    policies=deepcopy(_POLICY_BLUEPRINTS[key])
    _enrich_policies(policies,key)
    # Adapt the blueprint totals to the reviewed scenario facts if they differ.
    target_total=int(facts.get("total_monthly_premium_won") or sum(p["premium_won"] for p in policies))
    current_total=sum(int(p["premium_won"]) for p in policies)
    if target_total!=current_total and policies:
        policies[-1]["premium_won"]+=target_total-current_total
    for p in policies:
        # Contract truth is deliberately richer than the customer's memory.
        # Fields that are not needed by the current mission stay explicitly
        # unknown instead of being fabricated later by the dialogue engine.
        p.setdefault("status","정상 유지")
        p.setdefault("payment_status","정상 납입")
        p.setdefault("contract_holder","본인")
        p.setdefault("insured","본인")
        p.setdefault("beneficiary","계약 설정 확인")
        p.setdefault("premium_payer",p.get("contract_holder","본인"))
        p.setdefault("surrender_value_won",None)
        p.setdefault("surrender_value_state","이번 과제 미확인")
        p.setdefault("change_history",[])
        p.setdefault("claim_links",[])
        p["aliases"]=list(dict.fromkeys([p["name"],*_ALIASES.get(p["name"],[])]))
        for c in p.get("coverages",[]):
            c.setdefault("status","정상")
            c.setdefault("renewal_type",p.get("renewal","확인 필요"))
            c.setdefault("coverage_end",p.get("coverage_term","확인 필요"))
            c.setdefault("waiting_period","가상 증권 상세 확인")
            c.setdefault("reduction_period","가상 증권 상세 확인")
            c.setdefault("source","훈련용 가상 증권")
            c["aliases"]=list(dict.fromkeys([c["name"],*_COVERAGE_ALIASES.get(c["id"],[])]))
    ctx=deepcopy(_PROFILE_CONTEXT.get(key,_PROFILE_CONTEXT["C07-BASE"]))
    base["family"]=ctx["family"];base["health"]=ctx["health"];base["claims"]=ctx["claims"];base["attitude"]=ctx["attitude"]
    base["document"].update(ctx["document"])
    base["financial"]={"burden_trigger":facts.get("burden_trigger"),"preference":facts.get("preference")}
    base["goals"]=[
        {"priority":1,"goal":"보험료 부담 완화","source":"상담 신청"},
        {"priority":2,"goal":str(facts.get("preference") or "필요한 보장 유지"),"source":"숨은/조건부 니즈"},
        {"priority":3,"goal":"기존 계약을 확인한 뒤 변경 여부 판단","source":"훈련 목표"},
    ]
    base["insurance"]={
        "total_monthly_premium_won":target_total,
        "policies":policies,
        "portfolio_summary":{
            "policy_count":len(policies),
            "renewable_count":sum(1 for p in policies if "갱신" in str(p.get("renewal",""))),
            "nonrenewable_count":sum(1 for p in policies if p.get("renewal")=="비갱신"),
        },
    }
    base["document"]["graph"]={
        "type":"policy_portfolio",
        "policy_ids":[p["id"] for p in policies],
        "sections":{p["id"]:["contract","premium","coverages","coverage_detail","terms","status"] for p in policies},
        "depths":["portfolio","policy_summary","coverages","coverage_detail"],
    }
    # Customer memory is deliberately different from document truth for some profiles.
    total_memory=target_total
    if key=="C07-FAMILY": total_memory=380000
    elif key=="C07-CASHFLOW": total_memory=500000
    elif key=="C07-RENEWAL": total_memory=550000
    base["knowledge"]["total_premium"]={"truth":target_total,"memory":total_memory,"memory_state":"exact" if total_memory==target_total else "approx","document_state":"unseen"}
    base["knowledge"]["policies"]={}
    for p in policies:
        base["knowledge"]["policies"][p["id"]]={
            "exists":"known" if p.get("memory_level") in ("exact","approx","partial","exists") else "unknown",
            "premium_memory":p.get("memory_premium_won"),
            "premium_memory_state":p.get("memory_level","unknown"),
            "purpose_memory":p.get("purpose") if p.get("memory_level") in ("exact","partial") else None,
            "coverage_memory":"broad" if p.get("memory_level") in ("exact","partial","exists") else "unknown",
            "document_state":"unseen",
            "disclosed_fields":[],
        }
    validate_world(base)
    return base

def policies(world:dict)->list[dict]:
    return list(world.get("insurance",{}).get("policies") or [])

def find_policy(world:dict, text:str, *, active_policy_id:str|None=None) -> dict|None:
    n=_normalize(text)
    found=[]
    for p in policies(world):
        for a in p.get("aliases",[]):
            aa=_normalize(a)
            if aa and aa in n:
                found.append((len(aa),p));break
    if found:
        found.sort(key=lambda x:x[0],reverse=True);return found[0][1]
    if active_policy_id:
        return next((p for p in policies(world) if p["id"]==active_policy_id),None)
    return None

def find_policies(world:dict,text:str)->list[dict]:
    n=_normalize(text);found=[]
    for p in policies(world):
        if any(_normalize(a) in n for a in p.get("aliases",[]) if _normalize(a)):
            found.append(p)
    # Keep document order while de-duplicating.
    seen=set();out=[]
    for p in found:
        if p["id"] not in seen:seen.add(p["id"]);out.append(p)
    return out

def find_coverage_key(text:str)->str|None:
    code=master_find_code(text)
    if code:return code
    n=_normalize(text)
    for key,aliases in _COVERAGE_ALIASES.items():
        if any(_normalize(a) in n for a in aliases):return _LEGACY_MASTER_MAP.get(key,key)
    return None

def find_coverage_keys(text:str)->list[str]:
    codes=master_find_codes(text)
    return list(dict.fromkeys(codes))

def remembered_policy_names(world:dict)->list[str]:
    out=[]
    for p in policies(world):
        k=world.get("knowledge",{}).get("policies",{}).get(p["id"],{})
        if k.get("exists") == "known":out.append(p["name"])
    return out

def policy_names(world:dict)->list[str]:
    return [p["name"] for p in policies(world)]

def premium_total(world:dict, *, from_document:bool=False)->int|None:
    k=world.get("knowledge",{}).get("total_premium",{})
    return k.get("truth") if from_document else k.get("memory")

def open_document(world:dict)->tuple[bool,str]:
    d=world["document"]
    if d.get("can_open_now"):
        d["opened"]=True
        k=world.get("knowledge",{})
        k.get("total_premium",{})["document_state"]="confirmed"
        for v in k.get("policies",{}).values():v["document_state"]="confirmed"
        return True, f"{d.get('location','증권')}을 열었어요."
    return False, document_access_message(world)

def document_access_message(world:dict)->str:
    d=world.get("document",{})
    access=d.get("access")
    if access=="spouse_managed":return "지금 제 손에는 전체 증권이 없어요. 배우자에게 자료를 받아야 정확히 확인할 수 있을 것 같아요."
    if access=="partial_mobile":return "휴대폰에 일부 계약 자료는 있어요. 없는 계약은 나중에 추가로 받아야 할 것 같아요."
    if d.get("can_open_now"):return f"{d.get('location','증권')}이 있어서 지금 확인할 수 있어요."
    return "지금 바로 확인 가능한 증권이 있는지는 확인이 필요해요."

def can_send_document(world:dict)->bool:
    return bool(world.get("document",{}).get("can_send"))

def mark_document_shared(world:dict)->None:
    world.setdefault("document",{})["shared"]=True

def policy_premium_lines(world:dict, selected:list[dict]|None=None)->list[str]:
    ps=selected or policies(world)
    return [f"{p['name']} {won_text(p['premium_won'])}" for p in ps]

def won_text(value:int|None)->str:
    if value is None:return "금액 확인 필요"
    value=int(value)
    if value>=100000000 and value%100000000==0:return f"{value//100000000}억원"
    if value>=100000000 and value%10000000==0:return f"{value/100000000:g}억원"
    if value%10000==0:return f"{value//10000}만원"
    return f"{value:,}원"

def policy_summary(p:dict, *, include_premium:bool=True)->str:
    bits=[p["name"]]
    if include_premium:bits.append(f"월 {won_text(p.get('premium_won'))}")
    bits.append(p.get("product_type","상품 유형 확인"))
    bits.append(p.get("renewal","갱신 여부 확인"))
    return " · ".join(bits)

def coverage_summary(p:dict, *, include_amounts:bool=True, max_items:int=5)->str:
    covs=p.get("coverages") or []
    if not covs:return f"{p['name']}은 증권 요약에서 세부 담보가 별도로 정리돼 있지 않아요."
    parts=[]
    for c in covs[:max_items]:
        if include_amounts and c.get("amount_won") is not None:parts.append(f"{c['name']} {won_text(c['amount_won'])}")
        else:parts.append(c["name"])
    return f"{p['name']}에는 " + ", ".join(parts) + "이 보여요."

def coverage_across_portfolio(world:dict,key:str)->list[tuple[dict,dict]]:
    out=[]
    for p in policies(world):
        for c in p.get("coverages",[]):
            if c.get("id")==key or c.get("master_code")==key or key in [c.get("kind")]:out.append((p,c))
    return out

def public_world_snapshot(world:dict)->dict:
    """Return only information safe for debugging/reference, not hidden UI facts."""
    return {"version":world.get("version"),"profile_id":world.get("profile_id"),"document_access":world.get("document",{}).get("access"),"policy_count":len(policies(world))}


def coverage_by_code(policy:dict, code:str|None)->dict|None:
    if not code:return None
    for c in policy.get("coverages",[]):
        if c.get("master_code")==code or c.get("id")==code:return c
    return None

def coverage_detail_text(c:dict)->str:
    amount=c.get("amount_won")
    parts=[c.get("name","담보")]
    if amount is not None:parts.append(won_text(amount))
    if c.get("limit_text"):parts.append(str(c["limit_text"]))
    for k,v in (c.get("detail") or {}).items():parts.append(f"{k} {v}")
    return " · ".join(parts)

def policy_coverage_detail_lines(policy:dict)->list[str]:
    return [coverage_detail_text(c) for c in policy.get("coverages",[])]

def answerability(world:dict, policy:dict|None=None, coverage:dict|None=None)->str:
    """document | memory | unavailable. Keeps answerability separate from truth."""
    if world.get("document",{}).get("opened"):
        return "document"
    if policy:
        k=world.get("knowledge",{}).get("policies",{}).get(policy.get("id"),{})
        if coverage and k.get("coverage_memory") not in ("broad","exact"):return "unavailable"
        if k.get("exists")=="known":return "memory"
    return "unavailable"

def set_document_cursor(world:dict, *, policy_id:str|None=None, section:str|None=None, coverage_code:str|None=None)->None:
    d=world.setdefault("document",{});cursor=d.setdefault("cursor",{})
    if policy_id is not None:cursor["policy_id"]=policy_id
    if section is not None:cursor["section"]=section
    if coverage_code is not None:cursor["coverage_code"]=coverage_code
    if coverage_code:d["depth"]="coverage_detail"
    elif section=="coverages":d["depth"]="coverages"
    elif policy_id:d["depth"]="policy_summary"
    else:d["depth"]="portfolio"

def validate_world(world:dict)->None:
    ps=policies(world)
    ids=[p.get("id") for p in ps]
    if len(ids)!=len(set(ids)):raise ValueError("가상 보험 원장의 계약 ID가 중복되었습니다.")
    if ps:
        expected=int(world.get("insurance",{}).get("total_monthly_premium_won") or 0)
        actual=sum(int(p.get("premium_won") or 0) for p in ps)
        if expected!=actual:raise ValueError(f"가상 보험료 합계 불일치: {expected} != {actual}")
    cov_ids=set()
    for p in ps:
        for c in p.get("coverages",[]):
            key=(p.get("id"),c.get("id"))
            if key in cov_ids:raise ValueError("가상 증권 담보 ID가 중복되었습니다.")
            cov_ids.add(key)
            code=c.get("master_code")
            if code and code not in COVERAGE_MASTER:raise ValueError(f"알 수 없는 표준보장 코드: {code}")

def customer_style(world:dict)->str:
    a=world.get("attitude",{})
    if a.get("insurance_knowledge")=="낮음":return "plain"
    if a.get("change_resistance")=="높음":return "cautious"
    return "neutral"
