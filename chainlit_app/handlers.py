"""
Chainlit 조사/채팅 핸들러.

기존 Reflex의 ResearchState.start_research() / send_message()를
Chainlit 방식으로 재작성한 모듈입니다.

핵심 차이:
- Reflex yield → Chainlit await msg.send() / msg.update() / msg.stream_token()
- rx.State 변수 → cl.user_session.get/set
- self._add_message() → cl.Message()
"""

from __future__ import annotations

import json
import re

import chainlit as cl

from core.agent import run_agent, parse_sections, _build_initial_context
from db import conversations as conv_db
from db import artifacts as art_db
from db.artifacts import SECTION_SCHEMAS
from chainlit_app.ui_helpers import TOOL_LABELS, send_suggestions, update_artifact_sidebar
from utils.logger import get_logger

log = get_logger("Handlers")

# ── 라벨 상수 ──────────────────────────────────────────────────────

_LABEL = {
    "general": "일반정보 분석",
    "finance": "재무정보 분석",
    "executives": "임원정보 분석",
}

# ── HITL 타임아웃 (초) ────────────────────────────────────────────
_HITL_TIMEOUT = 300  # 5분


# ── 헬퍼 ────────────────────────────────────────────────────────────


def _get_title(agent_type: str, section_key: str) -> str:
    """SECTION_SCHEMAS에서 section_key에 해당하는 제목을 찾습니다."""
    for s in SECTION_SCHEMAS.get(agent_type, []):
        if s["key"] == section_key:
            return s["title"]
    return section_key


def _extract_exec_names_from_table(text: str) -> list[str]:
    """
    임원 리스트 텍스트에서 임원 이름을 추출합니다.

    마크다운 테이블의 첫 번째 컬럼(이름)을 파싱합니다.
    """
    names: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        # 마크다운 테이블 행: | 이름 | 직위 | ... |
        if line.startswith("|") and not line.startswith("|--") and not line.startswith("| --"):
            cells = [c.strip() for c in line.split("|")]
            # 첫 빈칸과 마지막 빈칸 제거
            cells = [c for c in cells if c]
            if cells and cells[0] not in ("이름", "성명", "Name", "---", ""):
                # 헤더 행 제외
                name = cells[0].strip("*").strip()
                if name and not re.match(r"^-+$", name):
                    names.append(name)
    return names


# ── 조사 핸들러 ─────────────────────────────────────────────────────


async def handle_research() -> None:
    """
    조사 시작 버튼 클릭 시 호출.

    일반/재무: 단일 단계 조사 (run_agent 1회).
    임원정보: 2단계 HITL 조사 (C2 해결).
      - Phase 1: 임원 리스트 수집
      - HITL: 사용자가 프로파일링 대상 선택
      - Phase 2: 선택된 임원 프로파일링
    """
    agent_type: str = cl.user_session.get("agent_type")  # type: ignore[assignment]

    if agent_type == "executives":
        await _handle_executives_research()
    else:
        await _handle_standard_research()


async def _handle_standard_research() -> None:
    """일반정보/재무정보 조사 핸들러 (단일 단계)."""
    # ── 세션에서 상태 가져오기 ──
    company: dict = cl.user_session.get("active_company")  # type: ignore[assignment]
    agent_type: str = cl.user_session.get("agent_type")  # type: ignore[assignment]
    api_messages: list[dict] = cl.user_session.get("api_messages") or []
    jurir_no: str = company.get("jurir_no", "")

    cl.user_session.set("is_streaming", True)

    # ── 대화 저장/생성 → conv_id 획득 ──
    conv_id = await conv_db.save_conversation(
        jurir_no=jurir_no,
        agent_type=agent_type,
        messages=api_messages,
        corp_code=company.get("corp_code"),
        corp_name=company.get("corp_name", ""),
    )

    # ── 섹션 초기화 ──
    await art_db.init_sections(conv_id, jurir_no, agent_type)

    # ── 상태 메시지 전송 ──
    label = _LABEL.get(agent_type, agent_type)
    corp_name = company.get("corp_name", "")
    status_msg = cl.Message(
        content=f"## 🔍 {corp_name} — {label}\n\n⏳ 분석을 시작합니다...",
    )
    await status_msg.send()

    try:
        full_response = ""

        async for event in run_agent(
            agent_type=agent_type,
            company=company,
            messages=api_messages,
        ):
            if event.type == "text":
                # C3: 채팅에 스트리밍하지 않고 축적만
                full_response += event.content

            elif event.type == "progress":
                tool_name = event.metadata.get("tool_name")
                if tool_name and tool_name in TOOL_LABELS:
                    # C4: cl.Step으로 도구 호출 표시
                    async with cl.Step(name=TOOL_LABELS[tool_name]) as step:
                        step.output = event.content
                else:
                    # 도구가 아닌 진행 상황 → 상태 메시지 업데이트
                    status_msg.content = f"## 🔍 {corp_name} — {label}\n\n⏳ {event.content}"
                    await status_msg.update()

            elif event.type == "done":
                # ── 섹션 파싱 및 저장 ──
                sections = parse_sections(agent_type, full_response)
                for section_key, content in sections.items():
                    title = _get_title(agent_type, section_key)
                    await art_db.save_section(
                        conversation_id=conv_id,
                        jurir_no=jurir_no,
                        agent_type=agent_type,
                        section_key=section_key,
                        title=title,
                        content=content,
                    )

                # ── 대화 히스토리 업데이트 ──
                api_messages.append({"role": "assistant", "content": full_response})
                cl.user_session.set("api_messages", api_messages)

                await conv_db.save_conversation(
                    jurir_no=jurir_no,
                    agent_type=agent_type,
                    messages=api_messages,
                    corp_code=company.get("corp_code"),
                    corp_name=company.get("corp_name", ""),
                )

                # ── 아티팩트 사이드바 업데이트 ──
                await update_artifact_sidebar(jurir_no, agent_type)

                # ── 상태 메시지 완료로 업데이트 ──
                status_msg.content = f"## ✅ {corp_name} — {label} 완료"
                await status_msg.update()

                # ── C5: 후속 질문 제안 ──
                await send_suggestions(agent_type, company)

            elif event.type == "error":
                await cl.Message(content=f"❌ 오류: {event.content}").send()

    except Exception as e:
        log.error("조사", str(e))
        await cl.Message(content=f"❌ 에러 발생: {e}").send()
    finally:
        cl.user_session.set("is_streaming", False)


# ── 임원 HITL 조사 핸들러 (C2 해결) ──────────────────────────────


async def _handle_executives_research() -> None:
    """
    임원정보 조사 — 2단계 HITL 플로우.

    Phase 1: 임원 리스트만 수집 (에이전트에게 리스트만 요청)
    HITL:    사용자에게 프로파일링 대상 선택 요청 (cl.AskActionMessage)
    Phase 2: 선택된 임원만 프로파일링 실행
    """
    company: dict = cl.user_session.get("active_company")  # type: ignore[assignment]
    agent_type = "executives"
    api_messages: list[dict] = cl.user_session.get("api_messages") or []
    jurir_no: str = company.get("jurir_no", "")
    corp_name: str = company.get("corp_name", "기업")

    cl.user_session.set("is_streaming", True)

    # ── 대화 저장 + 섹션 초기화 ──
    conv_id = await conv_db.save_conversation(
        jurir_no=jurir_no,
        agent_type=agent_type,
        messages=api_messages,
        corp_code=company.get("corp_code"),
        corp_name=corp_name,
    )
    await art_db.init_sections(conv_id, jurir_no, agent_type)

    # ════════════════════════════════════════════════════════════════
    # Phase 1: 임원 리스트 수집
    # ════════════════════════════════════════════════════════════════
    status_msg = cl.Message(
        content=f"🔍 {corp_name}의 임원정보 분석 — 1단계: 임원 리스트 수집 중...",
    )
    await status_msg.send()

    # 에이전트에게 1단계만 수행하도록 지시
    context = _build_initial_context(agent_type, company)
    phase1_input = (
        f"{context}\n\n"
        "위 기업에 대한 임원정보 분석 **1단계**를 수행해주세요.\n"
        "다양한 소스에서 임원 목록을 수집하여 '## 임원 리스트' 섹션으로 작성해주세요.\n"
        "**중요**: 3단계(개별 프로파일링)는 아직 시작하지 마세요. "
        "임원 리스트 표만 완성하고 멈추어 주세요."
    )

    phase1_response = ""
    try:
        async for event in run_agent(
            agent_type=agent_type,
            company=company,
            messages=[],
            user_input=phase1_input,
        ):
            if event.type == "text":
                phase1_response += event.content

            elif event.type == "progress":
                tool_name = event.metadata.get("tool_name")
                if tool_name and tool_name in TOOL_LABELS:
                    async with cl.Step(name=TOOL_LABELS[tool_name]) as step:
                        step.output = event.content
                else:
                    status_msg.content = f"📋 1단계: {event.content}"
                    await status_msg.update()

            elif event.type == "done":
                # Phase 1 완료 — 임원 리스트 섹션 저장
                sections = parse_sections(agent_type, phase1_response)
                exec_list_content = sections.get("executive_list", "")

                if exec_list_content:
                    await art_db.save_section(
                        conversation_id=conv_id,
                        jurir_no=jurir_no,
                        agent_type=agent_type,
                        section_key="executive_list",
                        title="임원 리스트",
                        content=exec_list_content,
                    )

                # 대화 히스토리에 Phase 1 추가
                api_messages.append({"role": "user", "content": phase1_input})
                api_messages.append({"role": "assistant", "content": phase1_response})
                cl.user_session.set("api_messages", api_messages)

            elif event.type == "error":
                await cl.Message(content=f"❌ 1단계 오류: {event.content}").send()
                cl.user_session.set("is_streaming", False)
                return

    except Exception as e:
        log.error("임원1단계", str(e))
        await cl.Message(content=f"❌ 1단계 에러: {e}").send()
        cl.user_session.set("is_streaming", False)
        return

    # ════════════════════════════════════════════════════════════════
    # HITL: 프로파일링 대상 선택 요청
    # ════════════════════════════════════════════════════════════════
    cl.user_session.set("is_streaming", False)

    # 임원 이름 추출
    sections = parse_sections(agent_type, phase1_response)
    exec_list_content = sections.get("executive_list", phase1_response)
    exec_names = _extract_exec_names_from_table(exec_list_content)

    if not exec_names:
        # 이름 추출 실패 시 전체 리스트 표시
        await cl.Message(
            content=f"📋 **임원 리스트**\n\n{exec_list_content}\n\n"
            "임원 이름을 자동 추출하지 못했습니다. "
            "프로파일링할 임원 이름을 직접 입력해주세요.",
        ).send()

        user_msg = await cl.AskUserMessage(
            content="프로파일링할 임원 이름을 쉼표로 구분하여 입력해주세요.",
            timeout=_HITL_TIMEOUT,
        ).send()

        if user_msg:
            selected_names = [n.strip() for n in user_msg["output"].split(",") if n.strip()]
        else:
            await cl.Message(content="⏰ 시간 초과. 전원을 프로파일링합니다.").send()
            selected_names = exec_names or []
    else:
        # 임원 리스트를 번호 목록으로 표시
        name_list = "\n".join(f"{i+1}. **{name}**" for i, name in enumerate(exec_names))

        # HITL 선택 요청
        hitl_response = await cl.AskActionMessage(
            content=(
                f"📋 **{corp_name}** 임원 리스트 수집 완료 ({len(exec_names)}명)\n\n"
                f"{name_list}\n\n"
                "프로파일링 대상을 선택해주세요:"
            ),
            actions=[
                cl.Action(
                    name="hitl_choice",
                    payload=json.dumps({"choice": "all"}),
                    label=f"👥 전원 프로파일링 ({len(exec_names)}명)",
                ),
                cl.Action(
                    name="hitl_choice",
                    payload=json.dumps({"choice": "top3"}),
                    label="⭐ 상위 3명만",
                    description="신원확신도가 높은 상위 3명만 프로파일링",
                ),
                cl.Action(
                    name="hitl_choice",
                    payload=json.dumps({"choice": "manual"}),
                    label="✏️ 직접 선택",
                    description="프로파일링할 임원을 직접 입력",
                ),
            ],
            timeout=_HITL_TIMEOUT,
        ).send()

        if hitl_response is None:
            await cl.Message(content="⏰ 시간 초과. 전원을 프로파일링합니다.").send()
            selected_names = exec_names
        else:
            try:
                payload = json.loads(hitl_response.get("payload", "{}"))
            except (json.JSONDecodeError, AttributeError):
                payload = {}
            choice = payload.get("choice", "all")

            if choice == "all":
                selected_names = exec_names
                await cl.Message(content=f"✅ 전원 ({len(exec_names)}명) 프로파일링을 시작합니다.").send()

            elif choice == "top3":
                selected_names = exec_names[:3]
                top3_str = ", ".join(selected_names)
                await cl.Message(content=f"✅ 상위 3명 프로파일링: {top3_str}").send()

            elif choice == "manual":
                # 사용자가 직접 입력
                user_msg = await cl.AskUserMessage(
                    content=(
                        "프로파일링할 임원 이름을 쉼표(,)로 구분하여 입력해주세요.\n"
                        f"예: {', '.join(exec_names[:2])}"
                    ),
                    timeout=_HITL_TIMEOUT,
                ).send()

                if user_msg:
                    selected_names = [n.strip() for n in user_msg["output"].split(",") if n.strip()]
                    sel_str = ", ".join(selected_names)
                    await cl.Message(content=f"✅ 선택된 임원: {sel_str}").send()
                else:
                    await cl.Message(content="⏰ 시간 초과. 전원을 프로파일링합니다.").send()
                    selected_names = exec_names
            else:
                selected_names = exec_names

    if not selected_names:
        await cl.Message(content="⚠️ 프로파일링 대상이 없습니다. 조사를 종료합니다.").send()
        return

    # ════════════════════════════════════════════════════════════════
    # Phase 2: 선택된 임원 프로파일링
    # ════════════════════════════════════════════════════════════════
    cl.user_session.set("is_streaming", True)

    selected_str = ", ".join(selected_names)
    phase2_input = (
        f"사용자가 프로파일링 대상으로 다음 {len(selected_names)}명을 선택했습니다: {selected_str}\n\n"
        "이제 3단계(개별 임원 프로파일링)를 시작해주세요.\n"
        "각 임원에 대해 '## [임원명] 프로파일' 형식으로 섹션을 작성하고,\n"
        "기본정보/표면정보/심층정보/라포/가설/브리핑을 포함해주세요."
    )

    status_msg = cl.Message(
        content=f"🔍 {corp_name}의 임원 프로파일링 — {len(selected_names)}명 분석 중...",
    )
    await status_msg.send()

    phase2_response = ""
    try:
        async for event in run_agent(
            agent_type=agent_type,
            company=company,
            messages=api_messages,
            user_input=phase2_input,
        ):
            if event.type == "text":
                phase2_response += event.content

            elif event.type == "progress":
                tool_name = event.metadata.get("tool_name")
                if tool_name and tool_name in TOOL_LABELS:
                    async with cl.Step(name=TOOL_LABELS[tool_name]) as step:
                        step.output = event.content
                else:
                    status_msg.content = f"👤 프로파일링: {event.content}"
                    await status_msg.update()

            elif event.type == "done":
                # ── 프로파일 섹션 파싱 및 저장 ──
                sections = parse_sections(agent_type, phase2_response)

                # 큐레이션 패널 저장 (선택 기록)
                curation_content = (
                    f"**프로파일링 대상**: {selected_str}\n"
                    f"**총 {len(exec_names)}명 중 {len(selected_names)}명 선택**"
                )
                await art_db.save_section(
                    conversation_id=conv_id,
                    jurir_no=jurir_no,
                    agent_type=agent_type,
                    section_key="curation_panel",
                    title="큐레이션 패널",
                    content=curation_content,
                )

                # 프로파일 섹션 저장
                for section_key, content in sections.items():
                    title = _get_title(agent_type, section_key)
                    # 동적 프로파일 키(profile_0 등)는 SECTION_SCHEMAS에 없으므로 제목 추출
                    if section_key.startswith("profile_") and title == section_key:
                        # 섹션 첫 줄에서 제목 추출
                        first_line = content.split("\n")[0].strip("#").strip()
                        title = first_line or section_key
                    await art_db.save_section(
                        conversation_id=conv_id,
                        jurir_no=jurir_no,
                        agent_type=agent_type,
                        section_key=section_key,
                        title=title,
                        content=content,
                    )

                # ── 대화 히스토리 업데이트 ──
                api_messages.append({"role": "user", "content": phase2_input})
                api_messages.append({"role": "assistant", "content": phase2_response})
                cl.user_session.set("api_messages", api_messages)

                await conv_db.save_conversation(
                    jurir_no=jurir_no,
                    agent_type=agent_type,
                    messages=api_messages,
                    corp_code=company.get("corp_code"),
                    corp_name=corp_name,
                )

                # ── 아티팩트 사이드바 업데이트 ──
                await update_artifact_sidebar(jurir_no, agent_type)

                # ── 완료 메시지 ──
                await cl.Message(
                    content=f"✅ {corp_name} 임원 프로파일링 완료 ({len(selected_names)}명)"
                ).send()

                # ── 후속 질문 제안 ──
                await send_suggestions(agent_type, company)

            elif event.type == "error":
                await cl.Message(content=f"❌ 프로파일링 오류: {event.content}").send()

    except Exception as e:
        log.error("임원2단계", str(e))
        await cl.Message(content=f"❌ 프로파일링 에러: {e}").send()
    finally:
        cl.user_session.set("is_streaming", False)


# ── 채팅 핸들러 ─────────────────────────────────────────────────────


async def handle_chat_message(user_input: str) -> None:
    """
    사용자 후속 채팅 메시지 처리.

    run_agent()를 실행하여 실시간 스트리밍 응답을 제공합니다.
    아티팩트(섹션)는 덮어쓰지 않습니다 (B2 해결).
    """
    # ── 세션에서 상태 가져오기 ──
    company: dict = cl.user_session.get("active_company")  # type: ignore[assignment]
    agent_type: str = cl.user_session.get("agent_type")  # type: ignore[assignment]
    api_messages: list[dict] = cl.user_session.get("api_messages") or []
    jurir_no: str = company.get("jurir_no", "")

    cl.user_session.set("is_streaming", True)

    # ── 빈 응답 메시지 생성 (스트리밍용) ──
    response_msg = cl.Message(content="")
    await response_msg.send()

    try:
        full_response = ""

        async for event in run_agent(
            agent_type=agent_type,
            company=company,
            messages=api_messages,
            user_input=user_input,
        ):
            if event.type == "text":
                # 실시간 스트리밍
                full_response += event.content
                await response_msg.stream_token(event.content)

            elif event.type == "progress":
                tool_name = event.metadata.get("tool_name")
                if tool_name and tool_name in TOOL_LABELS:
                    async with cl.Step(name=TOOL_LABELS[tool_name]) as step:
                        step.output = event.content
                else:
                    # 진행 상황을 별도 메시지로 업데이트하지 않음
                    # (스트리밍 중이므로 response_msg에 간섭하지 않기 위해)
                    pass

            elif event.type == "done":
                # B2: parse_sections() 호출하지 않음 — 아티팩트 덮어쓰기 방지
                await response_msg.update()

                # C5: 후속 질문 제안
                await send_suggestions(agent_type, company)

                # ── 대화 히스토리 업데이트 ──
                api_messages.append({"role": "user", "content": user_input})
                api_messages.append({"role": "assistant", "content": full_response})
                cl.user_session.set("api_messages", api_messages)

                await conv_db.save_conversation(
                    jurir_no=jurir_no,
                    agent_type=agent_type,
                    messages=api_messages,
                    corp_code=company.get("corp_code"),
                    corp_name=company.get("corp_name", ""),
                )

            elif event.type == "error":
                await cl.Message(content=f"❌ 오류: {event.content}").send()

    except Exception as e:
        log.error("메시지", str(e))
        await cl.Message(content=f"❌ 에러 발생: {e}").send()
    finally:
        cl.user_session.set("is_streaming", False)
