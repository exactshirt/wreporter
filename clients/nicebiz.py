"""
NiceBIZ API 클라이언트.

httpx 기반. OAuth2 인증 (client_id + client_secret).
임원 정보 및 기업 정보를 조회합니다.

NICEBIZ_CLIENT_ID, NICEBIZ_CLIENT_SECRET은 선택 키입니다.
키가 없으면 None을 반환하고 경고만 출력합니다.
"""

from __future__ import annotations

import httpx

from utils.config import load_config
from utils.logger import get_logger

log = get_logger("NiceBIZ")

_BASE = "https://api.nicebizinfo.com"
_TOKEN_URL = f"{_BASE}/oauth/token"
_TIMEOUT = 15.0

# 캐싱된 토큰
_access_token: str | None = None


async def _ensure_token() -> str | None:
    """OAuth2 토큰을 발급받습니다. 키가 없으면 None 반환."""
    global _access_token
    if _access_token:
        return _access_token

    cfg = load_config()
    if not cfg.nicebiz_client_id or not cfg.nicebiz_client_secret:
        log.warn("인증", "NICEBIZ 키 미설정 — NiceBIZ 기능 비활성")
        return None

    log.step("인증", "토큰 발급 요청 중...")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": cfg.nicebiz_client_id,
                    "client_secret": cfg.nicebiz_client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            _access_token = data.get("access_token")
            if _access_token:
                log.ok("인증", "토큰 발급 성공")
            else:
                log.error("인증", f"토큰 응답에 access_token 없음: {data}")
            return _access_token
    except Exception as e:
        log.error("인증", f"토큰 발급 실패: {e}")
        return None


async def _get(endpoint: str, params: dict) -> dict | None:
    """인증된 GET 요청."""
    token = await _ensure_token()
    if not token:
        return None

    url = f"{_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # 토큰 만료 — 재발급 후 재시도
                global _access_token
                _access_token = None
                token = await _ensure_token()
                if not token:
                    return None
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
            log.error("API", f"HTTP {e.response.status_code}: {endpoint}")
            return None
        except httpx.RequestError as e:
            log.error("API", f"네트워크 오류: {e}")
            return None


async def fetch_executives(bizr_no: str) -> list[dict] | None:
    """
    NiceBIZ에서 기업 임원 정보를 조회합니다.

    Args:
        bizr_no: 사업자등록번호 10자리.

    Returns:
        임원 리스트. 키 미설정 또는 실패 시 None.
    """
    log.start(f"임원 조회: {bizr_no}")
    data = await _get("/api/v1/executives", {"bizr_no": bizr_no})
    if data is None:
        log.finish(f"임원 조회: {bizr_no}")
        return None
    result = data.get("data", data.get("list", []))
    if isinstance(result, list):
        log.ok("임원", f"{len(result)}명")
    else:
        log.warn("임원", f"예상치 못한 응답 형식: {type(result)}")
        result = []
    log.finish(f"임원 조회: {bizr_no}")
    return result


async def fetch_company_info(bizr_no: str) -> dict | None:
    """
    NiceBIZ에서 기업 기본 정보를 조회합니다.

    Args:
        bizr_no: 사업자등록번호 10자리.

    Returns:
        기업 정보 dict. 키 미설정 또는 실패 시 None.
    """
    log.start(f"기업정보 조회: {bizr_no}")
    data = await _get("/api/v1/company", {"bizr_no": bizr_no})
    if data is None:
        log.finish(f"기업정보 조회: {bizr_no}")
        return None
    result = data.get("data", data)
    log.ok("기업정보")
    log.finish(f"기업정보 조회: {bizr_no}")
    return result
