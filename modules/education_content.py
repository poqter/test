"""Validated, packaged education data; no customer writes or shared cache."""
import json
from pathlib import Path
from datetime import date
from .app_registry import APP_BY_ID
from .consultation_documents import fingerprint


def valid_text(value):
    return isinstance(value,str) and bool(value.strip())


def validate(data):
    if not isinstance(data,dict):raise ValueError('교육 콘텐츠는 객체 형식이어야 합니다.')
    if data.get('schema_version')!=1:raise ValueError('교육 콘텐츠 버전이 올바르지 않습니다.')
    for key in ('edited_at','source','verification_status'):
        if not valid_text(data.get(key)):raise ValueError('교육 콘텐츠 기준 정보가 없습니다.')
    date.fromisoformat(data['edited_at'])
    ids=set()
    for section in ('terms','simulations','quizzes'):
        if not isinstance(data.get(section),list) or not data[section]:raise ValueError('교육 항목이 없습니다.')
        for item in data[section]:
            if not isinstance(item,dict) or not valid_text(item.get('id')) or item['id'] in ids:raise ValueError('교육 항목 ID가 없거나 중복되었습니다.')
            ids.add(item['id'])
            required=('title','body','category') if section=='terms' else ('question','explanation')
            if not all(valid_text(item.get(key)) for key in required):raise ValueError('교육 항목의 필수 문구가 없습니다.')
            if section!='terms':
                options=item.get('options');answer=item.get('answer')
                if not isinstance(options,list) or len(options)<2 or not all(valid_text(v) for v in options) or len(set(options))!=len(options):raise ValueError('문항 선택지가 올바르지 않습니다.')
                if type(answer) is not int or not 0<=answer<len(options):raise ValueError('문항 정답 번호가 올바르지 않습니다.')
    for section in ('checklists','guides','faq'):
        if not isinstance(data.get(section),dict) or not data[section]:raise ValueError('교육 자료가 없습니다.')
        for title,value in data[section].items():
            if not valid_text(title):raise ValueError('교육 자료 제목이 없습니다.')
            if section=='faq':
                if not valid_text(value):raise ValueError('FAQ 답변이 없습니다.')
            elif not isinstance(value,list) or not value or not all(valid_text(v) for v in value):raise ValueError('교육 자료 형식이 올바르지 않습니다.')
            if section=='guides' and (len(value)!=3 or value[1] not in APP_BY_ID):raise ValueError('권장 도구 경로가 올바르지 않습니다.')
    return data


def load_education():
    with (Path(__file__).resolve().parents[1]/'data/education_content.json').open(encoding='utf-8') as handle:
        return validate(json.load(handle))


def search_terms(items,query,category='전체'):
    words=query.casefold().split()
    return [item for item in items if (category=='전체' or item['category']==category) and all(word in (item['title']+' '+item['body']).casefold() for word in words)]


def question_version(item):return fingerprint(item)


def record_answer(attempts,item,selected):
    if selected not in item['options']:raise ValueError('선택지 중 하나를 선택해 주세요.')
    previous=attempts.get(item['id'],{})
    if previous.get('version')!=question_version(item):previous={}
    correct=selected==item['options'][item['answer']]
    return {'version':question_version(item),'selected':selected,'correct':correct,
            'first_correct':previous.get('first_correct',correct),'attempts':previous.get('attempts',0)+1}


def current_attempt(attempts,item):
    result=attempts.get(item['id'])
    return result if result and result.get('version')==question_version(item) else None
