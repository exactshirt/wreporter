"""
Lesson 1: async/await 기초

규칙:
- 각 함수의 pass를 지우고 코드를 채워주세요
- 완료 후 실행: .venv\Scripts\python -m pytest tests/practice/test_practice_01_async.py -v
"""

import asyncio


# ── 과제 1: 첫 번째 async 함수 ─────────────────────────────────────
# "hello"를 반환하는 async 함수를 완성하세요.
# 힌트: 일반 함수와 거의 같지만, def 앞에 async를 붙이면 됩니다.

async def my_first_async():
    print("hello")


def test_my_first_async():
    result = asyncio.run(my_first_async())
    assert result == "hello"


# ── 과제 2: await로 다른 async 함수 호출하기 ───────────────────────
# get_greeting()은 이미 만들어진 async 함수입니다.
# 이것을 호출해서 결과를 반환하는 함수를 완성하세요.
# 힌트: async 함수를 호출할 때는 await를 앞에 붙여야 합니다.

async def get_greeting():
    """이미 완성된 함수 (수정하지 마세요)"""
    return "안녕하세요"


async def call_greeting():
    return await get_greeting()  # <-- 여기를 수정. get_greeting()을 await로 호출해서 반환하세요


def test_call_greeting():
    result = asyncio.run(call_greeting())
    assert result == "안녕하세요"


# ── 과제 3: asyncio.gather로 동시 실행 ─────────────────────────────
# 두 async 함수를 동시에 실행하고, 결과를 튜플로 반환하세요.
# 힌트: asyncio.gather(함수1(), 함수2())는 둘을 동시에 실행합니다.
#       결과는 리스트로 반환됩니다.

async def get_name():
    """이미 완성된 함수 (수정하지 마세요)"""
    return "김영업"


async def get_role():
    """이미 완성된 함수 (수정하지 마세요)"""
    return "B2B 영업"


async def get_profile():
    return asyncio.gather(get_name(), get_role())  # <-- 여기를 수정. get_name()과 get_role()을 동시에 실행하세요


def test_get_profile():
    result = asyncio.run(get_profile())
    assert result == ["김영업", "B2B 영업"]
