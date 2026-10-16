"""KB text-PDF adapter. No network, disk persistence or workbook intermediary.

Only the recognized A4 KB detailed-coverage layout is supported. Ambiguous
records are retained for review rather than discarded as absent coverage.
Amounts in coverage records are in 만원; premiums are in 원.
"""
from collections import OrderedDict
from datetime import date
from io import BytesIO
import re
import unicodedata


def norm(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))


def amount(value):
    text = norm(value).replace(",", "").replace("원", "")
    if text in ("0", "-"):
        return 0
    if not re.fullmatch(r"(?:\d+(?:\.\d+)?억)?(?:\d+(?:\.\d+)?만)?(?:\d+(?:\.\d+)?)?", text) or not text:
        raise ValueError("읽을 수 없는 가입금액: " + str(value))
    total = 0.0
    for unit, factor in (("억", 10000), ("만", 1)):
        match = re.match(r"(\d+(?:\.\d+)?)" + unit, text)
        if match:
            total += float(match[1]) * factor
            text = text[match.end():]
    if text:
        total += float(text) / 10000
    return round(total, 6)


def extract_kb_pdf(content, password=None):
    import pdfplumber
    if not content.startswith(b"%PDF-"):
        raise ValueError("PDF 형식이 아닙니다.")
    contracts = []
    customer = age = source_date = None
    expected_count = None
    with pdfplumber.open(BytesIO(content), password=password) as document:
        if len(document.pages) > 100:
            raise ValueError("KB PDF는 100쪽 이하만 지원합니다.")
        for page_no, page in enumerate(document.pages, 1):
            # Header inspection avoids extracting every repeated summary table.
            header = page.crop((0, 0, page.width, 65)).extract_text() or ""
            if "기준담보" not in header:
                continue
            person = re.search(r"([^\s]+)\s*님의", header)
            person_age = re.search(r"\((\d+)세", header)
            timestamp = re.search(r"20\d\d-\d\d-\d\d", header)
            if person and person_age:
                if customer and customer != person[1]:
                    raise ValueError("서로 다른 고객의 페이지가 포함되어 있습니다.")
                customer, age = person[1], person_age[1]
            if timestamp:
                if source_date and timestamp[0] != source_date:
                    raise ValueError("조회일이 다른 페이지가 섞여 있습니다.")
                source_date = timestamp[0]
            if "전체 계약리스트" in header and expected_count is None:
                # KB count is the first large number in the top summary band.
                band = page.crop((0, 65, page.width, 140)).extract_words()
                nums = [w for w in band if re.fullmatch(r"\d+", w['text'])]
                if nums:
                    expected_count = int(sorted(nums, key=lambda w: w['x0'])[0]['text'])
            if "상품별 가입담보상세" not in header:
                page.close()
                continue
            if abs(page.width - 595) > 2 or abs(page.height - 842) > 2:
                raise ValueError("지원하지 않는 KB 상세담보 페이지 크기입니다.")
            words = page.extract_words()
            def region(x0, y0, x1, y1):
                return " ".join(w['text'] for w in words if x0 <= w['x0'] < x1 and y0 <= w['top'] < y1)
            company = region(30, 75, 350, 96)
            product = region(30, 96, 570, 132)
            continuation = re.search(r"\((\d+)/(\d+)\)\s*$", product)
            product = re.sub(r"\s*\(\d+/\d+\)\s*$", "", product)
            periods = re.search(r"(\d{4}-\d\d-\d\d)~(\d{4}-\d\d-\d\d)", norm(region(100, 155, 400, 180)))
            terms = re.search(r"([^/]*)/(\d+)년/(.*)", norm(region(400, 135, 570, 155)))
            premium_text = region(400, 155, 570, 180)
            premium_match = re.search(r"([\d,]+)원", premium_text)
            if not company or not product or not periods or not terms:
                raise ValueError(f"{page_no}쪽 계약 머리글을 인식하지 못했습니다. 기존 엑셀 업로드를 이용하세요.")
            if not premium_match and "보험료미제공" not in norm(premium_text):
                raise ValueError(f"{page_no}쪽 보험료를 인식하지 못했습니다.")
            current = dict(company=company, product=product, start=periods[1], end=periods[2],
                           cycle=terms[1], years=int(terms[2]), maturity=terms[3],
                           monthly=int(premium_match[1].replace(',', '')) if premium_match else 0,
                           premium_missing=premium_match is None, fully_paid="납입완료" in premium_text,
                           pages=[page_no], rows=[], continuation_total=int(continuation[2]) if continuation else 1)
            if continuation and int(continuation[1]) > 1:
                if not contracts or any(norm(contracts[-1][k]) != norm(current[k]) for k in ('company','product','start','end')):
                    raise ValueError(f"{page_no}쪽의 앞 계약 페이지가 없습니다.")
                current = contracts[-1]
                if int(continuation[1]) != len(current['pages']) + 1:
                    raise ValueError("상세담보 페이지 순서가 맞지 않습니다.")
                current['pages'].append(page_no)
            else:
                contracts.append(current)
            anchors = [w for w in words if 30 <= w['x0'] < 55 and 195 < w['top'] < 790 and w['text'].isdigit()]
            if not anchors:
                raise ValueError(f"{page_no}쪽 상세담보 행을 인식하지 못했습니다.")
            for i, anchor in enumerate(anchors):
                top = anchor['top'] - 2
                bottom = anchors[i+1]['top'] - 2 if i+1 < len(anchors) else min(anchor['top']+25, 790)
                number = int(anchor['text'])
                if number != len(current['rows']) + 1:
                    raise ValueError(f"{page_no}쪽 담보번호 누락 또는 중복이 있습니다.")
                kind = region(55, top, 90, bottom)
                raw = region(90, top, 365, bottom)
                standard = region(365, top, 512, bottom)
                money = region(512, top, 570, bottom)
                if kind not in ('정액', '실손') or not raw or not standard:
                    raise ValueError(f"{page_no}쪽 {number}번 담보 열을 인식하지 못했습니다.")
                current['rows'].append(dict(number=number, kind=kind, raw=raw, standard=standard,
                                            value=amount(money), page=page_no))
            page.close()
    if not customer or not age or not source_date or not contracts:
        raise ValueError("KB 텍스트 PDF의 고객정보/상세담보를 찾지 못했습니다. 스캔본·요약본은 기존 엑셀을 이용하세요.")
    if expected_count is None or expected_count != len(contracts):
        raise ValueError(f"전체 계약 수({expected_count})와 상세 계약 수({len(contracts)})가 다릅니다. 전체 PDF를 업로드하세요.")
    if any(len(c['pages']) != c['continuation_total'] for c in contracts):
        raise ValueError("상세담보 연속 페이지가 누락되었습니다.")
    return dict(customer_name=customer, age=age, source_date=source_date, contracts=contracts)


DIRECT = {
    '질병사망':'질병사망', '상해사망':'재해(상해)사망', '암진단':'일반암',
    '소액암진단(유사암진단)':'유사암', '고액암진단':'고액암',
    '뇌혈관질환진단':'뇌혈관', '뇌졸중진단':'뇌졸중', '뇌출혈진단':'뇌출혈',
    '허혈성심장질환진단':'허혈성심장질환', '급성심근경색진단':'급성심근경색증',
    '질병수술':'질병수술', '상해수술':'상해수술', '질병종수술':'질병종수술', '상해종수술':'상해종수술',
    '암수술':'암수술', '뇌혈관질환수술':'뇌혈관질환수술', '허혈성심장질환수술':'허혈성심장질환수술',
    '질병입원일당':'질병입원', '상해입원일당':'상해입원', '암입원일당':'암입원',
    '간병인질병입원일당':'간병인지원입원일-질병', '간병인상해입원일당':'간병인지원입원일-상해',
    '질병간호·간병통합서비스사용일당':'질병간호간병통합입원일당',
    '상해간호·간병통합서비스사용일당':'상해간호간병통합입원일당',
    '교통사고처리지원금':'교통사고처리지원금', '교통사고처리지원금(6주미만진단)':'교통사고처리지원금(6주미만)',
    '자동차사고변호사선임비용':'변호사선임비용', '교통사고벌금(대인)':'운전자벌금(대인)',
    '교통사고벌금(대물)':'운전자벌금(대물)', '자동차사고부상위로금':'자동차사고부상위로금',
    '가족생활배상책임':'일상생활배상책임', '일상생활배상책임':'일상생활배상책임',
    '치과치료(보존)':'치아보존치료비', '보철치료(영구치)':'치아보철치료비',
    '골절진단':'골절진단비', '화상진단':'화상진단비', '깁스치료':'깁스치료비',
    '질병통원':'질병통원', '상해통원':'상해통원', '암통원':'암통원', '치과통원':'치과통원',
    '응급실내원비':'응급실내원비', '항암방사선약물치료비':'항암방사선약물치료비',
    '표적항암약물허가치료비':'표적항암약물허가치료비',
    '중증질환(뇌혈관)산정특례대상':'뇌혈관산정특례',
    '중증질환(심장)산정특례대상':'심장질환산정특례',
    '치매진단(경증)':'경증치매',
}


def classify(row):
    standard = norm(row['standard']).replace('(유병자)', '')
    raw = norm(row['raw'])
    value = row['value']
    if standard == '특정질병진단':
        for key in ('통풍', '대상포진'):
            if re.search(key+r'진단비',raw):
                return [(key+'진단비',value)], None
    if standard == '치매진단' and raw == '중증치매':
        return [('중증치매',value)], '중증치매 담보: 일시금·분할 지급 여부 확인'
    if standard == '고액항암치료비' and '표적항암약물허가치료' in raw:
        return [('표적항암약물허가치료비',value)], None
    if standard == '응급치료' and '비응급' not in raw:
        return [('응급실내원비',value)], '응급환자 조건의 담보만 반영'
    if standard in ('타인사망교통사고처리지원금','타인부상교통사고처리지원금','중상해교통사고처리지원금'):
        return [('교통사고처리지원금',value)], '확인 필요: 사고 조건별 한도를 단순 합산하지 않음'
    if standard in DIRECT:
        return [(DIRECT[standard], value)], None
    for disease, label in [('상해','재해(상해)장해'),('질병','질병후유장해')]:
        if standard == disease+'후유장해':
            reason = '후유장해 3% 환산: 적용 장해율 확인 필요'
            # Do not include a stated higher threshold in the 3% estimate.
            threshold = re.search(r'\((\d+)[~\-]',raw)
            if threshold and int(threshold[1]) > 3:
                return [(label+'80%이상',value)], '3%보다 높은 최소 장해율: 3% 환산에서 제외'
            return [(label+'3%일경우',round(value*.03,6)), (label+'80%이상',value)], reason
        if standard == disease+'80%이상후유장해':
            return [(label+'80%이상', value)], None
    if row['kind'] == '실손' and standard.startswith('상해+질병'):
        return [('상해입원(실손)',value),('질병입원(실손)',value)], '확인 필요: 상해·질병 공통한도'
    if row['kind'] == '실손' and standard.startswith(('질병(', '상해(')):
        disease = standard[:2]
        if '입원+통원' in standard:
            return [(disease+'입원(실손)',value),(disease+'통원(실손)',value)], '확인 필요: 입원·통원 통합한도, 원문 반복행 유지'
        if '입원의료비' in standard:
            return [(disease+'입원(실손)',value)], None
        if any(k in standard for k in ['통원의료비','외래의료비','처방조제료']):
            return [(disease+'통원(실손)',value)], '실손 통원: 외래·처방의 개별 한도 확인'
    return [], '기존 분류에 자동 연결하지 않은 담보'


def convert_kb(raw, calculation_month):
    from modules.consultation.analyzer_model import DISPLAY_NAMES, _group_for
    year, month = map(int, calculation_month.split('-'))
    date(year, month, 1)
    if calculation_month < raw['source_date'][:7]:
        raise ValueError('계산 기준월은 PDF 조회월보다 빠를 수 없습니다.')
    contracts, details, issues = [], [], []
    labels = list(DISPLAY_NAMES)
    values = {label: [] for label in labels}
    for index,c in enumerate(raw['contracts']):
        y,m = map(int,c['start'][:7].split('-'))
        total_count=c['years']*12
        supported_payment = c['cycle']=='월납' and total_count > 0 and not c['premium_missing']
        paid_count=min(max((year-y)*12+month-m+1,0),total_count) if supported_payment else 0
        if c['fully_paid'] and supported_payment:
            paid_count=total_count
        known_payment = supported_payment
        contracts.append(dict(company=c['company'],product=c['product'],start=c['start'],
            coverage_period=c['start'].replace('-','.')+'~'+('종신' if c['end'].startswith('9999') else c['end'][:4]),
            payment_count=f'{paid_count}/{total_count}회' if known_payment else '-',
            payment_cycle=(c['cycle'] or '확인 필요')+' / '+(str((y*12+m-1+total_count-1)//12) if known_payment else '확인 필요'),
            monthly=c['monthly'],total=total_count*c['monthly'] if known_payment else 0,
            paid=paid_count*c['monthly'],remaining=(total_count-paid_count)*c['monthly'] if known_payment else 0,
            premium_missing=c['premium_missing'], payment_unknown=not known_payment))
        if not known_payment:
            issues.append(dict(contract=index,label='납입정보',reason='보험료 미제공 또는 납입주기·기간 확인 필요',page=c['pages'][0]))
        sums={label:0 for label in labels}
        pending=set()
        for row in c['rows']:
            targets, reason=classify(row)
            for label,value in targets:
                sums[label]+=value
                if reason and reason.startswith('확인 필요:'):
                    pending.add(label)
            details.append(dict(contract=index,**row,targets=[t[0] for t in targets],reason=reason or '직접 분류'))
            if reason or any(label in ('질병종수술','상해종수술','치아보존치료비') for label,_ in targets):
                issues.append(dict(contract=index,label=', '.join(t[0] for t in targets) or row['standard'],
                    reason=reason or '서로 다른 지급조건의 담보 합계: 개별 금액 확인',page=row['page']))
        for label in labels:
            values[label].append('확인 필요' if label in pending else round(sums[label],6))
    return dict(customer_name=raw['customer_name'],age=raw['age'],contracts=contracts,
        coverages=[dict(label=k,display=DISPLAY_NAMES[k],group=_group_for(k),values=values[k]) for k in labels],
        source_date=raw['source_date'],calculation_month=calculation_month,details=details,issues=issues,source_type='kb_pdf')


def parse_kb_pdf(content, calculation_month):
    from modules.shared.runtime_cache import cached, digest_bytes
    import copy
    raw=cached('parse:analyzer:kb', 'kb-v1:'+digest_bytes(content),lambda:extract_kb_pdf(content))
    return convert_kb(copy.deepcopy(raw),calculation_month)
