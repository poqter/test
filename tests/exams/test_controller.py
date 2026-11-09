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
 def test_aborted_attempts_do_not_change_completed_scores(self):
  members=[{'id':'1'},{'id':'2'},{'id':'3'}]
  rows=[
   {'id':'done','user_id':'1','mode':'exam','status':'submitted','started_at':'2026-10-01T01:00:00Z','submitted_at':'2026-10-01T02:00:00Z','result':{'sections':[{'name':'손해','score':80,'passed':True}]}},
   {'id':'stopped','user_id':'1','mode':'exam','status':'aborted','started_at':'2026-10-02T01:00:00Z','updated_at':'2026-10-02T02:00:00Z','result':None},
   {'id':'only-stopped','user_id':'2','mode':'exam','status':'aborted','started_at':'2026-10-03T01:00:00Z','result':None},
   {'id':'newer','user_id':'3','mode':'exam','status':'submitted','started_at':'2026-10-05T01:00:00Z','submitted_at':'2026-10-05T02:00:00Z','result':{'sections':[{'name':'손해','score':50,'passed':False}]}},
   {'id':'older-stop','user_id':'3','mode':'exam','status':'aborted','started_at':'2026-10-04T01:00:00Z','updated_at':'2026-10-06T01:00:00Z','result':None},
  ]
  people,subjects=summarize(members,rows)
  self.assertEqual([p['state'] for p in people],['학습 완료','중단','학습 완료'])
  self.assertEqual([p['latest_aborted'] for p in people],[True,True,False])
  self.assertTrue(all(p['has_aborted'] for p in people))
  self.assertEqual(people[0]['scores'][0]['score'],80)
  self.assertEqual(subjects['손해'],{'total':2,'passed':1})
if __name__=='__main__':unittest.main()

