"""Parse coverage comparison documents conservatively; amounts are candidates, not advice."""
from __future__ import annotations
from io import BytesIO
import re
import pdfplumber

METRICS = ('일반암', '유사암', '뇌혈관질환', '허혈성심장질환')

def _amount(s):
    s=s.replace(',', '').replace(' ', '')
    m=re.fullmatch(r'(\d+(?:\.\d+)?)(억|천만|백만|만원|만|원)', s)
    if not m:return None
    return round(float(m[1]) * {'억':100000000,'천만':10000000,'백만':1000000,'만원':10000,'만':10000,'원':1}[m[2]])

def _classify(name):
    s=re.sub(r'\s+','',name)
    if any(x in s for x in ('납입','산정특례','보험료')):return None
    if '진단' in s and not any(x in s for x in ('수술','치료')):
        if '뇌혈관질환' in s or '뇌혈관진단' in s:return '뇌혈관질환'
        if '허혈성심장질환' in s or '허혈심장질환' in s:return '허혈성심장질환'
        if any(x in s for x in ('소액암','유사암')) and '유사암제외' not in s:return '유사암'
        if '특정암' not in s and '고액암' not in s and ('유사암제외' in s or re.search(r'암진단(?:비|Ⅱ|II|특약)',s) or '일반암' in s):return '일반암'
    if '간병' in s:return '간병'
    if '암' in s and any(x in s for x in ('치료','수술')):return '암 치료'
    if any(x in s for x in ('순환계','혈전','뇌혈관','심장')) and any(x in s for x in ('치료','수술')):return '뇌·심장 치료'
    if '수술' in s:return '수술'
    if any(x in s for x in ('통풍','당뇨','골절','화상')):return '기타 보장'
    return None

def extract_pdf(data: bytes, password: str = ""):
    """Return distinct candidate rows and premium candidates with source pages.

    The selected summary pages are deliberately constrained; this is not a full
    policy interpretation and rows require explicit human review.
    """
    with pdfplumber.open(BytesIO(data), password=password or "") as pdf:
        if len(pdf.pages)>160:raise ValueError('PDF는 160쪽 이내로 나누어 올려 주세요.')
        pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    if not any(t.strip() for _,t in pages):
        return {'rows':[], 'premiums':[], 'warnings':['텍스트를 읽을 수 없는 PDF입니다. 계약정보를 직접 입력해 주세요.'], 'page_count':len(pages)}
    summaries=[]; carry=False
    for n,t in pages:
        if ('가입담보요약' in t or '상품제안서_가입담보' in t or '보험계약의 개요' in t or ('가입내용 요약' in t and '주계약ㆍ특약보험료' in t)):
            summaries.append((n,t));carry=True;continue
        if carry and (('보장명 가입금액' in t) or ('납입주기 : 월납' in t and ('할인전보험료' in t or '선택특약' in t))):
            summaries.append((n,t));carry=False;continue
        carry=False
    if not summaries:return {'rows':[], 'premiums':[], 'warnings':['가입 내용 요약을 자동으로 찾지 못했습니다. 계약정보를 직접 입력해 주세요.'], 'page_count':len(pages)}
    rows=[]; premiums=set()
    for n,t in summaries:
        for m in re.finditer(r'(?:할인후초회보험료|1회 보험료|납입보험료|주계약ㆍ특약보험료\s*월납|실납입보험료)\s*([\d,]+)\s*원',t):premiums.add(int(m[1].replace(',','')))
        lines=t.splitlines(); previous=''
        for line in lines:
            direct=_classify(line)
            continuation=bool(re.match(r'^\s*(?:(?:\d+\.?\s+)?[\d,]+(?:천만원|백만원|만원|억원|원)\s+\d|[\d,]+\s+(?:종신|\d+세만기|\d+년)\s+)',line))
            combined=previous+' '+line if not direct and (line.lstrip().startswith('특약') or continuation) else line
            kind=direct or (_classify(previous) if combined!=line else None)
            if kind:
                # Only accept a table amount followed by a premium column; avoid amounts in names such as annual limits.
                matches=list(re.finditer(r'(?<![\d,])([\d,]+(?:\.\d+)?\s*(?:억원|천만원|백만원|만원|원))(?=\s+[\d,]+(?:세만기|년만기|\s))',line))
                amount=_amount(matches[-1].group(1).replace('천만원','천만').replace('백만원','백만').replace('억원','억')) if matches else None
                if amount is None:
                    m=re.search(r'(?:^|\s)([\d,]+)\s+(?:종신|\d+세만기|\d+년)\s+(?:\d+년납|전기납)',line)
                    if m:amount=int(m[1].replace(',',''))*10000
                if amount is not None:
                    rows.append({'항목':kind,'금액(원)':amount,'페이지':n,'원문':combined.strip()[:240],'확인':False})
            previous=line
        # Some forms give the premium only as a summary-line total.
        for m in re.finditer(r'(?:합\s*계|실납입보험료)\s+([\d,]{4,})\s*(?:원)?',t):premiums.add(int(m[1].replace(',','')))
    for _,t in pages[:6]:
        m=re.search(r'할인전보험료\s+실납입보험료\s+([\d,]+)\s*원\s+([\d,]+)\s*원',t)
        if m:premiums.add(int(m[2].replace(',','')))
    seen=set(); unique=[]
    for row in rows:
        key=(row['항목'],row['금액(원)'],row['원문'])
        if key not in seen:seen.add(key);unique.append(row)
    warnings=['자동 추출은 참고용입니다. 금액과 지급 조건을 원본과 대조해 주세요.']
    if len(premiums)>1:warnings.append('서로 다른 보험료가 표시되어 있어 확인이 필요합니다.')
    if any('암진단Ⅱ 특약' in t and '자궁암, 유방암, 전립선암' in t for _,t in pages):
        warnings.append('일반암에서 자궁암·유방암·전립선암이 별도 분류되는 조건을 확인하세요.')
    return {'rows':unique,'premiums':sorted(premiums),'warnings':warnings,'page_count':len(pages)}

def signed_total(items):
    vals=[x.get('premium') for x in items]
    return sum(vals) if vals and all(isinstance(v,(int,float)) and v>=0 for v in vals) else None

def format_won(n):
    return '확인 필요' if n is None else f'{int(n):,}원'

def format_coverage(n):
    if n is None:return '확인 필요'
    if n==0:return '0원 (확인됨)'
    if n>=100000000:
        e,rem=divmod(int(n),100000000)
        return f'{e}억' + (f' {rem//10000:,}만' if rem else '')+'원'
    return f'{n//10000:,}만 원' if n%10000==0 else f'{n:,}원'


def summarize_candidate(row):
    """Compact customer-facing labels; amounts are rider face amounts, not promises."""
    raw=re.sub(r'\s+','',row['원문']); cat=row['항목']
    if cat=='암 치료':
        if '표적항암' in raw:label='표적항암 치료'
        elif '카티' in raw or 'CAR-T' in raw:label='카티 항암치료'
        elif '중입자' in raw:label='중입자 치료'
        elif '항암약물' in raw and '주요치료' not in raw:label='항암약물치료'
        elif '주요치료' in raw:label=('비급여 ' if '비급여' in raw else '')+'암 주요치료'
        elif '다빈치' in raw:label='다빈치 암수술'
        else:label='암 치료'
    elif cat=='뇌·심장 치료':label='혈전용해치료' if '혈전용해' in raw else '순환계 주요치료'
    elif cat=='수술':label='질병수술' if '질병수술' in raw else ('상해수술' if '상해' in raw else '특정 질병 수술')
    elif cat=='간병':
        label='간호·간병 통합서비스' if '통합서비스' in raw else '간병인 사용'
        if '요양병원제외' in raw:label+='(요양병원 제외)'
        elif '요양병원' in raw:label+='(요양병원)'
    else:
        label=next((x+' 진단' for x in ('통풍','당뇨','골절','화상') if x in raw),'기타 보장')
    return f"{label} {format_coverage(row['금액(원)'])} (가입금액 · {row['페이지']}쪽 · 조건 확인)"
