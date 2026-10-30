import json
from pathlib import Path
from hwarang_academy.education.onboarding import completion

COURSE=json.loads((Path(__file__).parents[1]/'hwarang_academy/education/onboarding.json').read_text())

def test_course_contract():
    assert [l['day'] for l in COURSE['lessons']]==list(range(1,31))
    assert len({l['id'] for l in COURSE['lessons']})==30
    assert [l['day'] for l in COURSE['lessons'] if l['mentor_required']]==[7,14,21,30]
    for l in COURSE['lessons']:
        assert len(l['body'])>100 and len(l['practice'])>20
        assert all(0<=q['answer']<len(q['options']) for q in l['quiz'])

def test_certification_requires_current_revision_and_reviews():
    rows=[dict(lesson_id=l['id'],revision=1,status='submitted') for l in COURSE['lessons']]
    assert completion(COURSE,rows)==(30,0,False)
    for row in rows:
        if row['lesson_id'] in ['d07','d14','d21','d30']:row['status']='approved'
    assert completion(COURSE,rows)==(30,4,True)
    rows[6]['status']='revision_requested'
    assert completion(COURSE,rows)==(29,3,False)
    rows[6]['status']='approved';rows[6]['revision']=0
    assert completion(COURSE,rows)==(29,3,False)
