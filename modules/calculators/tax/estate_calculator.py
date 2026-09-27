"""KRW input / two-view adapter around the existing Hwarang estate engine.

Supported ordinary resident estates share calculations with the old report.
Special-business eligibility and multi-beneficiary surcharge audit remain.
"""
from datetime import date
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import AS_OF
from modules.calculators.tax.inheritance_tax import calculate as legacy_calculate, spouse_statutory_share

NAME='상속세계산기';M=10**12
YESNO=('아니요','예')
GROUPS=('직계비속','직계존속','배우자 단독')
FIELDS={NAME:[
 ('상속개시일 (2026년·피상속인 거주자)',AS_OF,'날짜',0),
 ('본래 상속재산 총평가액 (금융재산 포함)',1000000000,'원',M),
 ('추정·간주 상속재산 (과세 보험금·퇴직금 등)',0,'원',M),
 ('위 재산 중 비과세·불산입액',0,'원',M),
 ('공과금',0,'원',M),
 ('확정 채무 합계 (금융채무 포함)',0,'원',M),
 ('실제 일반 장례비용',5000000,'원',M),
 ('실제 봉안시설·자연장지 비용',0,'원',M),
 ('10년 이내 상속인 사전증여 합산액',0,'원',M),
 ('5년 이내 비상속인 사전증여 합산액',0,'원',M),
 ('자녀공제 대상 자녀 수',2,'명',100),
 ('미성년자공제 대상 잔여 연수 합계 (각자 19세까지·1년 미만 올림)',0,'년',1900),
 ('65세 이상 연로자공제 대상 인원 (배우자 제외)',0,'명',100),
 ('장애인공제 대상 기대여명 연수 합계 (각자 올림·공식 통계 확인)',0,'년',10000),
 ('배우자 생존','아니요','선택',YESNO),
 ('배우자와 공동상속하는 상속인',GROUPS[0],'선택',GROUPS),
 ('배우자를 제외한 공동상속인 수 (상속포기 전)',2,'명',100),
 ('배우자 실제 상속금액',0,'원',M),
 ('5억원 이상 배우자공제의 분할·등기·신고 요건 확인','아니요','선택',YESNO),
 ('합산된 배우자 사전증여 과세표준',0,'원',M),
 ('총재산에 포함된 적격 금융재산 (최대주주 주식 등 제외)',0,'원',M),
 ('확정 채무 합계에 포함된 금융채무',0,'원',M),
 ('요건 확인된 동거주택 순가액',0,'원',M),
 ('요건·법정 한도 확인된 기타 공제 (아래 자동 가업공제 제외)',0,'원',M),
 ('선순위 상속인이 아닌 수유자 유증액 (위 총재산에 포함)',0,'원',M),
 ('선순위 상속포기로 다음 순위가 받은 금액',0,'원',M),
 ('합산 사전증여액 중 증여재산 공제 등을 차감한 공제한도 차감액',0,'원',M),
 ('적격 감정평가수수료 공제액',0,'원',M),
 ('수증자별 법정 한도를 적용한 증여세액공제 확인액',0,'원',M),
 ('외국납부 등 그 밖의 확인된 세액공제',0,'원',M),
 ('기한 내 적정 신고 3% 공제','예','선택',YESNO),
 ('실제 동원 가능한 현금성 납부재원 (재산가액과 별개)',0,'원',M),
 ('30% 세대생략 대상 재산 합계 (합산 증여 포함·대습 제외)',0,'원',M),
 ('40% 대상 재산 합계 (각 미성년 수령액 20억원 초과자만)',0,'원',M),
 ('민법1001조 대습상속 확인 재산 (위 할증 대상에서 제외)',0,'원',M),
 ('위 총재산에 더할 비상장주식 최종 평가액 (중복 제외)',0,'원',M),
 ('전체 재산에 포함된 적격 가업상속재산가액',0,'원',M),
 ('피상속인 계속 경영기간',10,'년',100),
 ('가업·상속인·중견기업 납부능력·동시공제 제한 등 요건 확인','아니요','선택',YESNO),
]}


def estate(start=AS_OF,gross=1000000000,deemed=0,excluded=0,dues=0,debt=0,
           funeral=5000000,burial=0,prior_heirs=0,prior_others=0,children=2,minor_years=0,
           elderly=0,disability_years=0,spouse='아니요',group=GROUPS[0],coheirs=2,
           spouse_actual=0,spouse_confirmed='아니요',spouse_prior_base=0,financial_assets=0,
           financial_debt=0,home=0,other_deduction=0,bequest=0,waiver=0,prior_limit=0,
           appraisal=0,gift_credit=0,other_credit=0,timely='예',liquid=0,skip30=0,skip40=0,substitution=0,extra_stock=0,business_value=0,business_years=10,business_confirmed='아니요'):
 try:start=start if type(start) is date else date.fromisoformat(str(start))
 except ValueError:raise ValueError('상속개시일을 확인해 주세요.') from None
 if start.year!=2026:raise ValueError('이 화면은 2026년 거주자 상속을 계산합니다.')
 amounts=list(map(num,(gross,deemed,excluded,dues,debt,funeral,burial,prior_heirs,prior_others,
                     spouse_actual,spouse_prior_base,financial_assets,financial_debt,home,
                     other_deduction,bequest,waiver,prior_limit,appraisal,gift_credit,other_credit,liquid)))
 gross,deemed,excluded,dues,debt,funeral,burial,prior_heirs,prior_others,spouse_actual,spouse_prior_base,financial_assets,financial_debt,home,other_deduction,bequest,waiver,prior_limit,appraisal,gift_credit,other_credit,liquid=amounts
 extra_stock,business_value=map(num,(extra_stock,business_value));gross+=extra_stock
 business_years=period(business_years,100,True)
 if business_confirmed not in YESNO:raise ValueError('가업상속 적격 확인을 선택하세요.')
 if business_value and (business_confirmed!='예' or business_years<10):raise ValueError('가업상속공제는10년 이상 계속 경영 및 모든 적격요건 확인이 필요합니다.')
 if business_value>gross+deemed-excluded:raise ValueError('가업상속재산은 전체 과세대상 재산 이하여야 합니다.')
 business_cap=D(60000000000 if business_years>=30 else 40000000000 if business_years>=20 else 30000000000 if business_years>=10 else 0)
 business_deduction=min(business_value,business_cap)
 other_deduction+=business_deduction
 children=period(children,100,True);minor_years=period(minor_years,1900,True)
 elderly=period(elderly,100,True);disability_years=period(disability_years,10000,True);coheirs=period(coheirs,100,True)
 if group not in GROUPS or any(v not in YESNO for v in (spouse,spouse_confirmed,timely)):
  raise ValueError('상속인 및 공제 요건을 확인해 주세요.')
 if excluded>gross+deemed or financial_assets>gross+deemed-excluded:
  raise ValueError('비과세·금융재산은 입력한 전체 과세대상 재산 범위를 확인해 주세요.')
 if financial_debt>debt:raise ValueError('금융채무는 확정 채무 합계에 포함되어야 합니다. 중복 차감하지 않습니다.')
 if prior_limit>prior_heirs+prior_others or spouse_prior_base>prior_heirs:
  raise ValueError('사전증여 관련 차감액은 합산 사전증여 재산 범위를 초과할 수 없습니다.')
 if bequest+waiver>gross+deemed-excluded:raise ValueError('유증·차순위 상속금액의 중복 및 총재산 범위를 확인해 주세요.')
 if spouse_actual>gross+deemed-excluded:raise ValueError('배우자 실제 상속액은 이번 상속재산 범위 내여야 합니다.')
 if spouse=='아니요' and (spouse_actual or spouse_prior_base or spouse_confirmed=='예' or group==GROUPS[2]):
  raise ValueError('배우자 없음 선택과 배우자 공제 입력이 일치하지 않습니다.')
 if spouse=='예' and group!=GROUPS[2] and not coheirs:raise ValueError('공동상속인 수를 입력하거나 배우자 단독을 선택해 주세요.')
 if spouse=='예' and spouse_actual>=500000000 and spouse_confirmed!='예':
  raise ValueError('배우자 실제 상속액이 5억원 이상이면 분할·신고 요건을 먼저 확인해 주세요. 미확인 금액에 자동 공제를 적용하지 않습니다.')
 skip30,skip40,substitution=[num(v) for v in (skip30,skip40,substitution)]
 skip_denominator=gross+deemed-excluded+prior_heirs+prior_others
 if skip30+skip40+substitution>skip_denominator:
  raise ValueError('30%·40%·대습상속 제외액은 서로 중복 없이 합산 상속재산 이내여야 합니다.')
 if skip40 and skip40<=2000000000:
  raise ValueError('40%는 미성년자 개인별 합산 수령액이 20억원을 초과할 때 적용합니다. 그 이하는 30% 대상에 포함합니다.')
 funeral_ded=min(max(funeral,D(5000000)),D(10000000))+min(burial,D(5000000))
 # Existing calculations are in 10,000 KRW. Convert once at this boundary.
 won_inputs=dict(gross_estate=gross,deemed_estate=deemed,non_taxable=excluded,public_dues=dues,
  liabilities=debt,funeral_expense=funeral_ded,prior_gifts_heirs=prior_heirs,prior_gifts_non_heirs=prior_others,
  minor_deduction=D(minor_years)*10000000,disability_deduction=D(disability_years)*10000000,
  spouse_actual_inheritance=spouse_actual,spouse_prior_gift_tax_base=spouse_prior_base,
  net_financial_assets=max(D(0),financial_assets-financial_debt),cohabiting_home_value=home,
  other_deduction=other_deduction,non_heir_bequest=bequest,inheritance_waiver_next_rank=waiver,
  prior_gift_tax_base_for_limit=prior_limit,appraisal_fee=appraisal,gift_tax_credit=gift_credit,other_tax_credit=other_credit,
  generation_skip_amount=D(0),generation_skip_30_amount=skip30,generation_skip_40_amount=skip40)
 args={k:float(v/10000) for k,v in won_inputs.items()}
 args.update(children_count=children,elderly_count=elderly,lump_mode=True,spouse_exists=spouse=='예',
  spouse_solo=group==GROUPS[2] and spouse=='예',spouse_share=spouse_statutory_share(group,coheirs) if spouse=='예' else 0,
  generation_skip_minor_over_2b=False,apply_filing_credit=timely=='예')
 r=legacy_calculate(**args)
 def w(key):return D(str(getattr(r,key)))*10000
 due=w('estimated_tax_due')
 rows=[{'항목':label,'금액':w(key)} for key,label in (
  ('gross_estate','본래·간주재산 합계'),('taxable_estate','상속세 과세가액'),('personal_or_lump','기초·인적 또는 일괄 공제'),
  ('spouse_deduction','배우자 공제'),('financial_deduction','금융재산 공제'),('home_deduction','동거주택 공제'),
  ('other_deduction','기타 확인 공제'),('deduction_limit','공제 종합한도'),('allowed_deduction','실제 적용 공제'),
  ('tax_base','과세표준'),('calculated_tax','산출세액'),('generation_skip_surcharge','세대생략 할증'),('tax_credits','증여·기타 세액공제'),('filing_credit','신고세액공제'),
  ('estimated_tax_due','상속세 추정액'))]
 rows.append({'항목':'가업상속 공제 (공제종합한도 적용 전)','금액':business_deduction})
 rows.insert(1,{'항목':'장례·봉안시설 공제','금액':funeral_ded})
 return FinanceResult({'상속세 추정액':due,'과세표준':w('tax_base'),'배우자 공제':w('spouse_deduction'),
  '세대생략 할증':w('generation_skip_surcharge'),'금융재산 공제':w('financial_deduction'),'장례비용 공제':funeral_ded,
  '가업상속 공제 (공제종합한도 적용 전)':business_deduction,'입력한 현금재원 대비 부족액':max(D(0),due-liquid)},
  '기존 화랑 상속세 엔진을 공유합니다. 재산−불산입−공과금·채무·장례비+사전증여→공제 종합한도 내 상속공제→누진세율→확인된 세액공제→신고공제3%.',
  [f'법령 대조 기준일 {AS_OF} · 2026년 거주자 일반 상속 · 상속세및증여세법 제19~27조.',
   '배우자 단독 상속이면 일괄5억원을 선택하지 않습니다. 공동상속 지분은 배우자1.5 대 직계존비속 각1이며 포기 전 구성을 입력합니다. 실제 상속5억원 이상은 분할·등기·신고 요건 확인이 필요합니다.',
   '일반 장례비는 최소500만·최대1000만원, 봉안시설·자연장지는 추가최대500만원입니다. 금융채무는 총채무에 이미 포함된 금액으로 입력해 재산에서 두 번 차감하지 않습니다.',
   '공제 종합한도에서 사전증여 관련 금액을 차감하는 규정은 과세가액5억원 초과 때에만 적용합니다. 기타 유증·상속포기 금액은 별도 차감합니다.',
   '미성년·장애인 공제는 각 개인의 잔여 연수/공식 기대여명에1년 미만 올림 후 합산합니다. 장애인 통계표 자동 조회와 적격 동거가족 판정은 아직 미구현입니다.',
   '세대생략은 각 수령자별로 30% 대상과 미성년·수령액20억원초과 40% 대상을 판정한 뒤 합계로 입력합니다. 개인별 판정에는 상속에 합산된 사전증여도 포함합니다. 여러 미성년자의 합계가20억원을 넘는다고 모두40%가 되는 것은 아닙니다.',
   '대습상속은 민법1001조 요건이 확인된 금액만 제외합니다. 사망 외 법정 상속결격·상속권상실도 해당 조문과 상속개시일별 적용 요건을 확인해야 하며 상속포기와 혼동하지 않습니다. 자동 가족관계·법률자격 판정은 하지 않습니다.',
   '할증비율 분모는 불산입 제외 상속재산과 합산 사전증여이며 채무·장례비 차감 전입니다. 30%·40%·대습 제외 금액은 서로 중복되지 않아야 합니다.',
   '이번 연결 화면은 비거주자, 주식 평가/할증, 가업·영농 자격 자동심사, 증여세액공제 수증자별 한도 자동계산을 아직 지원하지 않습니다. 해당 사례의 확정 계산으로 사용하지 않습니다.',
   '가업상속은 확인된 적격 재산과 계속 경영기간으로300억/400억/600억원 한도를 적용합니다(제18조의2). 기업·상속인·중견기업 납부능력·사후관리·동일재산 영농공제 배제 등 자격은 사전에 확인해야 합니다. 자동 계산한 가업공제를 기타 공제에 다시 입력하지 마세요. 추가 주식 평가액은 본래 총평가액에 더해지므로 중복을 제외합니다. 영농·재해 등은 개별 요건·한도·중복제한을 검토한 공제액만 입력합니다. 실제 현금재원은 금융재산 과세평가액과 별도로 입력합니다. 보험금이 간주상속재산이면 과세재산에 포함해 계산합니다.',
   '기존 보고서와 동일한 계산식에 원화 입력 및 고객/설계사 출력을 연결했습니다. 원 단위 반올림 예상치이며 확인 입력 외 특례·신고서별 단수처리는 포함하지 않습니다.'],rows)


def calculate(name,values):
 if name!=NAME or len(values) not in (35,len(FIELDS[NAME])):raise ValueError('계산기 입력 항목을 확인해 주세요.')
 return estate(*values)
