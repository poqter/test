"""Server-only OpenAI adapter. No automatic retries; no keys in presentation."""
from dataclasses import dataclass
import json, os, io, wave, math
import requests
from jsonschema import validate
from .contracts import CUSTOMER, COACH, EVALUATOR, INSTRUCTIONS

class ProviderError(RuntimeError):
    def __init__(self,message,*,uncertain=True):
        super().__init__(message);self.uncertain=uncertain

@dataclass
class Config:
    api_key: str=''
    customer_model: str='gpt-4.1-mini'
    coach_model: str='gpt-4.1-mini'
    evaluator_model: str='gpt-4.1-mini'
    transcription_model: str='gpt-4o-mini-transcribe'
    speech_model: str='gpt-4o-mini-tts'
    customer_credits: int=1
    coach_credits: int=1
    evaluator_credits: int=5
    timeout: int=60

    @classmethod
    def from_mapping(cls,mapping):
        conf=dict(mapping.get('simulator_ai',{}) or {})
        # An existing briefing OpenAI key can be reused; no cross-feature model setting changes.
        key=conf.pop('api_key','') or mapping.get('OPENAI_API_KEY','') or os.getenv('OPENAI_API_KEY','')
        allowed=set(cls.__dataclass_fields__)-{'api_key'}
        out=cls(api_key=str(key),**{k:v for k,v in conf.items() if k in allowed})
        for k in ('customer_credits','coach_credits','evaluator_credits'):
            if not isinstance(getattr(out,k),int) or getattr(out,k)<1:raise ValueError('AI 차감 단위를 확인해 주세요.')
        return out
    def model(self,role):return getattr(self,role.lower()+'_model')
    def credits(self,role):return getattr(self,role.lower()+'_credits')


def wav_seconds(data):
    try:
        with wave.open(io.BytesIO(data),'rb') as w:
            seconds=w.getnframes()/w.getframerate()
    except (wave.Error,EOFError,ZeroDivisionError) as exc:
        raise ValueError('WAV 음성 파일을 확인해 주세요.') from exc
    if not 0<seconds<=180:raise ValueError('음성은 한 번에 3분 이내로 녹음해 주세요.')
    return math.ceil(seconds)

class OpenAIProvider:
    def __init__(self,config,http=None):self.config=config;self.http=http or requests.Session()
    def _post(self,path,**kwargs):
        if not self.config.api_key:raise ProviderError('OpenAI API 키가 설정되지 않았습니다.',uncertain=False)
        try:
            res=self.http.post('https://api.openai.com/v1/'+path,
                headers={'Authorization':'Bearer '+self.config.api_key}, timeout=(10,self.config.timeout),**kwargs)
        except requests.RequestException as exc:
            raise ProviderError('응답을 확인하지 못했습니다. 중복 호출을 막기 위해 요청을 보류했습니다.') from exc
        if res.status_code>=400:
            uncertain=res.status_code>=500 or res.status_code in (408,409)
            raise ProviderError('AI 요청이 거절되었거나 처리 상태를 확인하지 못했습니다. 설정과 사용 기록을 확인해 주세요.',uncertain=uncertain)
        return res
    def generate(self,role,context):
        schema_role='EVALUATOR' if role=='COACH' and context.get('_practice_report') else role
        schema={'CUSTOMER':CUSTOMER,'COACH':COACH,'EVALUATOR':EVALUATOR}[schema_role]
        response=self._post('responses',json={'model':self.config.model(role),'store':False,
            'instructions':INSTRUCTIONS[schema_role], 'input':json.dumps(context,ensure_ascii=False),
            'max_output_tokens':{'CUSTOMER':1200,'COACH':1200,'EVALUATOR':5000}[schema_role],
            'text':{'format':{'type':'json_schema','name':'hwarang_'+role.lower(),'strict':True,'schema':schema}}})
        try:
            data=response.json()
            if data.get('status')!='completed':raise ValueError('incomplete')
            raw=''.join(c.get('text','') for o in data.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text')
            result=json.loads(raw);validate(result,schema)
            if role=='CUSTOMER' and (not result['reply'].strip() or len(result['reply'])>2000):raise ValueError('reply')
            return {'result':result,'usage':data.get('usage',{}),'provider_id':data.get('id'), 'model':data.get('model',self.config.model(role))}
        except Exception as exc:
            raise ProviderError('AI 응답 형식을 검증하지 못했습니다. 재호출 없이 확인 대기 상태로 보관합니다.') from exc
    def transcribe(self,audio):
        seconds=wav_seconds(audio)
        response=self._post('audio/transcriptions',data={'model':self.config.transcription_model,'language':'ko','response_format':'json'},
                            files={'file':('speech.wav',audio,'audio/wav')})
        try:
            data=response.json();text=str(data['text']).strip()
            if not text or len(text)>2400:raise ValueError('empty or long')
            return {'result':{'text':text},'usage':data.get('usage',{}),'model':self.config.transcription_model,'seconds':seconds}
        except Exception as exc:raise ProviderError('음성 인식 결과를 확인하지 못했습니다. 이 결과는 평가하지 않습니다.') from exc
    def speak(self,text,voice,style="calm"):
        if voice not in ('alloy','nova','onyx','coral','sage'):raise ValueError('지원하지 않는 목소리입니다.')
        if not text.strip() or len(text)>2000:raise ValueError('재생할 문장 길이를 확인해 주세요.')
        response=self._post('audio/speech',json={'model':self.config.speech_model,'input':text,'voice':voice,
            'response_format':'wav','instructions':'자연스러운 한국어 고객 대화. 과장하지 마세요. '+{'calm':'차분하고 편안하게 말하세요.','cautious':'신중하게 잠깐씩 쉬어 말하세요.','terse':'짧고 담백하게 말하세요.','questioning':'질문하는 의도를 또렷하게 표현하세요.','senior':'여유 있는 속도로 또렷하게 말하세요.'}.get(style,'차분하게 말하세요.')})
        data=response.content
        try:seconds=wav_seconds(data)
        except ValueError as exc:raise ProviderError('생성된 음성 길이를 확인하지 못했습니다.') from exc
        return {'result':{'audio_generated':True},'audio':data,'seconds':seconds,'usage':{},'model':self.config.speech_model}
