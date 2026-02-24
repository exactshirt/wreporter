"""탭 바 컴포넌트 — 일반정보/재무정보/임원정보 전환."""

import reflex as rx

from wreporter.state.research_state import ResearchState


_TABS = [
    {"key": "general", "label": "일반정보"},
    {"key": "finance", "label": "재무정보"},
    {"key": "executives", "label": "임원정보"},
]


def _tab_button(tab_key: str, tab_label: str) -> rx.Component:
    """개별 탭 버튼."""
    is_active = ResearchState.active_tab == tab_key

    return rx.box(
        rx.text(
            tab_label,
            font_size="13px",
            font_weight=rx.cond(is_active, "600", "400"),
            color=rx.cond(is_active, "var(--teal-9)", "#6a6a80"),
        ),
        padding="8px 16px",
        cursor="pointer",
        border_bottom=rx.cond(
            is_active,
            "2px solid var(--teal-9)",
            "2px solid transparent",
        ),
        _hover={"color": "#a0a0b0"},
        on_click=ResearchState.set_tab(tab_key),
    )


def tab_bar() -> rx.Component:
    """탭 바."""
    return rx.hstack(
        _tab_button("general", "일반정보"),
        _tab_button("finance", "재무정보"),
        _tab_button("executives", "임원정보"),
        spacing="0",
        border_bottom="1px solid #2a2a3a",
        padding_left="8px",
    )
