"""
에이전트 실행 엔진.

3개 전문 에이전트(General, Finance, Executives)의 실행 로직을 제공합니다.
Claude API 스트리밍 + Tool Use 루프를 관리하며,
진행 상황과 아티팩트 섹션을 이벤트로 전달합니다.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from clients.claude import StreamEvent, stream_chat
from core.tools import execute_tool, get_tools
from prompts import load_prompt
from utils.logger import get_logger

log = get_logger("Agent")


@dataclass
class AgentEvent:
    """에이전트 실행 이벤트."""
    type: str          # "text" | "progress" | "artifact_section" | "hitl_request" | "done" | "error"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ── 진행 단계 정의 ────────────────────────────────────────────────

PROGRESS_STEPS: dict[str, list[str]] = {
    "general": ["DB 조회", "웹 탐색", "콘텐츠 수집", "분석", "보고서 작성"],
    "finance": ["재무 데이터 수집", "산업 컨텍스트", "분석", "보고서 작성"],
    "executives": ["임원 리스트 확보", "큐레이션 대기", "표면 조사", "심층 조사", "보고서 작성"],
}


def _build_initial_context(agent_type: str, company: dict) -> str:
    """에이전트에게 전달할 기업 컨텍스트를 구성합니다."""
    import json
    lines = [
        f"## 대상 기업 정보",
        f"- 기업명: {company.get('corp_name', '알 수 없음')}",
        f"- 법인등록번호(jurir_no): {company.get('jurir_no', '')}",
    ]
    if company.get("corp_code"):
        lines.append(f"- DART 고유번호(corp_code): {company['corp_code']}")
    if company.get("bizr_no"):
        lines.append(f"- 사업자등록번호(bizr_no): {company['bizr_no']}")
    if company.get("corp_cls"):
        lines.append(f"- 상장구분: {company.get('market_label', company['corp_cls'])}")
    if company.get("industry"):
        lines.append(f"- 업종: {company['industry']}")
    if company.get("ceo_nm"):
        lines.append(f"- 대표자: {company['ceo_nm']}")
    if company.get("has_dart"):
        lines.append("- DART 데이터: 사용 가능")
    else:
        lines.append("- DART 데이터: 사용 불가 (FSC 전용 기업)")
    if company.get("hm_url"):
        lines.append(f"- 홈페이지: {company['hm_url']}")

    return "\n".join(lines)


async def run_agent(
    agent_type: str,
    company: dict,
    messages: list[dict[str, Any]],
    user_input: str | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    """
    에이전트를 실행합니다.

    Args:
        agent_type: "general" | "finance" | "executives".
        company: 기업 정보 dict.
        messages: 기존 대화 히스토리 (Claude API 형식).
        user_input: 사용자 입력 (None이면 초기 조사 요청).

    Yields:
        AgentEvent: 스트리밍 이벤트.
    """
    log.start(f"에이전트 실행: {agent_type} / {company.get('corp_name', '?')}")

    # ── 시스템 프롬프트 로드 ──
    system_prompt = load_prompt(f"system_{agent_type}")

    # ── 도구 정의 ──
    tools = get_tools(agent_type)

    # ── 메시지 구성 ──
    msgs = list(messages)  # 복사

    if user_input:
        # 후속 대화
        msgs.append({"role": "user", "content": user_input})
    elif not msgs:
        # 초기 조사 요청
        context = _build_initial_context(agent_type, company)
        initial_msg = (
            f"{context}\n\n"
            f"위 기업에 대한 {_AGENT_LABEL[agent_type]}를 시작해주세요. "
            f"도구를 사용하여 필요한 데이터를 수집하고, "
            f"섹션별로 분석 보고서를 작성해주세요."
        )
        msgs.append({"role": "user", "content": initial_msg})

    # ── 진행 상황 ──
    steps = PROGRESS_STEPS.get(agent_type, [])
    total_steps = len(steps)
    current_step_idx = 0

    yield AgentEvent(
        type="progress",
        content=steps[0] if steps else "시작",
        metadata={"step": 0, "total": total_steps, "percent": 0},
    )

    # ── Claude API 스트리밍 호출 ──
    full_response = ""
    tool_call_count = 0

    async for event in stream_chat(
        system_prompt=system_prompt,
        messages=msgs,
        tools=tools,
        tool_executor=execute_tool,
    ):
        if event.type == "text":
            full_response += event.content
            yield AgentEvent(type="text", content=event.content)

            # 아티팩트 섹션 감지 (## 섹션 헤더 기준)
            # 에이전트가 섹션을 작성할 때마다 진행 상황 업데이트
            if event.content.startswith("##"):
                current_step_idx = min(current_step_idx + 1, total_steps - 1)
                percent = int((current_step_idx / max(total_steps, 1)) * 100)
                yield AgentEvent(
                    type="progress",
                    content=steps[current_step_idx] if current_step_idx < total_steps else "완료",
                    metadata={"step": current_step_idx, "total": total_steps, "percent": percent},
                )

        elif event.type == "tool_call":
            tool_call_count += 1
            yield AgentEvent(
                type="progress",
                content=event.content,
                metadata={
                    **event.metadata,
                    "step": current_step_idx,
                    "total": total_steps,
                    "percent": int((current_step_idx / max(total_steps, 1)) * 100),
                },
            )

        elif event.type == "tool_result":
            yield AgentEvent(
                type="progress",
                content=event.content,
                metadata=event.metadata,
            )

        elif event.type == "done":
            yield AgentEvent(
                type="progress",
                content="완료",
                metadata={"step": total_steps, "total": total_steps, "percent": 100},
            )
            yield AgentEvent(
                type="done",
                content=full_response,
                metadata={"tool_calls": tool_call_count},
            )

        elif event.type == "error":
            yield AgentEvent(
                type="error",
                content=event.content,
                metadata=event.metadata,
            )

    log.ok("에이전트", f"텍스트 {len(full_response)}자, 도구 {tool_call_count}회")
    log.finish(f"에이전트 실행: {agent_type}")


# ── 상수 ──────────────────────────────────────────────────────────

_AGENT_LABEL = {
    "general": "일반정보 분석",
    "finance": "재무정보 분석",
    "executives": "임원정보 분석",
}


def parse_sections(agent_type: str, response_text: str) -> dict[str, str]:
    """
    에이전트 응답 텍스트에서 섹션별 내용을 추출합니다.

    프롬프트에서 정의한 섹션 키를 기반으로 응답을 분리합니다.

    Args:
        agent_type: 에이전트 유형.
        response_text: 에이전트의 전체 응답 텍스트.

    Returns:
        {section_key: section_content} dict.
    """
    from db.artifacts import SECTION_SCHEMAS

    schemas = SECTION_SCHEMAS.get(agent_type, [])
    if not schemas:
        return {"full": response_text}

    # 섹션 제목으로 분리
    sections: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []

    for line in response_text.split("\n"):
        # 섹션 헤더 감지: ## 또는 ### 로 시작하는 줄
        matched_key = _match_section_header(line, schemas)
        if matched_key:
            # 이전 섹션 저장
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = matched_key
            current_lines = [line]
        else:
            current_lines.append(line)

    # 마지막 섹션 저장
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    # 임원 프로파일은 동적 키 처리
    if agent_type == "executives":
        _extract_profiles(response_text, sections)

    return sections


def _match_section_header(line: str, schemas: list[dict[str, str]]) -> str:
    """줄이 섹션 헤더와 매칭되면 해당 section_key를 반환합니다."""
    stripped = line.strip().lstrip("#").strip()
    for schema in schemas:
        title = schema["title"]
        key = schema["key"]
        if title in stripped or key in stripped.lower().replace(" ", "_"):
            return key
    return ""


def _extract_profiles(text: str, sections: dict[str, str]) -> None:
    """임원 프로파일 섹션을 동적으로 추출합니다."""
    import re
    # "## [임원명] 프로파일" 또는 "### [임원명]" 패턴 매칭
    profile_pattern = re.compile(r"^#{2,3}\s+(.+?)\s*프로파일", re.MULTILINE)
    matches = list(profile_pattern.finditer(text))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        profile_content = text[start:end].strip()
        sections[f"profile_{i}"] = profile_content
