"""
Chainlit UI 헬퍼 함수.

환영 메시지, 후속 질문 제안, 아티팩트(보고서) 표시를 담당합니다.
Reflex 버전의 artifact_view + chat 컴포넌트 역할을 재현합니다.
"""

from __future__ import annotations

import chainlit as cl

from db import artifacts as art_db
from db.artifacts import SECTION_SCHEMAS
from utils.logger import get_logger

log = get_logger("UIHelpers")

# ── 도구 라벨 매핑 (handlers.py에서도 참조) ─────────────────────

TOOL_LABELS = {
    "search_google": "🔍 Google 검색",
    "fetch_webpage": "🌐 웹 페이지 수집",
    "get_company_info": "🏢 기업 정보 조회",
    "get_fsc_outline": "📋 FSC 기업개요 조회",
    "fetch_dart_finance": "📊 DART 재무제표 조회",
    "fetch_fsc_summary": "📊 FSC 요약재무 조회",
    "fetch_fsc_balance_sheet": "📊 FSC 재무상태표 조회",
    "fetch_fsc_income_statement": "📊 FSC 손익계산서 조회",
    "fetch_dart_executives": "👤 DART 임원현황 조회",
    "fetch_nicebiz_executives": "👤 NICEBIZ 임원 조회",
}

# ── 에이전트별 후속 질문 제안 ────────────────────────────────────

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

_AGENT_LABELS = {
    "general": "일반정보",
    "finance": "재무정보",
    "executives": "임원정보",
}

_AGENT_DESCRIPTIONS = {
    "general": "기업개요 · AX 동향 · 사업 현황 · 영업 인사이트",
    "finance": "재무제표 · 수익성 · 건전성 · 투자여력",
    "executives": "임원 리스트 · 의사결정 구조 · 인물 프로파일링",
}

_AGENT_ICONS = {
    "general": "🏢",
    "finance": "📊",
    "executives": "👤",
}


# ── 환영 메시지 ──────────────────────────────────────────────────


async def send_welcome(agent_type: str, pins: list[dict] | None = None) -> None:
    """
    환영 메시지를 표시합니다.

    - 핀된 기업이 있으면: 선택된 기업 정보 + 조사 시작 버튼
    - 핀된 기업이 없으면: 검색 안내
    """
    company: dict | None = cl.user_session.get("active_company")  # type: ignore[assignment]
    if pins is None:
        pins = cl.user_session.get("pins") or []

    icon = _AGENT_ICONS.get(agent_type, "🔍")
    label = _AGENT_LABELS.get(agent_type, "조사")
    desc = _AGENT_DESCRIPTIONS.get(agent_type, "")

    if not company:
        # 기업 미선택 상태
        await cl.Message(
            content=(
                f"## {icon} Wreporter — {label} 에이전트\n\n"
                f"> {desc}\n\n"
                "---\n\n"
                "**기업을 검색하여 시작하세요.**\n\n"
                "채팅창에 기업명을 입력하면 검색 결과가 표시됩니다.\n"
                "(예: `삼성`, `네이버`, `LG에너지솔루션`)"
            ),
        ).send()
        return

    corp_name = company.get("corp_name", "기업")
    market = company.get("market_label", "")
    market_str = f" · {market}" if market else ""

    # 핀된 기업 수 표시
    pin_info = ""
    if pins and len(pins) > 1:
        other_names = [p.get("corp_name", "") for p in pins if p.get("jurir_no") != company.get("jurir_no")]
        if other_names:
            pin_info = f"\n\n> 📌 핀된 기업 {len(pins)}개: **{corp_name}** (선택됨)"
            if len(other_names) <= 3:
                pin_info += ", " + ", ".join(other_names)
            else:
                pin_info += f", {', '.join(other_names[:3])} 외 {len(other_names)-3}개"

    actions = [
        cl.Action(
            name="start_research",
            payload={"agent_type": agent_type},
            label=f"🔍 {label} 조사 시작",
            description=f"{corp_name}의 {desc}을 분석합니다",
        ),
    ]

    await cl.Message(
        content=(
            f"## {icon} {corp_name}{market_str}\n\n"
            f"**{label} 에이전트** — {desc}\n"
            f"{pin_info}\n\n"
            "---\n\n"
            f"**`🔍 {label} 조사 시작`** 버튼을 클릭하거나, 원하는 내용을 직접 입력하세요.\n\n"
            f"다른 에이전트로 전환하려면 상단의 프로필 선택기에서 변경할 수 있습니다."
        ),
        actions=actions,
    ).send()


# ── 후속 질문 제안 (C5 해결) ─────────────────────────────────────


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
        content="💡 **추가로 궁금한 점이 있으신가요?**",
        actions=actions,
    ).send()


# ── 아티팩트 보고서 표시 ─────────────────────────────────────────


async def update_artifact_sidebar(jurir_no: str, agent_type: str) -> None:
    """
    DB에서 보고서 섹션을 로드하여 표시합니다.

    Reflex의 artifact_view처럼 각 섹션을 카드 형태로 보여주되,
    Chainlit에서는:
    1. 사이드 패널 (cl.Text display="side") — 전체 보고서
    2. 채팅 내 요약 메시지 — 각 섹션 제목 + 미리보기
    """
    sections = await art_db.get_sections(jurir_no, agent_type)
    if not sections:
        return

    label = _AGENT_LABELS.get(agent_type, agent_type)

    # ── 채팅 내 섹션별 요약 표시 ──
    summary_parts: list[str] = []
    full_report_parts: list[str] = []

    for sec in sections:
        content = sec.get("content", "")
        if not content:
            continue
        title = sec.get("title", sec.get("section_key", ""))
        status = sec.get("status", "done")

        # 상태 아이콘
        if status == "done":
            status_icon = "✅"
        elif status == "loading":
            status_icon = "⏳"
        else:
            status_icon = "⬜"

        # 요약: 제목 + 첫 2줄 미리보기
        preview_lines = [l for l in content.split("\n") if l.strip()][:2]
        preview = " ".join(preview_lines)[:120]
        if len(preview) >= 120:
            preview += "…"

        summary_parts.append(f"### {status_icon} {title}\n> {preview}")

        # 전체 보고서
        full_report_parts.append(f"## {title}\n\n{content}")

    if not summary_parts:
        return

    # ── 1. 채팅 내 섹션 요약 카드 ──
    summary_content = (
        f"## 📋 {label} 보고서\n\n"
        + "\n\n---\n\n".join(summary_parts)
        + "\n\n---\n\n"
        "> 📄 전체 보고서는 **사이드 패널**에서 확인할 수 있습니다. "
        "각 섹션 이름을 클릭하세요."
    )

    # ── 2. 사이드 패널 — 각 섹션을 개별 cl.Text로 ──
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

    await cl.Message(
        content=summary_content,
        elements=elements,
    ).send()
