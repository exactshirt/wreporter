"""
clients/web.py 단위 테스트.

실제 웹페이지를 가져와서 텍스트 변환을 테스트합니다.
"""

import pytest

from clients.web import fetch_page, fetch_pages, WebPage, _extract_text


# ── fetch_page ────────────────────────────────────────────────────

async def test_fetch_page_returns_webpage():
    """실제 웹페이지를 가져와 WebPage 객체를 반환해야 합니다."""
    page = await fetch_page("https://example.com")
    assert page is not None
    assert isinstance(page, WebPage)
    assert page.url == "https://example.com"
    assert len(page.title) > 0
    assert len(page.text_content) > 0


async def test_fetch_page_invalid_url_returns_none():
    """잘못된 URL은 None을 반환해야 합니다."""
    page = await fetch_page("https://this-domain-does-not-exist-12345.com")
    assert page is None


async def test_fetch_page_non_html_returns_none():
    """HTML이 아닌 콘텐츠는 None을 반환해야 합니다."""
    page = await fetch_page("https://httpbin.org/image/png")
    assert page is None


# ── fetch_pages ───────────────────────────────────────────────────

async def test_fetch_pages_returns_list():
    """여러 URL을 동시에 가져올 수 있어야 합니다."""
    pages = await fetch_pages(["https://example.com"])
    assert len(pages) >= 1
    assert all(isinstance(p, WebPage) for p in pages)


async def test_fetch_pages_skips_failures():
    """실패한 URL은 건너뛰어야 합니다."""
    pages = await fetch_pages([
        "https://example.com",
        "https://this-domain-does-not-exist-12345.com",
    ])
    assert len(pages) == 1


# ── _extract_text ─────────────────────────────────────────────────

def test_extract_text_gets_title():
    """HTML에서 제목을 추출해야 합니다."""
    html = "<html><head><title>테스트 제목</title></head><body>본문</body></html>"
    title, text, links = _extract_text(html)
    assert title == "테스트 제목"
    assert "본문" in text


def test_extract_text_removes_script_and_style():
    """script와 style 태그가 제거되어야 합니다."""
    html = """
    <html><body>
    <script>alert('bad')</script>
    <style>.hidden{display:none}</style>
    <p>실제 내용</p>
    </body></html>
    """
    _, text, _ = _extract_text(html)
    assert "alert" not in text
    assert "display:none" not in text
    assert "실제 내용" in text


def test_extract_text_extracts_links():
    """외부 링크를 추출해야 합니다."""
    html = """
    <html><body>
    <a href="https://example.com">예시 링크</a>
    <a href="/internal">내부 링크</a>
    </body></html>
    """
    _, _, links = _extract_text(html)
    # 외부 링크만 추출
    assert len(links) == 1
    assert links[0]["href"] == "https://example.com"
    assert links[0]["text"] == "예시 링크"
