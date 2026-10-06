# Offline regression checks

```bash
python3 -m pytest -q
```

외부 HTTP(S) 요청은 conftest.py에서 차단합니다. 프로젝트 OpenAI API와 실제 Supabase에 접속하지 않습니다. 저장·화면·권한·실패·PDF 검증은 모의 데이터와 가짜 저장소를 사용합니다. 실제 API의 출력 품질과 운영 서버 검증은 별도입니다.

1.7.4-stage1 기준 224개 테스트 + 하위 검사 61개 통과. 실제 기기·메신저 미리보기 검증과 구분합니다.
