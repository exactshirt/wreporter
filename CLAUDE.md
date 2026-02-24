# Wreporter
B2B 영업팀용 기업 분석 리포트 자동 생성 시스템. Reflex + Supabase + Claude API.

---

## 운영자 참고
- 운영자는 SW 엔지니어가 아님. 코드 수정 시 무엇을 왜 바꿨는지 설명할 것.
- 수정 후 pytest 결과를 보여줄 것.
- 에러 메시지는 운영자가 이해할 수 있는 한국어로 설명할 것.

---

## 아키텍처
- State: wreporter/state/ — UI 상태, core/ 함수를 호출 (State에 로직 직접 쓰지 않기)
- Core: core/ — 비즈니스 로직 (Reflex 독립 실행 가능)
- Clients: clients/ — httpx 기반 async API 클라이언트
- Prompts: prompts/ — .md 파일로 분리
- 로깅: utils/logger.py — 모든 core/ 함수에 🟢❌ 로깅 포함

---

## 규칙
- Python 3.10+, async/await, type hints 필수
- 새 함수 작성 시 테스트도 함께
- DART API 에러코드 013 = 정상 분기 (데이터 없음, 에러 아님!)

---

## 명령어
- `reflex run` — 개발 서버 (localhost:3000)
- `pytest tests/ -v` — 전체 테스트
- `.venv\Scripts\activate` — Windows 가상환경 활성화 (source 아님!)

---

## 검증 기준값 (테스트 시 사용)
- 삼성전자 corp_code: `00126380`
- 삼성전자 검색 키워드: `"삼성"` → 결과 있어야 함
- DART 재무: `fetch_finance("00126380", "2023", "11011")` → 데이터 있어야 함

---

## 잘못된 행동 기록 (같은 실수 방지)
- corp_code NULL 필터 걸면 안 됨 — 70만건 중 DART 등록 기업만 corp_code 보유, FSC 전용은 NULL이 정상
- DART status "013" = 에러 아님, 데이터 없음 (None 반환, 예외 던지지 않음)
- Supabase key = service_role 사용 (anon key 아님)
- Windows: `cp` 명령 없음 → `copy` 사용
- Windows: `source` 없음 → `.venv\Scripts\activate` 사용

---

## Plan 모드 활용 (Boris Cherny #6)
- 새 파일/기능 만들기 전: Shift+Tab x2로 Plan 모드 시작
- 계획 확인 후 Shift+Tab 한 번 → Auto-accept 전환
- 큰 작업은 Plan 없이 바로 시작하지 말 것

---

## 검증 피드백 루프 (Boris Cherny #13 — 가장 중요)
- 모든 함수/파일 작성 후 반드시 실제 데이터로 테스트 실행
- 테스트 완료 후 pytest 실행
- 검증 없이 "완료"라고 하지 말 것

---

## 잘못된 행동 기록 (도메인)
- 비상장 기업 대부분은 "비상장비외감" — "비상장외감"은 DART에 감사보고서가 제출된 소수만 해당
- 어드민 통계의 "외감" 카운트는 전체 비상장이 아님, 추후 정책 수정 필요

---

## Phase 진행 상황
- Phase 1: Step 1~7 완료
- Phase 2~5: 미착수
