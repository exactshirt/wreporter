"""
db/conversations.py 단위 테스트.

실제 Supabase conversations 테이블에 대한 CRUD 테스트.
"""

import pytest

from db import conversations as conv_db
from tests.test_db.conftest import TEST_JURIR_NO, TEST_CORP_NAME


# ── save_conversation / get_conversation ──────────────────────────

async def test_save_conversation_returns_id(cleanup_test_conversation):
    """대화 저장 시 id를 반환해야 합니다."""
    messages = [{"role": "user", "content": "테스트 메시지"}]
    conv_id = await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=messages,
        corp_name=TEST_CORP_NAME,
    )
    assert conv_id is not None
    assert isinstance(conv_id, str)


async def test_get_conversation_returns_saved_data(cleanup_test_conversation):
    """저장한 대화를 조회할 수 있어야 합니다."""
    messages = [
        {"role": "user", "content": "삼성전자 분석해줘"},
        {"role": "assistant", "content": "분석을 시작하겠습니다."},
    ]
    await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=messages,
        corp_name=TEST_CORP_NAME,
    )

    conv = await conv_db.get_conversation(TEST_JURIR_NO, "general")
    assert conv is not None
    assert conv["jurir_no"] == TEST_JURIR_NO
    assert conv["agent_type"] == "general"
    assert len(conv["messages"]) == 2
    assert conv["messages"][0]["role"] == "user"


async def test_get_conversation_returns_none_for_missing(cleanup_test_conversation):
    """존재하지 않는 대화는 None을 반환해야 합니다."""
    conv = await conv_db.get_conversation("0000000000000", "general")
    assert conv is None


async def test_save_conversation_upserts_on_conflict(cleanup_test_conversation):
    """같은 jurir_no+agent_type으로 저장하면 업데이트되어야 합니다."""
    msgs1 = [{"role": "user", "content": "첫 번째"}]
    id1 = await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=msgs1,
        corp_name=TEST_CORP_NAME,
    )

    msgs2 = [{"role": "user", "content": "첫 번째"}, {"role": "assistant", "content": "두 번째"}]
    id2 = await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=msgs2,
        corp_name=TEST_CORP_NAME,
    )

    # 같은 레코드가 업데이트되어야 함
    assert id1 == id2

    conv = await conv_db.get_conversation(TEST_JURIR_NO, "general")
    assert len(conv["messages"]) == 2


# ── agent_type 분리 ───────────────────────────────────────────────

async def test_different_agent_types_are_independent(cleanup_test_conversation):
    """다른 agent_type의 대화는 독립적이어야 합니다."""
    await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=[{"role": "user", "content": "일반정보"}],
        corp_name=TEST_CORP_NAME,
    )
    await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="finance",
        messages=[{"role": "user", "content": "재무정보"}],
        corp_name=TEST_CORP_NAME,
    )

    general = await conv_db.get_conversation(TEST_JURIR_NO, "general")
    finance = await conv_db.get_conversation(TEST_JURIR_NO, "finance")
    assert general["messages"][0]["content"] == "일반정보"
    assert finance["messages"][0]["content"] == "재무정보"


# ── delete_conversation ───────────────────────────────────────────

async def test_delete_conversation_removes_record(cleanup_test_conversation):
    """대화 삭제 후 조회하면 None이어야 합니다."""
    await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=[{"role": "user", "content": "삭제될 대화"}],
        corp_name=TEST_CORP_NAME,
    )
    assert await conv_db.get_conversation(TEST_JURIR_NO, "general") is not None

    await conv_db.delete_conversation(TEST_JURIR_NO, "general")
    assert await conv_db.get_conversation(TEST_JURIR_NO, "general") is None
