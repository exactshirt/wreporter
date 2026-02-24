"""
Chainlit UI 헬퍼 함수.

환영 메시지, 후속 질문 제안, 아티팩트 사이드바 표시를 담당합니다.
"""

from __future__ import annotations

import chainlit as cl

from db import artifacts as art_db
from utils.logger import get_logger

log = get_logger("UIHelpers")

# ── 도구 라벨 매핑 (handlers.py에서도 참조 가능) ─────────────────────

TOOL_LABELS = {
    "search_google": "🔍 Google 검색 중",
    "fetch_webpage": "🌐 웹 페이지 수집 중",
    "get_company_info": "🏢 기업 정보 조회 중",
    "get_fsc_outline": "📋 FSC 기업개요 조회 중",
    "fetch_dart_finance": "📊 DART 재무제표 조회 중",
    "fetch_fsc_summary": "📊 FSC 요약재무 조회 중",
    "fetch_fsc_balance_sheet": "📊 FSC 재무상태표 조회 중",
    "fetch_fsc_income_statement": "📊 FSC 손익계산서 조회 중",
    "fetch_dart_executives": "👤 DART 임원현황 조회 중",
    "fetch_nicebiz_executives": "👤 NICEBIZ 임원 조회 중",
}

# ── 에이전트별 후속 질문 제안 ────────────────────────────────────────

_SUGGESTIONS: dict[str, list[dict[str, str]]] = {
    "general": [
        {"label": "📰 최근 뉴스 더 찾기", "query": "이 기업의 최근 뉴스를 더 찾아주세요"},
        {"label": "🏭 경쟁사 비교", "query": "주요 경쟁사와 비교 분석해주세요"},
        {"label": "🤖 AX 전략 심화", "query": "AX(AI 전환) 전략을 더 심층 분석해주세요"},
    ],
    "finance": [
        {"label": "📊 동종업계 비교", "query": "동종업계 재무 지표와 비교해주세요"},
        {"label": "💰 투자여력 상세", "query": "IT/AX 투자여력을 상세 분석해주세요"},
        {"label": "⚠️ 리스크 요인", "query": "주요 재무 리스크 요인을 분석해주세요"},
    ],
    "executives": [
        {"label": "🏛️ 의사결정 구조", "query": "의사결정 구조를 분석해주세요"},
        {"label": "🔗 임원 네트워크", "query": "임원 네트워크와 경력 배경을 분석해주세요"},
    ],
}

_WELCOME: dict[str, str] = {
    "general": "기업의 일반정보를 조사합니다. 기업개요, AX 동향, 사업 현황, 영업 인사이트를 분석합니다.",
    "finance": "기업의 재무정보를 분석합니다. 재무제표, 건전성, 투자여력을 평가합니다.",
    "executives": "기업의 임원정보를 조사합니다. 임원 리스트, 의사결정 구조, 주요 인물을 분석합니다.",
}


# ── 환영 메시지 ──────────────────────────────────────────────────────


async def send_welcome(agent_type: str, pins: list[dict] | None = None) -> None:
    """환영 메시지 + 조사 시작 버튼을 표시합니다."""
    company: dict | None = cl.user_session.get("active_company")  # type: ignore[assignment]
    if not company:
        await cl.Message(
            content="👋 **Wreporter**에 오신 것을 환영합니다!\n\n"
            "기업명을 입력하면 검색하고 핀 추가할 수 있습니다."
        ).send()
        return

    corp_name = company.get("corp_name", "기업")
    desc = _WELCOME.get(agent_type, "조사를 시작합니다.")

    actions = [
        cl.Action(
            name="start_research",
            payload={"agent_type": agent_type},
            label="🚀 조사 시작",
            description=f"{corp_name}의 {agent_type} 조사를 시작합니다",
        ),
    ]

    await cl.Message(
        content=f"**{corp_name}** — {desc}",
        actions=actions,
    ).send()


# ── 후속 질문 제안 (C5 해결) ─────────────────────────────────────────


async def send_suggestions(agent_type: str, company: dict) -> None:
    """에이전트별 후속 질문 제안 버튼을 표시합니다."""
    suggestions = _SUGGESTIONS.get(agent_type, [])
    if not suggestions:
        return

    actions = [
        cl.Action(
            name="suggestion",
            payload={"query": s["query"]},
            label=s["label"],
        )
        for s in suggestions
    ]

    await cl.Message(
        content="💡 추가로 궁금한 점이 있으신가요?",
        actions=actions,
    ).send()


# ── 아티팩트 사이드바 ────────────────────────────────────────────────


async def update_artifact_sidebar(jurir_no: str, agent_type: str) -> None:
    """
    DB에서 섹션을 로드하여 사이드바(cl.Text)로 표시합니다.

    각 섹션의 content가 비어있지 않으면 사이드바에 추가합니다.
    """
    sections = await art_db.get_sections(jurir_no, agent_type)

    elements: list[cl.Text] = []
    for sec in sections:
        content = sec.get("content", "")
        if not content:
            continue
        title = sec.get("title", sec.get("section_key", ""))
        elements.append(
            cl.Text(
                name=title,
                content=content,
                display="side",
            )
        )

    if elements:
        await cl.Message(
            content="📋 보고서 섹션이 사이드바에 표시됩니다.",
            elements=elements,
        ).send()
