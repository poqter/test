"""All identities come from the authenticated server session, never widget inputs."""
from uuid import UUID
class Repository:
    def __init__(self,auth,owner):self.auth=auth;self.owner=str(UUID(owner))
    def rpc(self,name,**kw):
        return self.auth._request('POST','/rest/v1/rpc/hwarang_studio_'+name,admin=True,
                                  json={'p_actor':self.owner,**kw})
    def save(self,s,op=None):return self.rpc('store',p_data=s,p_version=s['version'],p_op=op)
    def load(self,sid):return self.rpc('get',p_id=str(UUID(sid)))
    def rows(self):return self.rpc('list') or []
    def claim(self,s,key,role):return self.rpc('claim',p_id=s['id'],p_version=s['version'],p_op=key,p_purpose=role)
    def update(self,key,status,request=None,result=None):
        return self.rpc('request_update',p_op=key,p_status=status,p_request=request,p_result=result)
    def recipients(self):return self.rpc('recipients') or []
    def share(self,sid,recipient,fields,active=True):
        return self.rpc('share',p_id=sid,p_recipient=str(UUID(recipient)),p_fields=list(fields),p_active=active)
    def manager(self,sid=None):return self.rpc('manager',p_id=sid)
    def review(self,sid,note,response=False):return self.rpc('review',p_id=sid,p_note=note,p_response=response)
    def reviews(self,sid):return self.rpc('reviews',p_id=sid) or []
