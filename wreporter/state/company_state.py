"""기업 검색 상태 관리.

UI 입력값과 검색 결과를 추적합니다.
비즈니스 로직은 db.queries에 위임합니다.
"""

import reflex as rx

from db.queries import search_companies
from utils.logger import get_logger

log = get_logger("CompanyState")

_SOURCE_LABELS = {"dart": "DART", "fsc": "FSC", "both": "DART+FSC"}


def _normalize(row: dict) -> dict:
    """None 값을 빈 문자열로, source_label 추가."""
    out = {k: (v if v is not None else "") for k, v in row.items()}
    out["source_label"] = _SOURCE_LABELS.get(out.get("data_source", ""), "")
    return out


class CompanyState(rx.State):
    """기업 검색 UI 상태."""

    keyword: str = ""
    results: list[dict] = []
    is_loading: bool = False
    selected_company: dict = {}

    @rx.event
    async def handle_search(self, keyword: str) -> None:
        """검색어 입력 시 호출. 2글자 이상이면 DB 검색."""
        self.keyword = keyword
        if len(keyword) < 2:
            self.results = []
            return

        self.is_loading = True
        yield

        try:
            raw = await search_companies(keyword, limit=20)
            self.results = [_normalize(r) for r in raw]
        except Exception as e:
            log.error("검색", str(e))
            self.results = []
        finally:
            self.is_loading = False

    @rx.event
    def select_company(self, company: dict) -> None:
        """검색 결과에서 기업을 선택."""
        self.selected_company = company
        self.results = []
        self.keyword = company.get("corp_name", "")

    @rx.event
    def clear_selection(self) -> None:
        """선택 초기화, 검색 화면으로 복귀."""
        self.selected_company = {}
        self.keyword = ""
        self.results = []
