"""아티팩트 뷰 컴포넌트 — 섹션별 카드 렌더링."""

import reflex as rx

from wreporter.state.research_state import ResearchState
from wreporter.state.pin_state import PinState


def _section_card(section: rx.Var) -> rx.Component:
    """개별 섹션 카드."""
    return rx.box(
        rx.vstack(
            # 섹션 헤더
            rx.hstack(
                rx.text(
                    section["title"],
                    font_weight="600",
                    font_size="14px",
                    color="#e0e0e0",
                ),
                rx.spacer(),
                rx.cond(
                    section["status"] == "loading",
                    rx.spinner(size="1"),
                    rx.cond(
                        section["status"] == "done",
                        rx.icon("circle-check", size=14, color="var(--teal-9)"),
                        rx.icon("circle", size=14, color="#4a4a60"),
                    ),
                ),
                width="100%",
            ),
            # 섹션 내용
            rx.cond(
                section["content"] != "",
                rx.box(
                    rx.markdown(
                        section["content"],
                    ),
                    width="100%",
                    font_size="13px",
                    line_height="1.7",
                    overflow_x="auto",
                ),
                # 빈 상태
                rx.cond(
                    section["status"] == "loading",
                    rx.center(
                        rx.vstack(
                            rx.spinner(size="2"),
                            rx.text("분석 중...", font_size="12px", color="#6a6a80"),
                            spacing="2",
                            align_items="center",
                        ),
                        padding="24px",
                    ),
                    rx.center(
                        rx.text("아직 조사하지 않은 섹션입니다", font_size="12px", color="#4a4a60"),
                        padding="16px",
                    ),
                ),
            ),
            spacing="2",
            width="100%",
        ),
        padding="16px",
        border="1px solid #2a2a3a",
        border_radius="8px",
        background="#111118",
        width="100%",
    )


def _empty_state() -> rx.Component:
    """아티팩트가 없을 때의 빈 상태."""
    return rx.center(
        rx.vstack(
            rx.icon("file-text", size=48, color="#3a3a50"),
            rx.text(
                "아직 조사를 실행하지 않았습니다",
                font_size="14px",
                color="#6a6a80",
            ),
            rx.text(
                "오른쪽 채팅에서 '조사 시작'을 클릭하거나",
                font_size="12px",
                color="#4a4a60",
            ),
            rx.text(
                "원하는 내용을 직접 입력하세요",
                font_size="12px",
                color="#4a4a60",
            ),
            spacing="2",
            align_items="center",
        ),
        height="100%",
        min_height="400px",
    )


def artifact_view() -> rx.Component:
    """아티팩트 영역 전체."""
    return rx.box(
        rx.cond(
            ResearchState.has_artifact,
            # 섹션 카드 리스트
            rx.box(
                rx.vstack(
                    rx.foreach(ResearchState.current_sections, _section_card),
                    spacing="3",
                    width="100%",
                    padding="16px",
                ),
                overflow_y="auto",
                height="100%",
            ),
            # 빈 상태
            _empty_state(),
        ),
        flex="3",
        height="100%",
        border_right="1px solid #2a2a3a",
    )
