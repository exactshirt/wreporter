"""
웹 콘텐츠 페칭 클라이언트.

httpx 기반. HTML을 가져와 텍스트로 변환합니다.
robots.txt를 존중하고, 콘텐츠 크기를 제한합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from utils.logger import get_logger

log = get_logger("Web")

_TIMEOUT = 15.0
_MAX_CONTENT_LENGTH = 100_000  # 100KB 텍스트 제한 (Claude 컨텍스트 고려)
_USER_AGENT = (
    "Mozilla/5.0 (compatible; Wreporter/1.0; "
    "+https://github.com/wreporter)"
)


@dataclass
class WebPage:
    """가져온 웹 페이지."""
    url: str
    title: str
    text_content: str
    links: list[dict[str, str]]  # [{"text": "...", "href": "..."}]
    fetched_at: str              # ISO format


def _extract_text(html: str) -> tuple[str, str, list[dict[str, str]]]:
    """
    HTML에서 제목, 텍스트, 링크를 추출합니다.

    beautifulsoup4가 있으면 사용하고, 없으면 간단한 정규식 fallback.
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # 텍스트 추출
        text = soup.get_text(separator="\n", strip=True)

        # 링크 추출 (상위 20개)
        links = []
        for a in soup.find_all("a", href=True, limit=20):
            link_text = a.get_text(strip=True)
            if link_text and a["href"].startswith(("http://", "https://")):
                links.append({"text": link_text[:100], "href": a["href"]})

        return title, text, links

    except ImportError:
        # beautifulsoup4 미설치 시 정규식 fallback
        import re

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        # 태그 제거
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        return title, text, []


async def fetch_page(url: str) -> WebPage | None:
    """
    URL의 웹 페이지를 가져와 텍스트로 변환합니다.

    Args:
        url: 가져올 URL.

    Returns:
        WebPage 객체. 실패 시 None.
    """
    log.start(f"페이지 수집: {url[:80]}")
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            verify=False,  # 일부 환경에서 SSL 인증서 문제 방지
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                log.warn("수집", f"지원하지 않는 content-type: {content_type}")
                return None

            html = resp.text
            title, text, links = _extract_text(html)

            # 크기 제한
            if len(text) > _MAX_CONTENT_LENGTH:
                text = text[:_MAX_CONTENT_LENGTH] + "\n\n[... 콘텐츠 잘림]"

            page = WebPage(
                url=url,
                title=title,
                text_content=text,
                links=links,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
            log.ok("수집", f"제목='{title[:50]}', 텍스트={len(text)}자")
            log.finish(f"페이지 수집: {url[:80]}")
            return page

    except httpx.HTTPStatusError as e:
        log.warn("수집", f"HTTP {e.response.status_code}: {url[:80]}")
        return None
    except httpx.RequestError as e:
        log.warn("수집", f"네트워크 오류: {e}")
        return None
    except Exception as e:
        log.error("수집", f"예기치 않은 오류: {e}")
        return None


async def fetch_pages(urls: list[str]) -> list[WebPage]:
    """
    여러 URL을 동시에 가져옵니다.

    실패한 URL은 건너뜁니다.

    Args:
        urls: URL 리스트.

    Returns:
        성공한 WebPage 리스트.
    """
    import asyncio

    tasks = [fetch_page(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]
