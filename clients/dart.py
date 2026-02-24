"""
DART(전자공시시스템) OpenAPI 클라이언트.

httpx.AsyncClient 기반. 타임아웃 10초, 네트워크 오류 시 1회 재시도.
DART_API_KEY는 utils/config.py에서 로드합니다.

DART 에러코드 정책:
  status "000" → 성공
  status "013" → 데이터 없음 (정상 분기, None 반환)
  그 외         → ValueError 예외
"""

import httpx

from utils.config import load_config
from utils.logger import get_logger

log = get_logger("DART")

_BASE = "https://opendart.fss.or.kr/api"
_TIMEOUT = 10.0


async def _get(url: str, params: dict) -> dict:
    """GET 요청. 네트워크 오류(타임아웃·연결 실패 등) 시 1회 재시도."""
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


def _check_status(data: dict, context: str) -> dict | None:
    """
    DART API 공통 status 처리.

    Returns:
        dict  : status "000" 성공
        None  : status "013" 데이터 없음 (정상 분기)

    Raises:
        ValueError: 그 외 오류 코드
    """
    status = data.get("status", "")
    if status == "000":
        return data
    if status == "013":
        log.warn(context, "데이터 없음 (status=013)")
        return None
    raise ValueError(
        f"DART API 오류 [{context}] status={status} / {data.get('message', '')}"
    )


async def search_disclosures(
    corp_code: str,
    bgn_de: str,
    end_de: str,
) -> dict | None:
    """
    DART 공시 목록을 조회합니다.

    Args:
        corp_code: DART 고유번호 8자리 (예: "00126380")
        bgn_de   : 시작일 YYYYMMDD (예: "20230101")
        end_de   : 종료일 YYYYMMDD (예: "20231231")

    Returns:
        성공 시 응답 dict — list 키에 공시 목록 포함.
        데이터 없음(status=013)이면 None.
    """
    log.start(f"공시목록 조회: {corp_code} ({bgn_de}~{end_de})")
    cfg = load_config()
    params = {
        "crtfc_key": cfg.dart_api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": 100,
    }
    log.step("API", f"GET {_BASE}/list.json")
    data = await _get(f"{_BASE}/list.json", params)
    result = _check_status(data, "공시목록")
    if result is not None:
        log.ok("API", f"{len(result.get('list', []))}건")
    log.finish(f"공시목록 조회: {corp_code}")
    return result


async def fetch_executives(
    corp_code: str,
    bsns_year: str,
    reprt_code: str,
) -> dict | None:
    """
    DART 임원 현황을 조회합니다.

    Args:
        corp_code  : DART 고유번호 8자리
        bsns_year  : 사업연도 4자리 (예: "2023")
        reprt_code : 보고서 코드 (11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기)

    Returns:
        성공 시 응답 dict — list 키에 임원 목록 포함.
        데이터 없음이면 None.
    """
    log.start(f"임원현황 조회: {corp_code} {bsns_year}")
    cfg = load_config()
    params = {
        "crtfc_key": cfg.dart_api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
    }
    log.step("API", f"GET {_BASE}/exctvSttus.json")
    data = await _get(f"{_BASE}/exctvSttus.json", params)
    result = _check_status(data, "임원현황")
    if result is not None:
        log.ok("API", f"{len(result.get('list', []))}명")
    log.finish(f"임원현황 조회: {corp_code}")
    return result


async def fetch_finance(
    corp_code: str,
    bsns_year: str,
    reprt_code: str,
) -> dict | None:
    """
    DART 단일회사 전체 재무제표를 조회합니다 (연결재무제표 우선).

    Args:
        corp_code  : DART 고유번호 8자리
        bsns_year  : 사업연도 4자리 (예: "2023")
        reprt_code : 보고서 코드 (11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기)

    Returns:
        성공 시 응답 dict — list 키에 재무 항목 포함.
        데이터 없음이면 None.
    """
    log.start(f"재무제표 조회: {corp_code} {bsns_year}")
    cfg = load_config()
    params = {
        "crtfc_key": cfg.dart_api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": "CFS",  # 연결재무제표
    }
    log.step("API", f"GET {_BASE}/fnlttSinglAcnt.json")
    data = await _get(f"{_BASE}/fnlttSinglAcnt.json", params)
    result = _check_status(data, "재무제표")
    if result is not None:
        log.ok("API", f"{len(result.get('list', []))}개 항목")
    log.finish(f"재무제표 조회: {corp_code}")
    return result
