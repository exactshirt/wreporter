"""
환경변수 설정 로더.

.env 파일에서 API 키 등을 읽어 Settings 객체로 반환합니다.
필수 키가 없으면 ValueError를 발생시키고, 선택 키가 없으면 경고만 출력합니다.
"""

import os
import warnings
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REQUIRED_KEYS = [
    "DART_API_KEY",
    "ANTHROPIC_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SERPER_API_KEY",
]

OPTIONAL_KEYS = [
    "FSC_API_KEY",
    "NICEBIZ_CLIENT_ID",
    "NICEBIZ_CLIENT_SECRET",
]


@dataclass
class Settings:
    dart_api_key: str
    anthropic_api_key: str
    supabase_url: str
    supabase_key: str
    serper_api_key: str
    fsc_api_key: str | None = None
    nicebiz_client_id: str | None = None
    nicebiz_client_secret: str | None = None


def load_config(env_path: Path | None = None) -> Settings:
    """
    .env 파일을 로드하고 Settings 객체를 반환합니다.

    Args:
        env_path: .env 파일 경로. None이면 현재 디렉터리의 .env를 자동 탐색합니다.

    Returns:
        Settings: 환경변수가 담긴 설정 객체.

    Raises:
        ValueError: 필수 키 중 하나라도 없을 때.
    """
    load_dotenv(env_path, override=False)

    missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]
    if missing:
        messages = "\n".join(
            f"❌ {key}가 .env에 없습니다. .env.example을 참고하세요."
            for key in missing
        )
        raise ValueError(f"필수 환경변수가 설정되지 않았습니다:\n{messages}")

    for key in OPTIONAL_KEYS:
        if not os.getenv(key):
            warnings.warn(
                f"⚠️ {key}가 .env에 없습니다. 관련 기능이 비활성화됩니다.",
                stacklevel=2,
            )

    return Settings(
        dart_api_key=os.environ["DART_API_KEY"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_key=os.environ["SUPABASE_KEY"],
        serper_api_key=os.environ["SERPER_API_KEY"],
        fsc_api_key=os.getenv("FSC_API_KEY"),
        nicebiz_client_id=os.getenv("NICEBIZ_CLIENT_ID"),
        nicebiz_client_secret=os.getenv("NICEBIZ_CLIENT_SECRET"),
    )
