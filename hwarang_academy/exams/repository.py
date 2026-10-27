"""Only the trusted Streamlit server supplies the authenticated actor ID."""
class Repository:
    def __init__(self, auth, owner):
        if not owner:
            raise ValueError('로그인이 필요합니다.')
        self.auth, self.owner = auth, owner

    def call(self, action, **payload):
        return self.auth._request('POST', '/rest/v1/rpc/hwarang_exam', admin=True,
                                  json={'p_actor': self.owner, 'p_action': action, 'p_payload': payload})
