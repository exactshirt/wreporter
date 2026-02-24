"""
세션 수준 API 결과 캐시.

같은 기업에 대해 여러 에이전트가 중복 API 호출하는 것을 방지합니다.
프로세스 수명 동안 유지되며, 명시적으로 초기화할 수 있습니다.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from utils.logger import get_logger

log = get_logger("Cache")

_cache: dict[str, Any] = {}


async def cached_fetch(key: str, fetch_fn: Callable[[], Awaitable[Any]]) -> Any:
    """
    캐시된 결과를 반환하거나, 없으면 fetch_fn을 실행하고 캐시합니다.

    Args:
        key: 캐시 키 (예: "dart_finance_00126380_2023").
        fetch_fn: 데이터를 가져오는 async 함수.

    Returns:
        캐시된 또는 새로 가져온 결과.
    """
    if key in _cache:
        log.step("캐시", f"HIT: {key}")
        return _cache[key]

    log.step("캐시", f"MISS: {key}")
    result = await fetch_fn()
    _cache[key] = result
    return result


def get_cached(key: str) -> Any | None:
    """캐시에서 직접 조회합니다. 없으면 None."""
    return _cache.get(key)


def set_cached(key: str, value: Any) -> None:
    """캐시에 직접 저장합니다."""
    _cache[key] = value


def clear_cache() -> None:
    """전체 캐시를 초기화합니다."""
    _cache.clear()
    log.step("캐시", "전체 초기화")


def clear_company_cache(jurir_no: str) -> None:
    """특정 기업 관련 캐시만 초기화합니다."""
    keys_to_remove = [k for k in _cache if jurir_no in k]
    for k in keys_to_remove:
        del _cache[k]
    if keys_to_remove:
        log.step("캐시", f"{jurir_no} 관련 {len(keys_to_remove)}건 삭제")
