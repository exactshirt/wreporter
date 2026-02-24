"""
Supabase 클라이언트.

get_client()를 await하면 연결된 AsyncClient를 반환합니다.
같은 프로세스 내에서 한 번만 생성하는 싱글턴 패턴을 사용합니다.
"""

import asyncio

from supabase import AsyncClient, acreate_client

from utils.config import load_config
from utils.logger import get_logger

log = get_logger("Supabase")

_client: AsyncClient | None = None
_lock = asyncio.Lock()


async def get_client() -> AsyncClient:
    """
    Supabase AsyncClient를 반환합니다.
    첫 호출 시 연결을 생성하고, 이후에는 동일 인스턴스를 재사용합니다.
    """
    global _client
    if _client is None:
        async with _lock:
            if _client is None:
                cfg = load_config()
                log.step("연결", f"Supabase 연결 중... ({cfg.supabase_url})")
                _client = await acreate_client(cfg.supabase_url, cfg.supabase_key)
                log.ok("연결")
    return _client
