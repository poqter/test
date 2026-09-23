"""One public directory for home and portal; invalid entries fail separately."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date


def safe_url(value):
    if not isinstance(value,str) or any(c.isspace() or ord(c)<32 for c in value):raise ValueError('잘못된 URL')
    p=urlsplit(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('HTTPS 주소가 필요합니다.')
    return value


def normalize(value):return re.sub(r'[\s\-·_]+','',str(value)).casefold()


def filter_insurers(rows,query='',group='전체'):
    q=normalize(query)
    return [r for r in rows if (group=='전체' or r['group']==group) and any(q in normalize(v) for v in [r['name'],r.get('phone',''),*r.get('aliases',[])])]


def filter_resources(rows,query='',group='전체'):
    words=query.casefold().split()
    return [r for r in rows if (group=='전체' or r['group']==group) and all(w in (r['name']+' '+r['description']+' '+r['scope']).casefold() for w in words)]


def validate_catalog(data):
    if not isinstance(data,dict) or data.get('schema_version')!=1:raise ValueError('잘못된 목록 버전')
    date.fromisoformat(data['edited_at'])
    result={'schema_version':1,'edited_at':data['edited_at'],'insurers':[],'resources':[]};issues=[]
    for section,idkey in [('insurers','slug'),('resources','id')]:
        if not isinstance(data.get(section),list):raise ValueError('목록 형식 오류')
        seen=set()
        for index,row in enumerate(data[section]):
            try:
                if not isinstance(row,dict):raise ValueError('항목 형식 오류')
                identity=row[idkey]
                if not isinstance(identity,str) or not re.fullmatch(r'[a-z0-9_-]+',identity) or identity in seen:raise ValueError('중복 또는 잘못된 ID')
                for key in ('name','group','url'):
                    if not isinstance(row.get(key),str) or not row[key].strip():raise ValueError('필수 항목 없음')
                safe_url(row['url'])
                dates=('phone_verified_at','portal_checked_at') if section=='insurers' else ('content_verified_at','link_verified_at','access_checked_at')
                for key in dates:
                    if row.get(key):date.fromisoformat(row[key])
                if section=='insurers':
                    if row['group'] not in ('기본 포털','생명보험','손해보험'):raise ValueError('분류 오류')
                    if not isinstance(row.get('aliases'),list) or not all(isinstance(v,str) for v in row['aliases']):raise ValueError('별칭 오류')
                    if not isinstance(row.get('phone'),str) or (row['phone'] and not re.fullmatch(r'[0-9-]{8,15}',row['phone'])):raise ValueError('번호 형식 오류')
                    if row.get('phone_source_url'):safe_url(row['phone_source_url'])
                    if row.get('phone_verified_at') and not row.get('phone_source_url'):raise ValueError('번호 검증 출처 없음')
                else:
                    for key in ('description','scope','access_status','verification_note'):
                        if not isinstance(row.get(key),str):raise ValueError('자료 설명 오류')
                    safe_url(row['source_url'])
                seen.add(identity);result[section].append(dict(row))
            except (ValueError,KeyError,TypeError):issues.append(f'{section} {index+1}번 항목의 형식·주소를 확인하세요.')
    return result,issues


def load_catalog():
    try:
        with (Path(__file__).resolve().parents[1]/'data/portal_catalog.json').open(encoding='utf-8') as f:return validate_catalog(json.load(f))
    except (ValueError,OSError,KeyError,TypeError):
        return {'edited_at':'확인 필요','insurers':[],'resources':[]},['포털 목록 파일을 확인하세요. 다른 업무는 계속 이용할 수 있습니다.']
