"""
FSC(금융위원회) 공공데이터 OpenAPI 클라이언트.

두 개의 API 서비스를 사용합니다:
  - GetFinaStatInfoService_V2  : 재무정보 (요약재무제표, 재무상태표, 손익계산서)
  - GetCorpBasicInfoService_V2 : 기업기본정보 (기업개요)

httpx.AsyncClient 기반. 타임아웃 10초, 네트워크 오류 시 1회 재시도.
FSC_API_KEY는 utils/config.py에서 로드합니다 (선택 키 — 없으면 ValueError).

공통 응답 구조:
  response.header.resultCode == "00" → 성공
  그 외 → ValueError 예외
  데이터 없음 → 빈 리스트([]) 또는 None 반환.

bizYear(사업연도) 처리:
  FSC API는 bizYear가 필수가 아니므로 빈 값으로 전체 조회 후
  가장 최신 bizYear 항목만 반환합니다.
  응답이 bizYear 오름차순으로 정렬되므로, totalCount > numOfRows인 경우
  마지막 페이지를 추가로 조회합니다 (최대 2회 API 호출).
"""

import math

import httpx

from utils.config import load_config
from utils.logger import get_logger

log = get_logger("FSC")

_FINANCE_BASE = "http://apis.data.go.kr/1160100/service/GetFinaStatInfoService_V2"
_CORP_BASE = "http://apis.data.go.kr/1160100/service/GetCorpBasicInfoService_V2"
_TIMEOUT = 10.0
_PAGE_SIZE = 100


# ── 공통 HTTP / 응답 처리 ──────────────────────────────────────────────────────

async def _get(url: str, params: dict) -> dict:
    """GET 요청. 네트워크 오류 시 1회 재시도."""
    async with httpx.AsyncClient() as client:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = await client.get(url, params=params, timeout=_TIMEOUT)
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_exc = e
                if attempt == 0:
                    log.warn("재시도", f"네트워크 오류, 재시도 중... ({e})")
        raise last_exc  # type: ignore[misc]


def _extract_items(data: dict, context: str) -> tuple[list[dict], int]:
    """
    FSC 공통 응답에서 items list와 totalCount를 추출합니다.

    Returns:
        (items, totalCount)

    Raises:
        ValueError: resultCode != "00"
    """
    header = data.get("response", {}).get("header", {})
    code = header.get("resultCode", "")
    if code != "00":
        raise ValueError(
            f"FSC API 오류 [{context}] code={code} / {header.get('resultMsg', '')}"
        )

    body = data.get("response", {}).get("body", {})
    total = body.get("totalCount", 0)
    items_node = body.get("items") or {}
    item = items_node.get("item", [])
    if isinstance(item, dict):
        item = [item]   # 단건 응답이 dict로 오는 경우 처리

    return item, total


def _latest_year(items: list[dict]) -> list[dict]:
    """items 중 최신 bizYear 항목만 반환."""
    if not items:
        return []
    max_year = max(it.get("bizYear", "0") for it in items)
    return [it for it in items if it.get("bizYear") == max_year]


def _require_key(cfg) -> str:
    """FSC API 키 존재 여부 확인. 없으면 ValueError."""
    if not cfg.fsc_api_key:
        raise ValueError(
            "FSC_API_KEY가 .env에 설정되지 않았습니다. "
            ".env.example을 참고해 FSC_API_KEY를 추가하세요."
        )
    return cfg.fsc_api_key


async def _fetch_latest(url: str, crno: str, context: str) -> list[dict]:
    """
    bizYear 없이 전체 조회 후 최신 연도 항목을 반환합니다.

    응답이 bizYear 오름차순으로 정렬되므로:
    1차 요청 (pageNo=1, numOfRows=100) → totalCount 파악
    totalCount > 100이면 마지막 페이지를 추가 조회해 최신 연도 데이터 확보.
    """
    cfg = load_config()
    key = _require_key(cfg)
    params = {
        "serviceKey": key,
        "resultType": "json",
        "numOfRows": _PAGE_SIZE,
        "pageNo": 1,
        "crno": crno,
    }

    log.step("API", f"GET {url} (pageNo=1)")
    data = await _get(url, params)
    items, total = _extract_items(data, context)

    if total > _PAGE_SIZE:
        last_page = math.ceil(total / _PAGE_SIZE)
        log.step("API", f"GET {url} (pageNo={last_page}, total={total})")
        data_last = await _get(url, {**params, "pageNo": last_page})
        items, _ = _extract_items(data_last, context)

    result = _latest_year(items)
    year = result[0]["bizYear"] if result else "N/A"
    log.ok("API", f"{len(result)}건 (bizYear={year})")
    return result


# ── 재무정보 (GetFinaStatInfoService_V2) ──────────────────────────────────────

async def fetch_summary(jurir_no: str) -> list[dict]:
    """
    요약재무제표 최신 연도 조회 (getSummFinaStat_V2).

    연결·별도 구분 없이 최신 bizYear 항목을 모두 반환합니다.
    연결(fnclDcd="110")과 별도(fnclDcd="120") 두 행이 함께 올 수 있습니다.

    Args:
        jurir_no: 법인등록번호 13자리 (예: "1301110006246")

    Returns:
        최신 연도 요약재무제표 항목 list.
        주요 필드:
          bizYear      : 사업연도
          fnclDcdNm    : 재무제표 구분명 (연결요약재무제표 / 별도요약재무제표)
          enpSaleAmt   : 기업매출금액
          enpBzopPft   : 기업영업이익
          enpCrtmNpf   : 기업당기순이익
          enpTastAmt   : 기업총자산금액
          enpTdbtAmt   : 기업총부채금액
          enpTcptAmt   : 기업총자본금액
        데이터 없으면 [].
    """
    log.start(f"요약재무제표 조회: {jurir_no}")
    result = await _fetch_latest(
        f"{_FINANCE_BASE}/getSummFinaStat_V2", jurir_no, "요약재무제표"
    )
    log.finish(f"요약재무제표 조회: {jurir_no}")
    return result


async def fetch_balance_sheet(jurir_no: str) -> list[dict]:
    """
    재무상태표 최신 연도 조회 (getBs_V2).

    Args:
        jurir_no: 법인등록번호 13자리

    Returns:
        최신 연도 재무상태표 항목 list.
        주요 필드:
          bizYear       : 사업연도
          acitNm        : 계정과목명 (자산총계, 유동자산, 부채총계 등)
          crtmAcitAmt   : 당기 금액
          pvtrAcitAmt   : 전기 금액
          bpvtrAcitAmt  : 전전기 금액
        데이터 없으면 [].
    """
    log.start(f"재무상태표 조회: {jurir_no}")
    result = await _fetch_latest(
        f"{_FINANCE_BASE}/getBs_V2", jurir_no, "재무상태표"
    )
    log.finish(f"재무상태표 조회: {jurir_no}")
    return result


async def fetch_income_statement(jurir_no: str) -> list[dict]:
    """
    손익계산서 최신 연도 조회 (getIncoStat_V2).

    Args:
        jurir_no: 법인등록번호 13자리

    Returns:
        최신 연도 손익계산서 항목 list.
        주요 필드:
          bizYear       : 사업연도
          acitNm        : 계정과목명 (수익, 영업이익, 당기순이익 등)
          crtmAcitAmt   : 당기 금액
          pvtrAcitAmt   : 전기 금액
          bpvtrAcitAmt  : 전전기 금액
        데이터 없으면 [].
    """
    log.start(f"손익계산서 조회: {jurir_no}")
    result = await _fetch_latest(
        f"{_FINANCE_BASE}/getIncoStat_V2", jurir_no, "손익계산서"
    )
    log.finish(f"손익계산서 조회: {jurir_no}")
    return result


# ── 기업기본정보 (GetCorpBasicInfoService_V2) ─────────────────────────────────

async def fetch_corp_outline(jurir_no: str) -> dict | None:
    """
    기업개요 조회 (getCorpOutline_V2).

    DART corp_code가 없는 비상장 기업도 조회 가능합니다.

    Args:
        jurir_no: 법인등록번호 13자리

    Returns:
        기업 개요 dict. 없으면 None.
        주요 필드:
          corpNm         : 법인명
          enpRprFnm      : 기업대표자성명
          enpBsadr       : 기업기본주소
          enpEstbDt      : 기업설립일자 (YYYYMMDD)
          enpMainBizNm   : 기업주요사업명
          enpEmpeCnt     : 기업종업원수
          bzno           : 사업자등록번호
          smenpYn        : 중소기업여부 (Y/N)
    """
    log.start(f"기업개요 조회: {jurir_no}")
    cfg = load_config()
    key = _require_key(cfg)

    url = f"{_CORP_BASE}/getCorpOutline_V2"
    params = {
        "serviceKey": key,
        "resultType": "json",
        "numOfRows": 1,
        "pageNo": 1,
        "crno": jurir_no,
    }
    log.step("API", f"GET {url}")
    data = await _get(url, params)
    items, _ = _extract_items(data, "기업개요")

    if items:
        log.ok("API", items[0].get("corpNm", "이름 없음"))
        log.finish(f"기업개요 조회: {jurir_no}")
        return items[0]
    else:
        log.warn("API", "결과 없음")
        log.finish(f"기업개요 조회: {jurir_no}")
        return None
