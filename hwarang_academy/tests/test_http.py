"""Real loopback HTTP contract tests for the optional local launcher."""
import json,threading,unittest,uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import run_academy_local as web

class LocalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();web.STATES.clear()
    def setUp(self):self.sid=uuid.uuid4().hex
    def post(self,kind='bootstrap',headers=None,**data):
        h={'Content-Type':'application/json','X-Hwarang-Local':web.TOKEN,'Origin':self.base}
        if headers:h.update(headers)
        payload={'session':self.sid,'view':'simulator','action':{'event_id':uuid.uuid4().hex,'kind':kind,**data}}
        req=Request(self.base+'/api/action',data=json.dumps(payload).encode(),headers=h)
        with urlopen(req,timeout=3) as response:return json.load(response)
    def test_static_home(self):
        with urlopen(self.base,timeout=3) as r:self.assertEqual(r.status,200)
    def test_hidden_source_is_not_served(self):
        with self.assertRaises(HTTPError) as e:urlopen(self.base+'/hwarang_academy/data/source/worked_scenario_rules.json',timeout=3)
        self.assertEqual(e.exception.code,404)
    def test_missing_token_rejected(self):
        with self.assertRaises(HTTPError) as e:self.post(headers={'X-Hwarang-Local':''})
        self.assertEqual(e.exception.code,403)
    def test_cross_origin_rejected(self):
        with self.assertRaises(HTTPError) as e:self.post(headers={'Origin':'https://untrusted.invalid'})
        self.assertEqual(e.exception.code,403)
    def test_real_http_chat(self):
        p0=self.post('start',scenario_id='C07-S01',mode='SOLO')
        profile=p0['session'].get('profile_id','')
        p=self.post('send',text='전체 월 보험료는 얼마인가요?',expected_turn=1)
        text=p['session']['messages'][-1]['text']
        expected={'C07-BASE':'43만원','C07-CASHFLOW':'51만원','C07-FAMILY':'38만원','C07-RENEWAL':'55만원'}
        self.assertIn(expected.get(profile,'만원'),text)
    def test_distinct_browser_session_ids(self):
        self.post('start',scenario_id='C07-S01',mode='SOLO');self.post('send',text='전체 월 보험료는 얼마인가요?',expected_turn=1)
        self.sid=uuid.uuid4().hex;p=self.post();self.assertNotIn('session',p)
    def test_api_refuses_oversized_request(self):
        req=Request(self.base+'/api/action',data=b'x'*20000,headers={'X-Hwarang-Local':web.TOKEN})
        with self.assertRaises(HTTPError) as e:urlopen(req,timeout=3)
        self.assertEqual(e.exception.code,400)

if __name__=='__main__':unittest.main()
