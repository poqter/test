"""Explicit eligibility assumptions for synthetic integration cases only."""
def fill_confirmed_case(at,name):
 for box in at.selectbox:
  if not box.key or not box.key.startswith('cov_'):continue
  if box.options==['미확인','확인']:box.select('확인')
  elif box.options==['아니요','예'] and any(w in box.label for w in ('확인','요건 충족')) and not any(w in box.label for w in ('배당 기간','상속 공제','상속금액','5억원 이상')):box.select('예')
  elif box.label=='신고의무 자격':box.select('거주자·내국법인, 면제 없음 확인')
 fixes={
  '양도소득세계산기': {'1세대 1주택 비과세 요건 별도 확인 (거주 등 포함)':'아니요'},
  '차등배당계산기': {'정산용 실제 소득세액 확인':'아니요','종합과세 계산 방식':'배당가산 대상 확인'},
  '지주회사 수입배당금계산기': {'배당 유형·법인·보유기간의 적용 대상 여부':'적용 대상 확인'},
  '법인 부동산 보유·양도 비교계산기': {'법인 토지등 양도 추가과세 구분':'추가과세 없음 확인','개인 1세대 1주택 비과세 요건 확인':'아니요'},
  '취득세 중과계산기': {'확인된 적용 구분':'비주택 일반 유상취득'},
  '특수관계자 임대료계산기': {'시가 확인 방법':'비교 가능한 시가 확인'},
  '창업중소기업 세액감면계산기': {'최초 소득 발생 상태':'최초 소득 발생연도 확인','감면 기본 요건':'적격 업종·중소기업·실질 창업·계속사업 요건 확인','2024년 이전 창업 신성장서비스업 특례 요건 확인':'아니요'},
 }
 if name=='증여세계산기':
  for box in at.selectbox:
   if '세대생략' in box.label and box.options==['아니요','예']:box.select('아니요')
 for box in at.selectbox:
  if box.label in fixes.get(name,{}):box.select(fixes[name][box.label])
 if name=='창업중소기업 세액감면계산기':
  at.number_input(key='cov_'+name+'_3').set_value(2024)
  at.text_input(key='cov_'+name+'_7').set_value('200000000')
 if name=='법인 4대보험계산기':at.text_input(key='cov_'+name+'_6').set_value('0.7')
