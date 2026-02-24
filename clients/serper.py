"""
Serper Google Search API 클라이언트.

httpx.AsyncClient 기반. 타임아웃 10초, 네트워크 오류 시 1회 재시도.
SERPER_API_KEY는 utils/config.py에서 로드합니다.
"""

import httpx

from utils.config import load_config
from utils.logger import get_logger

log = get_logger("Serper")

_URL = "https://google.serper.dev/search"
_TIMEOUT = 10.0


async def search(
    query: str,
    gl: str = "kr",
    hl: str = "ko",
    num: int = 10,
) -> list[dict]:
    """
    Google 검색 결과(organic)를 반환합니다.

    Args:
        query: 검색어 (예: "삼성전자 AI")
        gl   : 국가 코드 (기본값: "kr" — 한국)
        hl   : 언어 코드 (기본값: "ko" — 한국어)
        num  : 반환 결과 수 (기본값: 10)

    Returns:
        organic 검색 결과 list[dict].
        각 항목에 title, link, snippet 등이 포함됩니다.
        결과 없으면 빈 리스트.
    """
    log.start(f"검색: '{query}'")
    cfg = load_config()
    payload = {"q": query, "gl": gl, "hl": hl, "num": num}
    headers = {
        "X-API-KEY": cfg.serper_api_key,
        "Content-Type": "application/json",
    }
    log.step("API", f"POST {_URL}")

    async with httpx.AsyncClient() as client:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = await client.post(
                    _URL, json=payload, headers=headers, timeout=_TIMEOUT
                )
                resp.raise_for_status()
                data = resp.json()
                results: list[dict] = data.get("organic", [])
                log.ok("API", f"{len(results)}건")
                log.finish(f"검색: '{query}'")
                return results
            except httpx.RequestError as e:
                last_exc = e
                if attempt == 0:
                    log.warn("재시도", f"네트워크 오류, 재시도 중... ({e})")
        raise last_exc  # type: ignore[misc]
