"""Officer income-classification cap, separate from corporate deduction cap."""
from datetime import date,timedelta
import calendar
from .finance_models import D,num,FinanceResult
from .personal_tax_models import AS_OF
NAME='임원퇴직금 한도계산기';M=10**12
FIELDS={NAME:[('임원 취임일','2014-01-01','날짜',0),('최종 재직일 (2026년)','2026-12-31','날짜',0),
 ('퇴직 전 법정 기간 총급여 연평균 환산액',180000000,'원',M),('2019년 말 이전 법정 기간 총급여 연평균 환산액',120000000,'원',M),
 ('지급 예정 퇴직급여',500000000,'원',M),('2011년 말 퇴직 가정 금액 (해당자 별도 확인)',0,'원',M),
 ('법인 정관·지급규정 등에 따른 손금 한도 확인액',702000000,'원',M),
 ('법인 손금 한도 별도 확인','아니요','선택',('아니요','예'))]}

def months_ceil(start,end):
 if end<start:return 0
 stop=end+timedelta(days=1)
 n=(stop.year-start.year)*12+stop.month-start.month
 y,m=divmod(start.year*12+start.month-1+n,12)
 anniversary=date(y,m+1,min(start.day,calendar.monthrange(y,m+1)[1]))
 return n+(stop>anniversary)

def executive(start='2014-01-01',end='2026-12-31',recent=180000000,old=120000000,payment=500000000,pre2012=0,corp_limit=702000000,confirmed='아니요'):
 try:
  start=start if type(start) is date else date.fromisoformat(str(start))
  end=end if type(end) is date else date.fromisoformat(str(end))
 except ValueError:raise ValueError('취임일·최종 재직일을 확인해 주세요.') from None
 if end.year!=2026 or start>end:raise ValueError('2026년 퇴직이며 취임일이 최종 재직일 이전이어야 합니다.')
 recent,old,payment,pre2012,corp_limit=[num(v) for v in (recent,old,payment,pre2012,corp_limit)]
 if confirmed not in ('예','아니요'):raise ValueError('법인 한도 확인 여부를 확인해 주세요.')
 if start>=date(2012,1,1) and pre2012:raise ValueError('2012년 이후 취임이면 2011년 말 퇴직 가정 금액은 0원입니다.')
 if start<date(2012,1,1) and not pre2012:raise ValueError('2012년 이전 재직자는 당시 퇴직 가정 금액을 확인해 입력해야 합니다.')
 m3=months_ceil(max(start,date(2012,1,1)),min(end,date(2019,12,31)))
 m2=months_ceil(max(start,date(2020,1,1)),end)
 cap3=old*D(m3)/12*D('.3');cap2=recent*D(m2)/12*D('.2');cap=pre2012+cap3+cap2
 excess=max(D(0),payment-cap)
 metrics={'개인 퇴직소득 한도':cap,'근로소득으로 분류되는 초과액':excess,'한도 내 퇴직급여':min(payment,cap),
 '2012~2019 한도':cap3,'2020년 이후 한도':cap2,'2012~2019 근무 개월':m3,'2020년 이후 근무 개월':m2}
 if confirmed=='예':metrics.update({'법인 확인 손금 한도':corp_limit,'법인 손금 한도 초과액':max(D(0),payment-corp_limit)})
 else:metrics['법인 손금 한도']='정관·지급규정 등 별도 확인 전'
 return FinanceResult(metrics,'개인 한도=2011년 말 퇴직 가정 금액+2019년 기준 연평균급여×1/10×2012~2019개월/12×3+퇴직 기준 연평균급여×1/10×2020년 이후개월/12×2.',
 [f'법령 대조 기준일 {AS_OF} · 소득세법22조(개인 퇴직소득)와 법인세법 시행령44조(법인 손금)는 서로 다른 한도입니다.',
 '현실적인 퇴직, 연속된 단일 임원 재직기간을 가정합니다. 마지막으로 재직한 날을 입력하며 1개월 미만 잔여기간을 올림합니다. 중간정산·재입사·다른 법인 합산기간은 미지원입니다.',
 '최근 급여는 2020년 이후 재직기간과 퇴직 전3년 중 짧은 기간의 총급여를 연평균 환산합니다. 과거 급여는2012~2019재직기간과2019년 말 이전3년 중 짧은 기간을 사용합니다. 비과세 급여 제외입니다.',
 '정관 배수를 개인 한도의2배·3배와 혼동하지 않습니다. 법인 손금 한도는 정관·위임 지급규정에 따른 금액 등을 확인한 값이며 이 화면에서 자격을 자동 확정하지 않습니다.',
 '표시된 초과액은 소득분류 금액이며 납부세액이 아닙니다. 법인 손금불산입의 소득처분과 개인 근로소득 전환을 중복 합산하지 않습니다.'],
 [{'기간':'2012~2019','개월':m3,'기준 연급여':old,'개인 한도':cap3},{'기간':'2020년 이후','개월':m2,'기준 연급여':recent,'개인 한도':cap2}],
 units={'2012~2019 근무 개월':'개월','2020년 이후 근무 개월':'개월'})

def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return executive(*values)
