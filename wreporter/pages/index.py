"""메인 페이지 — Phase 2 통합 리서치 인터페이스."""

import reflex as rx

from wreporter.components.sidebar import sidebar
from wreporter.components.tab_bar import tab_bar
from wreporter.components.artifact_view import artifact_view
from wreporter.components.chat import chat_panel
from wreporter.state.pin_state import PinState
from wreporter.state.research_state import ResearchState


def _search_dropdown_item(company: rx.Var) -> rx.Component:
    """검색 드롭다운의 개별 항목."""
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(
                    company["corp_name"],
                    font_size="13px",
                    font_weight="500",
                    color="#e0e0e0",
                ),
                rx.hstack(
                    rx.badge(company["market_label"], variant="soft", size="1"),
                    rx.text(
                        company["industry"],
                        font_size="11px",
                        color="#6a6a80",
                        overflow="hidden",
                        text_overflow="ellipsis",
                        white_space="nowrap",
                        max_width="150px",
                    ),
                    spacing="1",
                ),
                spacing="0",
            ),
            rx.spacer(),
            rx.icon("pin", size=14, color="#6a6a80"),
            width="100%",
            align_items="center",
        ),
        padding="8px 12px",
        cursor="pointer",
        _hover={"background": "rgba(255,255,255,0.05)"},
        on_click=PinState.pin_company(company),
    )


def _header_search() -> rx.Component:
    """헤더 검색 입력 + 드롭다운."""
    return rx.box(
        rx.input(
            placeholder="기업 검색 후 핀으로 추가...",
            value=PinState.search_keyword,
            on_change=PinState.handle_search,
            variant="soft",
            size="2",
            width="300px",
        ),
        rx.cond(
            PinState.show_search_dropdown & (PinState.search_results.length() > 0),
            rx.box(
                rx.vstack(
                    rx.foreach(PinState.search_results, _search_dropdown_item),
                    spacing="0",
                ),
                position="absolute",
                top="100%",
                left="0",
                width="350px",
                max_height="400px",
                overflow_y="auto",
                background="#1a1a28",
                border="1px solid #2a2a3a",
                border_radius="8px",
                box_shadow="0 8px 32px rgba(0,0,0,0.4)",
                z_index="100",
                margin_top="4px",
            ),
            rx.fragment(),
        ),
        position="relative",
    )


def header() -> rx.Component:
    """상단 헤더."""
    return rx.hstack(
        # 로고
        rx.hstack(
            rx.icon("search", size=16, color="var(--teal-9)"),
            rx.text(
                "Wreporter",
                font_size="12px",
                font_weight="600",
                letter_spacing="-0.02em",
                color="var(--teal-9)",
            ),
            align="center",
            gap="6px",
        ),
        rx.spacer(),
        # 검색
        _header_search(),
        rx.spacer(),
        # 관리자 링크
        rx.link(
            rx.text("Admin", font_size="11px", color="#6a6a80"),
            href="/admin",
        ),
        align="center",
        padding="0 16px",
        height="38px",
        border_bottom="1px solid rgba(255,255,255,0.06)",
        background="#111118",
        flex_shrink="0",
        width="100%",
    )


def _no_pin_state() -> rx.Component:
    """핀된 기업이 없을 때의 메인 영역."""
    return rx.center(
        rx.vstack(
            rx.text("W", font_size="48px", opacity="0.08", font_weight="bold"),
            rx.text(
                "분석할 기업을 검색하고 핀으로 추가하세요",
                font_size="13px",
                color="#44445a",
                text_align="center",
            ),
            rx.text(
                "핀된 기업의 일반정보, 재무정보, 임원정보를",
                font_size="12px",
                color="#3a3a4a",
                text_align="center",
            ),
            rx.text(
                "AI 에이전트와 함께 분석할 수 있습니다",
                font_size="12px",
                color="#3a3a4a",
                text_align="center",
            ),
            spacing="2",
            align_items="center",
        ),
        flex="1",
    )


def main_content() -> rx.Component:
    """메인 콘텐츠 영역 (탭 + 아티팩트 + 채팅)."""
    return rx.cond(
        PinState.has_pinned,
        rx.box(
            # 탭 바
            tab_bar(),
            # 메인 분할 뷰
            rx.hstack(
                artifact_view(),
                chat_panel(),
                spacing="0",
                flex="1",
                overflow="hidden",
                align_items="stretch",
            ),
            display="flex",
            flex_direction="column",
            flex="1",
            overflow="hidden",
        ),
        _no_pin_state(),
    )


@rx.page(route="/", title="Wreporter", on_load=PinState.load_pins)
def index() -> rx.Component:
    """메인 페이지 — Phase 2 통합 리서치 인터페이스."""
    return rx.box(
        header(),
        rx.hstack(
            sidebar(),
            main_content(),
            spacing="0",
            flex="1",
            overflow="hidden",
            align_items="stretch",
        ),
        display="flex",
        flex_direction="column",
        height="100vh",
        overflow="hidden",
        background="#0a0a0f",
    )
