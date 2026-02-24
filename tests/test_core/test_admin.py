"""
core/admin.py 통합 테스트.

DB 통계 조회, API 키 상태, 연결 테스트를 검증합니다.
"""

from core.admin import (
    DbStats,
    PingResult,
    get_api_key_statuses,
    get_db_stats,
    ping_supabase,
    run_all_pings,
)


# ── get_db_stats (6회 쿼리 → 한 번만 호출) ──────────────────────────────────


async def test_get_db_stats():
    """DB 통계가 올바른 구조와 값을 반환해야 합니다."""
    stats = await get_db_stats()

    # 타입 확인
    assert isinstance(stats, DbStats)

    # 총 기업 수 > 0
    assert stats.total_companies > 0

    # with + without = total
    assert stats.with_corp_code + stats.without_corp_code == stats.total_companies

    # DART 등록 기업이 1개 이상
    assert stats.with_corp_code > 0

    # 코스피(Y), 코스닥(K) 존재하고 1개 이상
    assert "Y" in stats.by_corp_cls
    assert "K" in stats.by_corp_cls
    assert stats.by_corp_cls["Y"] > 0
    assert stats.by_corp_cls["K"] > 0


# ── get_api_key_statuses ─────────────────────────────────────────────────────


def test_get_api_key_statuses_returns_list():
    """API 키 상태가 8개 항목 리스트로 반환되어야 합니다."""
    statuses = get_api_key_statuses()
    assert isinstance(statuses, list)
    assert len(statuses) == 8


def test_get_api_key_statuses_has_dart_key():
    """DART_API_KEY가 포함되어야 합니다."""
    statuses = get_api_key_statuses()
    names = [s.name for s in statuses]
    assert "DART_API_KEY" in names


def test_get_api_key_statuses_required_flag():
    """DART는 필수, FSC는 선택이어야 합니다."""
    statuses = get_api_key_statuses()
    dart = next(s for s in statuses if s.name == "DART_API_KEY")
    assert dart.required is True
    fsc = next(s for s in statuses if s.name == "FSC_API_KEY")
    assert fsc.required is False


def test_get_api_key_statuses_configured_dart():
    """DART_API_KEY가 설정되어 있어야 합니다 (.env에 존재)."""
    statuses = get_api_key_statuses()
    dart = next(s for s in statuses if s.name == "DART_API_KEY")
    assert dart.configured is True


# ── ping ─────────────────────────────────────────────────────────────────────


async def test_ping_supabase_succeeds():
    """Supabase 연결 테스트가 성공해야 합니다."""
    result = await ping_supabase()
    assert isinstance(result, PingResult)
    assert result.success is True
    assert result.elapsed_ms > 0


async def test_run_all_pings():
    """전체 핑 테스트가 4개 결과를 반환하고 필수 필드가 있어야 합니다."""
    results = await run_all_pings()

    assert isinstance(results, list)
    assert len(results) == 4

    for r in results:
        assert isinstance(r.name, str)
        assert isinstance(r.success, bool)
        assert isinstance(r.message, str)
        assert isinstance(r.elapsed_ms, float)
