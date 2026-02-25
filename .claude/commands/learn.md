# 학습 모드

이 프로젝트의 코드를 교재로 사용하여 Python 프로그래밍을 가르쳐줘.

## 시작 방법
- 사용자가 주제를 명시했으면 (예: `/learn async`) 그 주제로 시작
- 주제가 없으면 아래 커리큘럼 순서에서 다음 단계를 제안하고 물어봐줘

## 이 프로젝트 기준 학습 커리큘럼 (권장 순서)
1. async/await — clients/ 폴더 전체가 async 함수로 작성됨
2. type hints — 모든 함수에 타입이 명시됨
3. httpx — 외부 API(DART, FSC, Serper) 호출 방식
4. Pydantic / dataclass — 데이터 구조 정의
5. pytest — 테스트 작성법과 검증

## 수업 규칙
1. 비개발자 수준으로 설명 (SW 엔지니어가 아닌 운영자 기준)
2. 각 개념마다 이 프로젝트의 실제 코드에서 예시를 찾아 보여줘
3. 작은 실습 과제를 출제 (tests/practice/ 폴더에 실습 파일 생성)
4. 과제 완료 후 pytest로 검증

## 실습 과제 형식
tests/practice/ 폴더에 test_practice_XX.py 파일을 생성하고,
빈칸 채우기 형태로 출제. 예시:

    # 과제: async 함수가 뭔지 이해하기
    # 아래 빈칸을 채워서 테스트를 통과시키세요

    async def my_first_async():
        """TODO: 'hello'를 반환하는 async 함수를 완성하세요"""
        pass  # ← 여기를 수정

    def test_my_first_async():
        import asyncio
        result = asyncio.run(my_first_async())
        assert result == "hello"

## 과제 완료 후
pytest가 통과하면 다음을 제안해줘:
`/remember [주제] 학습 완료 — [배운 핵심 1줄 요약]`
