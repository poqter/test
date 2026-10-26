"""Public packets are built from saved, validated facts; never from browser input."""
from hashlib import sha256
import json
from urllib.parse import urlencode
from .public_body import customer_body, public_html, public_pdf, preview_png


def share_url(base, token, asset=None):
    return base+'?'+urlencode({'token':token,**({'asset':asset} if asset else {})})


def build_packet(snapshot, briefing, revision, sender, base, token):
    body=customer_body(snapshot.get('content_payload') or {})
    packet={'schema':'hwarang-share-v3','body':body,'briefing_date':briefing['briefing_date'],
        'sender':{'name':str(sender['name']),'position':str(sender['position'])},
        'edition':{'number':int(revision.get('revision_no') or 1),
        'corrected_at':revision.get('generated_at') if revision.get('revision_type')=='correction' else None}}
    version=sha256(json.dumps(packet,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]
    packet['asset_version']=version
    packet['rendered_html']=public_html(packet,canonical_url=share_url(base,token),
        image_url=share_url(base,token,'preview'),pdf_url=share_url(base,token,'pdf'))
    return packet


def packet_assets(packet):
    return {'preview.png':('image/png',preview_png(packet)),
            'briefing.pdf':('application/pdf',public_pdf(packet))}


PROFILE_ORDER = ('MARKET', 'NEWS', 'INSURANCE')


def combine_bodies(bundles, selected_codes=None):
    """Same-date customer projections; deduplicate events and canonical sources."""
    dates = {str(b['briefing']['briefing_date']) for b in bundles}
    if not bundles:
        raise ValueError('공유 가능한 게시본이 없습니다.')
    sections, issues, seen_keys, seen_urls = [], [], set(), set()
    flow = []
    metrics = []
    extras={"weather":[],"calendar":[]}
    for bundle in sorted(bundles, key=lambda b: PROFILE_ORDER.index(b['briefing']['profile_code'])):
        body = customer_body(bundle['snapshot'].get('content_payload') or {})
        for key in extras:extras[key].extend(body.get(key) or [])
        selected = []
        for row in body['issues']:
            key = row.get('event_key')
            urls = {s['url'] for s in row.get('sources') or []}
            if (key in seen_keys or urls & seen_urls) and body['profile_code'] != 'INSURANCE' and not (body['profile_code']=='NEWS' and row.get('headline_sufficient')):
                continue
            seen_keys.add(key); seen_urls.update(urls)
            item = {**row, 'section_label': body['profile_label'], 'section_code': body['profile_code']}
            selected.append(item); issues.append(item)
        sections.append({'profile_code': body['profile_code'], 'profile_label': body['profile_label'],
                         'as_of': body.get('as_of'), 'briefing_date': str(bundle['briefing']['briefing_date']), 'article_count': len(selected)})
        if body['profile_code'] == 'MARKET':
            flow = body.get('market_flow') or []
            metrics = body.get('market_metrics') or []
    if selected_codes:
        labels = {'MARKET':'경제·금융', 'NEWS':'종합뉴스', 'INSURANCE':'보험업계'}
        present = {s['profile_code'] for s in sections}
        sections += [{'profile_code':c, 'profile_label':labels[c], 'briefing_date':None, 'as_of':None, 'article_count':0} for c in PROFILE_ORDER if c in selected_codes and c not in present]
        sections.sort(key=lambda s: PROFILE_ORDER.index(s['profile_code']))
    return {'schema': 'hwarang-public-v2', 'profile_code': 'COMBINED',
            'profile_label': '오늘의 브리핑', 'as_of': max(s['as_of'] or '' for s in sections),
            'sections': sections, 'issues': issues, 'market_flow': flow, 'market_metrics': metrics, 'research': {},**extras}


def render_packet(packet, base, token):
    version = sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    packet['asset_version'] = version
    packet['rendered_html'] = public_html(packet, canonical_url=share_url(base, token),
        image_url=share_url(base, token, 'preview'), pdf_url=share_url(base, token, 'pdf'))
    return packet


def build_combined_packet(bundles, sender, base, token, *, selected_codes=None, requested_date=None, weather=None):
    body=combine_bodies(bundles, selected_codes)
    if weather is not None:
        body["weather_forecast"]=weather
    return render_packet({'schema': 'hwarang-share-v3', 'body': body, 'reader_version':'20261026-share-preview',
        'selected_profiles':list(selected_codes or [b['briefing']['profile_code'] for b in bundles]),
        'requested_date':requested_date or max(str(b['briefing']['briefing_date']) for b in bundles),
        'briefing_date': max(str(b['briefing']['briefing_date']) for b in bundles),
        'sender': {'name': str(sender['name']), 'position': str(sender['position'])},
        'components': [{'profile_code': b['briefing']['profile_code'], 'revision_id': str(b['revision']['id']),
                        'revision_no': int(b['revision'].get('revision_no') or 1), 'briefing_date':str(b['briefing']['briefing_date'])} for b in bundles],
        'edition': {'number': max(int(b['revision'].get('revision_no') or 1) for b in bundles),
            'corrected_at': max((b['revision'].get('generated_at') or '' for b in bundles
                                 if b['revision'].get('revision_type') == 'correction'), default=None)}}, base, token)
