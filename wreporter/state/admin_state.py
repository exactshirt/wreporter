"""
관리자 페이지 상태.

core/admin.py의 비즈니스 로직을 호출하고 결과를 UI에 반영합니다.
State에 로직을 직접 쓰지 않고, core/ 함수만 호출합니다.
"""

import reflex as rx


class AdminState(rx.State):
    """관리자 페이지 UI 상태."""

    # ── 시스템 대시보드 ──────────────────────────────────────

    # DB 통계
    total_companies: int = 0
    with_corp_code: int = 0
    without_corp_code: int = 0
    corp_cls_y: int = 0
    corp_cls_k: int = 0
    corp_cls_n: int = 0
    corp_cls_e: int = 0
    stats_loaded: bool = False
    stats_loading: bool = False

    # API 키 상태
    api_keys: list[dict[str, str]] = []

    # 연결 테스트 결과
    ping_results: list[dict[str, str]] = []
    ping_loading: bool = False

    # ── 기업 데이터 관리 ─────────────────────────────────────

    search_keyword: str = ""
    search_results: list[dict] = []
    search_loading: bool = False

    selected_company: dict = {}
    has_selected: bool = False

    # 외부 API 데이터
    dart_finance: list[dict] = []
    dart_executives: list[dict] = []
    dart_disclosures: list[dict] = []
    fsc_summary: list[dict] = []
    fsc_outline: dict = {}
    api_data_loading: bool = False

    # ── 페이지 로드 ──────────────────────────────────────────

    async def on_page_load(self):
        """페이지 진입 시 DB 통계 + API 키 상태를 로드합니다."""
        self._load_api_keys()
        self.stats_loading = True
        yield

        from core.admin import get_db_stats

        stats = await get_db_stats()
        self.total_companies = stats.total_companies
        self.with_corp_code = stats.with_corp_code
        self.without_corp_code = stats.without_corp_code
        self.corp_cls_y = stats.by_corp_cls.get("Y", 0)
        self.corp_cls_k = stats.by_corp_cls.get("K", 0)
        self.corp_cls_n = stats.by_corp_cls.get("N", 0)
        self.corp_cls_e = stats.by_corp_cls.get("E", 0)
        self.stats_loaded = True
        self.stats_loading = False

    def _load_api_keys(self):
        """API 키 상태를 확인합니다."""
        from core.admin import get_api_key_statuses

        statuses = get_api_key_statuses()
        self.api_keys = [
            {
                "name": s.name,
                "display_name": s.display_name,
                "configured": str(s.configured),
                "required": str(s.required),
            }
            for s in statuses
        ]

    # ── 연결 테스트 ──────────────────────────────────────────

    async def run_ping_tests(self):
        """모든 API 연결 테스트를 실행합니다."""
        self.ping_loading = True
        self.ping_results = []
        yield
        from core.admin import run_all_pings

        results = await run_all_pings()
        self.ping_results = [
            {
                "name": r.name,
                "success": str(r.success),
                "message": r.message,
                "elapsed_ms": str(round(r.elapsed_ms, 1)),
            }
            for r in results
        ]
        self.ping_loading = False

    # ── 기업 검색 ────────────────────────────────────────────

    def set_search_keyword(self, value: str):
        """검색어 입력."""
        self.search_keyword = value

    async def search_companies(self):
        """기업 검색을 실행합니다."""
        if len(self.search_keyword.strip()) < 2:
            self.search_results = []
            return
        self.search_loading = True
        yield
        from db.queries import search_companies

        self.search_results = await search_companies(
            self.search_keyword.strip()
        )
        self.search_loading = False

    async def handle_search_key(self, key: str):
        """검색 입력에서 Enter 키 처리."""
        if key == "Enter":
            return AdminState.search_companies

    # ── 기업 선택 ────────────────────────────────────────────

    def select_company(self, company: dict):
        """기업을 선택합니다."""
        self.selected_company = company
        self.has_selected = True
        self.dart_finance = []
        self.dart_executives = []
        self.dart_disclosures = []
        self.fsc_summary = []
        self.fsc_outline = {}

    def clear_selection(self):
        """선택 해제."""
        self.selected_company = {}
        self.has_selected = False

    # ── DART API 데이터 조회 ─────────────────────────────────

    async def fetch_dart_finance(self):
        """선택 기업의 DART 재무제표를 조회합니다."""
        corp_code = self.selected_company.get("corp_code")
        if not corp_code:
            return
        self.api_data_loading = True
        yield
        from clients.dart import fetch_finance

        result = await fetch_finance(corp_code, "2023", "11011")
        self.dart_finance = result.get("list", []) if result else []
        self.api_data_loading = False

    async def fetch_dart_executives(self):
        """선택 기업의 DART 임원현황을 조회합니다."""
        corp_code = self.selected_company.get("corp_code")
        if not corp_code:
            return
        self.api_data_loading = True
        yield
        from clients.dart import fetch_executives

        result = await fetch_executives(corp_code, "2023", "11011")
        self.dart_executives = result.get("list", []) if result else []
        self.api_data_loading = False

    async def fetch_dart_disclosures(self):
        """선택 기업의 DART 공시목록을 조회합니다."""
        corp_code = self.selected_company.get("corp_code")
        if not corp_code:
            return
        self.api_data_loading = True
        yield
        from clients.dart import search_disclosures

        result = await search_disclosures(corp_code, "20230101", "20231231")
        self.dart_disclosures = result.get("list", []) if result else []
        self.api_data_loading = False

    # ── FSC API 데이터 조회 ──────────────────────────────────

    async def fetch_fsc_data(self):
        """선택 기업의 FSC 요약재무 + 기업개요를 조회합니다."""
        jurir_no = self.selected_company.get("jurir_no")
        if not jurir_no:
            return
        self.api_data_loading = True
        yield
        from clients.fsc import fetch_corp_outline, fetch_summary

        self.fsc_summary = await fetch_summary(jurir_no)
        self.fsc_outline = await fetch_corp_outline(jurir_no) or {}
        self.api_data_loading = False
