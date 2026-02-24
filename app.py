"""Chainlit 진입점 — Wreporter 메인 앱.

Chat Profiles: 일반정보 / 재무정보 / 임원정보
세션 상태: agent_type, api_messages, active_company, pins, is_streaming
"""

from __future__ import annotations

# .env 로드 (Chainlit은 자동 로드하지 않음)
from dotenv import load_dotenv
load_dotenv(override=True)

import chainlit as cl

from chainlit_app.handlers import handle_research, handle_chat_message
from chainlit_app.pin_manager import (
    load_pins,
    search_and_pin,
    render_pin_list,
    pin_company,
    unpin_company,
)
from chainlit_app.ui_helpers import send_welcome

# ── 프로필 매핑 ──────────────────────────────────────────────────
PROFILE_MAP = {
    "일반정보": "general",
    "재무정보": "finance",
    "임원정보": "executives",
}


# ── Chat Profiles ────────────────────────────────────────────────
@cl.set_chat_profiles
async def chat_profiles():
    return [
        cl.ChatProfile(
            name="일반정보",
            markdown_description="기업 개요·사업 현황·뉴스 등 일반 정보를 분석합니다.",
            icon="/public/logo.png",
        ),
        cl.ChatProfile(
            name="재무정보",
            markdown_description="재무제표·수익성·안정성 등 재무 지표를 분석합니다.",
            icon="/public/logo.png",
        ),
        cl.ChatProfile(
            name="임원정보",
            markdown_description="등기임원·주요주주·보수 현황 등 임원 정보를 분석합니다.",
            icon="/public/logo.png",
        ),
    ]


# ── 세션 시작 ────────────────────────────────────────────────────
@cl.on_chat_start
async def on_chat_start():
    """새 세션 초기화."""
    # Chat Profile에서 agent_type 결정
    profile = cl.user_session.get("chat_profile") or "일반정보"
    agent_type = PROFILE_MAP.get(profile, "general")

    # 세션 상태 초기화
    cl.user_session.set("agent_type", agent_type)
    cl.user_session.set("api_messages", [])
    cl.user_session.set("active_company", None)
    cl.user_session.set("pins", [])
    cl.user_session.set("is_streaming", False)

    # DB에서 핀 목록 로드
    pins = await load_pins()
    cl.user_session.set("pins", pins)

    # 핀된 기업이 있으면 첫 번째를 활성화
    if pins:
        cl.user_session.set("active_company", pins[0])

    # 환영 메시지 전송
    await send_welcome(agent_type, pins)


# ── 메시지 수신 ──────────────────────────────────────────────────
@cl.on_message
async def on_message(message: cl.Message):
    """사용자 메시지 처리."""
    content = message.content.strip()
    active = cl.user_session.get("active_company")

    # 기업이 선택되지 않은 경우 → 검색으로 라우팅
    if active is None:
        await search_and_pin(content)
        return

    # /조사 명령어 → 조사 시작
    if content == "/조사":
        await handle_research()
        return

    # 일반 채팅
    await handle_chat_message(content)


# ── 액션 콜백 ────────────────────────────────────────────────────
@cl.action_callback("select_company")
async def on_select_company(action: cl.Action):
    """검색 결과에서 기업 선택."""
    import json

    company = json.loads(action.payload)
    cl.user_session.set("active_company", company)

    # 핀 목록에 없으면 자동 핀
    pins = cl.user_session.get("pins") or []
    jurir_no = company.get("jurir_no", "")
    if not any(p.get("jurir_no") == jurir_no for p in pins):
        await pin_company(company)

    agent_type = cl.user_session.get("agent_type", "general")
    await cl.Message(
        content=f"**{company.get('corp_name', '')}** 가 선택되었습니다.\n"
        f"`/조사` 를 입력하면 {_agent_label(agent_type)} 분석을 시작합니다.",
    ).send()


@cl.action_callback("start_research")
async def on_start_research(action: cl.Action):
    """조사 시작 버튼."""
    await handle_research()


@cl.action_callback("suggestion")
async def on_suggestion(action: cl.Action):
    """추천 질문 클릭."""
    import json
    try:
        data = json.loads(action.payload) if isinstance(action.payload, str) else action.payload
        query = data.get("query", "") if isinstance(data, dict) else str(data)
    except (json.JSONDecodeError, AttributeError):
        query = action.payload or action.value or ""
    if query:
        await handle_chat_message(query)


@cl.action_callback("pin_company")
async def on_pin_company(action: cl.Action):
    """기업 핀 추가."""
    import json

    company = json.loads(action.payload)
    await pin_company(company)
    # 선택도 함께 수행
    cl.user_session.set("active_company", company)
    agent_type = cl.user_session.get("agent_type", "general")
    await cl.Message(
        content=f"📌 **{company.get('corp_name', '')}**가 핀 추가 및 선택되었습니다.\n"
        f"`/조사`를 입력하면 {_agent_label(agent_type)} 분석을 시작합니다.",
    ).send()


@cl.action_callback("unpin_company")
async def on_unpin_company(action: cl.Action):
    """기업 핀 해제."""
    jurir_no = action.payload or action.value or ""
    if jurir_no:
        await unpin_company(jurir_no)
        # 현재 활성 기업이 언핀된 기업이면 해제
        active = cl.user_session.get("active_company")
        if active and active.get("jurir_no") == jurir_no:
            cl.user_session.set("active_company", None)


# ── 헬퍼 ─────────────────────────────────────────────────────────
_AGENT_LABELS = {
    "general": "일반정보",
    "finance": "재무정보",
    "executives": "임원정보",
}


def _agent_label(agent_type: str) -> str:
    return _AGENT_LABELS.get(agent_type, agent_type)
