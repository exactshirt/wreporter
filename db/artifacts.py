"""
아티팩트(섹션별 보고서) CRUD.

artifacts 테이블을 사용하여 에이전트가 생성한 보고서 섹션을 관리합니다.
각 섹션은 section_key로 식별되며, 독립적으로 업데이트됩니다.
"""

from datetime import datetime, timezone

from db.client import get_client
from utils.logger import get_logger

log = get_logger("Artifacts")

# ── 섹션 스키마 정의 ──────────────────────────────────────────────
SECTION_SCHEMAS: dict[str, list[dict[str, str]]] = {
    "general": [
        {"key": "company_overview", "title": "기업개요"},
        {"key": "ax_moves", "title": "AX 관련 최근행보"},
        {"key": "biz_moves", "title": "사업 관련 최근행보"},
        {"key": "ax_insights", "title": "AX 영업 인사이트"},
        {"key": "smalltalk", "title": "스몰톡 소재"},
    ],
    "finance": [
        {"key": "financial_summary", "title": "최근 3년 재무 요약"},
        {"key": "financial_health", "title": "재무건전성 평가"},
        {"key": "key_changes", "title": "핵심 변화"},
        {"key": "ax_investment", "title": "AX 투자여력"},
        {"key": "sales_considerations", "title": "영업 시 고려사항"},
    ],
    "executives": [
        {"key": "executive_list", "title": "임원 리스트"},
        {"key": "curation_panel", "title": "큐레이션 패널"},
        # profile_0, profile_1, ... 은 동적으로 추가됨
    ],
}


async def get_sections(jurir_no: str, agent_type: str) -> list[dict]:
    """
    기업+에이전트의 모든 아티팩트 섹션을 조회합니다.

    Returns:
        섹션 리스트 (section_key, title, content, status, version 포함).
        없으면 빈 리스트.
    """
    log.start(f"섹션 조회: {jurir_no}/{agent_type}")
    try:
        client = await get_client()
        resp = (
            await client.table("artifacts")
            .select("*")
            .eq("jurir_no", jurir_no)
            .eq("agent_type", agent_type)
            .order("created_at")
            .execute()
        )
        data = resp.data or []
        log.ok("조회", f"{len(data)}개 섹션")
        log.finish(f"섹션 조회: {jurir_no}/{agent_type}")
        return data
    except Exception as e:
        log.error("조회", str(e))
        raise


async def get_section(
    jurir_no: str, agent_type: str, section_key: str
) -> dict | None:
    """특정 섹션 하나를 조회합니다."""
    client = await get_client()
    resp = (
        await client.table("artifacts")
        .select("*")
        .eq("jurir_no", jurir_no)
        .eq("agent_type", agent_type)
        .eq("section_key", section_key)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


async def save_section(
    conversation_id: str,
    jurir_no: str,
    agent_type: str,
    section_key: str,
    title: str,
    content: str,
) -> str:
    """
    섹션을 생성하거나 업데이트합니다 (upsert).

    이미 같은 (jurir_no, agent_type, section_key) 조합이 있으면
    content를 업데이트하고 version을 증가시킵니다.

    Args:
        conversation_id: 연결된 대화 id.
        jurir_no: 법인등록번호.
        agent_type: 에이전트 유형.
        section_key: 섹션 식별자.
        title: 섹션 제목.
        content: Markdown 본문.

    Returns:
        아티팩트 레코드의 id.
    """
    log.start(f"섹션 저장: {jurir_no}/{agent_type}/{section_key}")
    try:
        client = await get_client()
        now = datetime.now(timezone.utc).isoformat()

        # 기존 섹션 확인 (버전 증가용)
        existing = await get_section(jurir_no, agent_type, section_key)
        version = (existing["version"] + 1) if existing else 1

        row = {
            "conversation_id": conversation_id,
            "jurir_no": jurir_no,
            "agent_type": agent_type,
            "section_key": section_key,
            "title": title,
            "content": content,
            "status": "done",
            "version": version,
            "updated_at": now,
        }

        # upsert: INSERT or UPDATE in one query
        resp = (
            await client.table("artifacts")
            .upsert(row, on_conflict="jurir_no,agent_type,section_key")
            .execute()
        )

        art_id = resp.data[0]["id"]
        log.ok("저장", f"v{version}")
        log.finish(f"섹션 저장: {jurir_no}/{agent_type}/{section_key}")
        return art_id
    except Exception as e:
        log.error("저장", str(e))
        raise


async def update_section_status(
    jurir_no: str, agent_type: str, section_key: str, status: str
) -> None:
    """
    섹션의 상태만 업데이트합니다.

    Args:
        status: "empty" | "loading" | "done".
    """
    client = await get_client()
    await (
        client.table("artifacts")
        .update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("jurir_no", jurir_no)
        .eq("agent_type", agent_type)
        .eq("section_key", section_key)
        .execute()
    )


async def init_sections(
    conversation_id: str, jurir_no: str, agent_type: str
) -> None:
    """
    에이전트 유형에 맞는 빈 섹션들을 초기화합니다.

    이미 섹션이 존재하면 건너뜁니다.
    최적화: 1회 SELECT + 1회 bulk INSERT (기존 N+1 패턴 대체).
    """
    schema = SECTION_SCHEMAS.get(agent_type, [])
    if not schema:
        return

    # 기존 섹션 키 조회 (1회)
    existing_sections = await get_sections(jurir_no, agent_type)
    existing_keys = {s["section_key"] for s in existing_sections}

    # 새로 추가할 섹션만 필터링
    new_rows = [
        {
            "conversation_id": conversation_id,
            "jurir_no": jurir_no,
            "agent_type": agent_type,
            "section_key": sec["key"],
            "title": sec["title"],
            "content": "",
            "status": "empty",
            "version": 0,
        }
        for sec in schema
        if sec["key"] not in existing_keys
    ]

    # bulk insert (1회)
    if new_rows:
        client = await get_client()
        await client.table("artifacts").insert(new_rows).execute()
