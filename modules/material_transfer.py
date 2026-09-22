"""Explicit allowlisted, session-local source snapshots. No full customer objects."""
from datetime import date, datetime, timezone
from decimal import Decimal
from .consultation_documents import fingerprint
from .calculator_catalog import MODES
from .calculator_exports import formatted_results


def candidate(source, state):
    if source=='consultation_helper':
        values=[state.get('b_summary_'+k,'') for k in ('topic','facts','priorities','pending','next')]
        body=state.get('b_summary_edit','')
        alias=state.get('b_alias','') if state.get('b_summary_include_alias') else ''
        reviewed=fingerprint(['summary',body,True,alias,date.today().isoformat()])
        if not body.strip() or state.get('b_summary_source')!=fingerprint(values) or state.get('b_summary_review')!=reviewed:
            return None
        fields={'상담 요약':body}
        assumptions='입력한 상담 사실과 미확인 사항을 직접 검토한 요약입니다. 자동 지급·가입 판정이 아닙니다.'
        signature=fingerprint([values,body,reviewed])
    elif source=='quick_calculators':
        result=state.get('a_calculation')
        mode=state.get('a_mode',state.get('hw.draft.quick_calculators',{}).get('fields',{}).get('a_mode'))
        if not result or state.get('a_review_token')!=result['token'] or mode!=result['title']:
            return None
        kind,_,specs,_,_=MODES[result['title']]
        inputs=[]
        if kind in ('age','change'):
            for key,label in [('a_birth','생년월일'),('a_reference','기준일')]:
                value=state.get(key)
                if value is None:return None
                inputs.append((label,value.isoformat()))
        else:
            for key,label,typ,default,low,high in specs:
                value=state.get(f'a_{kind}_{key}',default)
                raw=Decimal(str(value)).quantize(Decimal('.01'))
                rendered=f'{raw:,.2f}만원' if typ=='money' else f'{raw}%' if typ=='rate' else str(value)
                inputs.append((label,rendered))
        if inputs!=result['inputs']:return None
        fields=dict(formatted_results(result['values']))
        # Birth date is intentionally excluded; optional numeric assumptions remain selectable.
        for label,value in inputs:
            if label!='생년월일':fields['입력 · '+label]=value
        assumptions=result['formula']+'\n'+result['assumptions']
        signature=fingerprint([result['token'],inputs,fields,assumptions])
    else:
        raise ValueError('허용되지 않은 원본 도구입니다.')
    envelope=state.get('hw.draft.'+source,{})
    return {'source_page':source,'input_revision':envelope.get('input_revision',0),
            'signature':signature,'fields':fields,'assumptions':assumptions}


def selected_payload(source,selected,state):
    value=candidate(source,state)
    if not value or not selected or any(key not in value['fields'] for key in selected):
        raise ValueError('원본에서 현재 내용을 검토하고 가져올 항목을 선택해 주세요.')
    return {**value,'fields':{key:value['fields'][key] for key in selected},
            'created_at':datetime.now(timezone.utc).isoformat(),'reviewed':False}


def is_current(payload,state):
    value=candidate(payload['source_page'],state)
    return bool(value and value['signature']==payload['signature'])


def payload_text(payload):
    return '\n\n'.join(f'{key}\n{value}' for key,value in payload['fields'].items())+'\n\n계산·상담 가정\n'+payload['assumptions']
