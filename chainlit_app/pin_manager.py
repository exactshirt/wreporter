"""
핀(즐겨찾기) 기업 관리 — Chainlit UI.

db/pins.py CRUD를 호출하고 결과를 Chainlit 메시지/액션으로 표시합니다.
"""

from __future__ import annotations

import json

import chainlit as cl

from db import pins as pin_db
from db import queries as query_db
from db import artifacts as art_db
from db.artifacts import SECTION_SCHEMAS
from utils.logger import get_logger

log = get_logger("PinManager")


# ── 핀 목록 로드 ─────────────────────────────────────────────────────


async def load_pins() -> list[dict]:
    """DB에서 전체 핀 목록을 가져옵니다."""
    return await pin_db.get_all_pins()


# ── 조사 진행 뱃지 (A3 해결) ─────────────────────────────────────────


async def _research_badge(jurir_no: str) -> str:
    """
    각 에이전트별 조사 완료 여부를 뱃지 문자열로 반환합니다.

    예: "일반✅ 재무⬜ 임원⬜"
    """
    labels = {"general": "일반", "finance": "재무", "executives": "임원"}
    parts: list[str] = []

    for agent_type, label in labels.items():
        sections = await art_db.get_sections(jurir_no, agent_type)
        # 스키마에 정의된 섹션 중 하나라도 done이면 완료로 판단
        done = any(s.get("status") == "done" for s in sections)
        mark = "✅" if done else "⬜"
        parts.append(f"{label}{mark}")

    return " ".join(parts)


# ── 핀 목록 렌더링 ───────────────────────────────────────────────────


async def render_pin_list(pins: list[dict] | None = None, agent_type: str | None = None) -> None:
    """
    핀 목록을 Chainlit 메시지 + 액션 버튼으로 표시합니다.

    각 핀에 대해:
    - 영문명(corp_eng_name) 표시 (A2 해결)
    - 선택/언핀 버튼 항상 표시 (A1 해결)
    - 조사 진행 뱃지 표시 (A3 해결)
    """
    # 인자가 없으면 세션에서 가져옴
    if pins is None:
        pins = cl.user_session.get("pins") or []
    if agent_type is None:
        agent_type = cl.user_session.get("agent_type") or "general"

    if not pins:
        await cl.Message(content="📌 핀된 기업이 없습니다. 기업을 검색하여 추가해주세요.").send()
        return

    lines: list[str] = []
    actions: list[cl.Action] = []

    for i, pin in enumerate(pins):
        corp_name = pin.get("corp_name", "이름 없음")
        eng_name = pin.get("corp_eng_name", "")
        market = pin.get("market_label", "")
        jurir_no = pin.get("jurir_no", "")

        badge = await _research_badge(jurir_no)

        # 표시 텍스트 구성
        name_display = f"**{corp_name}**"
        if eng_name:
            name_display += f" ({eng_name})"
        if market:
            name_display += f" · {market}"

        lines.append(f"{i + 1}. {name_display}\n   {badge}")

        # 선택 버튼 (A1)
        actions.append(
            cl.Action(
                name="select_company",
                payload=json.dumps(pin, ensure_ascii=False, default=str),
                label=f"📋 {corp_name} 선택",
            )
        )
        # 언핀 버튼 (A1)
        actions.append(
            cl.Action(
                name="unpin_company",
                payload=jurir_no,
                label=f"❌ {corp_name} 핀 해제",
            )
        )

    content = "📌 **핀된 기업 목록**\n\n" + "\n".join(lines)
    await cl.Message(content=content, actions=actions).send()


# ── 기업 검색 & 핀 추가 ──────────────────────────────────────────────


async def search_and_pin(keyword: str) -> None:
    """
    기업을 검색하여 결과를 액션 버튼으로 표시합니다.

    2글자 이상일 때만 검색을 실행합니다.
    """
    keyword = keyword.strip()
    if len(keyword) < 2:
        await cl.Message(content="⚠️ 검색어는 2글자 이상 입력해주세요.").send()
        return

    results = await query_db.search_companies(keyword)

    if not results:
        await cl.Message(content=f"🔍 '{keyword}'에 대한 검색 결과가 없습니다.").send()
        return

    actions: list[cl.Action] = []
    lines: list[str] = []

    for r in results[:10]:  # 최대 10개만 표시
        corp_name = r.get("corp_name", "이름 없음")
        eng_name = r.get("corp_eng_name", "")
        market = r.get("market_label", "")
        ceo = r.get("ceo_nm", "")

        display = f"**{corp_name}**"
        if eng_name:
            display += f" ({eng_name})"
        if market:
            display += f" · {market}"
        if ceo:
            display += f" · 대표: {ceo}"
        lines.append(f"- {display}")

        company_data = {
            "jurir_no": r.get("jurir_no", ""),
            "corp_name": corp_name,
            "corp_code": r.get("corp_code"),
            "corp_cls": r.get("corp_cls"),
            "corp_eng_name": eng_name or "",
            "market_label": market or "",
            "source_label": r.get("source_label", ""),
            "has_dart": r.get("has_dart", False),
            "industry": r.get("industry", ""),
            "ceo_nm": ceo or "",
        }
        actions.append(
            cl.Action(
                name="pin_company",
                payload=json.dumps(company_data, ensure_ascii=False, default=str),
                label=f"📌 {corp_name} 핀 추가",
            )
        )

    content = f"🔍 **'{keyword}' 검색 결과** ({len(results)}건)\n\n" + "\n".join(lines)
    await cl.Message(content=content, actions=actions).send()


async def pin_company(company: dict) -> None:
    """
    기업을 핀 목록에 추가하고 세션을 업데이트합니다.

    Args:
        company: 기업 정보 dict (jurir_no, corp_name 필수).
    """
    # has_dart가 문자열로 전달될 수 있으므로 변환
    if isinstance(company.get("has_dart"), str):
        company["has_dart"] = company["has_dart"] == "True"

    corp_name = company.get("corp_name", "기업")
    await pin_db.add_pin(company)

    # 세션의 핀 목록 갱신
    pins = await load_pins()
    cl.user_session.set("pins", pins)

    await cl.Message(content=f"📌 **{corp_name}**이(가) 핀 목록에 추가되었습니다.").send()


async def unpin_company(jurir_no: str) -> None:
    """
    핀을 해제하고 세션을 업데이트합니다.

    Args:
        jurir_no: 법인등록번호.
    """
    await pin_db.remove_pin(jurir_no)

    # 세션의 핀 목록 갱신
    pins = await load_pins()
    cl.user_session.set("pins", pins)

    await cl.Message(content="📌 핀이 해제되었습니다.").send()
