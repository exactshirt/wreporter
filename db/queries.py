"""
Supabase 쿼리 함수.

view_company_dashboard 뷰 및 companies 테이블 조회를 담당합니다.
"""

from db.client import get_client
from utils.logger import get_logger

log = get_logger("Supabase")

_VIEW = "view_company_dashboard"
_SEARCH_COLS = (
    "corp_code, jurir_no, bizr_no, corp_name, corp_eng_name, corp_legal_name, "
    "ceo_nm, corp_cls, data_source, hm_url, induty_code, industry, "
    "emp_cnt, adres, est_dt, enp_main_biz_nm"
)

_CORP_CLS_LABEL: dict[str, str] = {
    "Y": "코스피",
    "K": "코스닥",
    "N": "코넥스",
}


def _add_labels(row: dict) -> dict:
    """corp_cls → market_label, has_dart 필드를 추가해 반환합니다."""
    cls = row.get("corp_cls", "")
    row["market_label"] = _CORP_CLS_LABEL.get(cls, "비상장(외감)" if row.get("corp_code") else "비상장(비외감)")
    row["has_dart"] = row.get("corp_code") is not None
    return row


async def search_companies(keyword: str, limit: int = 20) -> list[dict]:
    """
    기업명으로 검색합니다. view_company_dashboard 뷰를 사용하며
    상장기업(코스피·코스닥)이 먼저 노출됩니다.

    검색 전략 (TS edge function swift-task와 동일):
    1차: 전방 일치 (`삼성%`) — corp_cls 내림차순(상장 우선), 최대 10건
    2차: 1차 결과가 5건 미만이면 포함 검색(`%삼성%`)으로 보완해 합산 최대 limit건

    Args:
        keyword: 검색어 2자 이상 (예: "삼성")
        limit: 최대 반환 건수, 기본값 20

    Returns:
        각 항목에 포함된 주요 필드:
        - corp_code   : DART 고유번호 (None이면 DART 사용 불가)
        - jurir_no    : 법인등록번호  (FSC / NICEBIZ 식별자)
        - corp_name   : 기업명
        - corp_cls    : 상장구분 (Y=코스피, K=코스닥, N=코넥스, E=외감)
        - market_label: 한글 구분명 (코스피 / 코스닥 / 비상장 등)
        - has_dart    : DART 데이터 사용 가능 여부 (bool)
        결과 없으면 빈 리스트 반환.
    """
    log.start(f"기업 검색: '{keyword}'")
    try:
        client = await get_client()

        # ── 1차: 전방 일치, 상장기업 우선 ────────────────────────────────
        log.step("1차 쿼리", f"corp_name ilike '{keyword}%' order corp_cls desc limit 10")
        resp1 = (
            await client.table(_VIEW)
            .select(_SEARCH_COLS)
            .ilike("corp_name", f"{keyword}%")
            .order("corp_cls", desc=True)
            .limit(10)
            .execute()
        )
        data = resp1.data or []

        # ── 2차: 전방 일치 결과가 5건 미만이면 포함 검색으로 보완 ─────────
        if len(data) < 5:
            seen = {r.get("jurir_no") or r.get("corp_code") for r in data}
            remaining = limit - len(data)
            log.step("2차 쿼리", f"corp_name ilike '%{keyword}%' order corp_cls desc limit 20")
            resp2 = (
                await client.table(_VIEW)
                .select(_SEARCH_COLS)
                .ilike("corp_name", f"%{keyword}%")
                .order("corp_cls", desc=True)
                .limit(20)
                .execute()
            )
            for row in (resp2.data or []):
                key = row.get("jurir_no") or row.get("corp_code")
                if key not in seen:
                    data.append(row)
                    seen.add(key)
                    if len(data) >= limit:
                        break

        data = data[:limit]
        data = [_add_labels(r) for r in data]

        log.ok("쿼리", f"{len(data)}건 반환")
        log.finish(f"기업 검색: '{keyword}'")
        return data

    except Exception as e:
        log.error("쿼리", str(e))
        raise


async def get_company(corp_code: str) -> dict | None:
    """
    고유번호(corp_code)로 기업 상세 정보를 조회합니다.

    Args:
        corp_code: DART 고유번호 8자리 (예: "00126380")

    Returns:
        기업 정보 dict, 없으면 None.
    """
    log.start(f"기업 조회: {corp_code}")
    try:
        client = await get_client()
        log.step("쿼리", f"corp_code = '{corp_code}'")

        resp = (
            await client.table("companies")
            .select("*")
            .eq("corp_code", corp_code)
            .limit(1)
            .execute()
        )

        if resp.data:
            company = resp.data[0]
            log.ok("쿼리", company.get("corp_name", "이름 없음"))
            log.finish(f"기업 조회: {corp_code}")
            return company
        else:
            log.warn("쿼리", f"corp_code={corp_code} 결과 없음")
            log.finish(f"기업 조회: {corp_code}")
            return None

    except Exception as e:
        log.error("쿼리", str(e))
        raise


async def get_company_by_jurir(jurir_no: str) -> dict | None:
    """
    법인등록번호(jurir_no)로 기업 상세 정보를 조회합니다.

    corp_code(DART 고유번호)가 없는 기업도 조회할 수 있습니다.
    FSC / NICEBIZ API 호출 전 기업 정보를 확인할 때 사용합니다.

    Args:
        jurir_no: 법인등록번호 13자리 (예: "1101110006246")

    Returns:
        기업 정보 dict, 없으면 None.
    """
    log.start(f"기업 조회 (법인번호): {jurir_no}")
    try:
        client = await get_client()
        log.step("쿼리", f"jurir_no = '{jurir_no}'")

        resp = (
            await client.table("companies")
            .select("*")
            .eq("jurir_no", jurir_no)
            .limit(1)
            .execute()
        )

        if resp.data:
            company = resp.data[0]
            log.ok("쿼리", company.get("corp_name", "이름 없음"))
            log.finish(f"기업 조회 (법인번호): {jurir_no}")
            return company
        else:
            log.warn("쿼리", f"jurir_no={jurir_no} 결과 없음")
            log.finish(f"기업 조회 (법인번호): {jurir_no}")
            return None

    except Exception as e:
        log.error("쿼리", str(e))
        raise
