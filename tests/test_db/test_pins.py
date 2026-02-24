"""
db/pins.py 단위 테스트.

실제 Supabase pinned_companies 테이블에 대한 CRUD 테스트.
테스트용 jurir_no를 사용하며, 테스트 전후로 정리합니다.
"""

import pytest

from db import pins
from tests.test_db.conftest import TEST_JURIR_NO, TEST_CORP_NAME


# ── add_pin ───────────────────────────────────────────────────────

async def test_add_pin_creates_record(cleanup_test_pin):
    """핀 추가 시 id를 반환해야 합니다."""
    company = {
        "jurir_no": TEST_JURIR_NO,
        "corp_name": TEST_CORP_NAME,
        "corp_cls": "E",
        "market_label": "비상장외감",
        "has_dart": False,
        "industry": "테스트업종",
        "ceo_nm": "테스트대표",
    }
    pin_id = await pins.add_pin(company)
    assert pin_id is not None
    assert isinstance(pin_id, str)
    assert len(pin_id) > 0


async def test_add_pin_duplicate_returns_existing_id(cleanup_test_pin):
    """이미 핀된 기업을 다시 추가하면 기존 id를 반환합니다."""
    company = {"jurir_no": TEST_JURIR_NO, "corp_name": TEST_CORP_NAME}
    id1 = await pins.add_pin(company)
    id2 = await pins.add_pin(company)
    assert id1 == id2


# ── get_all_pins ──────────────────────────────────────────────────

async def test_get_all_pins_returns_list(cleanup_test_pin):
    """핀 목록을 리스트로 반환해야 합니다."""
    result = await pins.get_all_pins()
    assert isinstance(result, list)


async def test_get_all_pins_includes_added_pin(cleanup_test_pin):
    """추가한 핀이 목록에 포함되어야 합니다."""
    company = {
        "jurir_no": TEST_JURIR_NO,
        "corp_name": TEST_CORP_NAME,
        "industry": "테스트업종",
        "ceo_nm": "테스트대표",
    }
    await pins.add_pin(company)
    all_pins = await pins.get_all_pins()
    jurir_nos = [p.get("jurir_no") for p in all_pins]
    assert TEST_JURIR_NO in jurir_nos


async def test_get_all_pins_has_required_fields(cleanup_test_pin):
    """핀 레코드에 필수 필드가 있어야 합니다."""
    company = {
        "jurir_no": TEST_JURIR_NO,
        "corp_name": TEST_CORP_NAME,
        "industry": "테스트업종",
        "ceo_nm": "테스트대표",
    }
    await pins.add_pin(company)
    all_pins = await pins.get_all_pins()
    test_pin = next(p for p in all_pins if p["jurir_no"] == TEST_JURIR_NO)
    assert "id" in test_pin
    assert test_pin["corp_name"] == TEST_CORP_NAME
    assert test_pin["industry"] == "테스트업종"
    assert test_pin["ceo_nm"] == "테스트대표"


# ── is_pinned ─────────────────────────────────────────────────────

async def test_is_pinned_returns_true_after_add(cleanup_test_pin):
    """핀 추가 후 is_pinned이 True를 반환해야 합니다."""
    company = {"jurir_no": TEST_JURIR_NO, "corp_name": TEST_CORP_NAME}
    await pins.add_pin(company)
    assert await pins.is_pinned(TEST_JURIR_NO) is True


async def test_is_pinned_returns_false_for_unknown():
    """존재하지 않는 jurir_no는 False를 반환해야 합니다."""
    assert await pins.is_pinned("0000000000000") is False


# ── remove_pin ────────────────────────────────────────────────────

async def test_remove_pin_deletes_record(cleanup_test_pin):
    """핀 삭제 후 is_pinned이 False여야 합니다."""
    company = {"jurir_no": TEST_JURIR_NO, "corp_name": TEST_CORP_NAME}
    await pins.add_pin(company)
    assert await pins.is_pinned(TEST_JURIR_NO) is True

    await pins.remove_pin(TEST_JURIR_NO)
    assert await pins.is_pinned(TEST_JURIR_NO) is False
