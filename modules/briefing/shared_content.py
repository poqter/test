"""Immutable common customer content and per-sender references."""
from copy import deepcopy
from hashlib import sha256
import json
from .public_body import public_html
from .sharing import share_url
from .weather import weather_html
IDENTITY='__HW_IDENTITY_9e21__'
TOKEN='__HW_TOKEN_9e21__'
WEATHER='__HW_WEATHER_9e21__'
VISIBLE_WEATHER=('status','reason','region_code','region_name','date','condition','morning','afternoon','low','high','guidance')

def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def split_packet(packet,base):
    common=deepcopy(packet)
    for key in ('sender','asset_version','rendered_html'):common.pop(key,None)
    weather=common['body'].pop('weather_forecast',None)
    visible={k:weather[k] for k in VISIBLE_WEATHER if k in weather} if weather else {}
    common['reader_version']='20261026-shared-content'
    if any(marker in json.dumps(common,ensure_ascii=False) for marker in (IDENTITY,TOKEN,WEATHER)):
        raise ValueError('Reserved rendering marker in content')
    template=public_html({**common,'sender':{'name':IDENTITY,'position':''}},canonical_url=share_url(base,TOKEN),image_url=share_url(base,TOKEN,'preview'))
    template=template.replace('<div class="reader-heading-weather"></div>','<div class="reader-heading-weather">'+WEATHER+'</div>')
    content={'packet':common,'html_template':template}
    weather_record={'payload':visible,'rendered_html':weather_html(visible) if visible else ''}
    preview_id=digest({'sender':packet['sender'],'date':packet['requested_date'],'design':'preview-20261026'})
    content_id,weather_id=digest(content),digest(weather_record)
    key=digest({'content':content_id,'weather':weather_id,'sender':packet['sender']})
    return {'content_id':content_id,'content':content,'weather_id':weather_id,'weather':weather_record,'preview_id':preview_id,'reuse_key':key,'sender':packet['sender']}
