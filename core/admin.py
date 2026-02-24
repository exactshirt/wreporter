"""
관리자 대시보드 비즈니스 로직.

DB 통계 조회, API 키 상태 확인, API 연결 테스트를 담당합니다.
Reflex와 독립적으로 실행 가능합니다.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv

from db.client import get_client
from utils.logger import get_logger

log = get_logger("Admin")


# ── 데이터 구조 ──────────────────────────────────────────────────────────────


@dataclass
class DbStats:
    """DB 기업 통계."""

    total_companies: int
    with_corp_code: int
    without_corp_code: int
    by_corp_cls: dict[str, int] = field(default_factory=dict)


@dataclass
class ApiKeyStatus:
    """API 키 설정 상태."""

    name: str
    display_name: str
    configured: bool
    required: bool


@dataclass
class PingResult:
    """API 연결 테스트 결과."""

    name: str
    success: bool
    message: str
    elapsed_ms: float


# ── API 키 설정 ──────────────────────────────────────────────────────────────

_KEY_CONFIG: list[tuple[str, str, bool]] = [
    ("DART_API_KEY", "DART (전자공시)", True),
    ("ANTHROPIC_API_KEY", "Anthropic (Claude AI)", True),
    ("SUPABASE_URL", "Supabase (URL)", True),
    ("SUPABASE_KEY", "Supabase (Key)", True),
    ("SERPER_API_KEY", "Serper (Google 검색)", True),
    ("FSC_API_KEY", "FSC (금융위원회)", False),
    ("NICEBIZ_CLIENT_ID", "NICEBIZ (Client ID)", False),
    ("NICEBIZ_CLIENT_SECRET", "NICEBIZ (Client Secret)", False),
]


# ── DB 통계 ──────────────────────────────────────────────────────────────────


async def get_db_stats() -> DbStats:
    """
    DB 기업 통계를 조회합니다.

    companies 테이블에서 총 건수, corp_code 보유 건수,
    상장구분별(corp_cls) 분포를 집계합니다.

    Returns:
        DbStats 객체
    """
    log.start("DB 통계 조회")
    try:
        client = await get_client()

        log.step("쿼리", "RPC get_company_stats (단일 쿼리)")
        resp = await client.rpc("get_company_stats").execute()

        if resp.data:
            row = resp.data[0]
            total = row.get("total", 0)
            with_code = row.get("with_corp_code", 0)
            by_cls = {
                "Y": row.get("cls_y", 0),
                "K": row.get("cls_k", 0),
                "N": row.get("cls_n", 0),
                "E": row.get("cls_e", 0),
            }
        else:
            total = with_code = 0
            by_cls = {}

        stats = DbStats(
            total_companies=total,
            with_corp_code=with_code,
            without_corp_code=total - with_code,
            by_corp_cls=by_cls,
        )
        log.ok("쿼리", f"총 {total:,}건, DART {with_code:,}건")
        log.finish("DB 통계 조회")
        return stats

    except Exception as e:
        log.error("쿼리", str(e))
        raise


# ── API 키 상태 ──────────────────────────────────────────────────────────────


def get_api_key_statuses() -> list[ApiKeyStatus]:
    """
    API 키 설정 상태를 확인합니다.

    .env에서 각 키의 존재 여부를 판단합니다.
    load_config()를 사용하지 않아 필수 키 누락 시에도 에러가 발생하지 않습니다.

    Returns:
        ApiKeyStatus 리스트
    """
    load_dotenv(override=False)
    return [
        ApiKeyStatus(
            name=name,
            display_name=display,
            configured=bool(os.getenv(name)),
            required=required,
        )
        for name, display, required in _KEY_CONFIG
    ]


# ── 연결 테스트 ──────────────────────────────────────────────────────────────


async def ping_supabase() -> PingResult:
    """Supabase 연결을 테스트합니다."""
    start = time.monotonic()
    try:
        client = await get_client()
        await client.table("companies").select("corp_code").limit(1).execute()
        elapsed = (time.monotonic() - start) * 1000
        log.ok("Ping", f"Supabase 응답 {elapsed:.0f}ms")
        return PingResult("Supabase", True, "연결 성공", elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        log.error("Ping", f"Supabase 실패: {e}")
        return PingResult("Supabase", False, str(e)[:100], elapsed)


async def ping_dart() -> PingResult:
    """DART API 연결을 테스트합니다."""
    start = time.monotonic()
    try:
        import httpx

        from utils.config import load_config

        cfg = load_config()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                "https://opendart.fss.or.kr/api/company.json",
                params={"crtfc_key": cfg.dart_api_key, "corp_code": "00126380"},
                timeout=10.0,
            )
            resp.raise_for_status()
        elapsed = (time.monotonic() - start) * 1000
        log.ok("Ping", f"DART 응답 {elapsed:.0f}ms")
        return PingResult("DART", True, "연결 성공", elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        log.error("Ping", f"DART 실패: {e}")
        return PingResult("DART", False, str(e)[:100], elapsed)


async def ping_fsc() -> PingResult:
    """FSC API 연결을 테스트합니다."""
    start = time.monotonic()
    try:
        from utils.config import load_config

        cfg = load_config()
        if not cfg.fsc_api_key:
            return PingResult("FSC", False, "API 키 미설정", 0.0)

        from clients.fsc import fetch_corp_outline

        await fetch_corp_outline("1301110006246")  # 삼성전자
        elapsed = (time.monotonic() - start) * 1000
        log.ok("Ping", f"FSC 응답 {elapsed:.0f}ms")
        return PingResult("FSC", True, "연결 성공", elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        log.error("Ping", f"FSC 실패: {e}")
        return PingResult("FSC", False, str(e)[:100], elapsed)


async def ping_serper() -> PingResult:
    """Serper API 연결을 테스트합니다."""
    start = time.monotonic()
    try:
        from clients.serper import search

        await search("test", num=1)
        elapsed = (time.monotonic() - start) * 1000
        log.ok("Ping", f"Serper 응답 {elapsed:.0f}ms")
        return PingResult("Serper", True, "연결 성공", elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        log.error("Ping", f"Serper 실패: {e}")
        return PingResult("Serper", False, str(e)[:100], elapsed)


async def run_all_pings() -> list[PingResult]:
    """모든 API 연결을 동시에 테스트합니다."""
    log.start("전체 연결 테스트")
    results = await asyncio.gather(
        ping_supabase(),
        ping_dart(),
        ping_fsc(),
        ping_serper(),
    )
    log.finish("전체 연결 테스트")
    return list(results)
