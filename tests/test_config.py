"""
utils/config.py 테스트.

환경변수 로딩, 필수 키 누락 에러, 선택 키 누락 경고를 검증합니다.
"""

import warnings
from pathlib import Path

import pytest

# 테스트마다 환경변수를 초기화하기 위해 os.environ을 직접 다룹니다.
import os

REQUIRED_ENV = {
    "DART_API_KEY": "dart-test-key",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "supabase-test-key",
    "SERPER_API_KEY": "serper-test-key",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """각 테스트 전에 관련 환경변수를 모두 제거하고, load_dotenv를 비활성화합니다.

    load_dotenv를 막지 않으면 실제 .env 파일을 읽어서 삭제한 키를 복원해버리므로,
    monkeypatch로 환경변수를 제어하는 테스트가 정상 동작하지 않습니다.
    (test_load_config_from_env_file처럼 env_path를 직접 넘기는 테스트는 제외)
    """
    monkeypatch.setattr("utils.config.load_dotenv", lambda *args, **kwargs: None)

    all_keys = [
        "DART_API_KEY",
        "ANTHROPIC_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SERPER_API_KEY",
        "FSC_API_KEY",
        "NICEBIZ_CLIENT_ID",
        "NICEBIZ_CLIENT_SECRET",
    ]
    for key in all_keys:
        monkeypatch.delenv(key, raising=False)


# ── 정상 케이스 ──────────────────────────────────────────────────────────────

def test_load_config_returns_settings(monkeypatch):
    """필수 키가 모두 있으면 Settings 객체를 정상 반환합니다."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    from utils.config import load_config, Settings

    config = load_config()

    assert isinstance(config, Settings)
    assert config.dart_api_key == "dart-test-key"
    assert config.anthropic_api_key == "sk-ant-test"
    assert config.supabase_url == "https://test.supabase.co"
    assert config.supabase_key == "supabase-test-key"
    assert config.serper_api_key == "serper-test-key"


def test_optional_keys_are_none_when_missing(monkeypatch):
    """선택 키가 없으면 None으로 설정됩니다."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    from utils.config import load_config

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        config = load_config()

    assert config.fsc_api_key is None
    assert config.nicebiz_client_id is None
    assert config.nicebiz_client_secret is None


def test_optional_keys_loaded_when_present(monkeypatch):
    """선택 키가 있으면 정상적으로 값이 들어갑니다."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("FSC_API_KEY", "fsc-test-key")
    monkeypatch.setenv("NICEBIZ_CLIENT_ID", "nicebiz-id-test")
    monkeypatch.setenv("NICEBIZ_CLIENT_SECRET", "nicebiz-secret-test")

    from utils.config import load_config

    config = load_config()

    assert config.fsc_api_key == "fsc-test-key"
    assert config.nicebiz_client_id == "nicebiz-id-test"
    assert config.nicebiz_client_secret == "nicebiz-secret-test"


# ── 에러 케이스 ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("missing_key", [
    "DART_API_KEY",
    "ANTHROPIC_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SERPER_API_KEY",
])
def test_missing_required_key_raises_value_error(monkeypatch, missing_key):
    """필수 키가 하나라도 없으면 ValueError가 발생합니다."""
    for key, value in REQUIRED_ENV.items():
        if key != missing_key:
            monkeypatch.setenv(key, value)

    from utils.config import load_config

    with pytest.raises(ValueError) as exc_info:
        load_config()

    assert missing_key in str(exc_info.value)
    assert ".env.example을 참고하세요" in str(exc_info.value)


def test_error_message_contains_all_missing_keys(monkeypatch):
    """여러 키가 동시에 없으면 에러 메시지에 모든 키가 포함됩니다."""
    # 아무 키도 설정하지 않음

    from utils.config import load_config

    with pytest.raises(ValueError) as exc_info:
        load_config()

    error_message = str(exc_info.value)
    for key in ["DART_API_KEY", "ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "SERPER_API_KEY"]:
        assert key in error_message


# ── 경고 케이스 ───────────────────────────────────────────────────────────────

def test_missing_optional_key_warns(monkeypatch):
    """선택 키가 없으면 경고 메시지가 출력됩니다."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    # FSC_API_KEY, NICEBIZ_CLIENT_ID, NICEBIZ_CLIENT_SECRET 는 설정하지 않음

    from utils.config import load_config

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_config()

    warning_messages = [str(w.message) for w in caught]
    assert any("FSC_API_KEY" in msg for msg in warning_messages)
    assert any("NICEBIZ_CLIENT_ID" in msg for msg in warning_messages)
    assert any("NICEBIZ_CLIENT_SECRET" in msg for msg in warning_messages)


def test_no_warning_when_all_optional_keys_present(monkeypatch):
    """선택 키가 모두 있으면 경고가 없습니다."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("FSC_API_KEY", "fsc-key")
    monkeypatch.setenv("NICEBIZ_CLIENT_ID", "nicebiz-id")
    monkeypatch.setenv("NICEBIZ_CLIENT_SECRET", "nicebiz-secret")

    from utils.config import load_config

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_config()

    assert len(caught) == 0


# ── .env 파일 직접 로드 테스트 ─────────────────────────────────────────────────

def test_load_config_from_env_file(tmp_path, monkeypatch):
    """tmp_path에 만든 .env 파일을 직접 읽어옵니다."""
    # 이 테스트는 실제 load_dotenv 동작이 필요하므로 autouse fixture의 mock을 해제합니다.
    import dotenv
    monkeypatch.setattr("utils.config.load_dotenv", dotenv.load_dotenv)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "DART_API_KEY=dart-file-key\n"
        "ANTHROPIC_API_KEY=sk-ant-file\n"
        "SUPABASE_URL=https://file.supabase.co\n"
        "SUPABASE_KEY=file-supabase-key\n"
        "SERPER_API_KEY=file-serper-key\n"
        "FSC_API_KEY=file-fsc-key\n",
        encoding="utf-8",
    )

    from utils.config import load_config

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        config = load_config(env_path=env_file)

    assert config.dart_api_key == "dart-file-key"
    assert config.fsc_api_key == "file-fsc-key"
    assert config.nicebiz_client_id is None
    assert config.nicebiz_client_secret is None
    # NICEBIZ_CLIENT_ID, NICEBIZ_CLIENT_SECRET 경고 각 1개씩
    assert sum(1 for w in caught if "NICEBIZ_CLIENT_ID" in str(w.message)) == 1
    assert sum(1 for w in caught if "NICEBIZ_CLIENT_SECRET" in str(w.message)) == 1
