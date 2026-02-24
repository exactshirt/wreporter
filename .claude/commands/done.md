# 작업 완료 후 검증

방금 만든/수정한 것을 검증해줘.

1. 실제 데이터로 테스트:
   - DB/Supabase 관련이면: search_companies("삼성") 실행
   - DART 관련이면: 삼성전자(corp_code: 00126380)로 호출
   - Serper 관련이면: "삼성전자 AI" 검색
   - Reflex 관련이면: reflex run 에러 없는지 확인

2. pytest tests/ -v 실행

3. 결과 요약:
   - ✅ 통과
   - ❌ 실패 + 원인 (한국어)

실패하면 바로 고쳐줘.
