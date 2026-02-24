"""
Supabase 연동 통합 테스트.

실제 Supabase에 연결하여 companies 테이블을 조회합니다.
자격증명은 tests/test_clients/conftest.py에서 .env.example로부터 로드합니다.
"""

import pytest

from db.queries import get_company, get_company_by_jurir, search_companies


# ── search_companies ──────────────────────────────────────────────────────────

async def test_search_companies_samsung_returns_results():
    """'삼성' 검색 시 1건 이상 반환되어야 합니다."""
    results = await search_companies("삼성")
    assert len(results) > 0


async def test_search_companies_returns_required_fields():
    """결과 각 항목에 필수 필드가 모두 있어야 합니다."""
    results = await search_companies("삼성")
    for row in results:
        assert "corp_code" in row
        assert "jurir_no" in row
        assert "corp_name" in row
        assert "ceo_nm" in row
        assert "corp_cls" in row
        assert "market_label" in row
        assert "has_dart" in row


async def test_search_companies_samsung_electronics_appears():
    """'삼성' 검색 시 삼성전자(코스피 상장)가 결과에 포함되어야 합니다."""
    results = await search_companies("삼성")
    names = [r["corp_name"] for r in results]
    assert any("삼성전자" in n for n in names), f"삼성전자 없음: {names}"


async def test_search_companies_listed_first():
    """상장기업(Y/K/N)이 비상장(E)보다 앞에 나와야 합니다."""
    results = await search_companies("삼성")
    cls_list = [r["corp_cls"] for r in results if r["corp_cls"] in ("Y", "K", "N", "E")]
    listed = [c for c in cls_list if c in ("Y", "K", "N")]
    unlisted = [c for c in cls_list if c == "E"]
    if listed and unlisted:
        # 첫 비상장 기업의 인덱스가 마지막 상장기업 인덱스보다 뒤에 있어야 함
        last_listed_idx = max(i for i, c in enumerate(cls_list) if c in ("Y", "K", "N"))
        first_unlisted_idx = min(i for i, c in enumerate(cls_list) if c == "E")
        assert last_listed_idx < first_unlisted_idx


async def test_search_companies_limit():
    """limit 파라미터가 정상 적용되어야 합니다."""
    results = await search_companies("삼성", limit=3)
    assert len(results) <= 3


async def test_search_companies_no_match_returns_empty():
    """존재하지 않는 회사명 검색 시 빈 리스트를 반환해야 합니다."""
    results = await search_companies("존재하지않는회사XYZ99999")
    assert results == []


# ── get_company ───────────────────────────────────────────────────────────────

async def test_get_company_samsung_electronics():
    """삼성전자(00126380) 조회 시 corp_name에 '삼성전자'가 포함되어야 합니다."""
    company = await get_company("00126380")
    assert company is not None
    assert "삼성전자" in company["corp_name"]


async def test_get_company_returns_corp_code():
    """조회 결과의 corp_code가 요청한 값과 일치해야 합니다."""
    company = await get_company("00126380")
    assert company is not None
    assert company["corp_code"] == "00126380"


async def test_get_company_not_found_returns_none():
    """존재하지 않는 corp_code 조회 시 None을 반환해야 합니다."""
    result = await get_company("00000000")
    assert result is None


# ── get_company_by_jurir ──────────────────────────────────────────────────────

async def test_get_company_by_jurir_samsung_electronics():
    """삼성전자 법인등록번호로 조회 시 corp_name에 '삼성전자'가 포함되어야 합니다."""
    company = await get_company_by_jurir("1301110006246")
    assert company is not None
    assert "삼성전자" in company["corp_name"]


async def test_get_company_by_jurir_returns_jurir_no():
    """조회 결과의 jurir_no가 요청한 값과 일치해야 합니다."""
    company = await get_company_by_jurir("1301110006246")
    assert company is not None
    assert company["jurir_no"] == "1301110006246"


async def test_get_company_by_jurir_not_found_returns_none():
    """존재하지 않는 jurir_no 조회 시 None을 반환해야 합니다."""
    result = await get_company_by_jurir("0000000000001")
    assert result is None
