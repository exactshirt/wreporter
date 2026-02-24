"""
test_clients/ 전용 설정.

.env에 placeholder 값이 들어 있는 경우를 대비해
실제 키가 담긴 .env.example을 우선 로드합니다.
"""

import pytest
from dotenv import load_dotenv
from pathlib import Path

# override=True: .env.example의 실제 키로 기존 placeholder 값을 덮어씁니다.
load_dotenv(Path(__file__).parents[2] / ".env.example", override=True)


@pytest.fixture(autouse=True)
def reset_supabase_client():
    """
    테스트마다 Supabase 클라이언트 싱글턴을 초기화합니다.

    pytest-asyncio는 테스트별로 새 이벤트 루프를 생성하는데,
    이전 루프에서 만든 async 커넥션을 재사용하면 오류가 발생합니다.
    각 테스트 전후로 _client를 None으로 리셋해 새 커넥션을 생성하게 합니다.
    """
    import db.client
    db.client._client = None
    yield
    db.client._client = None
