"""
Serper Google Search API 클라이언트 통합 테스트.

실제 Serper API에 연결합니다.
자격증명은 tests/test_clients/conftest.py에서 .env.example로부터 로드합니다.
"""

import pytest

from clients.serper import search


# ── 통합 테스트 (실제 API 호출) ───────────────────────────────────────────────

async def test_search_returns_list():
    """검색 결과가 리스트여야 합니다."""
    results = await search("삼성전자 AI")
    assert isinstance(results, list)


async def test_search_returns_results():
    """'삼성전자 AI' 검색 시 1건 이상 반환되어야 합니다."""
    results = await search("삼성전자 AI")
    assert len(results) > 0


async def test_search_result_has_required_fields():
    """각 결과 항목에 title과 link가 있어야 합니다."""
    results = await search("삼성전자 AI")
    assert len(results) > 0
    for item in results:
        assert "title" in item
        assert "link" in item


async def test_search_limit_num():
    """num 파라미터가 반환 건수 상한으로 적용되어야 합니다."""
    results = await search("삼성전자", num=3)
    assert len(results) <= 3


async def test_search_default_params():
    """기본 파라미터(gl=kr, hl=ko)로 정상 동작해야 합니다."""
    results = await search("삼성SDI 배터리")
    assert isinstance(results, list)
