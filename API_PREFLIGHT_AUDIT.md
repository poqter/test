# HWARANG API 연결 전 수정 감사 결과

## 수정 완료
1. Voice reservation 만료시간 정합성
2. 1인 1 AI Session 원자적 강제
3. blocked activity rollback 문제
4. 동시 idempotency 이중 reservation race
5. 정식평가 동일 Snapshot 재사용
6. Customer AI hidden 분석/제안 노출 제거
7. 보험정보 단계 공개용 Python 승인 `insurance_memory`
8. Retry 시 기존 reservation 재사용 계약
9. Frontend / deterministic backend / future AI 입력 제한 2,400자 정렬
10. 관리자센터 KST 표기
11. PRE-API deployed-environment 자가진단
12. jsonschema direct dependency

## 운영 원칙
- Migration 11 적용 전에는 실제 OpenAI API를 연결하지 않습니다.
- Migration 11 적용 후에도 API Key 연결 전까지 AI runtime은 OFF입니다.
- Customer/Coach/Evaluator 실제 모델 ID는 API 연결 시점에 공식 API 문서로 최종 확인합니다.
- Voice V1 정책은 GPT-Live-1을 유지합니다.
- 동일 평가의 순차 재호출은 Snapshot Cache로 막습니다.
- 실제 paid adapter를 붙일 때 EVALUATOR idempotency key에도 동일 source_snapshot_hash를 포함하여
  동시 호출 비용까지 막아야 합니다.
