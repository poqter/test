"""Coordinate-based Pro report extraction; preserves unknown insurers and source evidence."""
from io import BytesIO
import re
import pdfplumber


def norm(s):
    return re.sub(r'\s+','',str(s or '')).replace('\x00','')


def cell(page,x0,x1,y0,y1):
    scale=page.width/595
    chars=[c for c in page.chars if x0*scale <= (c['x0']+c['x1'])/2 < x1*scale and y0 <= (c['top']+c['bottom'])/2 < y1]
    lines=[]
    for c in sorted(chars,key=lambda c:(round(c['top'],1),c['x0'])):
        if not lines or abs(c['top']-lines[-1][0]['top'])>2:lines.append([c])
        else:lines[-1].append(c)
    return ' '.join(''.join(c['text'] for c in sorted(line,key=lambda c:c['x0'])) for line in lines).replace('\x00','').strip()


def anchors(page,left,right):
    scale=page.width/595
    crop=page.crop((left*scale,0,right*scale,page.height))
    return [(w['top'],w['bottom'],w['text']) for w in crop.extract_words(x_tolerance=1,y_tolerance=2) if re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?',w['text'])]


def incomplete(s):
    return '...' in s or '…' in s or s.count('(')!=s.count(')') or s.count('[')!=s.count(']')


def compatible(a,b):
    a=norm(a).split('...')[0].split('…')[0];b=norm(b).split('...')[0].split('…')[0]
    return bool(a and b and (a.startswith(b) or b.startswith(a)))


def extract_report(data):
    summaries=[];details=[];texts=[];warnings=[]
    with pdfplumber.open(BytesIO(data)) as pdf:
        for n,page in enumerate(pdf.pages,1):
            text=page.extract_text() or '';texts.append(text)
            if '보장분석 요약 리포트' in text:
                markers=[]
                # Retain full category labels; use detail rows below to resolve merged-cell placement.
                chars=[c for c in page.chars if 29*page.width/595 <= c['x0'] < 95*page.width/595 and c['top']>150]
                blocks=[]
                for c in sorted(chars,key=lambda c:(c['top'],c['x0'])):
                    if not blocks or c['top']-blocks[-1][-1]['top']>12:blocks.append([c])
                    else:blocks[-1].append(c)
                for b in blocks:
                    lo=min(c['top'] for c in b);hi=max(c['bottom'] for c in b)
                    label=cell(page,29,95,lo-1,hi+1)
                    if len(norm(label))<40:markers.append(((lo+hi)/2,label))
                for top,bottom,contract in anchors(page,473,528):
                    y=(top+bottom)/2;lo=top-2;hi=bottom+2
                    company=cell(page,100,167,lo,hi)
                    product=cell(page,167,303,lo,hi)
                    coverage=cell(page,303,428,lo,hi)
                    amount=cell(page,428,473,lo,hi)
                    expiry=cell(page,528,577,lo,hi)
                    if not coverage or not re.fullmatch(r'[\d,]+(?:\.\d+)?',amount):
                        warnings.append(f'{n}쪽 {contract}: 담보명·금액 확인 필요');continue
                    category=min(markers,key=lambda m:abs(m[0]-y))[1] if markers else ''
                    summaries.append(dict(company=company or '확인 필요',product=product,coverage=coverage,amount=amount+'만원',contract_date=contract,expiry_date=expiry,category=category,source_page=n,source_y=round(y,2)))
            elif '상품별 보험 가입현황' in text:
                header=[c for c in page.chars if 90*page.height/842<c['top']<135*page.height/842]
                big=max((c['size'] for c in header),default=18)
                titlechars=[c for c in header if abs(c['size']-big)<.5]
                product=cell(page,25,570,min((c['top'] for c in titlechars),default=102)-1,max((c['bottom'] for c in titlechars),default=123)+1)
                company=cell(page,25,570,85*page.height/842,102*page.height/842)
                previous=''
                for top,bottom,contract in anchors(page,415,491):
                    if top<220*page.height/842:continue
                    lo=top-2;hi=bottom+2
                    coverage=cell(page,129,339,lo,hi)
                    amount=cell(page,339,415,lo,hi)
                    expiry=cell(page,491,570,lo,hi)
                    category=cell(page,25,129,lo,hi)
                    if category:previous=category
                    if not coverage or not (re.fullmatch(r'[\d,]+(?:\.\d+)?',amount) or amount=='-'):
                        warnings.append(f'{n}쪽 {contract}: 상세표 행 확인 필요');continue
                    details.append(dict(company=company,product=product,coverage=coverage,amount=amount+'만원' if amount!='-' else '확인 필요',contract_date=contract,expiry_date=expiry,category=category or previous,source_page=n,source_y=round((top+bottom)/2,2)))
        page_count=len(pdf.pages)
    if not summaries and not details:
        warnings.append("지원하는 보장분석 표를 찾지 못했습니다. 이미지 PDF 또는 다른 양식은 원본 확인이 필요합니다.")
    result=reconcile_rows(summaries,details)
    first='\n'.join(texts[:2]);name=re.search(r'([가-힣]{2,5})님을\s*위한',first);dt=re.search(r'작성일자\s*(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',first)
    return dict(customer=name[1] if name else '확인 필요',report_date=f'{dt[1]}.{int(dt[2]):02d}.{int(dt[3]):02d}' if dt else '확인 필요',coverages=result,page_count=page_count,extraction_warnings=warnings,summary_row_count=len(summaries),detail_row_count=len(details))


def reconcile_rows(summaries, details):
    # Match on contract title, amount, coverage prefix and month. Ambiguity is retained, not guessed.
    matched_details=set();rows=[]
    for s in summaries:
        candidates=[(i,d) for i,d in enumerate(details) if (not d.get('company') or compatible(s['company'],d['company'])) and compatible(s['product'],d['product']) and compatible(s['coverage'],d['coverage']) and (s['amount']==d['amount'] or d['amount']=='확인 필요') and d['contract_date'].startswith(s['contract_date']) and (d['expiry_date'].startswith(s['expiry_date']) or s['expiry_date']==d['expiry_date'])]
        exact=[x for x in candidates if norm(x[1]['category'])==norm(s['category'])]
        if exact:candidates=exact
        distinct={(norm(d.get('company','')),norm(d['product']),norm(d['coverage']),d['contract_date'],d['expiry_date']) for _,d in candidates}
        r=dict(s);r['source_pages']=[s['source_page']];r['categories']=[];r['source_records']=[dict(s)];r['verification_notes']=[]
        if len(distinct)==1 and candidates:
            d=candidates[0][1]
            r.update(product=d['product'],coverage=d['coverage'],contract_date=d['contract_date'],expiry_date=d['expiry_date'],category=d['category'])
            if d.get('company') and compatible(s['company'],d['company']):r['company']=d['company']
            if d['amount']=='확인 필요':
                r['amount']='확인 필요';r['verification_notes'].append('상세표 금액 미표기 · 요약표 금액 대조 필요')
            for i,d in candidates:
                matched_details.add(i);r['source_pages'].append(d['source_page']);r['source_records'].append(dict(d))
                if d['category'] not in r['categories']:r['categories'].append(d['category'])
            r['verification_notes'].append('상품별 상세표·요약표 대조')
        else:
            r['categories']=[s['category']]
            r['verification_notes'].append('상세표 연결 모호' if candidates else '상세표 대조 필요')
        if not r['categories']:r['categories']=[r['category']]
        r['source_pages']=sorted(set(r['source_pages']))
        rows.append(r)
    # A detail-only entry must not disappear when the summary is incomplete.
    for i,d in enumerate(details):
        if i in matched_details:continue
        companies={s['company'] for s in summaries if compatible(s['product'],d['product']) and d['contract_date'].startswith(s['contract_date'])}
        r=dict(d,company=d.get('company') or (next(iter(companies)) if len(companies)==1 else '확인 필요'),categories=[d['category']],source_pages=[d['source_page']],source_records=[dict(d)],verification_notes=['상세표에서만 확인 · 계약 연결 확인 필요'])
        rows.append(r)
    merged={}
    for r in rows:
        key=tuple(norm(r[k]) for k in ('company','product','coverage','amount','contract_date','expiry_date'))
        if key in merged:
            old=merged[key]
            for k in ('categories','source_pages','verification_notes'):
                old[k]=list(dict.fromkeys(old[k]+r[k]))
            old['source_records']+=r['source_records']
        else:merged[key]=r
    result=list(merged.values())
    for r in result:
        r['category']=' · '.join(r['categories'])
        # Repeated categories may be two indistinguishable contracts, not a combined benefit.
        evidence={(x['source_page'],x['source_y']):x for x in r['source_records']}
        r['source_records']=list(evidence.values())
        counts={}
        for x in evidence.values():
            if len(x['contract_date'])==10:
                cat=norm(x['category']);counts[cat]=counts.get(cat,0)+1
        if any(n>1 for n in counts.values()):
            r['verification_notes'].append('동일 조건 계약 구분 필요 · 증권번호 확인')
        notes=[]
        if incomplete(r['coverage']) or incomplete(r['product']):notes.append('원본 명칭 잘림 가능성')
        if any('필요' in x or '모호' in x for x in r['verification_notes']):notes.append('원본 대조 필요')
        if not r['company'] or r['company']=='확인 필요' or incomplete(r['company']):notes.append('회사명 확인 필요')
        r['extraction_status']=' · '.join(notes) if notes else '상세표 대조 완료'
        r['source_pages']=sorted(r['source_pages'])
    return result
