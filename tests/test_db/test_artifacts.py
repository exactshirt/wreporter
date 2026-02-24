"""
db/artifacts.py 단위 테스트.

실제 Supabase artifacts 테이블에 대한 CRUD 테스트.
conversations 테이블에 먼저 레코드를 생성해야 FK 제약을 충족합니다.
"""

import pytest

from db import artifacts as art_db
from db import conversations as conv_db
from tests.test_db.conftest import TEST_JURIR_NO, TEST_CORP_NAME


@pytest.fixture
async def test_conversation():
    """테스트용 대화 레코드를 생성하고 cleanup합니다."""
    conv_id = await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=[],
        corp_name=TEST_CORP_NAME,
    )
    yield conv_id
    # CASCADE 삭제: 대화 삭제 시 아티팩트도 함께 삭제됨
    await conv_db.delete_conversation(TEST_JURIR_NO, "general")


# ── SECTION_SCHEMAS ───────────────────────────────────────────────

def test_section_schemas_has_all_agent_types():
    """3개 에이전트 유형 모두 스키마가 있어야 합니다."""
    assert "general" in art_db.SECTION_SCHEMAS
    assert "finance" in art_db.SECTION_SCHEMAS
    assert "executives" in art_db.SECTION_SCHEMAS


def test_general_schema_has_5_sections():
    """일반정보는 5개 섹션이어야 합니다."""
    assert len(art_db.SECTION_SCHEMAS["general"]) == 5


def test_finance_schema_has_5_sections():
    """재무정보는 5개 섹션이어야 합니다."""
    assert len(art_db.SECTION_SCHEMAS["finance"]) == 5


def test_executives_schema_has_base_sections():
    """임원정보는 최소 2개 기본 섹션이어야 합니다."""
    assert len(art_db.SECTION_SCHEMAS["executives"]) >= 2


def test_section_schema_has_key_and_title():
    """모든 스키마 항목에 key와 title이 있어야 합니다."""
    for agent_type, sections in art_db.SECTION_SCHEMAS.items():
        for sec in sections:
            assert "key" in sec, f"{agent_type}: key 없음"
            assert "title" in sec, f"{agent_type}: title 없음"


# ── save_section / get_section ────────────────────────────────────

async def test_save_section_returns_id(test_conversation):
    """섹션 저장 시 id를 반환해야 합니다."""
    art_id = await art_db.save_section(
        conversation_id=test_conversation,
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        section_key="company_overview",
        title="기업개요",
        content="## 기업개요\n테스트 내용입니다.",
    )
    assert art_id is not None
    assert isinstance(art_id, str)


async def test_get_section_returns_saved_data(test_conversation):
    """저장한 섹션을 조회할 수 있어야 합니다."""
    content = "## 기업개요\n삼성전자는 대한민국의 대표 전자기업입니다."
    await art_db.save_section(
        conversation_id=test_conversation,
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        section_key="company_overview",
        title="기업개요",
        content=content,
    )

    section = await art_db.get_section(TEST_JURIR_NO, "general", "company_overview")
    assert section is not None
    assert section["section_key"] == "company_overview"
    assert section["title"] == "기업개요"
    assert section["content"] == content
    assert section["status"] == "done"
    assert section["version"] == 1


async def test_save_section_increments_version(test_conversation):
    """같은 섹션을 다시 저장하면 version이 증가해야 합니다."""
    await art_db.save_section(
        conversation_id=test_conversation,
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        section_key="company_overview",
        title="기업개요",
        content="v1 내용",
    )
    await art_db.save_section(
        conversation_id=test_conversation,
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        section_key="company_overview",
        title="기업개요",
        content="v2 수정된 내용",
    )

    section = await art_db.get_section(TEST_JURIR_NO, "general", "company_overview")
    assert section["version"] == 2
    assert section["content"] == "v2 수정된 내용"


# ── get_sections ──────────────────────────────────────────────────

async def test_get_sections_returns_all_for_agent(test_conversation):
    """에이전트 유형에 해당하는 모든 섹션을 반환해야 합니다."""
    await art_db.save_section(
        test_conversation, TEST_JURIR_NO, "general",
        "company_overview", "기업개요", "내용1",
    )
    await art_db.save_section(
        test_conversation, TEST_JURIR_NO, "general",
        "ax_moves", "AX 관련 최근행보", "내용2",
    )

    sections = await art_db.get_sections(TEST_JURIR_NO, "general")
    assert len(sections) == 2
    keys = {s["section_key"] for s in sections}
    assert keys == {"company_overview", "ax_moves"}


async def test_get_sections_returns_empty_for_no_data():
    """데이터가 없으면 빈 리스트를 반환해야 합니다."""
    sections = await art_db.get_sections("0000000000000", "general")
    assert sections == []


# ── init_sections ─────────────────────────────────────────────────

async def test_init_sections_creates_empty_sections(test_conversation):
    """init_sections가 스키마에 맞는 빈 섹션들을 생성해야 합니다."""
    await art_db.init_sections(test_conversation, TEST_JURIR_NO, "general")

    sections = await art_db.get_sections(TEST_JURIR_NO, "general")
    assert len(sections) == 5  # general은 5개 섹션

    for sec in sections:
        assert sec["content"] == ""
        assert sec["status"] == "empty"
        assert sec["version"] == 0


# ── update_section_status ─────────────────────────────────────────

async def test_update_section_status(test_conversation):
    """섹션 상태만 업데이트할 수 있어야 합니다."""
    await art_db.init_sections(test_conversation, TEST_JURIR_NO, "general")

    await art_db.update_section_status(
        TEST_JURIR_NO, "general", "company_overview", "loading"
    )

    section = await art_db.get_section(TEST_JURIR_NO, "general", "company_overview")
    assert section["status"] == "loading"


# ── CASCADE 삭제 ──────────────────────────────────────────────────

async def test_cascade_delete_removes_artifacts(cleanup_test_conversation):
    """대화 삭제 시 연결된 아티팩트도 함께 삭제되어야 합니다."""
    conv_id = await conv_db.save_conversation(
        jurir_no=TEST_JURIR_NO,
        agent_type="general",
        messages=[],
        corp_name=TEST_CORP_NAME,
    )
    await art_db.save_section(
        conv_id, TEST_JURIR_NO, "general",
        "company_overview", "기업개요", "삭제될 내용",
    )

    # 아티팩트가 존재하는지 확인
    assert await art_db.get_section(TEST_JURIR_NO, "general", "company_overview") is not None

    # 대화 삭제 (CASCADE)
    await conv_db.delete_conversation(TEST_JURIR_NO, "general")

    # 아티팩트도 삭제되었는지 확인
    assert await art_db.get_section(TEST_JURIR_NO, "general", "company_overview") is None
