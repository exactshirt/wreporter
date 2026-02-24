"""
Anthropic Claude API 스트리밍 클라이언트.

anthropic SDK 기반. messages.stream()으로 실시간 응답을 생성합니다.
Tool Use를 지원하며, 도구 호출 시 콜백을 통해 실행 결과를 반환받습니다.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Awaitable
from dataclasses import dataclass, field
from typing import Any

import anthropic

from utils.config import load_config
from utils.logger import get_logger

log = get_logger("Claude")

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_DEFAULT_MAX_TOKENS = 8192


@dataclass
class StreamEvent:
    """스트리밍 이벤트."""
    type: str          # "text" | "tool_call" | "tool_result" | "thinking" | "done" | "error"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# 도구 실행 콜백 타입: (tool_name, tool_input) -> tool_result_str
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[str]]


async def stream_chat(
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_executor: ToolExecutor | None = None,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Claude API 스트리밍 호출.

    Tool Use 루프를 자동으로 처리합니다:
    1. 모델 응답 스트리밍
    2. tool_use 블록 발견 시 tool_executor 콜백으로 실행
    3. tool_result를 messages에 추가하고 다시 호출
    4. 최종 텍스트 응답까지 반복

    Args:
        system_prompt: 시스템 프롬프트.
        messages: 대화 히스토리 (Claude API 형식).
        tools: 도구 정의 리스트 (없으면 도구 미사용).
        tool_executor: 도구 실행 콜백 (tools가 있으면 필수).
        model: 모델 ID.
        max_tokens: 최대 토큰 수.

    Yields:
        StreamEvent: 스트리밍 이벤트.
    """
    log.start("스트리밍 호출")
    cfg = load_config()
    client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)

    # 메시지 복사 (원본 변경 방지)
    msgs = [dict(m) for m in messages]

    try:
        while True:
            # ── API 호출 ──────────────────────────────────────────
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": msgs,
            }
            if tools:
                kwargs["tools"] = tools

            log.step("API", f"model={model}, msgs={len(msgs)}")

            # 응답 수집용
            collected_text = ""
            tool_use_blocks: list[dict[str, Any]] = []
            current_tool_id = ""
            current_tool_name = ""
            current_tool_input_json = ""

            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    # 텍스트 델타
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            collected_text += event.delta.text
                            yield StreamEvent(type="text", content=event.delta.text)
                        elif hasattr(event.delta, "partial_json"):
                            current_tool_input_json += event.delta.partial_json

                    # 콘텐츠 블록 시작
                    elif event.type == "content_block_start":
                        block = event.content_block
                        if hasattr(block, "type") and block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            current_tool_input_json = ""
                            yield StreamEvent(
                                type="tool_call",
                                content=f"🔍 {block.name} 실행 중...",
                                metadata={"tool_name": block.name, "tool_id": block.id},
                            )

                    # 콘텐츠 블록 종료
                    elif event.type == "content_block_stop":
                        if current_tool_name:
                            import json
                            try:
                                tool_input = json.loads(current_tool_input_json) if current_tool_input_json else {}
                            except json.JSONDecodeError:
                                tool_input = {}
                            tool_use_blocks.append({
                                "id": current_tool_id,
                                "name": current_tool_name,
                                "input": tool_input,
                            })
                            current_tool_name = ""
                            current_tool_input_json = ""

            # ── Tool Use 처리 ─────────────────────────────────────
            if tool_use_blocks and tool_executor:
                # assistant 메시지 추가 (텍스트 + tool_use 블록)
                assistant_content: list[dict[str, Any]] = []
                if collected_text:
                    assistant_content.append({"type": "text", "text": collected_text})
                for tb in tool_use_blocks:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tb["id"],
                        "name": tb["name"],
                        "input": tb["input"],
                    })
                msgs.append({"role": "assistant", "content": assistant_content})

                # 각 도구 실행
                tool_results: list[dict[str, Any]] = []
                for tb in tool_use_blocks:
                    log.step("도구", f"{tb['name']}({tb['input']})")
                    try:
                        result = await tool_executor(tb["name"], tb["input"])
                        log.ok("도구", f"{tb['name']} 완료")
                        yield StreamEvent(
                            type="tool_result",
                            content=f"✅ {tb['name']} 완료",
                            metadata={"tool_name": tb["name"], "result_preview": result[:200]},
                        )
                    except Exception as e:
                        result = f"도구 실행 오류: {e}"
                        log.error("도구", f"{tb['name']}: {e}")
                        yield StreamEvent(
                            type="tool_result",
                            content=f"❌ {tb['name']} 실패: {e}",
                            metadata={"tool_name": tb["name"], "error": str(e)},
                        )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tb["id"],
                        "content": result,
                    })

                # tool_result 메시지 추가
                msgs.append({"role": "user", "content": tool_results})

                # 다음 루프에서 모델 재호출
                continue

            # ── 도구 호출 없이 종료 ───────────────────────────────
            yield StreamEvent(type="done", content=collected_text)
            log.ok("API", f"텍스트 {len(collected_text)}자")
            log.finish("스트리밍 호출")
            return

    except anthropic.APIError as e:
        log.error("API", str(e))
        yield StreamEvent(type="error", content=str(e), metadata={"error_type": type(e).__name__})
    except Exception as e:
        log.error("API", str(e))
        yield StreamEvent(type="error", content=str(e))
