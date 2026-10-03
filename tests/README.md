# Lightweight regression checks

배포 전 최소 확인용 테스트입니다.

```bash
python -m unittest discover -s tests -p "test_*.py"
```

외부 Supabase 프로젝트나 고객 데이터에는 접속하지 않습니다.
