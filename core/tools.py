"""
에이전트 도구 정의 및 실행.

각 에이전트 유형별로 사용 가능한 도구 세트를 정의하고,
도구 이름 + 입력을 받아 실제 API를 호출하는 실행기를 제공합니다.
"""

from __future__ import annotations

import json
from typing import Any

from clients import dart, fsc, serper, web, nicebiz
from core.cache import cached_fetch
from db import queries
from utils.logger import get_logger

log = get_logger("Tools")


# ── 도구 정의 (Claude API tools 형식) ────────────────────────────

TOOL_SEARCH_GOOGLE = {
    "name": "search_google",
    "description": "Google 검색을 실행합니다. 뉴스, 기업 정보, 인물 정보 등을 검색할 때 사용합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "검색어"},
            "num": {"type": "integer", "description": "반환 결과 수 (기본값: 10)", "default": 10},
        },
        "required": ["query"],
    },
}

TOOL_FETCH_WEBPAGE = {
    "name": "fetch_webpage",
    "description": "URL의 웹 페이지를 가져와 텍스트 내용을 반환합니다. 뉴스 기사, 기업 홈페이지, 커뮤니티 글 등의 상세 내용을 수집할 때 사용합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "가져올 URL"},
        },
        "required": ["url"],
    },
}

TOOL_GET_COMPANY_INFO = {
    "name": "get_company_info",
    "description": "DB에서 기업 기본 정보를 조회합니다. jurir_no(법인등록번호) 또는 corp_code(DART 고유번호)로 조회합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "jurir_no": {"type": "string", "description": "법인등록번호 13자리"},
            "corp_code": {"type": "string", "description": "DART 고유번호 8자리"},
        },
    },
}

TOOL_GET_FSC_OUTLINE = {
    "name": "get_fsc_outline",
    "description": "FSC(금융위원회) 기업개요를 조회합니다. 설립일, 주요사업, 종업원수, 대표자 등의 정보를 얻습니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "jurir_no": {"type": "string", "description": "법인등록번호 13자리"},
        },
        "required": ["jurir_no"],
    },
}

TOOL_FETCH_DART_FINANCE = {
    "name": "fetch_dart_finance",
    "description": "DART 재무제표를 조회합니다. 매출액, 영업이익, 당기순이익, 자산, 부채 등의 재무 데이터를 얻습니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "corp_code": {"type": "string", "description": "DART 고유번호 8자리"},
            "bsns_year": {"type": "string", "description": "사업연도 4자리 (예: 2023)"},
            "reprt_code": {"type": "string", "description": "보고서 코드 (11011=사업보고서)", "default": "11011"},
        },
        "required": ["corp_code", "bsns_year"],
    },
}

TOOL_FETCH_FSC_SUMMARY = {
    "name": "fetch_fsc_summary",
    "description": "FSC 요약재무제표를 조회합니다. 매출, 영업이익, 순이익, 총자산, 총부채 등의 요약 재무를 얻습니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "jurir_no": {"type": "string", "description": "법인등록번호 13자리"},
        },
        "required": ["jurir_no"],
    },
}

TOOL_FETCH_FSC_BALANCE_SHEET = {
    "name": "fetch_fsc_balance_sheet",
    "description": "FSC 재무상태표를 조회합니다. 자산, 부채, 자본의 상세 항목을 얻습니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "jurir_no": {"type": "string", "description": "법인등록번호 13자리"},
        },
        "required": ["jurir_no"],
    },
}

TOOL_FETCH_FSC_INCOME = {
    "name": "fetch_fsc_income_statement",
    "description": "FSC 손익계산서를 조회합니다. 수익, 비용, 이익의 상세 항목을 얻습니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "jurir_no": {"type": "string", "description": "법인등록번호 13자리"},
        },
        "required": ["jurir_no"],
    },
}

TOOL_FETCH_DART_EXECUTIVES = {
    "name": "fetch_dart_executives",
    "description": "DART 임원현황을 조회합니다. 등기임원의 이름, 직위, 담당, 경력 등을 얻습니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "corp_code": {"type": "string", "description": "DART 고유번호 8자리"},
            "bsns_year": {"type": "string", "description": "사업연도 4자리"},
            "reprt_code": {"type": "string", "description": "보고서 코드", "default": "11011"},
        },
        "required": ["corp_code", "bsns_year"],
    },
}

TOOL_FETCH_NICEBIZ_EXECUTIVES = {
    "name": "fetch_nicebiz_executives",
    "description": "NiceBIZ에서 기업 임원 정보를 조회합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "bizr_no": {"type": "string", "description": "사업자등록번호 10자리"},
        },
        "required": ["bizr_no"],
    },
}


# ── 에이전트별 도구 세트 ──────────────────────────────────────────

TOOLS_BY_AGENT: dict[str, list[dict]] = {
    "general": [
        TOOL_SEARCH_GOOGLE,
        TOOL_FETCH_WEBPAGE,
        TOOL_GET_COMPANY_INFO,
        TOOL_GET_FSC_OUTLINE,
    ],
    "finance": [
        TOOL_FETCH_DART_FINANCE,
        TOOL_FETCH_FSC_SUMMARY,
        TOOL_FETCH_FSC_BALANCE_SHEET,
        TOOL_FETCH_FSC_INCOME,
        TOOL_SEARCH_GOOGLE,
        TOOL_FETCH_WEBPAGE,
    ],
    "executives": [
        TOOL_FETCH_DART_EXECUTIVES,
        TOOL_FETCH_NICEBIZ_EXECUTIVES,
        TOOL_SEARCH_GOOGLE,
        TOOL_FETCH_WEBPAGE,
        TOOL_GET_COMPANY_INFO,
    ],
}


def get_tools(agent_type: str) -> list[dict]:
    """에이전트 유형에 맞는 도구 정의 목록을 반환합니다."""
    return TOOLS_BY_AGENT.get(agent_type, [])


# ── 도구 실행기 ──────────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """
    도구를 실행하고 결과를 문자열로 반환합니다.

    Args:
        tool_name: 도구 이름.
        tool_input: 도구 입력 파라미터.

    Returns:
        실행 결과 문자열 (JSON 또는 텍스트).
    """
    log.step("실행", f"{tool_name}({tool_input})")
    try:
        result = await _dispatch(tool_name, tool_input)
        # 결과를 문자열로 변환
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        if result is None:
            return "데이터 없음"
        return str(result)
    except Exception as e:
        log.error("실행", f"{tool_name}: {e}")
        return f"오류: {e}"


async def _dispatch(name: str, inp: dict[str, Any]) -> Any:
    """도구 이름에 따라 실제 함수를 호출합니다."""

    if name == "search_google":
        return await serper.search(
            query=inp["query"],
            num=inp.get("num", 10),
        )

    if name == "fetch_webpage":
        page = await web.fetch_page(inp["url"])
        if page is None:
            return None
        return {
            "url": page.url,
            "title": page.title,
            "content": page.text_content[:50000],  # 50K 제한
            "links": page.links[:10],
        }

    if name == "get_company_info":
        jurir_no = inp.get("jurir_no")
        corp_code = inp.get("corp_code")
        if jurir_no:
            return await cached_fetch(
                f"company_{jurir_no}",
                lambda: queries.get_company_by_jurir(jurir_no),
            )
        if corp_code:
            return await cached_fetch(
                f"company_{corp_code}",
                lambda: queries.get_company(corp_code),
            )
        return "jurir_no 또는 corp_code가 필요합니다"

    if name == "get_fsc_outline":
        jurir_no = inp["jurir_no"]
        return await cached_fetch(
            f"fsc_outline_{jurir_no}",
            lambda: fsc.fetch_corp_outline(jurir_no),
        )

    if name == "fetch_dart_finance":
        corp_code = inp["corp_code"]
        year = inp["bsns_year"]
        code = inp.get("reprt_code", "11011")
        return await cached_fetch(
            f"dart_finance_{corp_code}_{year}_{code}",
            lambda: dart.fetch_finance(corp_code, year, code),
        )

    if name == "fetch_fsc_summary":
        jurir_no = inp["jurir_no"]
        return await cached_fetch(
            f"fsc_summary_{jurir_no}",
            lambda: fsc.fetch_summary(jurir_no),
        )

    if name == "fetch_fsc_balance_sheet":
        jurir_no = inp["jurir_no"]
        return await cached_fetch(
            f"fsc_bs_{jurir_no}",
            lambda: fsc.fetch_balance_sheet(jurir_no),
        )

    if name == "fetch_fsc_income_statement":
        jurir_no = inp["jurir_no"]
        return await cached_fetch(
            f"fsc_is_{jurir_no}",
            lambda: fsc.fetch_income_statement(jurir_no),
        )

    if name == "fetch_dart_executives":
        corp_code = inp["corp_code"]
        year = inp["bsns_year"]
        code = inp.get("reprt_code", "11011")
        return await cached_fetch(
            f"dart_exec_{corp_code}_{year}_{code}",
            lambda: dart.fetch_executives(corp_code, year, code),
        )

    if name == "fetch_nicebiz_executives":
        bizr_no = inp["bizr_no"]
        return await cached_fetch(
            f"nicebiz_exec_{bizr_no}",
            lambda: nicebiz.fetch_executives(bizr_no),
        )

    return f"알 수 없는 도구: {name}"
