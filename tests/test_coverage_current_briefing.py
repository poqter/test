from io import BytesIO
from pypdf import PdfReader
from modules.consultation.coverage_current_briefing import current_brief_pdf, _metric, _premium


def data():
    return {'customer_name':'가상고객', 'contracts':[{'company':'가상보험','product':'예시','payment_count':'12/240회','coverage_period':'90세','monthly':100000}, {'company':'가상보험2','product':'예시2','payment_count':'1/240회','monthly':50000}], 'coverages':[
        {'label':'일반암','display':'일반암','values':[30000000, 10000000]},
        {'label':'뇌출혈','display':'뇌출혈','values':[90000000, 0]},
        {'label':'질병입원(실손)','display':'질병 실손 입원','values':[50000000,50000000]},
    ]}


def text_of(b):
    return ''.join(page.extract_text() or '' for page in PdfReader(BytesIO(b)).pages)


def test_narrow_diagnosis_and_missing_are_not_misrepresented():
    p=data()
    assert _metric(p,'일반암')=='4,000만 원'
    assert _metric(p,'뇌혈관질환')=='확인 필요'
    assert _metric(p,'질병 실손 입원')=='계약별 확인'
    assert _premium(p)==150000
    p['contracts'][0]['payment_count']='240/240회'
    assert _premium(p) is None


def test_summary_is_one_page_and_preserves_consultant_and_unknown():
    p=data(); pdf=current_brief_pdf(p,{'display_name':'홍길동','position_name':'팀장'})
    assert len(PdfReader(BytesIO(pdf)).pages)==1
    text=text_of(pdf)
    assert '홍길동' in text and '확인 필요' in text and '뇌혈관질환' in text
    assert '실손은 합산하지 않습니다' in text


def test_detailed_output_does_not_truncate_coverage_or_contracts():
    p=data()
    p['contracts']=[{'company':f'가상보험{i}', 'product':f'계약{i}', 'payment_count':'1/240회', 'monthly':1000} for i in range(12)]
    p['coverages']=[{'label':f'가상담보{i}', 'display':f'가상담보{i}', 'values':[10000]*12} for i in range(50)]
    pdf=current_brief_pdf(p,detailed=True); text=text_of(pdf)
    assert len(PdfReader(BytesIO(pdf)).pages)>2
    assert '가상담보49' in text and '가상보험11' in text and '12번' in text
    assert '보장의 역할을 이해해요' in text
