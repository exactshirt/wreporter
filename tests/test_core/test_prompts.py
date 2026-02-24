"""
prompts/__init__.py 단위 테스트.

프롬프트 로딩 기능을 테스트합니다.
"""

import pytest

from prompts import load_prompt, list_prompts


# ── load_prompt ───────────────────────────────────────────────────

def test_load_prompt_general():
    """system_general 프롬프트를 로드할 수 있어야 합니다."""
    prompt = load_prompt("system_general")
    assert len(prompt) > 100
    assert "AX" in prompt or "에이전트" in prompt


def test_load_prompt_finance():
    """system_finance 프롬프트를 로드할 수 있어야 합니다."""
    prompt = load_prompt("system_finance")
    assert len(prompt) > 100
    assert "재무" in prompt or "finance" in prompt.lower()


def test_load_prompt_executives():
    """system_executives 프롬프트를 로드할 수 있어야 합니다."""
    prompt = load_prompt("system_executives")
    assert len(prompt) > 100
    assert "임원" in prompt or "OSINT" in prompt


def test_load_prompt_not_found_raises():
    """존재하지 않는 프롬프트는 FileNotFoundError를 발생시킵니다."""
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_prompt")


# ── list_prompts ──────────────────────────────────────────────────

def test_list_prompts_includes_all_three():
    """3개 시스템 프롬프트가 모두 포함되어야 합니다."""
    prompts = list_prompts()
    assert "system_general" in prompts
    assert "system_finance" in prompts
    assert "system_executives" in prompts
