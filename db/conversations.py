"""
대화 히스토리 CRUD.

conversations 테이블을 사용하여 에이전트별 대화를 영속적으로 관리합니다.
messages 필드는 JSONB 배열로, Claude API 메시지 형식과 1:1 대응됩니다.
"""

from datetime import datetime, timezone

from db.client import get_client
from utils.logger import get_logger

log = get_logger("Conversations")


async def get_conversation(jurir_no: str, agent_type: str) -> dict | None:
    """
    기업+에이전트 조합의 대화를 조회합니다.

    Args:
        jurir_no: 법인등록번호.
        agent_type: "general" | "finance" | "executives".

    Returns:
        대화 레코드 dict (id, messages 등 포함). 없으면 None.
    """
    log.start(f"대화 조회: {jurir_no}/{agent_type}")
    try:
        client = await get_client()
        resp = (
            await client.table("conversations")
            .select("*")
            .eq("jurir_no", jurir_no)
            .eq("agent_type", agent_type)
            .limit(1)
            .execute()
        )
        if resp.data:
            log.ok("조회", f"메시지 {len(resp.data[0].get('messages', []))}건")
            log.finish(f"대화 조회: {jurir_no}/{agent_type}")
            return resp.data[0]
        log.warn("조회", "대화 없음")
        log.finish(f"대화 조회: {jurir_no}/{agent_type}")
        return None
    except Exception as e:
        log.error("조회", str(e))
        raise


async def save_conversation(
    jurir_no: str,
    agent_type: str,
    messages: list[dict],
    corp_code: str | None = None,
    corp_name: str = "",
) -> str:
    """
    대화를 생성하거나 업데이트합니다 (upsert).

    jurir_no + agent_type 조합이 이미 있으면 messages를 업데이트하고,
    없으면 새 레코드를 생성합니다.

    Args:
        jurir_no: 법인등록번호.
        agent_type: "general" | "finance" | "executives".
        messages: Claude API 메시지 형식의 리스트.
        corp_code: DART 고유번호 (nullable).
        corp_name: 기업명.

    Returns:
        대화 레코드의 id.
    """
    log.start(f"대화 저장: {jurir_no}/{agent_type}")
    try:
        client = await get_client()
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "jurir_no": jurir_no,
            "agent_type": agent_type,
            "corp_code": corp_code,
            "corp_name": corp_name,
            "messages": messages,
            "updated_at": now,
        }
        resp = (
            await client.table("conversations")
            .upsert(row, on_conflict="jurir_no,agent_type")
            .execute()
        )
        conv_id = resp.data[0]["id"]
        log.ok("저장", f"id={conv_id}, 메시지 {len(messages)}건")
        log.finish(f"대화 저장: {jurir_no}/{agent_type}")
        return conv_id
    except Exception as e:
        log.error("저장", str(e))
        raise


async def append_message(
    jurir_no: str,
    agent_type: str,
    message: dict,
) -> None:
    """
    기존 대화에 메시지 하나를 추가합니다.

    대화가 없으면 아무 동작도 하지 않습니다.

    Args:
        jurir_no: 법인등록번호.
        agent_type: 에이전트 유형.
        message: 추가할 메시지 dict.
    """
    conv = await get_conversation(jurir_no, agent_type)
    if conv is None:
        log.warn("추가", "대화 없음 — 무시")
        return
    messages = conv.get("messages", [])
    messages.append(message)
    await save_conversation(
        jurir_no, agent_type, messages,
        corp_code=conv.get("corp_code"),
        corp_name=conv.get("corp_name", ""),
    )


async def delete_conversation(jurir_no: str, agent_type: str) -> None:
    """대화를 삭제합니다. 연결된 artifacts도 CASCADE 삭제됩니다."""
    log.start(f"대화 삭제: {jurir_no}/{agent_type}")
    try:
        client = await get_client()
        await (
            client.table("conversations")
            .delete()
            .eq("jurir_no", jurir_no)
            .eq("agent_type", agent_type)
            .execute()
        )
        log.ok("삭제")
        log.finish(f"대화 삭제: {jurir_no}/{agent_type}")
    except Exception as e:
        log.error("삭제", str(e))
        raise
