"""
DART OpenAPI 클라이언트 통합 테스트.

실제 DART API에 연결합니다.
자격증명은 tests/test_clients/conftest.py에서 .env.example로부터 로드합니다.

삼성전자(corp_code=00126380) 기준으로 검증합니다.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from clients.dart import fetch_executives, fetch_finance, search_disclosures

_CORP_CODE = "00126380"   # 삼성전자
_BSNS_YEAR = "2023"
_REPRT_CODE = "11011"     # 사업보고서 (DART 공식 코드: 11011)
_BGN_DE = "20230101"
_END_DE = "20231231"

FIXTURES = Path(__file__).parents[1] / "fixtures"


# ── search_disclosures ────────────────────────────────────────────────────────

async def test_search_disclosures_returns_dict():
    """공시 목록 조회 시 dict를 반환해야 합니다."""
    result = await search_disclosures(_CORP_CODE, _BGN_DE, _END_DE)
    assert result is not None
    assert isinstance(result, dict)


async def test_search_disclosures_has_list_key():
    """응답에 'list' 키가 있어야 합니다."""
    result = await search_disclosures(_CORP_CODE, _BGN_DE, _END_DE)
    assert result is not None
    assert "list" in result


async def test_search_disclosures_list_not_empty():
    """삼성전자 공시는 1건 이상이어야 합니다."""
    result = await search_disclosures(_CORP_CODE, _BGN_DE, _END_DE)
    assert result is not None
    assert len(result["list"]) > 0


async def test_search_disclosures_item_fields():
    """공시 항목에 필수 필드가 있어야 합니다."""
    result = await search_disclosures(_CORP_CODE, _BGN_DE, _END_DE)
    assert result is not None
    item = result["list"][0]
    assert "rcept_no" in item
    assert "report_nm" in item
    assert "rcept_dt" in item


async def test_search_disclosures_no_data_returns_none():
    """status=013 응답(데이터 없음)은 None을 반환해야 합니다 (에러가 아님)."""
    fixture = json.loads((FIXTURES / "dart_no_data.json").read_text(encoding="utf-8"))
    with patch("clients.dart._get", new_callable=AsyncMock, return_value=fixture):
        result = await search_disclosures(_CORP_CODE, "19000101", "19001231")
    assert result is None


# ── fetch_executives ──────────────────────────────────────────────────────────

async def test_fetch_executives_returns_dict():
    """임원 현황 조회 시 dict를 반환해야 합니다."""
    result = await fetch_executives(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    assert isinstance(result, dict)


async def test_fetch_executives_has_list_key():
    """응답에 'list' 키가 있어야 합니다."""
    result = await fetch_executives(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    assert "list" in result


async def test_fetch_executives_list_not_empty():
    """삼성전자 임원은 1명 이상이어야 합니다."""
    result = await fetch_executives(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    assert len(result["list"]) > 0


async def test_fetch_executives_item_fields():
    """임원 항목에 nm(이름)과 ofcps(직위) 필드가 있어야 합니다."""
    result = await fetch_executives(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    item = result["list"][0]
    assert "nm" in item
    assert "ofcps" in item


async def test_fetch_executives_no_data_returns_none():
    """status=013 응답은 None을 반환해야 합니다."""
    fixture = json.loads((FIXTURES / "dart_no_data.json").read_text(encoding="utf-8"))
    with patch("clients.dart._get", new_callable=AsyncMock, return_value=fixture):
        result = await fetch_executives("00000000", "1900", _REPRT_CODE)
    assert result is None


# ── fetch_finance ─────────────────────────────────────────────────────────────

async def test_fetch_finance_returns_dict():
    """재무제표 조회 시 dict를 반환해야 합니다."""
    result = await fetch_finance(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    assert isinstance(result, dict)


async def test_fetch_finance_has_list_key():
    """응답에 'list' 키가 있어야 합니다."""
    result = await fetch_finance(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    assert "list" in result


async def test_fetch_finance_list_not_empty():
    """삼성전자 재무 항목은 1개 이상이어야 합니다."""
    result = await fetch_finance(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    assert len(result["list"]) > 0


async def test_fetch_finance_contains_revenue():
    """재무 항목에 매출액이 포함되어야 합니다."""
    result = await fetch_finance(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    account_names = [item.get("account_nm", "") for item in result["list"]]
    assert any("매출액" in name for name in account_names), f"매출액 없음: {account_names[:10]}"


async def test_fetch_finance_amounts_are_strings():
    """금액 필드(thstrm_amount)는 문자열이어야 합니다."""
    result = await fetch_finance(_CORP_CODE, _BSNS_YEAR, _REPRT_CODE)
    assert result is not None
    for item in result["list"]:
        if item.get("thstrm_amount"):
            assert isinstance(item["thstrm_amount"], str)
            break


async def test_fetch_finance_no_data_returns_none():
    """status=013 응답은 None을 반환해야 합니다."""
    fixture = json.loads((FIXTURES / "dart_no_data.json").read_text(encoding="utf-8"))
    with patch("clients.dart._get", new_callable=AsyncMock, return_value=fixture):
        result = await fetch_finance("00000000", "1900", _REPRT_CODE)
    assert result is None


# ── 에러 코드 테스트 ──────────────────────────────────────────────────────────

async def test_unknown_status_raises_value_error():
    """013 이외의 오류 status는 ValueError를 발생시켜야 합니다."""
    error_response = {"status": "999", "message": "알 수 없는 오류"}
    with patch("clients.dart._get", new_callable=AsyncMock, return_value=error_response):
        with pytest.raises(ValueError, match="status=999"):
            await search_disclosures(_CORP_CODE, _BGN_DE, _END_DE)
