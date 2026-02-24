"""에이전트 연구 + 채팅 + 아티팩트 상태 관리.

각 (기업 + 에이전트 유형) 조합별로 독립적인 대화 히스토리와
섹션별 아티팩트를 관리합니다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import reflex as rx

from core.agent import AgentEvent, run_agent, parse_sections
from db import conversations as conv_db
from db import artifacts as art_db
from utils.logger import get_logger

log = get_logger("ResearchState")


class ResearchState(rx.State):
    """에이전트 대화와 아티팩트를 관리합니다."""

    # ── 탭 관리 ──
    active_tab: str = "general"  # "general" | "finance" | "executives"

    # ── 대화 히스토리 (기업+탭 조합별) ──
    # key: "{jurir_no}_{agent_type}", value: list[dict]
    # 각 dict: {"role": "user"|"assistant", "content": "...", "timestamp": "...", "type": "message"|"progress"|"tool"}
    conversations: dict[str, list[dict]] = {}

    # ── 아티팩트 (기업+탭 조합별) ──
    # key: "{jurir_no}_{agent_type}", value: dict[section_key, content]
    artifacts: dict[str, dict[str, str]] = {}
    artifact_titles: dict[str, dict[str, str]] = {}
    artifact_statuses: dict[str, dict[str, str]] = {}  # section_key -> "empty"|"loading"|"done"

    # ── 스트리밍 상태 ──
    is_streaming: bool = False
    streaming_text: str = ""

    # ── Progress bar ──
    progress_step: str = ""
    progress_percent: int = 0
    progress_steps: list[str] = []

    # ── 채팅 입력 ──
    chat_input: str = ""

    # ── Computed Vars ──

    @rx.var
    def conv_key(self) -> str:
        """현재 (기업+탭) 조합 키."""
        from wreporter.state.pin_state import PinState
        # Reflex computed var에서는 다른 state를 직접 참조 불가
        # 대신 _active_jurir_no 필드를 PinState 변경 시 동기화
        return f"{self._active_jurir_no}_{self.active_tab}"

    @rx.var
    def current_messages(self) -> list[dict]:
        """현재 대화 메시지 리스트."""
        key = f"{self._active_jurir_no}_{self.active_tab}"
        return self.conversations.get(key, [])

    @rx.var
    def current_sections(self) -> list[dict]:
        """현재 탭의 아티팩트 섹션 리스트 (UI 렌더링용)."""
        key = f"{self._active_jurir_no}_{self.active_tab}"
        contents = self.artifacts.get(key, {})
        titles = self.artifact_titles.get(key, {})
        statuses = self.artifact_statuses.get(key, {})

        sections = []
        for section_key, content in contents.items():
            sections.append({
                "key": section_key,
                "title": titles.get(section_key, section_key),
                "content": content,
                "status": statuses.get(section_key, "empty"),
            })
        return sections

    @rx.var
    def has_artifact(self) -> bool:
        """현재 탭에 아티팩트(로딩 중 또는 완료)가 있는지."""
        key = f"{self._active_jurir_no}_{self.active_tab}"
        statuses = self.artifact_statuses.get(key, {})
        return any(s in ("done", "loading") for s in statuses.values())

    # ── 내부 상태 (PinState와 동기화) ──
    _active_jurir_no: str = ""

    # ── 이벤트 핸들러 ──

    @rx.event
    def set_tab(self, tab: str) -> None:
        """탭 전환."""
        self.active_tab = tab

    @rx.event
    def set_chat_input(self, value: str) -> None:
        self.chat_input = value

    @rx.event
    def handle_chat_submit(self, form_data: dict):
        """폼 제출 시 (Enter 키 또는 전송 버튼) send_message 이벤트 디스패치."""
        return ResearchState.send_message

    @rx.event
    async def sync_active_company(self, jurir_no: str) -> None:
        """PinState에서 활성 기업이 변경될 때 호출."""
        self._active_jurir_no = jurir_no
        if not jurir_no:
            return
        # DB에서 대화/아티팩트 로드
        await self._load_data_for_company(jurir_no)

    @rx.event
    async def start_research(self) -> None:
        """조사 시작 버튼 클릭. 에이전트 실행."""
        if self.is_streaming:
            return

        # PinState에서 현재 기업 정보 가져오기
        pin_state = await self.get_state(PinState)
        company = pin_state.active_company
        jurir_no = pin_state.active_jurir_no
        if not jurir_no:
            return

        key = f"{jurir_no}_{self.active_tab}"
        agent_type = self.active_tab

        # 스트리밍 시작
        self.is_streaming = True
        self.streaming_text = ""
        self.progress_percent = 0
        self.progress_step = "시작"

        # 초기 안내 메시지
        self._add_message(key, "assistant", f"🔍 {company.get('corp_name', '')}의 {_TAB_LABEL[agent_type]}를 시작합니다...")
        yield

        try:
            # 기존 Claude API 메시지 형식의 히스토리
            api_messages = self._get_api_messages(key)

            # 대화 저장 (또는 생성)
            conv_id = await conv_db.save_conversation(
                jurir_no=jurir_no,
                agent_type=agent_type,
                messages=api_messages,
                corp_code=company.get("corp_code"),
                corp_name=company.get("corp_name", ""),
            )

            # 섹션 초기화
            await art_db.init_sections(conv_id, jurir_no, agent_type)
            self._init_section_statuses(key, agent_type)
            yield

            # 에이전트 실행
            full_response = ""
            async for event in run_agent(
                agent_type=agent_type,
                company=company,
                messages=api_messages,
            ):
                if event.type == "text":
                    full_response += event.content
                    self.streaming_text += event.content
                    yield

                elif event.type == "progress":
                    self.progress_step = event.content
                    self.progress_percent = event.metadata.get("percent", 0)
                    self._add_message(key, "system", event.content, msg_type="progress")
                    yield

                elif event.type == "done":
                    # 응답 파싱 및 섹션 저장
                    sections = parse_sections(agent_type, full_response)
                    for section_key, content in sections.items():
                        schema = art_db.SECTION_SCHEMAS.get(agent_type, [])
                        title = section_key
                        for s in schema:
                            if s["key"] == section_key:
                                title = s["title"]
                                break

                        await art_db.save_section(
                            conversation_id=conv_id,
                            jurir_no=jurir_no,
                            agent_type=agent_type,
                            section_key=section_key,
                            title=title,
                            content=content,
                        )
                        # State 업데이트
                        if key not in self.artifacts:
                            self.artifacts[key] = {}
                        self.artifacts[key][section_key] = content
                        if key not in self.artifact_titles:
                            self.artifact_titles[key] = {}
                        self.artifact_titles[key][section_key] = title
                        if key not in self.artifact_statuses:
                            self.artifact_statuses[key] = {}
                        self.artifact_statuses[key][section_key] = "done"

                    # assistant 메시지 저장
                    self._add_message(key, "assistant", "보고서 작성이 완료되었습니다. 왼쪽에서 확인하세요.")
                    api_messages.append({"role": "assistant", "content": full_response})
                    await conv_db.save_conversation(
                        jurir_no=jurir_no,
                        agent_type=agent_type,
                        messages=api_messages,
                        corp_code=company.get("corp_code"),
                        corp_name=company.get("corp_name", ""),
                    )

                elif event.type == "error":
                    self._add_message(key, "system", f"❌ 오류: {event.content}", msg_type="error")

        except Exception as e:
            log.error("조사", str(e))
            self._add_message(key, "system", f"❌ 에러 발생: {e}", msg_type="error")
        finally:
            self.is_streaming = False
            self.streaming_text = ""
            self.progress_percent = 100
            self.progress_step = "완료"

    @rx.event
    async def send_message(self) -> None:
        """채팅 메시지 전송."""
        if self.is_streaming or not self.chat_input.strip():
            return

        pin_state = await self.get_state(PinState)
        company = pin_state.active_company
        jurir_no = pin_state.active_jurir_no
        if not jurir_no:
            return

        key = f"{jurir_no}_{self.active_tab}"
        agent_type = self.active_tab
        user_input = self.chat_input.strip()

        # 사용자 메시지 추가
        self._add_message(key, "user", user_input)
        self.chat_input = ""
        self.is_streaming = True
        self.streaming_text = ""
        yield

        try:
            api_messages = self._get_api_messages(key)

            full_response = ""
            async for event in run_agent(
                agent_type=agent_type,
                company=company,
                messages=api_messages,
                user_input=user_input,
            ):
                if event.type == "text":
                    full_response += event.content
                    self.streaming_text += event.content
                    yield

                elif event.type == "progress":
                    self.progress_step = event.content
                    self.progress_percent = event.metadata.get("percent", 0)
                    self._add_message(key, "system", event.content, msg_type="progress")
                    yield

                elif event.type == "done":
                    # 아티팩트 업데이트 여부 판단
                    sections = parse_sections(agent_type, full_response)
                    if sections:
                        conv = await conv_db.get_conversation(jurir_no, agent_type)
                        conv_id = conv["id"] if conv else ""
                        for section_key, content in sections.items():
                            if content.strip():
                                schema = art_db.SECTION_SCHEMAS.get(agent_type, [])
                                title = section_key
                                for s in schema:
                                    if s["key"] == section_key:
                                        title = s["title"]
                                        break
                                await art_db.save_section(
                                    conv_id, jurir_no, agent_type,
                                    section_key, title, content,
                                )
                                if key not in self.artifacts:
                                    self.artifacts[key] = {}
                                self.artifacts[key][section_key] = content
                                if key not in self.artifact_statuses:
                                    self.artifact_statuses[key] = {}
                                self.artifact_statuses[key][section_key] = "done"

                    self._add_message(key, "assistant", full_response)

                    # 대화 저장
                    api_messages.append({"role": "user", "content": user_input})
                    api_messages.append({"role": "assistant", "content": full_response})
                    await conv_db.save_conversation(
                        jurir_no=jurir_no,
                        agent_type=agent_type,
                        messages=api_messages,
                        corp_code=company.get("corp_code"),
                        corp_name=company.get("corp_name", ""),
                    )

                elif event.type == "error":
                    self._add_message(key, "system", f"❌ 오류: {event.content}", msg_type="error")

        except Exception as e:
            log.error("메시지", str(e))
            self._add_message(key, "system", f"❌ 에러 발생: {e}", msg_type="error")
        finally:
            self.is_streaming = False
            self.streaming_text = ""

    # ── 내부 헬퍼 ──

    def _add_message(
        self, key: str, role: str, content: str, msg_type: str = "message"
    ) -> None:
        """대화에 메시지를 추가합니다."""
        if key not in self.conversations:
            self.conversations[key] = []
        self.conversations[key] = self.conversations[key] + [{
            "role": role,
            "content": content,
            "type": msg_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    def _get_api_messages(self, key: str) -> list[dict]:
        """UI 메시지를 Claude API 형식으로 변환합니다."""
        msgs = self.conversations.get(key, [])
        api_msgs = []
        for m in msgs:
            if m.get("type") == "progress":
                continue  # 진행 상황 메시지는 API에 포함하지 않음
            if m["role"] in ("user", "assistant"):
                api_msgs.append({"role": m["role"], "content": m["content"]})
        return api_msgs

    def _init_section_statuses(self, key: str, agent_type: str) -> None:
        """섹션 상태를 초기화합니다."""
        schemas = art_db.SECTION_SCHEMAS.get(agent_type, [])
        if key not in self.artifact_statuses:
            self.artifact_statuses[key] = {}
        if key not in self.artifacts:
            self.artifacts[key] = {}
        if key not in self.artifact_titles:
            self.artifact_titles[key] = {}
        for s in schemas:
            if s["key"] not in self.artifact_statuses[key]:
                self.artifact_statuses[key][s["key"]] = "loading"
                self.artifacts[key][s["key"]] = ""
                self.artifact_titles[key][s["key"]] = s["title"]

    async def _load_data_for_company(self, jurir_no: str) -> None:
        """기업의 모든 에이전트 데이터를 DB에서 로드합니다.

        최적화: 6개 쿼리를 asyncio.gather로 병렬 실행.
        """
        agent_types = ("general", "finance", "executives")

        # 6개 쿼리를 병렬 실행 (기존 순차 6회 → 병렬 1회)
        results = await asyncio.gather(
            conv_db.get_conversation(jurir_no, "general"),
            conv_db.get_conversation(jurir_no, "finance"),
            conv_db.get_conversation(jurir_no, "executives"),
            art_db.get_sections(jurir_no, "general"),
            art_db.get_sections(jurir_no, "finance"),
            art_db.get_sections(jurir_no, "executives"),
        )
        convs = results[:3]
        sections_list = results[3:]

        for i, agent_type in enumerate(agent_types):
            key = f"{jurir_no}_{agent_type}"

            # 대화 로드
            conv = convs[i]
            if conv and conv.get("messages"):
                ui_msgs = []
                for m in conv["messages"]:
                    if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                        ui_msgs.append({
                            "role": m["role"],
                            "content": m.get("content", ""),
                            "type": "message",
                            "timestamp": m.get("timestamp", ""),
                        })
                self.conversations[key] = ui_msgs

            # 아티팩트 로드
            sections = sections_list[i]
            if sections:
                self.artifacts[key] = {}
                self.artifact_titles[key] = {}
                self.artifact_statuses[key] = {}
                for s in sections:
                    self.artifacts[key][s["section_key"]] = s.get("content", "")
                    self.artifact_titles[key][s["section_key"]] = s.get("title", "")
                    self.artifact_statuses[key][s["section_key"]] = s.get("status", "empty")


# ── 상수 ──────────────────────────────────────────────────────────

_TAB_LABEL = {
    "general": "일반정보 분석",
    "finance": "재무정보 분석",
    "executives": "임원정보 분석",
}

# PinState import (순환 참조 방지를 위해 함수 내에서만 사용)
from wreporter.state.pin_state import PinState  # noqa: E402
