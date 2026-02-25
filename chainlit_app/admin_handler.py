"""
/admin 채팅 명령어 핸들러.

core/admin.py의 비즈니스 로직을 호출하고 결과를 마크다운 메시지로 표시합니다.
"""

from __future__ import annotations

import chainlit as cl

from core.admin import get_db_stats, get_api_key_statuses, run_all_pings
from utils.logger import get_logger

log = get_logger("AdminHandler")

# ── 상장구분 라벨 ────────────────────────────────────────────────────

_CLS_LABELS = {"Y": "코스피", "K": "코스닥", "N": "코넥스", "E": "외감"}


async def handle_admin_command() -> None:
    """
    /admin 명령어 처리.

    DB 통계, API 키 상태, 연결 테스트 결과를 마크다운으로 표시합니다.
    """
    log.start("/admin 명령어 처리")

    status_msg = cl.Message(content="⏳ 관리자 정보를 조회 중입니다...")
    await status_msg.send()

    try:
        # ── 1. DB 통계 ──
        stats = await get_db_stats()

        cls_lines = "\n".join(
            f"  - {_CLS_LABELS.get(k, k)}: **{v:,}**건"
            for k, v in stats.by_corp_cls.items()
            if v > 0
        )

        stats_md = (
            f"### 📊 DB 통계\n"
            f"- 총 기업 수: **{stats.total_companies:,}**건\n"
            f"- DART 등록 (corp_code 보유): **{stats.with_corp_code:,}**건\n"
            f"- FSC 전용 (corp_code 없음): **{stats.without_corp_code:,}**건\n"
            f"- 상장구분별:\n{cls_lines}"
        )

        # ── 2. API 키 상태 ──
        keys = get_api_key_statuses()

        key_lines = "\n".join(
            f"  - {'✅' if k.configured else '❌'} {k.display_name}"
            f" {'(필수)' if k.required else '(선택)'}"
            for k in keys
        )
        keys_md = f"### 🔑 API 키 상태\n{key_lines}"

        # ── 3. 연결 테스트 ──
        pings = await run_all_pings()

        ping_lines = "\n".join(
            f"  - {'✅' if p.success else '❌'} **{p.name}**: "
            f"{p.message} ({p.elapsed_ms:.0f}ms)"
            for p in pings
        )
        pings_md = f"### 🔌 연결 테스트\n{ping_lines}"

        # ── 결과 표시 ──
        full_md = f"## 🛠️ Wreporter 관리자\n\n{stats_md}\n\n{keys_md}\n\n{pings_md}"
        status_msg.content = full_md
        await status_msg.update()

        log.ok("/admin", "완료")
        log.finish("/admin 명령어 처리")

    except Exception as e:
        log.error("/admin", str(e))
        status_msg.content = f"❌ 관리자 정보 조회 실패: {e}"
        await status_msg.update()
