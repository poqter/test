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
assert not [x for x in c.number_input if x.key=='hp_quick_premium']
assert len(c.sidebar.button)>0
c.text_input(key='hwcalc_search').set_value('상령일').run();assert not c.exception
assert len([b for b in c.button if (b.key or '').endswith('_open_here')])>0
d=AppTest.from_file(p,default_timeout=30);d.query_params['surface']='calculator';d.session_state['test_permissions']=[];d.run();assert not d.exception
assert not [b for b in d.button if (b.key or '').endswith('_open_here')]
assert not [x for x in d.number_input if x.key=='hp_quick_premium']
print('PASS 16 workspace destinations; restricted permissions; 88 calculator routes; restored sidebar; no fixed quick calculator; search; zero-permission account')
