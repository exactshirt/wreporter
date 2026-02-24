"""사이드바 컴포넌트 — 핀된 기업 리스트."""

import reflex as rx

from wreporter.state.pin_state import PinState


def _research_badge(company: rx.Var) -> rx.Component:
    """조사 상태 배지 (향후 구현 시 실제 상태 반영)."""
    return rx.text(
        "일반⬜ 재무⬜ 임원⬜",
        font_size="10px",
        color="#6a6a80",
    )


def _market_tag(label: rx.Var) -> rx.Component:
    """시장구분 태그."""
    return rx.badge(
        label,
        variant="soft",
        size="1",
    )


def pin_item(company: rx.Var) -> rx.Component:
    """핀된 기업 개별 항목."""
    is_active = PinState.active_jurir_no == company["jurir_no"]

    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(
                    company["corp_name"],
                    font_weight="600",
                    font_size="13px",
                    color=rx.cond(is_active, "#e0e0e0", "#a0a0b0"),
                    _hover={"color": "#e0e0e0"},
                    overflow="hidden",
                    text_overflow="ellipsis",
                    white_space="nowrap",
                    max_width="160px",
                ),
                rx.hstack(
                    _market_tag(company["market_label"]),
                    rx.text(
                        company["industry"],
                        font_size="11px",
                        color="#6a6a80",
                        overflow="hidden",
                        text_overflow="ellipsis",
                        white_space="nowrap",
                        max_width="100px",
                    ),
                    spacing="1",
                ),
                rx.text(
                    company["ceo_nm"],
                    font_size="11px",
                    color="#6a6a80",
                ),
                _research_badge(company),
                spacing="0",
                align_items="flex-start",
            ),
            rx.spacer(),
            rx.icon_button(
                rx.icon("x", size=12),
                variant="ghost",
                size="1",
                color="#6a6a80",
                _hover={"color": "#ff6b6b"},
                on_click=PinState.unpin_company(company["jurir_no"]),
                opacity="0",
                _group_hover={"opacity": "1"},
            ),
            width="100%",
            align_items="flex-start",
        ),
        padding="8px 12px",
        cursor="pointer",
        border_left=rx.cond(
            is_active,
            "2px solid var(--teal-9)",
            "2px solid transparent",
        ),
        background=rx.cond(
            is_active,
            "rgba(0,200,180,0.05)",
            "transparent",
        ),
        _hover={"background": "rgba(255,255,255,0.03)"},
        on_click=PinState.set_active(company["jurir_no"]),
        role="group",
    )


def sidebar() -> rx.Component:
    """사이드바 전체."""
    return rx.box(
        rx.vstack(
            # 헤더
            rx.hstack(
                rx.text(
                    "핀 된 기업",
                    font_weight="600",
                    font_size="13px",
                    color="#a0a0b0",
                ),
                rx.badge(
                    PinState.pin_count,
                    variant="soft",
                    size="1",
                ),
                spacing="2",
                padding="12px 12px 8px",
            ),
            rx.separator(color_scheme="gray", size="1"),
            # 핀 리스트
            rx.cond(
                PinState.has_pinned,
                rx.vstack(
                    rx.foreach(PinState.pinned, pin_item),
                    spacing="0",
                    width="100%",
                ),
                # 빈 상태
                rx.center(
                    rx.vstack(
                        rx.icon("pin", size=24, color="#4a4a60"),
                        rx.text(
                            "기업을 검색해",
                            font_size="12px",
                            color="#6a6a80",
                            text_align="center",
                        ),
                        rx.text(
                            "핀으로 추가하세요",
                            font_size="12px",
                            color="#6a6a80",
                            text_align="center",
                        ),
                        spacing="1",
                        align_items="center",
                    ),
                    height="200px",
                ),
            ),
            spacing="0",
            width="100%",
            height="100%",
        ),
        width="240px",
        min_width="240px",
        height="100vh",
        border_right="1px solid #2a2a3a",
        background="#0d0d14",
        overflow_y="auto",
    )
