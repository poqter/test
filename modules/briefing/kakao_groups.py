"""Per-user Kakao recipient groups, accessed with the signed-in user's token."""
from __future__ import annotations

from modules.shared.hwarang_auth import HwarangAuthService, SupabaseConfig

_PATH = '/rest/v1/hwarang_kakao_groups'


class KakaoGroups:
    def __init__(self, secrets, auth_state):
        self.auth = HwarangAuthService(SupabaseConfig.from_mapping(secrets))
        self.token = str((auth_state or {}).get('access_token') or '')
        if not self.token:
            raise ValueError('다시 로그인한 뒤 발송 명단을 이용해 주세요.')

    def list(self):
        return self.auth._request('GET', _PATH, access_token=self.token,
            params={'select': 'id,name,recipients,version,updated_at', 'order': 'updated_at.desc'}) or []

    def create(self, name):
        return self.auth._request('POST', _PATH, access_token=self.token,
            json={'name': name, 'recipients': []}, prefer='return=representation')

    def save(self, group, recipients):
        result = self.auth._request('PATCH', _PATH, access_token=self.token,
            params={'id': 'eq.' + group['id'], 'version': 'eq.' + str(group['version'])},
            json={'recipients': recipients}, prefer='return=representation')
        if not result:
            raise ValueError('다른 화면에서 명단이 변경됐습니다. 다시 열어 확인해 주세요.')

    def delete(self, group):
        result = self.auth._request('DELETE', _PATH, access_token=self.token,
            params={'id': 'eq.' + group['id'], 'version': 'eq.' + str(group['version'])},
            prefer='return=representation')
        if not result:
            raise ValueError('그룹이 변경됐습니다. 다시 열어 확인해 주세요.')


def load_template(repo):
    rows = repo._request('GET', '/rest/v1/hwarang_kakao_template',
        params={'id': 'eq.briefing-v1', 'select': 'file_bytes', 'limit': '1'})
    if not rows or not str(rows[0].get('file_bytes', '')).startswith('\\x'):
        raise ValueError('발송 엑셀 서식을 준비하지 못했습니다.')
    return bytes.fromhex(rows[0]['file_bytes'][2:])
