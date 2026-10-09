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
