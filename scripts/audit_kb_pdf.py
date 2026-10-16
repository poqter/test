"""Compare locally supplied KB PDF/XLSX pairs. Never embeds customer fixtures."""
import argparse, json, re, sys
from pathlib import Path
from difflib import SequenceMatcher
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.consultation.analyzer_pdf import extract_kb_pdf, convert_kb, norm
from modules.consultation.analyzer_model import _parse_source_file_uncached, DEFAULT_COVERAGES
import openpyxl

def compare(raw, workbook_path, month):
    new=convert_kb(raw,month)
    old=_parse_source_file_uncached(workbook_path.read_bytes())
    book=openpyxl.load_workbook(workbook_path,data_only=True)
    ws=book['계약사항'];pairs=[];used=set();differences=[];allcells=[]
    def add(kind,product,label,before,after,reason=''):
        differences.append(dict(kind=kind,product=product,label=label,before=before,after=after,reason=reason))
    for i,c in enumerate(old['contracts']):
        start=str(ws.cell(i+9,4).value)[:10].replace('.','-')
        options=[j for j,n in enumerate(new['contracts']) if norm(n['company'])==norm(c['company']) and n['start']==start and j not in used]
        scores=sorted([(SequenceMatcher(None,norm(c['product']),norm(new['contracts'][j]['product'])).ratio(),j) for j in options],reverse=True)
        if not scores or scores[0][0]<.5 or (len(scores)>1 and scores[0][0]==scores[1][0]):
            add('계약매칭',c['product'],'계약',c,None,'동일 보험사·가입일에서 상품 식별 불가');continue
        j=scores[0][1];used.add(j);pairs.append((i,j))
        for key in ('company','product','coverage_period','payment_count','payment_cycle','monthly','paid','remaining','total'):
            a,b=c[key],new['contracts'][j][key]
            if a != b:
                reason='공백·유니코드 표기 차이' if norm(a)==norm(b) else '원본 표기 또는 계산 기준 차이'
                add('계약정보',c['product'],key,a,b,reason)
        before={r['label']:r['values'][i] for r in old['coverages']}
        after={r['label']:r['values'][j] for r in new['coverages']}
        for label in sorted((before.keys()|after.keys()) & set(DEFAULT_COVERAGES)):
            a,b=before.get(label,'항목 없음'),after.get(label,'항목 없음')
            records=[r for r in new['details'] if r['contract']==j and label in r['targets']]
            same=(abs(float(a)-float(b))<.000001) if isinstance(a,(int,float)) and isinstance(b,(int,float)) else a==b
            allcells.append(dict(product=c['product'],label=label,before=a,after=b,match=same))
            if not same:
                add('항목구성' if label not in before or label not in after else '보장금액',c['product'],label,a,b,'; '.join(sorted(set(r['reason'] for r in records))) or '자동 분류 또는 통합한도 처리 차이')
    if [j for _,j in pairs] != list(range(len(new['contracts']))):
        add('계약순서','','출력 열 순서',[c['product'] for c in old['contracts']],[c['product'] for c in new['contracts']],'PDF는 원문 계약 순서 유지')
    for j in set(range(len(new['contracts'])))-used:
        add('계약매칭',new['contracts'][j]['product'],'계약',None,new['contracts'][j],'엑셀 대응 계약 없음')
    for key in ('customer_name','age'):
        if old[key]!=new[key]:add('고객정보','',key,old[key],new[key],'PDF 원문과 중간 엑셀 불일치')
    unmapped=[dict(product=new['contracts'][r['contract']]['product'],**r) for r in new['details'] if not r['targets']]
    book.close()
    return dict(customer=old['customer_name'],pdf_customer=new['customer_name'],source_date=raw['source_date'],month=month,
        contracts=len(old['contracts']),matched_contracts=len(pairs),details=len(new['details']),
        coverage_cells=len(allcells),coverage_mismatches=sum(not c['match'] and c['before']!='항목 없음' and c['after']!='항목 없음' for c in allcells),
        differences=differences,unmapped=unmapped,allcells=allcells)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pdf',required=True);p.add_argument('--xlsx',required=True);p.add_argument('--month',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=compare(extract_kb_pdf(Path(a.pdf).read_bytes()),Path(a.xlsx),a.month)
    Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print({k:v for k,v in r.items() if k not in ('differences','unmapped','allcells')})
