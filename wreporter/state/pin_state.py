"""핀(즐겨찾기) 기업 관리 상태.

사이드바의 핀 리스트와 헤더 검색을 담당합니다.
핀 데이터는 Supabase에 영속 저장됩니다.
"""

import reflex as rx

from db import pins as pin_db
from db.queries import search_companies
from utils.logger import get_logger

log = get_logger("PinState")

_SOURCE_LABELS = {"dart": "DART", "fsc": "FSC", "both": "DART+FSC"}


def _normalize(row: dict) -> dict:
    """None 값을 빈 문자열로, source_label 추가."""
    out = {k: (v if v is not None else "") for k, v in row.items()}
    out["source_label"] = _SOURCE_LABELS.get(out.get("data_source", ""), "")
    return out


class PinState(rx.State):
    """핀된 기업 목록과 현재 활성 기업을 관리합니다."""

    # ── 핀 리스트 ──
    pinned: list[dict] = []
    active_jurir_no: str = ""

    # ── 헤더 검색 ──
    search_keyword: str = ""
    search_results: list[dict] = []
    search_loading: bool = False
    show_search_dropdown: bool = False

    # ── Computed Vars ──

    @rx.var
    def active_company(self) -> dict:
        """현재 활성 기업의 정보."""
        for p in self.pinned:
            if p.get("jurir_no") == self.active_jurir_no:
                return p
        return {}

    @rx.var
    def has_pinned(self) -> bool:
        return len(self.pinned) > 0

    @rx.var
    def pin_count(self) -> int:
        return len(self.pinned)

    # ── 페이지 로드 ──

    @rx.event
    async def load_pins(self) -> None:
        """DB에서 핀 목록을 로드합니다. on_load에서 호출."""
        log.start("핀 목록 로드")
        try:
            self.pinned = await pin_db.get_all_pins()
            # 활성 기업이 없거나 목록에서 빠졌으면 첫 번째로 설정
            if self.pinned and (
                not self.active_jurir_no
                or not any(p.get("jurir_no") == self.active_jurir_no for p in self.pinned)
            ):
                self.active_jurir_no = self.pinned[0].get("jurir_no", "")
            elif not self.pinned:
                self.active_jurir_no = ""
            log.ok("로드", f"{len(self.pinned)}건")
        except Exception as e:
            log.error("로드", str(e))
        log.finish("핀 목록 로드")
        # ResearchState에 활성 기업 동기화
        if self.active_jurir_no:
            from wreporter.state.research_state import ResearchState
            yield ResearchState.sync_active_company(self.active_jurir_no)

    # ── 핀 관리 ──

    @rx.event
    async def pin_company(self, company: dict) -> None:
        """기업을 핀 리스트에 추가하고 활성화합니다."""
        jurir_no = company.get("jurir_no", "")
        if not jurir_no:
            return

        # 이미 핀되어 있으면 해당 기업으로 전환만
        for p in self.pinned:
            if p.get("jurir_no") == jurir_no:
                self.active_jurir_no = jurir_no
                self.search_results = []
                self.search_keyword = ""
                self.show_search_dropdown = False
                from wreporter.state.research_state import ResearchState
                yield ResearchState.sync_active_company(jurir_no)
                return

        # DB에 저장
        log.start(f"핀 추가: {company.get('corp_name', jurir_no)}")
        try:
            await pin_db.add_pin(company)
            # State에 추가
            self.pinned = [company] + self.pinned
            self.active_jurir_no = jurir_no
            self.search_results = []
            self.search_keyword = ""
            self.show_search_dropdown = False
            log.ok("추가")
        except Exception as e:
            log.error("추가", str(e))
        log.finish(f"핀 추가: {company.get('corp_name', jurir_no)}")
        # ResearchState에 활성 기업 동기화
        if self.active_jurir_no:
            from wreporter.state.research_state import ResearchState
            yield ResearchState.sync_active_company(self.active_jurir_no)

    @rx.event
    async def unpin_company(self, jurir_no: str) -> None:
        """핀을 해제합니다."""
        log.start(f"핀 삭제: {jurir_no}")
        try:
            await pin_db.remove_pin(jurir_no)
            self.pinned = [p for p in self.pinned if p.get("jurir_no") != jurir_no]
            # 활성 기업이 삭제되면 다음 기업으로 전환
            if self.active_jurir_no == jurir_no:
                self.active_jurir_no = self.pinned[0].get("jurir_no", "") if self.pinned else ""
            log.ok("삭제")
        except Exception as e:
            log.error("삭제", str(e))
        log.finish(f"핀 삭제: {jurir_no}")
        # ResearchState에 새 활성 기업 동기화
        from wreporter.state.research_state import ResearchState
        yield ResearchState.sync_active_company(self.active_jurir_no)

    @rx.event
    def set_active(self, jurir_no: str):
        """핀 리스트에서 기업 클릭 시 활성 전환 + ResearchState 동기화."""
        self.active_jurir_no = jurir_no
        from wreporter.state.research_state import ResearchState
        return ResearchState.sync_active_company(jurir_no)

    # ── 헤더 검색 ──

    @rx.event
    async def handle_search(self, keyword: str) -> None:
        """헤더 검색창 입력. 2글자 이상이면 DB 검색."""
        self.search_keyword = keyword
        if len(keyword) < 2:
            self.search_results = []
            self.show_search_dropdown = False
            return

        self.search_loading = True
        self.show_search_dropdown = True
        yield

        try:
            raw = await search_companies(keyword, limit=10)
            self.search_results = [_normalize(r) for r in raw]
        except Exception as e:
            log.error("검색", str(e))
            self.search_results = []
        finally:
            self.search_loading = False

    @rx.event
    def close_search(self) -> None:
        """검색 드롭다운 닫기."""
        self.show_search_dropdown = False
        self.search_results = []
        self.search_keyword = ""
