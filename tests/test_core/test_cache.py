"""
core/cache.py 단위 테스트.

세션 수준 캐시의 기본 동작을 테스트합니다.
"""

import pytest

from core.cache import cached_fetch, get_cached, set_cached, clear_cache, clear_company_cache


@pytest.fixture(autouse=True)
def clean_cache():
    """매 테스트 전후로 캐시를 초기화합니다."""
    clear_cache()
    yield
    clear_cache()


async def test_cached_fetch_calls_function_on_miss():
    """캐시 미스 시 fetch_fn이 호출되어야 합니다."""
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        return {"data": "test"}

    result = await cached_fetch("test_key", fetch)
    assert result == {"data": "test"}
    assert call_count == 1


async def test_cached_fetch_returns_cached_on_hit():
    """캐시 히트 시 fetch_fn이 호출되지 않아야 합니다."""
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        return {"data": "test"}

    await cached_fetch("test_key", fetch)
    result2 = await cached_fetch("test_key", fetch)
    assert result2 == {"data": "test"}
    assert call_count == 1  # 두 번째 호출에서는 증가하지 않음


def test_get_cached_returns_none_for_missing():
    """존재하지 않는 키는 None을 반환합니다."""
    assert get_cached("nonexistent") is None


def test_set_cached_stores_value():
    """직접 캐시에 저장할 수 있어야 합니다."""
    set_cached("manual", 42)
    assert get_cached("manual") == 42


def test_clear_cache_removes_all():
    """전체 캐시 초기화가 동작해야 합니다."""
    set_cached("a", 1)
    set_cached("b", 2)
    clear_cache()
    assert get_cached("a") is None
    assert get_cached("b") is None


def test_clear_company_cache_removes_matching():
    """특정 기업 관련 캐시만 삭제되어야 합니다."""
    set_cached("company_1234", "data1")
    set_cached("dart_finance_1234_2023", "data2")
    set_cached("company_5678", "other")
    clear_company_cache("1234")
    assert get_cached("company_1234") is None
    assert get_cached("dart_finance_1234_2023") is None
    assert get_cached("company_5678") == "other"
