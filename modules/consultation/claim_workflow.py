"""UI-independent claim review model. New-screen integration is deliberately separate.

Recommendations are preparation aids, never a determination of entitlement.
All mutations are explicit, stable IDs preserve edits across filter changes.
"""
from copy import deepcopy
from hashlib import sha256
import json


CLAIM_GROUPS = {
    '통원·입원·수술': ['실손 통원','실손 입원','약제비','입원일당','수술','응급실','기타 치료비'],
    '암 진단·치료': ['암 진단','암 수술','항암약물','표적항암','방사선','양성자','세기조절','CAR-T','중입자'],
    '뇌·심장·기타 진단': ['뇌질환','심장질환','골절','화상','기타 진단'],
    '간병·치매·장기요양': ['간병인','간호간병통합','치매','장기요양'],
    '사고·운전자·배상책임': ['일반 상해','교통사고 부상','교통사고처리지원금','벌금','변호사선임비용','배상책임'],
    '치아·임신·출산': ['치아','저체중아','신생아 입원/중환자실','선천이상','유산','사산','산모 입원','산모 수술'],
    '후유장해·사망': ['후유장해','사망'],
}
ALIASES = {'암 진단':'암','암 수술':'수술','방사선':'항암방사선','양성자':'양성자·세기조절',
    '세기조절':'양성자·세기조절','중입자':'중입자치료','교통사고 부상':'교통사고',
    '산모 입원':'입원일당','산모 수술':'수술'}
SOURCE_BASELINES = [
    {'url':'https://www.kbinsure.co.kr/CG205020001.ec', 'checked':'2026-09-28', 'scope':'일반상해·입원·수술 대체서류'},
    {'url':'https://direct.samsungfire.com/claim/PP040202_001.html?pcMode=true', 'checked':'2026-09-28', 'scope':'질병·상해·암·사망·태아 공통 안내'},
]


def rules_for_claim(claim):
    from .insurance_claim_guide import DOC_RULES, DocumentRule as D
    driver = {'교통사고처리지원금':'형사합의서·지급증빙','벌금':'약식명령문·판결문','변호사선임비용':'변호사 선임계약서·영수증'}
    if claim in driver:
        return [D(d.name,d.required_info,d.group) for d in DOC_RULES['운전자비용'] if d.name in ('사고사실확인서',driver[claim])]
    birth = {
        '저체중아':[D('출생증명서','출생일, 출생체중, 임신주수')],
        '신생아 입원/중환자실':[D('출생증명서','출생일, 청구인과 관계 확인'),D('입퇴원확인서','진단명, 진단코드, 입퇴원일'),D('신생아중환자실 사용확인서','실제 이용한 경우 이용기간',level='해당 시')],
        '선천이상':[D('진단서','선천이상 진단명, 진단코드, 확정진단일')],
        '유산':[D('유산진단서','유산 진단명, 진단코드, 진단일')],
        '사산':[D('사산증명서','사산 사실, 일자')],
    }
    return birth.get(claim,DOC_RULES.get(ALIASES.get(claim,claim),[]))


def stable_id(values):
    return sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]


def coverage_id(row):
    return stable_id([row.get(k, '') for k in ('company', 'product', 'coverage', 'amount', 'contract_date', 'expiry_date')])


def new_case():
    return {'file_id': '', 'rows': [], 'coverage_edits': {}, 'manual': [],
            'claims': [], 'answers': {}, 'dismissed': [], 'doc_edits': {},
            'message': '', 'message_fingerprint': ''}


def replace_source(case, file_id, rows, *, keep_manual=False):
    result = deepcopy(case)
    if result['file_id'] == file_id:
        return result
    result.update(file_id=file_id, rows=deepcopy(rows), coverage_edits={}, dismissed=[])
    if not keep_manual:
        result['manual'] = []
    return result


def grouped_coverages(rows):
    groups = {}
    for r in rows:
        key = (r.get('company', '확인 필요'), r.get('product', '확인 필요'),
               r.get('contract_date', ''), r.get('expiry_date', ''))
        groups.setdefault(key, []).append(deepcopy(r))
    return groups


def review_rows(case, claims, answers=None):
    from .insurance_claim_guide import match_coverages, refine_matches_with_answers
    narrow = {
        '암 수술': ('수술',('암',)),
        '양성자': ('양성자·세기조절',('양성자',)),
        '세기조절': ('양성자·세기조절',('세기조절',)),
        '교통사고처리지원금': ('운전자비용',('교통사고처리지원금',)),
        '벌금': ('운전자비용',('벌금',)),
        '변호사선임비용': ('운전자비용',('변호사선임',)),
        '저체중아': ('태아·출산',('저체중',)),
        '신생아 입원/중환자실': ('태아·출산',('신생아','인큐베이터')),
        '선천이상': ('태아·출산',('선천',)),
        '산모 입원': ('입원일당',('산모','임신','출산')),
        '산모 수술': ('수술',('산모','임신','출산')),
    }
    found = {}
    for claim in claims:
        legacy, terms = narrow.get(claim,(ALIASES.get(claim,claim),()))
        sources = [r for r in case['rows'] if not terms or any(t in r.get('coverage','') for t in terms)]
        # Unmapped birth benefits are conservative review candidates, not automatic selections.
        if claim in ('유산','사산'):
            sources = [dict(r,category='태아 '+r.get('category','')) for r in sources if claim in r.get('coverage','')]
            legacy = '태아·출산'
        matched = refine_matches_with_answers(match_coverages(sources,[legacy]), answers or {})
        for row in matched.to_dict('records'):
            original = dict(zip(('company','product','coverage','amount','contract_date','expiry_date'),
                               (row[k] for k in ('보험회사','상품명','관련 담보','가입금액','계약일','만기일'))))
            key = coverage_id(original)
            row['관련 청구'] = claim
            if key in found:
                prev=found[key]
                reasons=prev['관련 청구']+' · '+claim
                if not row['포함']:
                    prev['관련 청구']=reasons
                    continue
                row['관련 청구']=reasons
            if claim in ('유산','사산'):
                row.update(포함=False,분류='조건부 관련')
            row.update(case['coverage_edits'].get(key, {}))
            row['id'] = key
            found[key] = row
    result = list(found.values())
    return result + deepcopy(case['manual'])


def edit_coverage(case, key, **fields):
    allowed = {'포함', '보험회사', '상품명', '관련 담보', '가입금액', '확인사항'}
    if fields.keys() - allowed:
        raise ValueError('수정할 수 없는 필드')
    result = deepcopy(case)
    result['coverage_edits'].setdefault(key, {}).update(fields)
    return result


def source_page_numbers(row, page_count):
    return sorted({int(p) for p in row.get('source_pages', [row.get('source_page', 0)])
                   if str(p).isdigit() and 1 <= int(p) <= page_count})


# Actual treatment must be confirmed separately; one question can resolve multiple proposals.
PROPOSALS = {
    '수술': ('surgery', ('수술',), ('수술확인서',)),
    '입원일당': ('admission', ('입원일당', '입원급여'), ('입퇴원확인서',)),
    '실손 입원': ('admission', ('입원의료비', '입원실손'), ('진료비 계산서·영수증', '진료비 세부내역서', '입퇴원확인서')),
    '항암약물': ('drug', ('항암약물',), ('항암치료확인서',)),
    '표적항암': ('targeted', ('표적항암',), ('표적항암치료확인서',)),
    '항암방사선': ('radiation', ('항암방사선',), ('방사선치료확인서',)),
    '간병인': ('caregiver', ('간병인사용', '간병인지원'), ('간병인 사용확인서', '간병비 영수증')),
    '간호간병통합': ('integrated_care', ('간호간병통합',), ('간호·간병통합서비스 사용확인서',)),
}


def proposals(case):
    from .insurance_claim_guide import normalize_text
    result = []
    for claim, (question, terms, documents) in PROPOSALS.items():
        if claim in {ALIASES.get(c,c) for c in case['claims']} or claim in case['dismissed']:
            continue
        hits = []
        for row in case['rows']:
            text = normalize_text(row.get('coverage', ''))
            if any(term in text for term in terms):
                hits.append(coverage_id(row))
        answer = case['answers'].get(question, '확인 중')
        if hits and answer not in ('아니요','아니오','해당 없음'):
            result.append({'claim': claim, 'question': question, 'confirmed': answer == '예',
                           'evidence_ids': list(dict.fromkeys(hits)), 'documents': list(documents)})
    return result


def accept_proposal(case, claim):
    proposal = next((x for x in proposals(case) if x['claim'] == claim), None)
    if not proposal or not proposal['confirmed']:
        raise ValueError('실제 치료 여부를 먼저 확인해 주세요.')
    result = deepcopy(case)
    before={d['id'] for d in document_recommendations(case['claims'],case['answers'])}
    label={'항암방사선':'방사선'}.get(claim,claim)
    result['claims'].append(label)
    result['new_doc_ids']=list(set(result.get('new_doc_ids',[])) | {d['id'] for d in document_recommendations(result['claims'],result['answers']) if d['id'] not in before})
    return result


DIAGNOSIS_TESTS = {
    '암': [('조직병리검사 결과지','조직검사를 시행한 경우, 최종 병리진단과 검사 결과'),
           ('영상검사 판독지','이번 암 진단에 사용한 영상검사 결과'),
           ('혈액검사 결과지','이번 암 진단에 사용한 혈액검사 결과'),
           ('골수검사 결과지','이번 암 진단에 사용한 골수검사 결과')],
    '뇌질환': [('CT·MRI·MRA 등 영상검사 판독지','이번 뇌질환 진단에 사용한 영상검사 결과'),
              ('뇌혈관조영술 결과지','이번 뇌질환 진단에 사용한 검사 결과')],
    '심장질환': [('심전도 검사결과지','이번 심장질환 진단에 사용한 검사 결과'),
                ('심장초음파 검사결과지','이번 심장질환 진단에 사용한 검사 결과'),
                ('혈액검사 결과지','심장효소 등 이번 심장질환 진단에 사용한 검사 결과'),
                ('관상동맥조영술 결과지','이번 심장질환 진단에 사용한 검사 결과')],
}


def document_identity(name, target='피보험자', purpose='보험금 청구'):
    return stable_id([name,target,purpose])


def merge_information(requirements):
    """Deduplicate common fields, preserve claim-specific qualifiers."""
    import re
    fields=[]
    for claim, text in requirements:
        for part in re.split(r'[,，]', text):
            part=part.strip()
            if part and part not in fields: fields.append(part)
    return ', '.join(fields)


def document_recommendations(claims, answers=None):
    from .insurance_claim_guide import COMMON_DOCUMENTS, DocumentRule as D
    answers=answers or {}
    if not claims: return []
    rows={}
    conditions={'처방전':('prescription','예'),'깁스·부목 치료확인서':('cast','예'),
        '유전자·바이오마커 검사결과':('biomarker','예'),
        '중환자실·병실 이용확인서':('icu','예'),'대리청구 관계서류':('proxy','예'),
        '신생아중환자실 사용확인서':('nicu','예'),
        '기본증명서·가족관계증명서':('beneficiary','법정상속인')}
    for claim in ['공통']+list(dict.fromkeys(claims)):
        canonical=ALIASES.get(claim,claim)
        tests=DIAGNOSIS_TESTS.get(canonical)
        if tests is not None:
            rules=[D('진단서','각 청구 질환의 진단명·진단코드·확정진단일')]
            rules += [D(name,info,level='해당 시',default_selected=False) for name,info in tests]
            rules += [D('기타 검사자료','이번 진단에 사용한 검사명과 검사 결과',level='해당 시',default_selected=False)]
        else:
            rules=COMMON_DOCUMENTS if claim=='공통' else rules_for_claim(claim)
        for doc in rules:
            if claim=='실손 입원' and doc.name=='진단서': continue
            target='피보험자';purpose='보험금 청구'
            if claim=='공통':target='청구인'
            elif doc.name=='기본증명서·가족관계증명서':target='사망자';purpose='사망사실·상속관계 확인'
            elif '수익자' in doc.name:target='보험수익자'
            elif claim in ('저체중아','신생아 입원/중환자실','선천이상'):target='출생아'
            elif claim.startswith('산모') or claim in ('유산','사산'):target='산모'
            ident=document_identity(doc.name,target,purpose)
            tier='기본 추천' if doc.default_selected and doc.level=='기본 준비' else '추가 요청 시'
            included=tier=='기본 추천';question=''
            if doc.level=='해당 시':tier='조건부 추천';included=False
            if doc.name in conditions and not (claim=='약제비' and doc.name=='처방전'):
                question,yes=conditions[doc.name];tier='조건부 추천';included=answers.get(question)==yes
            item=rows.setdefault(ident,dict(id=ident,name=doc.name,group=doc.group,target=target,purpose=purpose,
                tier=tier,include=False,reasons=[],questions=[],requirements=[]))
            item['include'] |= included
            if included:item['tier']=tier
            if claim not in item['reasons']:item['reasons'].append(claim)
            if question and question not in item['questions']:item['questions'].append(question)
            item['requirements'].append((claim,doc.required_info))
    for item in rows.values():
        item['required_info']=merge_information(item['requirements'])
        item['default_info']=item['required_info']
    return list(rows.values())


def documents_for_case(case):
    result=document_recommendations(case['claims'],case['answers'])
    for row in result:
        edit=case['doc_edits'].get(row['id'],{})
        row['additional_info']=''
        if 'required_info' in edit:
            basis=edit.get('basis_info',row['default_info'])
            old={part.strip() for part in basis.split(',')}
            row['additional_info']=', '.join(part.strip() for part in row['default_info'].split(',') if part.strip() not in old)
        row.update({k:v for k,v in edit.items() if k in ('name','required_info','include')})
    return result


def proposal_delta(case, claim):
    before={d['id']:d for d in document_recommendations(case['claims'],case['answers'])}
    after=document_recommendations(case['claims']+[claim],case['answers'])
    return {'added':[d for d in after if d['id'] not in before],
            'updated':[d for d in after if d['id'] in before and d['required_info']!=before[d['id']]['required_info']]}


def message_fingerprint(claims, docs, name='', note=''):
    return stable_id([claims, [{k:r[k] for k in ('name','required_info','group')} for r in docs if r['include']], name, note])


def make_message(claims, docs, name='', note=''):
    lines = [f'{name}님, 보험금 청구 서류 안내드립니다.' if name else '보험금 청구 서류 안내드립니다.',
             '청구 내용: ' + ' · '.join(claims)]
    for group in ('병원 발급', '그 밖에 준비'):
        selected = [d for d in docs if d['include'] and (d['group']=='병원 발급')==(group=='병원 발급')]
        if selected:
            lines.extend(['', '['+group+']'])
            lines.extend(f"• {d['name']}: {d['required_info']}" for d in selected)
    if note.strip(): lines.extend(['', note.strip()])
    lines.extend(['', '보험회사·가입 담보에 따라 추가서류가 요청될 수 있습니다.'])
    return '\n'.join(lines)


def generate_message(case, name='', note='', *, replace=False):
    if case['message'] and not replace:
        raise ValueError('작성한 안내문을 교체할지 확인해 주세요.')
    result = deepcopy(case)
    docs = documents_for_case(case)+case.get('custom_docs',[])
    result['message'] = make_message(case['claims'], docs, name, note)
    result['message_fingerprint'] = message_fingerprint(case['claims'], docs, name, note)
    return result
