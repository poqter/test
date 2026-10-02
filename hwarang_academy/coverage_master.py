"""Training coverage master for HWARANG ACADEMY.

The catalog is based on the user-provided coverage checklist images.  It is a
simulation vocabulary/data schema, not a statement of any insurer's live policy
wording or statutory coverage.  Monetary limits inside fictional customer
portfolios are training data only.
"""
from __future__ import annotations
from typing import Any
import re

MASTER_VERSION = "2026-10-02-v1"

# code, group, display name, aliases, value type
_ROWS = [
    ("DEATH_DISEASE","사망","질병사망",["질병사망","질병 사망"],"lump_sum"),
    ("DEATH_ACCIDENT","사망","재해(상해)사망",["재해사망","상해사망","재해 사망","상해 사망"],"lump_sum"),
    ("DISABILITY_DISEASE_3","후유장해","질병후유장해3%일경우",["질병후유장해3%","질병후유장해 3%","질병장해3%"],"graded"),
    ("DISABILITY_DISEASE_80","후유장해","질병후유장해80%이상",["질병후유장해80%","질병후유장해 80%","질병장해80%"],"lump_sum"),
    ("DISABILITY_ACCIDENT_3","후유장해","재해(상해)장해3%일경우",["상해후유장해3%","재해후유장해3%","상해장해3%"],"graded"),
    ("DISABILITY_ACCIDENT_80","후유장해","재해(상해)장해80%이상",["상해후유장해80%","재해후유장해80%","상해장해80%"],"lump_sum"),
    ("CANCER_HIGH","암","고액암",["고액암","고액암진단비"],"lump_sum"),
    ("CANCER_GENERAL","암","일반암",["일반암","암진단비","암진단","암보장"],"lump_sum"),
    ("CANCER_SECONDARY","암","이차암(재진단,계속암)",["이차암","재진단암","계속암","재진단 계속암"],"lump_sum"),
    ("CANCER_MINOR","암","유사암",["유사암","소액암","유사암진단비"],"lump_sum"),
    ("CANCER_TARGET_DRUG","암치료","표적항암약물허가치료비",["표적항암","표적항암약물","표적항암약물허가치료비"],"treatment"),
    ("CANCER_RAD_CHEMO","암치료","항암방사선약물치료비",["항암방사선","항암약물","항암방사선약물치료비"],"treatment"),
    ("BRAIN_VASCULAR","뇌","뇌혈관",["뇌혈관","뇌혈관질환","뇌혈관진단비","뇌진단비"],"lump_sum"),
    ("BRAIN_STROKE","뇌","뇌졸중",["뇌졸중","뇌졸중진단비"],"lump_sum"),
    ("BRAIN_HEMORRHAGE","뇌","뇌출혈",["뇌출혈","뇌출혈진단비"],"lump_sum"),
    ("HEART_ISCHEMIC","심장","허혈성심장질환",["허혈성","허혈성심장질환","허혈성진단비","심장진단비"],"lump_sum"),
    ("HEART_AMI","심장","급성심근경색증",["급성심근경색","급성심근경색증","심근경색"],"lump_sum"),
    ("DEMENTIA_SEVERE","치매·간병","중증치매",["중증치매","중증치매진단비"],"lump_sum"),
    ("DEMENTIA_MILD","치매·간병","경증치매",["경증치매","경증치매진단비"],"lump_sum"),
    ("LTC_G1","치매·간병","장기간병요양진단(1급)",["장기요양1급","간병1급"],"lump_sum"),
    ("LTC_G12","치매·간병","장기간병요양진단(1,2급)",["장기요양1,2급","장기요양12급","간병1,2급"],"lump_sum"),
    ("LTC_G123","치매·간병","장기간병요양진단(1,2,3급)",["장기요양1,2,3급","장기요양123급"],"lump_sum"),
    ("LTC_G1234","치매·간병","장기간병요양진단(1,2,3,4급)",["장기요양1,2,3,4급","장기요양1234급"],"lump_sum"),
    ("SPECIAL_CANCER","산정특례","암산정특례",["암산정특례"],"special_case"),
    ("SPECIAL_BRAIN","산정특례","뇌혈관산정특례",["뇌혈관산정특례","뇌산정특례"],"special_case"),
    ("SPECIAL_HEART","산정특례","심장질환산정특례",["심장산정특례","심장질환산정특례"],"special_case"),
    ("SPECIAL_DEMENTIA","산정특례","중증치매산정특례",["중증치매산정특례","치매산정특례"],"special_case"),
    ("SURGERY_DISEASE","수술","질병수술",["질병수술","질병수술비","수술비"],"lump_sum"),
    ("SURGERY_DISEASE_CLASS","수술","질병종수술",["질병종수술","질병종수술비","종수술"],"graded"),
    ("SURGERY_ACCIDENT","수술","상해수술",["상해수술","상해수술비"],"lump_sum"),
    ("SURGERY_ACCIDENT_CLASS","수술","상해종수술",["상해종수술","상해종수술비"],"graded"),
    ("SURGERY_CANCER","수술","암수술",["암수술","암수술비"],"lump_sum"),
    ("SURGERY_BRAIN","수술","뇌혈관질환수술",["뇌혈관질환수술","뇌수술","뇌혈관수술"],"lump_sum"),
    ("SURGERY_HEART","수술","허혈성심장질환수술",["허혈성심장질환수술","심장수술","허혈성수술"],"lump_sum"),
    ("HOSP_DISEASE","입원","질병입원",["질병입원","질병입원일당"],"daily"),
    ("HOSP_ACCIDENT","입원","상해입원",["상해입원","상해입원일당"],"daily"),
    ("CAREGIVER_DISEASE","간병","간병인지원입원일-질병",["질병간병인","간병인지원질병","간병인입원질병"],"daily"),
    ("CAREGIVER_ACCIDENT","간병","간병인지원입원일-상해",["상해간병인","간병인지원상해","간병인입원상해"],"daily"),
    ("HOSP_CANCER","입원","암입원",["암입원","암입원일당"],"daily"),
    ("NURSING_ACCIDENT","간호간병","상해간호간병통합입원일당",["상해간호간병","상해간호간병통합"],"daily"),
    ("NURSING_DISEASE","간호간병","질병간호간병통합입원일당",["질병간호간병","질병간호간병통합"],"daily"),
    ("OUTPATIENT_DISEASE","통원","질병통원",["질병통원","질병통원비"],"visit"),
    ("OUTPATIENT_CANCER","통원","암통원",["암통원","암통원비"],"visit"),
    ("OUTPATIENT_ACCIDENT","통원","상해통원",["상해통원","상해통원비"],"visit"),
    ("OUTPATIENT_DENTAL","통원","치과통원",["치과통원","치과통원비"],"visit"),
    ("ER_VISIT","응급","응급실내원비",["응급실","응급실내원","응급실내원비"],"visit"),
    ("DRIVER_SETTLEMENT","운전자","교통사고처리지원금",["교통사고처리지원금","교사처","형사합의금","교통사고합의금"],"expense"),
    ("DRIVER_SETTLEMENT_UNDER6","운전자","교통사고처리지원금(6주미만)",["6주미만교통사고처리지원금","6주미만교사처","6주미만합의금"],"expense"),
    ("DRIVER_LAWYER","운전자","변호사선임비용",["변호사선임비","변호사선임비용","변호사비","변호사비용"],"expense"),
    ("DRIVER_FINE_PERSON","운전자","운전자벌금(대인)",["대인벌금","운전자벌금대인","벌금대인"],"expense"),
    ("DRIVER_FINE_PROPERTY","운전자","운전자벌금(대물)",["대물벌금","운전자벌금대물","벌금대물"],"expense"),
    ("DRIVER_INJURY","운전자","자동차사고부상위로금",["자동차사고부상위로금","자부치","자동차사고부상치료비"],"graded"),
    ("LIABILITY_DAILY","배상책임","일상생활배상책임",["일상생활배상책임","일배책","가족일상생활배상책임"],"liability"),
    ("DENTAL_PROSTHETIC","치아","치아보철치료비",["치아보철","보철치료비","임플란트","브릿지","틀니"],"treatment"),
    ("DENTAL_CONSERVATIVE","치아","치아보존치료비",["치아보존","보존치료비","충전","크라운"],"treatment"),
    ("DIAG_BURN","생활질환·상해","화상진단비",["화상진단","화상진단비"],"lump_sum"),
    ("DIAG_FRACTURE","생활질환·상해","골절진단비",["골절","골절진단","골절진단비"],"lump_sum"),
    ("TREAT_CAST","생활질환·상해","깁스치료비",["깁스","깁스치료","깁스치료비"],"treatment"),
    ("DIAG_GOUT","생활질환·상해","통풍진단비",["통풍","통풍진단","통풍진단비"],"lump_sum"),
    ("DIAG_SHINGLES","생활질환·상해","대상포진진단비",["대상포진","대상포진진단","대상포진진단비"],"lump_sum"),
    ("INDEMNITY_DISEASE_IN","실손","질병입원(실손)",["질병입원실손","질병입원 실손","실손질병입원","입원한도"],"reimbursement"),
    ("INDEMNITY_DISEASE_OUT","실손","질병통원(실손)",["질병통원실손","질병통원 실손","실손질병통원","통원한도"],"reimbursement"),
    ("INDEMNITY_ACCIDENT_IN","실손","상해입원(실손)",["상해입원실손","상해입원 실손","실손상해입원"],"reimbursement"),
    ("INDEMNITY_ACCIDENT_OUT","실손","상해통원(실손)",["상해통원실손","상해통원 실손","실손상해통원"],"reimbursement"),
    ("PET_LIABILITY_PROPERTY","반려동물","반려동물배상책임(대물)",["반려동물대물배상","펫대물배상"],"liability"),
    ("PET_LIABILITY_PERSON","반려동물","반려동물배상책임(대인)",["반려동물대인배상","펫대인배상"],"liability"),
    ("PET_DOG_SURGERY","반려동물","반려동물수술비(개)",["반려동물수술비","강아지수술비","펫수술비"],"treatment"),
    ("PET_DOG_HOSPITAL","반려동물","반려동물입원비(개)",["반려동물입원비","강아지입원비","펫입원비"],"daily"),
    ("PET_DOG_OUTPATIENT","반려동물","반려동물통원비(개)",["반려동물통원비","강아지통원비","펫통원비"],"visit"),
]

COVERAGE_MASTER: dict[str, dict[str, Any]] = {}
for code,group,name,aliases,value_type in _ROWS:
    COVERAGE_MASTER[code] = {
        "code":code,"group":group,"name":name,
        "aliases":list(dict.fromkeys([name,*aliases])),
        "value_type":value_type,
    }

# Only the three values visibly supplied in the reference image are preserved;
# the image did not establish their currency/unit, so they remain raw reference values.
COVERAGE_MASTER["PET_DOG_SURGERY"]["reference_standard_value"] = 100
COVERAGE_MASTER["PET_DOG_HOSPITAL"]["reference_standard_value"] = 20
COVERAGE_MASTER["PET_DOG_OUTPATIENT"]["reference_standard_value"] = 10


def norm(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(text or "").lower())


def coverage_record(code: str) -> dict[str, Any]:
    return dict(COVERAGE_MASTER[code])


def find_codes(text: str) -> list[str]:
    n=norm(text); hits=[]
    if not n:return hits
    for code,row in COVERAGE_MASTER.items():
        best=0
        for alias in row["aliases"]:
            a=norm(alias)
            if a and a in n:best=max(best,len(a))
        if best:hits.append((best,code))
    hits.sort(key=lambda x:x[0],reverse=True)
    return [c for _,c in hits]


def find_code(text: str) -> str | None:
    codes=find_codes(text)
    return codes[0] if codes else None


def validate_master() -> None:
    names=set()
    for code,row in COVERAGE_MASTER.items():
        if not code or code in names:raise ValueError("invalid coverage code")
        names.add(code)
        if not row.get("name") or not row.get("group") or not row.get("aliases"):
            raise ValueError(f"incomplete coverage master: {code}")
