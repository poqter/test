from copy import deepcopy
from datetime import date
import unittest
from hwarang_academy.exams.component import process
from hwarang_academy.exams.analytics import summarize,in_window
class Repo:
 def __init__(self):self.a={'id':'a','status':'active','revision':2,'answers':{'1':2},'flags':[],'cursor':0};self.calls=[]
 def call(self,action,**payload):
  self.calls.append(action)
  if action=='get':return deepcopy(self.a)
  return payload
class Tests(unittest.TestCase):
 def test_lost_reply(self):
  r=Repo();a=process(r,{'action':'save','payload':{'revision':1,'answers':{'1':2},'flags':[],'cursor':0}},r.a)
  self.assertEqual(a['revision'],2);self.assertEqual(r.calls,['get'])
 def test_conflict(self):
  r=Repo()
  with self.assertRaisesRegex(ValueError,'CONFLICT'):process(r,{'action':'save','payload':{'revision':1,'answers':{'1':1},'flags':[],'cursor':0}},r.a)
 def test_server_expired(self):
  r=Repo();r.a['status']='submitted';self.assertEqual(process(r,{'action':'save','payload':{}},r.a)['status'],'submitted')
 def test_latest_and_practice(self):
  members=[{'id':'1'},{'id':'2'}]
  rows=[{'id':str(i),'user_id':'1','mode':mode,'status':'submitted','started_at':day,'submitted_at':day,'result':{'sections':[{'name':'손해','score':score,'passed':score>=60}]}} for i,(mode,day,score) in enumerate([('exam','2026-10-01T01:00:00Z',90),('exam','2026-10-02T01:00:00Z',50),('practice','2026-10-03T01:00:00Z',100)])]
  p,s=summarize(members,rows);self.assertEqual(s['손해'],{'total':1,'passed':0});self.assertTrue(p[0]['below']);self.assertEqual(p[1]['state'],'미참여');self.assertEqual(p[1]['scores'],[])
 def test_kst_boundary(self):
  self.assertTrue(in_window({'started_at':'2026-10-26T15:01:00Z'},date(2026,10,27),date(2026,10,27)))
if __name__=='__main__':unittest.main()
