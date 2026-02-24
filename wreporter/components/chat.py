"""채팅 영역 컴포넌트 — 에이전트 대화 + progress bar."""

import reflex as rx

from wreporter.state.research_state import ResearchState
from wreporter.state.pin_state import PinState


def _message_bubble(msg: rx.Var) -> rx.Component:
    """개별 메시지 버블."""
    return rx.cond(
        msg["type"] == "progress",
        # 진행 상황 메시지
        rx.box(
            rx.hstack(
                rx.text(
                    msg["content"],
                    font_size="11px",
                    color="#6a6a80",
                    font_style="italic",
                ),
                spacing="1",
                padding_left="8px",
            ),
            padding="2px 0",
        ),
        # 일반 메시지
        rx.box(
            rx.vstack(
                rx.cond(
                    msg["role"] == "user",
                    # 사용자 메시지
                    rx.box(
                        rx.text(
                            msg["content"],
                            font_size="13px",
                            color="#e0e0e0",
                        ),
                        background="#1a3a5a",
                        padding="8px 12px",
                        border_radius="12px 12px 4px 12px",
                        max_width="85%",
                        align_self="flex-end",
                    ),
                    rx.cond(
                        msg["role"] == "assistant",
                        # 에이전트 메시지
                        rx.box(
                            rx.markdown(
                                msg["content"],
                                font_size="13px",
                            ),
                            background="#1a1a28",
                            padding="8px 12px",
                            border_radius="12px 12px 12px 4px",
                            max_width="85%",
                            align_self="flex-start",
                        ),
                        # 시스템 메시지 (에러 등)
                        rx.box(
                            rx.text(
                                msg["content"],
                                font_size="12px",
                                color=rx.cond(
                                    msg["type"] == "error",
                                    "#ff6b6b",
                                    "#6a6a80",
                                ),
                            ),
                            padding="4px 8px",
                            align_self="center",
                        ),
                    ),
                ),
                width="100%",
                align_items=rx.cond(
                    msg["role"] == "user",
                    "flex-end",
                    "flex-start",
                ),
            ),
            padding="4px 0",
            width="100%",
        ),
    )


def _progress_bar() -> rx.Component:
    """진행률 바."""
    return rx.cond(
        ResearchState.is_streaming,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.text(
                        ResearchState.progress_step,
                        font_size="11px",
                        color="#a0a0b0",
                    ),
                    rx.spacer(),
                    rx.text(
                        ResearchState.progress_percent.to(str) + "%",
                        font_size="11px",
                        color="var(--teal-9)",
                    ),
                    width="100%",
                ),
                rx.progress(
                    value=ResearchState.progress_percent,
                    width="100%",
                    size="1",
                    color_scheme="teal",
                ),
                spacing="1",
                width="100%",
            ),
            padding="8px 12px",
            border_top="1px solid #2a2a3a",
        ),
        rx.fragment(),
    )


def _welcome_message() -> rx.Component:
    """초기 환영 메시지."""
    return rx.center(
        rx.vstack(
            rx.icon("bot", size=32, color="var(--teal-9)"),
            rx.text(
                "에이전트가 준비되었습니다",
                font_size="14px",
                color="#a0a0b0",
                font_weight="500",
            ),
            rx.text(
                "아래 '조사 시작' 버튼을 클릭하거나",
                font_size="12px",
                color="#6a6a80",
            ),
            rx.text(
                "원하는 조사 내용을 직접 입력하세요",
                font_size="12px",
                color="#6a6a80",
            ),
            spacing="2",
            align_items="center",
        ),
        height="100%",
        min_height="200px",
    )


def _start_button() -> rx.Component:
    """조사 시작 버튼."""
    return rx.cond(
        PinState.has_pinned & ~ResearchState.is_streaming,
        rx.button(
            rx.icon("search", size=14),
            "조사 시작",
            variant="soft",
            color_scheme="teal",
            size="2",
            on_click=ResearchState.start_research,
            width="100%",
        ),
        rx.fragment(),
    )


def _chat_input() -> rx.Component:
    """채팅 입력 영역. Enter 키 또는 전송 버튼으로 전송."""
    return rx.box(
        rx.vstack(
            _start_button(),
            rx.form(
                rx.hstack(
                    rx.input(
                        placeholder="메시지를 입력하세요...",
                        value=ResearchState.chat_input,
                        on_change=ResearchState.set_chat_input,
                        name="message",
                        variant="soft",
                        size="2",
                        width="100%",
                        disabled=ResearchState.is_streaming,
                    ),
                    rx.icon_button(
                        rx.icon("send", size=14),
                        variant="soft",
                        color_scheme="teal",
                        size="2",
                        type="submit",
                        disabled=ResearchState.is_streaming,
                    ),
                    width="100%",
                    spacing="2",
                ),
                on_submit=ResearchState.handle_chat_submit,
                reset_on_submit=False,
            ),
            spacing="2",
            width="100%",
        ),
        padding="12px",
        border_top="1px solid #2a2a3a",
    )


def chat_panel() -> rx.Component:
    """채팅 영역 전체."""
    return rx.box(
        rx.vstack(
            # 메시지 리스트
            rx.cond(
                ResearchState.current_messages.length() > 0,
                rx.box(
                    rx.vstack(
                        rx.foreach(ResearchState.current_messages, _message_bubble),
                        spacing="1",
                        width="100%",
                        padding="12px",
                    ),
                    overflow_y="auto",
                    flex="1",
                ),
                _welcome_message(),
            ),
            # 스트리밍 텍스트 (실시간)
            rx.cond(
                ResearchState.is_streaming & (ResearchState.streaming_text != ""),
                rx.box(
                    rx.markdown(
                        ResearchState.streaming_text,
                        font_size="13px",
                    ),
                    background="#1a1a28",
                    padding="8px 12px",
                    margin="0 12px",
                    border_radius="8px",
                    max_height="200px",
                    overflow_y="auto",
                ),
                rx.fragment(),
            ),
            # Progress bar
            _progress_bar(),
            # 입력
            _chat_input(),
            spacing="0",
            height="100%",
        ),
        flex="2",
        height="100%",
        display="flex",
        flex_direction="column",
    )
