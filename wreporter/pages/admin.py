"""
관리자 페이지.

시스템 대시보드 + 기업 데이터 관리 UI를 제공합니다.
라우트: /admin
"""

import reflex as rx

from wreporter.state.admin_state import AdminState


# ── 시스템 대시보드 헬퍼 ─────────────────────────────────────────────────────


def stat_card(label: str, value: rx.Var, description: str = "") -> rx.Component:
    """통계 카드 하나."""
    return rx.card(
        rx.vstack(
            rx.text(label, size="2", color_scheme="gray"),
            rx.heading(value, size="6"),
            rx.cond(
                description != "",
                rx.text(description, size="1", color="gray"),
                rx.fragment(),
            ),
            align="center",
            spacing="1",
        ),
    )


def corp_cls_card() -> rx.Component:
    """상장구분별 분포 카드."""
    return rx.card(
        rx.vstack(
            rx.text("상장구분별", size="2", color_scheme="gray"),
            rx.vstack(
                rx.hstack(
                    rx.text("코스피:", size="2", weight="bold"),
                    rx.text(AdminState.corp_cls_y, size="2"),
                    spacing="1",
                ),
                rx.hstack(
                    rx.text("코스닥:", size="2", weight="bold"),
                    rx.text(AdminState.corp_cls_k, size="2"),
                    spacing="1",
                ),
                rx.hstack(
                    rx.text("코넥스:", size="2", weight="bold"),
                    rx.text(AdminState.corp_cls_n, size="2"),
                    spacing="1",
                ),
                rx.hstack(
                    rx.text("외감:", size="2", weight="bold"),
                    rx.text(AdminState.corp_cls_e, size="2"),
                    spacing="1",
                ),
                spacing="1",
            ),
            align="center",
            spacing="2",
        ),
    )


def api_key_row(key_info: rx.Var) -> rx.Component:
    """API 키 상태 한 줄."""
    return rx.hstack(
        rx.cond(
            key_info["configured"] == "True",
            rx.badge("ON", color_scheme="green", variant="solid", size="1"),
            rx.badge("OFF", color_scheme="red", variant="solid", size="1"),
        ),
        rx.text(key_info["display_name"], size="2"),
        rx.cond(
            key_info["required"] == "True",
            rx.badge("필수", color_scheme="red", variant="outline", size="1"),
            rx.badge("선택", color_scheme="gray", variant="outline", size="1"),
        ),
        spacing="2",
        align="center",
    )


def ping_result_row(result: rx.Var) -> rx.Component:
    """연결 테스트 결과 한 줄."""
    return rx.hstack(
        rx.cond(
            result["success"] == "True",
            rx.badge("OK", color_scheme="green", variant="solid", size="1"),
            rx.badge("FAIL", color_scheme="red", variant="solid", size="1"),
        ),
        rx.text(result["name"], size="2", weight="bold", min_width="80px"),
        rx.text(result["message"], size="2"),
        rx.text(
            result["elapsed_ms"] + "ms",
            size="1",
            color="gray",
        ),
        spacing="2",
        align="center",
    )


def dashboard_section() -> rx.Component:
    """시스템 대시보드 섹션."""
    return rx.vstack(
        rx.heading("시스템 대시보드", size="5"),
        # DB 통계
        rx.cond(
            AdminState.stats_loading,
            rx.center(rx.spinner(size="3"), width="100%", padding="4"),
            rx.grid(
                stat_card("총 기업 수", AdminState.total_companies),
                stat_card("DART 등록", AdminState.with_corp_code),
                stat_card("FSC 전용", AdminState.without_corp_code),
                corp_cls_card(),
                columns="4",
                spacing="4",
                width="100%",
            ),
        ),
        # API 키 상태
        rx.heading("API 키 상태", size="4"),
        rx.vstack(
            rx.foreach(AdminState.api_keys, api_key_row),
            spacing="2",
        ),
        # 연결 테스트
        rx.heading("연결 테스트", size="4"),
        rx.button(
            "테스트 실행",
            on_click=AdminState.run_ping_tests,
            loading=AdminState.ping_loading,
            size="2",
        ),
        rx.cond(
            AdminState.ping_results.length() > 0,
            rx.vstack(
                rx.foreach(AdminState.ping_results, ping_result_row),
                spacing="2",
            ),
            rx.fragment(),
        ),
        width="100%",
        spacing="4",
    )


# ── 기업 데이터 관리 헬퍼 ────────────────────────────────────────────────────


def search_result_row(row: rx.Var) -> rx.Component:
    """검색 결과 테이블 행."""
    return rx.table.row(
        rx.table.cell(rx.text(row["corp_name"], size="2")),
        rx.table.cell(rx.text(row["market_label"], size="2")),
        rx.table.cell(rx.text(row["ceo_nm"], size="2")),
        rx.table.cell(
            rx.cond(
                row["has_dart"],
                rx.badge("DART", color_scheme="green", size="1"),
                rx.badge("-", color_scheme="gray", size="1"),
            ),
        ),
        on_click=AdminState.select_company(row),
        cursor="pointer",
        _hover={"background": "var(--gray-a3)"},
    )


def info_item(label: str, value: rx.Var) -> rx.Component:
    """기업 상세 정보 한 줄."""
    return rx.hstack(
        rx.text(label + ":", size="2", weight="bold", min_width="100px"),
        rx.text(value, size="2"),
        spacing="2",
    )


def company_search_section() -> rx.Component:
    """기업 검색 섹션."""
    return rx.vstack(
        rx.heading("기업 데이터 관리", size="5"),
        rx.hstack(
            rx.input(
                placeholder="기업명 검색 (2자 이상)",
                value=AdminState.search_keyword,
                on_change=AdminState.set_search_keyword,
                on_key_down=AdminState.handle_search_key,
                width="300px",
                size="2",
            ),
            rx.button(
                "검색",
                on_click=AdminState.search_companies,
                loading=AdminState.search_loading,
                size="2",
            ),
            spacing="2",
        ),
        rx.cond(
            AdminState.search_results.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("기업명"),
                        rx.table.column_header_cell("구분"),
                        rx.table.column_header_cell("대표자"),
                        rx.table.column_header_cell("DART"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(AdminState.search_results, search_result_row),
                ),
                width="100%",
                size="2",
            ),
            rx.fragment(),
        ),
        width="100%",
        spacing="4",
    )


def company_detail_section() -> rx.Component:
    """선택 기업 상세 정보 + API 데이터 조회."""
    return rx.cond(
        AdminState.has_selected,
        rx.vstack(
            rx.separator(),
            rx.hstack(
                rx.heading(AdminState.selected_company["corp_name"], size="5"),
                rx.button(
                    "선택 해제",
                    on_click=AdminState.clear_selection,
                    variant="outline",
                    size="1",
                ),
                spacing="3",
                align="center",
            ),
            # 기본 정보
            rx.card(
                rx.vstack(
                    rx.heading("기본 정보", size="4"),
                    rx.grid(
                        info_item("대표자", AdminState.selected_company["ceo_nm"]),
                        info_item("구분", AdminState.selected_company["market_label"]),
                        info_item(
                            "DART 코드",
                            rx.cond(
                                AdminState.selected_company["corp_code"],
                                AdminState.selected_company["corp_code"],
                                "-",
                            ),
                        ),
                        info_item(
                            "법인번호",
                            rx.cond(
                                AdminState.selected_company["jurir_no"],
                                AdminState.selected_company["jurir_no"],
                                "-",
                            ),
                        ),
                        columns="2",
                        spacing="2",
                        width="100%",
                    ),
                    spacing="3",
                ),
                width="100%",
            ),
            # API 데이터 조회 버튼
            rx.heading("외부 API 데이터 조회", size="4"),
            rx.hstack(
                rx.cond(
                    AdminState.selected_company["has_dart"],
                    rx.hstack(
                        rx.button(
                            "재무제표",
                            on_click=AdminState.fetch_dart_finance,
                            size="2",
                            variant="outline",
                        ),
                        rx.button(
                            "임원현황",
                            on_click=AdminState.fetch_dart_executives,
                            size="2",
                            variant="outline",
                        ),
                        rx.button(
                            "공시목록",
                            on_click=AdminState.fetch_dart_disclosures,
                            size="2",
                            variant="outline",
                        ),
                        spacing="2",
                    ),
                    rx.text("DART 데이터 없음 (corp_code 미보유)", size="2", color="gray"),
                ),
                rx.button(
                    "FSC 데이터",
                    on_click=AdminState.fetch_fsc_data,
                    size="2",
                    variant="outline",
                ),
                spacing="3",
                align="center",
            ),
            rx.cond(
                AdminState.api_data_loading,
                rx.center(rx.spinner(size="3"), width="100%", padding="4"),
                rx.fragment(),
            ),
            # 결과 표시 영역
            api_data_display(),
            width="100%",
            spacing="4",
        ),
        rx.fragment(),
    )


def api_data_display() -> rx.Component:
    """API 데이터 결과 표시."""
    return rx.vstack(
        # DART 재무제표
        rx.cond(
            AdminState.dart_finance.length() > 0,
            rx.vstack(
                rx.heading("DART 재무제표 (2023)", size="4"),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("계정과목"),
                            rx.table.column_header_cell("당기"),
                            rx.table.column_header_cell("전기"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminState.dart_finance,
                            lambda row: rx.table.row(
                                rx.table.cell(
                                    rx.text(row["account_nm"], size="2")
                                ),
                                rx.table.cell(
                                    rx.text(row["thstrm_amount"], size="2")
                                ),
                                rx.table.cell(
                                    rx.text(row["frmtrm_amount"], size="2")
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                    size="1",
                ),
                spacing="2",
            ),
            rx.fragment(),
        ),
        # DART 임원현황
        rx.cond(
            AdminState.dart_executives.length() > 0,
            rx.vstack(
                rx.heading("DART 임원현황", size="4"),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("이름"),
                            rx.table.column_header_cell("직위"),
                            rx.table.column_header_cell("담당업무"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminState.dart_executives,
                            lambda row: rx.table.row(
                                rx.table.cell(rx.text(row["nm"], size="2")),
                                rx.table.cell(rx.text(row["ofcps"], size="2")),
                                rx.table.cell(
                                    rx.text(row["chrg_job"], size="2")
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                    size="1",
                ),
                spacing="2",
            ),
            rx.fragment(),
        ),
        # DART 공시목록
        rx.cond(
            AdminState.dart_disclosures.length() > 0,
            rx.vstack(
                rx.heading("DART 공시목록 (2023)", size="4"),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("보고서명"),
                            rx.table.column_header_cell("접수일"),
                            rx.table.column_header_cell("제출인"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminState.dart_disclosures,
                            lambda row: rx.table.row(
                                rx.table.cell(
                                    rx.text(row["report_nm"], size="2")
                                ),
                                rx.table.cell(
                                    rx.text(row["rcept_dt"], size="2")
                                ),
                                rx.table.cell(
                                    rx.text(row["flr_nm"], size="2")
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                    size="1",
                ),
                spacing="2",
            ),
            rx.fragment(),
        ),
        # FSC 요약재무
        rx.cond(
            AdminState.fsc_summary.length() > 0,
            rx.vstack(
                rx.heading("FSC 요약재무", size="4"),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("결산구분"),
                            rx.table.column_header_cell("매출액"),
                            rx.table.column_header_cell("영업이익"),
                            rx.table.column_header_cell("당기순이익"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminState.fsc_summary,
                            lambda row: rx.table.row(
                                rx.table.cell(
                                    rx.text(row["fnclDcdNm"], size="2")
                                ),
                                rx.table.cell(
                                    rx.text(row["enpSaleAmt"], size="2")
                                ),
                                rx.table.cell(
                                    rx.text(row["enpBzopPft"], size="2")
                                ),
                                rx.table.cell(
                                    rx.text(row["enpCrtmNpf"], size="2")
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                    size="1",
                ),
                spacing="2",
            ),
            rx.fragment(),
        ),
        # FSC 기업개요
        rx.cond(
            AdminState.fsc_outline.length() > 0,
            rx.vstack(
                rx.heading("FSC 기업개요", size="4"),
                rx.card(
                    rx.vstack(
                        info_item("기업명", AdminState.fsc_outline["corpNm"]),
                        info_item("대표자", AdminState.fsc_outline["enpRprFnm"]),
                        info_item("주소", AdminState.fsc_outline["enpBsadr"]),
                        info_item("설립일", AdminState.fsc_outline["enpEstbDt"]),
                        info_item(
                            "주요사업", AdminState.fsc_outline["enpMainBizNm"]
                        ),
                        spacing="2",
                    ),
                    width="100%",
                ),
                spacing="2",
            ),
            rx.fragment(),
        ),
        width="100%",
        spacing="4",
    )


# ── 페이지 ───────────────────────────────────────────────────────────────────


@rx.page(route="/admin", title="Wreporter 관리자", on_load=AdminState.on_page_load)
def admin_page() -> rx.Component:
    """관리자 페이지."""
    return rx.container(
        rx.vstack(
            rx.heading("Wreporter 관리자", size="7"),
            rx.separator(),
            dashboard_section(),
            rx.separator(),
            company_search_section(),
            company_detail_section(),
            spacing="6",
            width="100%",
            padding_y="6",
        ),
        max_width="1200px",
        padding_x="4",
    )
