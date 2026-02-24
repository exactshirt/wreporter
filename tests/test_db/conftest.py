"""
test_db/ 전용 설정.

Phase 2 DB 모듈 (pins, conversations, artifacts) 테스트를 위한 fixture.
"""

import pytest
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parents[2] / ".env.example", override=True)


@pytest.fixture(autouse=True)
def reset_supabase_client():
    """테스트마다 Supabase 클라이언트 싱글턴을 초기화합니다."""
    import db.client
    db.client._client = None
    yield
    db.client._client = None


# 테스트용 고유 jurir_no (실제 기업과 겹치지 않도록)
TEST_JURIR_NO = "9999999999999"
TEST_CORP_NAME = "테스트기업_Phase2"


@pytest.fixture
async def cleanup_test_pin():
    """테스트 전후로 테스트용 핀 데이터를 정리합니다."""
    from db import pins
    # 전처리: 혹시 남아있을 수 있는 이전 테스트 데이터 삭제
    try:
        await pins.remove_pin(TEST_JURIR_NO)
    except Exception:
        pass
    yield
    # 후처리: 테스트 데이터 삭제
    try:
        await pins.remove_pin(TEST_JURIR_NO)
    except Exception:
        pass


@pytest.fixture
async def cleanup_test_conversation():
    """테스트 전후로 테스트용 대화 데이터를 정리합니다."""
    from db import conversations
    # 전처리
    for agent_type in ("general", "finance", "executives"):
        try:
            await conversations.delete_conversation(TEST_JURIR_NO, agent_type)
        except Exception:
            pass
    yield
    # 후처리
    for agent_type in ("general", "finance", "executives"):
        try:
            await conversations.delete_conversation(TEST_JURIR_NO, agent_type)
        except Exception:
            pass
