"""기업 검색 컴포넌트.

검색 입력, 결과 드롭다운, 선택된 기업 카드를 제공합니다.
rx.foreach 내부에서는 Reflex Var만 사용 가능하므로
dict.get() 대신 dict["key"], rx.match로 동적 스타일 적용.
State에서 None→"" 정규화 완료된 데이터를 받습니다.
"""

import reflex as rx

from wreporter.state.company_state import CompanyState


def _market_tag(label: rx.Var[str]) -> rx.Component:
    """시장구분 태그. rx.match로 Var 기반 동적 색상."""
    bg = rx.match(
        label,
        ("코스피", "rgba(96,165,250,0.12)"),
        ("코스닥", "rgba(52,211,153,0.12)"),
        ("코넥스", "rgba(251,191,36,0.10)"),
        ("비상장(외감)", "rgba(168,85,247,0.10)"),
        "rgba(107,114,128,0.10)",
    )
    fg = rx.match(
        label,
        ("코스피", "#60a5fa"),
        ("코스닥", "#34d399"),
        ("코넥스", "#fbbf24"),
        ("비상장(외감)", "#a855f7"),
        "#9ca3af",
    )
    return rx.text(
        label,
        font_size="8px",
        font_family="'JetBrains Mono', monospace",
        padding="1px 5px",
        border_radius="3px",
        background=bg,
        color=fg,
        white_space="nowrap",
    )


def _source_tag(label: rx.Var[str]) -> rx.Component:
    """데이터 소스 태그. source_label(DART/FSC/DART+FSC) 직접 받음."""
    bg = rx.match(
        label,
        ("DART", "rgba(52,211,153,0.10)"),
        ("FSC", "rgba(96,165,250,0.10)"),
        ("DART+FSC", "rgba(139,92,246,0.10)"),
        "transparent",
    )
    fg = rx.match(
        label,
        ("DART", "#34d399"),
        ("FSC", "#60a5fa"),
        ("DART+FSC", "#8b5cf6"),
        "#9ca3af",
    )
    return rx.cond(
        label != "",
        rx.text(
            label,
            font_size="8px",
            font_family="'JetBrains Mono', monospace",
            padding="1px 5px",
            border_radius="3px",
            background=bg,
            color=fg,
            white_space="nowrap",
        ),
        rx.fragment(),
    )


def company_result_item(company: rx.Var[dict]) -> rx.Component:
    """검색 결과 드롭다운의 개별 항목. rx.foreach에서 Var[dict]로 전달됨."""
    return rx.box(
        # Row 1: 기업명 + 영문명
        rx.hstack(
            rx.text(
                company["corp_name"],
                font_size="12px",
                font_weight="600",
                color="#e8e8f0",
            ),
            rx.cond(
                company["corp_eng_name"] != "",
                rx.text(company["corp_eng_name"], font_size="10px", color="#9b9baf"),
                rx.fragment(),
            ),
            align="baseline",
            gap="6px",
            flex_wrap="wrap",
        ),
        # Row 2: 대표 + 시장구분 + 소스
        rx.hstack(
            rx.cond(
                company["ceo_nm"] != "",
                rx.text(
                    rx.text.span("대표 ", color="#6a6a80"),
                    company["ceo_nm"],
                    font_size="9px",
                    color="#9b9baf",
                ),
                rx.fragment(),
            ),
            _market_tag(company["market_label"]),
            _source_tag(company["source_label"]),
            gap="5px",
            flex_wrap="wrap",
            align="center",
            margin_top="2px",
        ),
        # Row 3: 업종 + 홈페이지
        rx.hstack(
            rx.cond(
                company["industry"] != "",
                rx.text(
                    rx.text.span("업종 ", color="#6a6a80"),
                    company["industry"],
                    font_size="9px",
                    color="#9b9baf",
                ),
                rx.fragment(),
            ),
            rx.cond(
                company["hm_url"] != "",
                rx.text(
                    rx.text.span("홈 ", color="#6a6a80"),
                    company["hm_url"],
                    font_size="9px",
                    color="#9b9baf",
                ),
                rx.fragment(),
            ),
            gap="5px",
            flex_wrap="wrap",
            align="center",
            margin_top="2px",
        ),
        padding="8px 12px",
        cursor="pointer",
        border_bottom="1px solid rgba(255,255,255,0.06)",
        _hover={"background": "#252530"},
        on_click=CompanyState.select_company(company),
    )


def search_results_dropdown() -> rx.Component:
    """검색 결과 드롭다운."""
    return rx.cond(
        CompanyState.results.length() > 0,
        rx.box(
            rx.foreach(CompanyState.results, company_result_item),
            position="absolute",
            top="calc(100% + 4px)",
            left="0",
            right="0",
            max_height="300px",
            overflow_y="auto",
            background="#111118",
            border="1px solid rgba(255,255,255,0.10)",
            border_radius="10px",
            box_shadow="0 8px 24px rgba(0,0,0,0.4)",
            z_index="100",
        ),
        rx.fragment(),
    )


def search_box() -> rx.Component:
    """검색 입력 + 드롭다운."""
    return rx.box(
        rx.box(
            rx.icon(
                "search",
                size=14,
                color="#44445a",
                position="absolute",
                left="11px",
                top="11px",
                pointer_events="none",
            ),
            rx.input(
                placeholder="기업명을 입력하세요...",
                value=CompanyState.keyword,
                on_change=CompanyState.handle_search,
                width="100%",
                padding="10px 14px 10px 34px",
                border="1px solid rgba(255,255,255,0.10)",
                border_radius="10px",
                background="#17171f",
                color="#e8e8f0",
                font_size="13px",
                outline="none",
                _focus={
                    "border_color": "#13deb9",
                    "box_shadow": "0 0 0 3px rgba(19,222,185,0.12)",
                },
                _placeholder={"color": "#44445a"},
            ),
            rx.cond(
                CompanyState.is_loading,
                rx.spinner(
                    size="1",
                    color="#13deb9",
                    position="absolute",
                    right="12px",
                    top="12px",
                ),
                rx.fragment(),
            ),
            position="relative",
        ),
        search_results_dropdown(),
        position="relative",
        width="100%",
        max_width="400px",
        margin="0 auto",
    )


def company_card() -> rx.Component:
    """선택된 기업의 정보 카드."""
    c = CompanyState.selected_company
    return rx.cond(
        c.length() > 0,
        rx.box(
            # 기업명 + 영문명
            rx.hstack(
                rx.text(
                    c["corp_name"],
                    font_size="16px",
                    font_weight="600",
                    color="#e8e8f0",
                ),
                rx.cond(
                    c["corp_eng_name"] != "",
                    rx.text(c["corp_eng_name"], font_size="11px", color="#9b9baf"),
                    rx.fragment(),
                ),
                align="baseline",
                gap="8px",
                flex_wrap="wrap",
            ),
            # 태그 행
            rx.hstack(
                _market_tag(c["market_label"]),
                _source_tag(c["source_label"]),
                gap="4px",
                margin_top="6px",
            ),
            # 상세 정보
            rx.vstack(
                rx.cond(
                    c["ceo_nm"] != "",
                    rx.text(
                        rx.text.span("대표 ", color="#6a6a80"),
                        c["ceo_nm"],
                        font_size="11px",
                        color="#9b9baf",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    c["industry"] != "",
                    rx.text(
                        rx.text.span("업종 ", color="#6a6a80"),
                        c["industry"],
                        font_size="11px",
                        color="#9b9baf",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    c["est_dt"] != "",
                    rx.text(
                        rx.text.span("설립 ", color="#6a6a80"),
                        c["est_dt"],
                        font_size="11px",
                        color="#9b9baf",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    c["hm_url"] != "",
                    rx.text(
                        rx.text.span("홈 ", color="#6a6a80"),
                        c["hm_url"],
                        font_size="11px",
                        color="#9b9baf",
                    ),
                    rx.fragment(),
                ),
                gap="2px",
                margin_top="8px",
                align="start",
            ),
            # 뒤로가기 버튼
            rx.button(
                rx.icon("arrow-left", size=12),
                " 다른 기업 검색",
                on_click=CompanyState.clear_selection,
                variant="outline",
                size="1",
                color="#9b9baf",
                margin_top="12px",
                cursor="pointer",
            ),
            padding="16px",
            border_radius="10px",
            background="#17171f",
            border="1px solid rgba(255,255,255,0.10)",
            max_width="400px",
            margin="16px auto 0",
        ),
        rx.fragment(),
    )
