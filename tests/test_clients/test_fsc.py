"""
FSC OpenAPI 클라이언트 통합 테스트.

실제 FSC API에 연결합니다.
자격증명은 tests/test_clients/conftest.py에서 .env.example로부터 로드합니다.

삼성전자(jurir_no=1301110006246) 기준으로 검증합니다.
"""

import pytest
from unittest.mock import AsyncMock, patch

from clients.fsc import (
    fetch_balance_sheet,
    fetch_corp_outline,
    fetch_income_statement,
    fetch_summary,
)

_JURIR_NO = "1301110006246"   # 삼성전자
_MISSING = "0000000000001"    # 존재하지 않는 법인번호


# ── fetch_summary ─────────────────────────────────────────────────────────────

async def test_fetch_summary_returns_list():
    """요약재무제표 조회 결과가 리스트여야 합니다."""
    result = await fetch_summary(_JURIR_NO)
    assert isinstance(result, list)


async def test_fetch_summary_not_empty():
    """삼성전자 요약재무제표는 1건 이상이어야 합니다."""
    result = await fetch_summary(_JURIR_NO)
    assert len(result) > 0


async def test_fetch_summary_single_year_only():
    """최신 bizYear 항목만 반환되어야 합니다 (연도 혼재 금지)."""
    result = await fetch_summary(_JURIR_NO)
    years = {item["bizYear"] for item in result}
    assert len(years) == 1, f"여러 연도가 혼재됨: {years}"


async def test_fetch_summary_has_required_fields():
    """요약재무제표 항목에 필수 필드가 있어야 합니다."""
    result = await fetch_summary(_JURIR_NO)
    assert len(result) > 0
    for item in result:
        assert "bizYear" in item
        assert "fnclDcdNm" in item
        assert "enpSaleAmt" in item     # 매출
        assert "enpBzopPft" in item     # 영업이익
        assert "enpTastAmt" in item     # 총자산


async def test_fetch_summary_empty_jurir_returns_empty():
    """존재하지 않는 법인번호 조회 시 빈 리스트를 반환해야 합니다."""
    result = await fetch_summary(_MISSING)
    assert result == []


# ── fetch_balance_sheet ───────────────────────────────────────────────────────

async def test_fetch_balance_sheet_returns_list():
    """재무상태표 조회 결과가 리스트여야 합니다."""
    result = await fetch_balance_sheet(_JURIR_NO)
    assert isinstance(result, list)


async def test_fetch_balance_sheet_not_empty():
    """삼성전자 재무상태표는 1건 이상이어야 합니다."""
    result = await fetch_balance_sheet(_JURIR_NO)
    assert len(result) > 0


async def test_fetch_balance_sheet_single_year_only():
    """최신 bizYear 항목만 반환되어야 합니다."""
    result = await fetch_balance_sheet(_JURIR_NO)
    years = {item["bizYear"] for item in result}
    assert len(years) == 1, f"여러 연도가 혼재됨: {years}"


async def test_fetch_balance_sheet_has_asset_account():
    """재무상태표에 자산 관련 계정이 있어야 합니다."""
    result = await fetch_balance_sheet(_JURIR_NO)
    account_names = [item.get("acitNm", "") for item in result]
    assert any("자산" in nm for nm in account_names), f"자산 계정 없음: {account_names}"


async def test_fetch_balance_sheet_amounts_present():
    """당기금액(crtmAcitAmt) 필드가 있어야 합니다."""
    result = await fetch_balance_sheet(_JURIR_NO)
    assert len(result) > 0
    assert all("crtmAcitAmt" in item for item in result)


# ── fetch_income_statement ────────────────────────────────────────────────────

async def test_fetch_income_statement_returns_list():
    """손익계산서 조회 결과가 리스트여야 합니다."""
    result = await fetch_income_statement(_JURIR_NO)
    assert isinstance(result, list)


async def test_fetch_income_statement_not_empty():
    """삼성전자 손익계산서는 1건 이상이어야 합니다."""
    result = await fetch_income_statement(_JURIR_NO)
    assert len(result) > 0


async def test_fetch_income_statement_single_year_only():
    """최신 bizYear 항목만 반환되어야 합니다."""
    result = await fetch_income_statement(_JURIR_NO)
    years = {item["bizYear"] for item in result}
    assert len(years) == 1, f"여러 연도가 혼재됨: {years}"


async def test_fetch_income_statement_has_operating_profit():
    """손익계산서에 영업이익 계정이 있어야 합니다."""
    result = await fetch_income_statement(_JURIR_NO)
    account_names = [item.get("acitNm", "") for item in result]
    assert any("영업" in nm for nm in account_names), f"영업이익 계정 없음: {account_names}"


# ── fetch_corp_outline ────────────────────────────────────────────────────────

async def test_fetch_corp_outline_returns_dict():
    """기업개요 조회 시 dict를 반환해야 합니다."""
    result = await fetch_corp_outline(_JURIR_NO)
    assert result is not None
    assert isinstance(result, dict)


async def test_fetch_corp_outline_corp_name():
    """기업명에 '삼성'이 포함되어야 합니다."""
    result = await fetch_corp_outline(_JURIR_NO)
    assert result is not None
    assert "삼성" in result.get("corpNm", ""), f"법인명: {result.get('corpNm')}"


async def test_fetch_corp_outline_has_required_fields():
    """기업개요에 필수 필드가 있어야 합니다."""
    result = await fetch_corp_outline(_JURIR_NO)
    assert result is not None
    assert "crno" in result
    assert "corpNm" in result


async def test_fetch_corp_outline_not_found_returns_none():
    """존재하지 않는 법인번호 조회 시 None을 반환해야 합니다."""
    result = await fetch_corp_outline(_MISSING)
    assert result is None


# ── API 키 누락 에러 처리 ─────────────────────────────────────────────────────

async def test_missing_api_key_raises_value_error():
    """FSC_API_KEY가 없으면 ValueError가 발생해야 합니다."""
    from utils.config import Settings

    mock_cfg = Settings(
        dart_api_key="x", anthropic_api_key="x",
        supabase_url="x", supabase_key="x",
        serper_api_key="x", fsc_api_key=None,
    )
    with patch("clients.fsc.load_config", return_value=mock_cfg):
        with pytest.raises(ValueError, match="FSC_API_KEY"):
            await fetch_summary(_JURIR_NO)
