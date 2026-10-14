from pathlib import Path
from streamlit.testing.v1 import AppTest
p=str(Path(__file__).with_name('harness.py'))
a=AppTest.from_file(p,default_timeout=30).run();assert not a.exception,a.exception
assert len([b for b in a.button if (b.key or '').startswith('hw_home_launch_')])==13
next(b for b in a.button if b.key=='hw_home_launch_comparison_builder').click().run();assert not a.exception
assert a.session_state['active_app']=='comparison_builder'
b=AppTest.from_file(p,default_timeout=30);b.session_state['test_allowed']=['insurance_claim_guide'];b.run();assert not b.exception
assert [x.key for x in b.button if (x.key or '').startswith('hw_home_launch_')]==['hw_home_launch_insurance_claim_guide']
c=AppTest.from_file(p,default_timeout=30);c.query_params['surface']='calculator';c.run();assert not c.exception,c.exception
assert len([b for b in c.button if (b.key or '').endswith('_open_here')])==88
c.number_input(key='hp_quick_premium').set_value(200000).run();assert not c.exception
assert any(m.value=='48,000,000원' for m in c.metric)
c.button(key='hp_quick_full').click().run();assert not c.exception,c.exception
assert c.session_state['hwcalc_open']=='총 납입보험료계산기'
assert c.session_state['hw.money_values']['a_total_premium']==200000
assert c.session_state['a_total_months']==240
assert c.session_state['a_total_paid']==0
c.button(key='hwcalc_back_catalog').click().run();assert not c.exception
assert c.number_input(key='hp_quick_premium').value==200000 # home input survives detail/back
c.text_input(key='hwcalc_search').set_value('상령일').run();assert not c.exception
assert len([b for b in c.button if (b.key or '').endswith('_open_here')])>0
d=AppTest.from_file(p,default_timeout=30);d.query_params['surface']='calculator';d.session_state['test_permissions']=[];d.run();assert not d.exception
assert not [b for b in d.button if (b.key or '').endswith('_open_here')]
assert not [x for x in d.number_input if x.key=='hp_quick_premium']
print('PASS 16 workspace destinations; restricted permissions; 88 calculator routes; quick result; detail/back; search; zero-permission account')
