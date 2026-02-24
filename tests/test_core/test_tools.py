"""
core/tools.py 단위 테스트.

도구 정의와 도구 실행기를 테스트합니다.
"""

import pytest

from core.tools import get_tools, execute_tool, TOOLS_BY_AGENT


# ── get_tools ─────────────────────────────────────────────────────

def test_get_tools_general_returns_4():
    """general 에이전트는 4개 도구를 가져야 합니다."""
    tools = get_tools("general")
    assert len(tools) == 4


def test_get_tools_finance_returns_6():
    """finance 에이전트는 6개 도구를 가져야 합니다."""
    tools = get_tools("finance")
    assert len(tools) == 6


def test_get_tools_executives_returns_5():
    """executives 에이전트는 5개 도구를 가져야 합니다."""
    tools = get_tools("executives")
    assert len(tools) == 5


def test_get_tools_unknown_returns_empty():
    """알 수 없는 유형은 빈 리스트를 반환합니다."""
    tools = get_tools("unknown")
    assert tools == []


def test_tool_definitions_have_required_fields():
    """모든 도구 정의에 name, description, input_schema가 있어야 합니다."""
    for agent_type, tools in TOOLS_BY_AGENT.items():
        for tool in tools:
            assert "name" in tool, f"{agent_type}: name 없음"
            assert "description" in tool, f"{agent_type}: description 없음"
            assert "input_schema" in tool, f"{agent_type}: input_schema 없음"


def test_general_tools_include_search_and_web():
    """general 에이전트에 search_google과 fetch_webpage가 포함되어야 합니다."""
    names = {t["name"] for t in get_tools("general")}
    assert "search_google" in names
    assert "fetch_webpage" in names


def test_finance_tools_include_dart_and_fsc():
    """finance 에이전트에 DART/FSC 재무 도구가 포함되어야 합니다."""
    names = {t["name"] for t in get_tools("finance")}
    assert "fetch_dart_finance" in names
    assert "fetch_fsc_summary" in names
    assert "fetch_fsc_balance_sheet" in names
    assert "fetch_fsc_income_statement" in names


def test_executives_tools_include_dart_exec():
    """executives 에이전트에 임원 관련 도구가 포함되어야 합니다."""
    names = {t["name"] for t in get_tools("executives")}
    assert "fetch_dart_executives" in names
    assert "fetch_nicebiz_executives" in names


# ── execute_tool ──────────────────────────────────────────────────

async def test_execute_tool_unknown_returns_error_message():
    """알 수 없는 도구 실행 시 에러 메시지를 반환합니다."""
    result = await execute_tool("unknown_tool", {})
    assert "알 수 없는 도구" in result


async def test_execute_tool_get_company_info_samsung():
    """삼성전자 기업 정보를 조회할 수 있어야 합니다."""
    result = await execute_tool("get_company_info", {"corp_code": "00126380"})
    assert "삼성전자" in result


async def test_execute_tool_get_company_info_no_params():
    """파라미터가 없으면 안내 메시지를 반환합니다."""
    result = await execute_tool("get_company_info", {})
    assert "jurir_no" in result or "corp_code" in result
