"""Durable operation claims, provider calls and existing credit/Voice reconciliation."""
from copy import deepcopy
from hashlib import sha256
import json
from . import domain as d
from .conversation import explicit_close, closing_result, guard_response
from .provider import ProviderError, wav_seconds
from modules.shared.ai_guardrails import (reserve_ai_request, start_ai_request, finalize_ai_request,
    reserve_voice_request, finalize_voice_request, release_ai_session)

class PendingRequest(RuntimeError):pass

class Runtime:
    def __init__(self,repo,provider):self.repo=repo;self.provider=provider;self.auth=repo.auth
    def key(self,s,role,payload):
        raw=json.dumps([s['id'],s['version'],role,payload],ensure_ascii=False,sort_keys=True)
        return sha256(raw.encode()).hexdigest()
    def _finalize(self,request,role,envelope,failed=False):
        if role in ('TRANSCRIBE','SPEECH'):
            return finalize_voice_request(self.auth,request_id=request,result_status='failed' if failed else 'completed',
                                          actual_seconds=0 if failed else envelope['seconds'])
        return finalize_ai_request(self.auth,request_id=request,result_status='failed' if failed else 'completed',
                                   actual_credits=0 if failed else envelope['credits'])
    def invoke(self,s,role,payload):
        key=self.key(s,role,payload if not isinstance(payload,bytes) else sha256(payload).hexdigest())
        claim=self.repo.claim(s,key,role)
        request=claim.get('request_id')
        if not claim.get('fresh'):
            if claim['status'] in ('received','completed'):
                envelope=claim['result']
                if claim['status']=='received':
                    self._finalize(request,role,envelope,failed=bool(envelope.get('result',{}).get('_rejected')))
                    self.repo.update(key,'completed',request,envelope)
                if envelope.get('result',{}).get('_rejected'):
                    self.repo.save(s,key)
                    raise ProviderError('사용할 수 없는 응답의 정산을 확인했습니다. 다시 보내 주세요.',uncertain=False)
                return key,envelope
            if claim['status']=='failed':
                # No automatic external retry even for safe failures. Advance checkpoint before another attempt.
                raise PendingRequest('실패한 요청입니다. 저장 상태를 새로 불러온 뒤 다시 시도해 주세요.')
            raise PendingRequest('이 요청은 이미 처리 중이거나 응답 확인 대기입니다. 중복 비용 방지를 위해 재호출하지 않습니다.')
        try:
            if role in ('TRANSCRIBE','SPEECH'):
                seconds=wav_seconds(payload) if role=='TRANSCRIBE' else 180
                reservation=reserve_voice_request(self.auth,user_id=s['owner'],academy_session_id=s['id'],turn_no=len(s['turns'])+1,
                                                 idempotency_key=key,requested_seconds=seconds)
            else:
                reservation=reserve_ai_request(self.auth,user_id=s['owner'],academy_session_id=s['id'],turn_no=len(s['turns'])+1,
                    purpose=role,idempotency_key=key,estimated_credits=self.provider.config.credits(role))
            request=reservation.get('request_id')
            if role in ('TRANSCRIBE','SPEECH') and int(reservation.get('allowed_voice_seconds') or 0)<seconds and reservation.get('request_status')=='reserved':
                raise ProviderError('이번 음성 요청을 처리할 Voice 잔여 시간이 부족합니다.',uncertain=False)
            if reservation.get('duplicate') or reservation.get('request_status')!='reserved':
                raise ProviderError('이용 권한·잔여량 또는 기존 요청 상태를 확인해 주세요.',uncertain=bool(reservation.get('duplicate')))
            status=start_ai_request(self.auth,request_id=request)
            if status.get('request_status')!='processing':raise ProviderError('요청을 시작할 수 없습니다.',uncertain=True)
            self.repo.update(key,'processing',request)
        except Exception as exc:
            # Reservation/transport failure may already have committed; never infer zero cost.
            known_rejection=any(code in str(exc) for code in ('AI_SERVICE_DISABLED','AI_TEXT_DISABLED','AI_ASSESSMENT_DISABLED','AI_VOICE_DISABLED','AI_SIMULATOR_PERMISSION_REQUIRED','AI_ASSESSMENT_PERMISSION_REQUIRED','AI_VOICE_PERMISSION_REQUIRED','INACTIVE_USER','ACADEMY_SESSION_INVALID_OR_CLOSED','INVALID_VOICE_SECONDS'))
            uncertain=(not isinstance(exc,ProviderError) or exc.uncertain) and not known_rejection
            self.repo.update(key,'uncertain' if uncertain else 'failed',request)
            if not uncertain:
                if request:self._finalize(request,role,{},True)
                self.repo.save(s,key)
            raise
        try:
            if role=='TRANSCRIBE':envelope=self.provider.transcribe(payload)
            elif role=='SPEECH':envelope=self.provider.speak(payload['text'],payload['voice'],payload.get('style','calm'))
            else:envelope=self.provider.generate(role,payload)
        except ProviderError as exc:
            if exc.response is not None:
                envelope={**exc.response,'credits':0,'purpose':role,'cost_usd':None,'request_id':request}
                # Preserve provider usage and unknown monetary cost; no usable
                # training reply means the learner's reserved credits are released.
                self.repo.update(key,'received',request,envelope)
                self._finalize(request,role,envelope,failed=True)
                self.repo.update(key,'completed',request,envelope)
                self.repo.save(s,key)
                raise
            if exc.uncertain:
                self.repo.update(key,'uncertain',request)
            else:
                self._finalize(request,role,{},True)
                self.repo.update(key,'failed',request)
                self.repo.save(s,key)
            raise
        envelope['credits']=self.provider.config.credits(role) if role not in ('TRANSCRIBE','SPEECH') else 0
        envelope['purpose']=role;envelope['cost_usd']=None;envelope['request_id']=request
        # Audio bytes are transient: never copied into the durable request log or learning record.
        persistent={k:v for k,v in envelope.items() if k!='audio'}
        self.repo.update(key,'received',request,persistent)
        self._finalize(request,role,envelope)
        self.repo.update(key,'completed',request,persistent)
        return key,envelope
    def _save(self,s,key,env):
        record={k:v for k,v in env.items() if k not in ('result','audio')}
        if not any(x.get('request_id')==record['request_id'] for x in s['usage']):s['usage'].append(record)
        saved=self.repo.save(s,key)
        if saved['ended']:release_ai_session(self.auth,user_id=saved['owner'],academy_session_id=saved['id'])
        return saved
    def send(self,s,text):
        if s['ended'] or s['stage_complete']:raise ValueError('현재 상담 단계에서 입력할 수 없습니다.')
        text=str(text).strip()
        if not text or len(text)>2400:raise ValueError('답변은 1~2,400자로 입력해 주세요.')
        if explicit_close(text):
            out=deepcopy(s);d.apply_turn(out,text,closing_result())
            saved=self.repo.save(out)
            release_ai_session(self.auth,user_id=saved['owner'],academy_session_id=saved['id'])
            return saved
        ctx=d.prompt_context(s,text);ctx['conversation']=ctx['conversation']+[{'role':'advisor','text':text,'turn':len(s['turns'])+1,'stage':s['stage']}]
        key,env=self.invoke(s,'CUSTOMER',ctx)
        out=deepcopy(s);d.apply_turn(out,text,guard_response(s,text,env['result']))
        return self._save(out,key,env)
    def hint(self,s):
        if s['mode']!='PRACTICE' or s['ended']:raise ValueError('자유 연습에서만 힌트를 사용할 수 있습니다.')
        cache_key=f"{s['branch']}:{len(s['turns'])}:{s['stage']}"
        if cache_key in s['hint_cache']:return s
        ctx={'goal':d.GOALS[s['stage']], 'conversation':s['messages'],'public':s['case']['public_state']}
        key,env=self.invoke(s,'COACH',ctx)
        out=deepcopy(s);out['hint_cache'][cache_key]=env['result'];out['hints'].append({'turn':len(s['turns'])+1,'branch':s['branch']})
        return self._save(out,key,env)
    def evaluate(self,s):
        if not s['ended']:raise ValueError('종료 후 피드백을 생성할 수 있습니다.')
        if s.get('report'):return s
        if not s['turns']:
            out=deepcopy(s);out['report']={'rows':[],'status':'평가 자료 부족','total_score':None,'notice':'제출한 답변이 없습니다.'}
            return self.repo.save(out)
        # Formal EVALUATOR permission stays unchanged; practice coaching does not impersonate a formal assessment.
        role='EVALUATOR' if s['mode']=='ASSESSMENT' else 'COACH'
        # Practice feedback uses the evaluator schema/instructions but COACH permission and tariff.
        context=d.report_context(s)
        if role=='COACH':context['_practice_report']=True
        key,env=self.invoke(s,role,context)
        out=deepcopy(s)
        try:out['report']=d.validate_report(out,env['result'])
        except ValueError:
            out['report']={'rows':[],'status':'評価 근거 확인 필요'.replace('評価','평가'),'total_score':None,
                           'notice':'AI 피드백의 근거를 검증하지 못했습니다. 자동 재호출하지 않습니다.'}
        return self._save(out,key,env)
    def transcribe(self,s,audio):
        if s['ended']:raise ValueError('종료한 상담에서는 음성을 입력할 수 없습니다.')
        wav_seconds(audio)  # Validate before taking a durable claim.
        key,env=self.invoke(s,'TRANSCRIBE',audio)
        return self._save(deepcopy(s),key,env),env['result']['text']
    def speak(self,s,text,voice):
        if voice not in ('alloy','nova','onyx','coral','sage') or not text.strip() or len(text)>2000:raise ValueError('재생할 목소리와 문장을 확인해 주세요.')
        key,env=self.invoke(s,'SPEECH',{'text':text,'voice':voice,'style':'senior' if s['case']['customer_state'].get('age',0)>=60 else s['personality']})
        return self._save(deepcopy(s),key,env),env.get('audio')
