import json
from pathlib import Path
import pytest
from hwarang_academy.education.interactive import answers_for
from hwarang_academy.education.onboarding import completion
from modules.shared.maintenance import blocked

COURSE=json.loads((Path(__file__).parents[1]/'hwarang_academy/education/foundation.json').read_text())
def test_curriculum_and_completion():
    required={**COURSE,'lessons':[l for l in COURSE['lessons'] if not l.get('optional')]}
    assert len(required['lessons'])==18
    assert sum(l['mentor_required'] for l in required['lessons'])==3
    rows=[dict(lesson_id=l['id'],revision=1,status='submitted') for l in required['lessons']]
    assert completion(required,rows)==(18,0,False)
    for r in rows:
        if r['lesson_id'].startswith('m'):r['status']='approved'
    assert completion(required,rows)==(18,3,True)
    rows[-1]['status']='revision_requested'
    assert completion(required,rows)==(17,2,False)
    assert blocked(COURSE['id'],{'role':'user'})
    assert not blocked(COURSE['id'],{'role':'super_admin'})

def test_contract_submission_derived_from_choices_not_pass_flag():
    s=dict(roles=['이서연 · 엄마','박하준 · 자녀','박하준 · 자녀'],amounts=['5만 원','1,000만 원','500만 원'],period='1',finalRoles=['0','0','1'],finalAmount='0',finalPeriod='0',evidence='1')
    a=answers_for('l02',s)
    assert all(a[k]==1 for k in ('roles','amounts','period','final'))
    s.update(roles=['박민수 · 아빠']*3,passed=[True]*4)
    assert answers_for('l02',s)['roles']==0
    s['evidence']='0'
    assert answers_for('l02',s)['final']==0

def test_choices_and_limits():
    assert answers_for('l01',{'pick':1,'transfer':2})['transfer']==2
    assert answers_for('m1',{'answers':[1,2,0]})['q2']==0
    with pytest.raises(ValueError):answers_for('l01',{'x':'x'*9000})
