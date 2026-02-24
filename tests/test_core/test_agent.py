"""
core/agent.py 단위 테스트.

parse_sections, _match_section_header, _build_initial_context 등
에이전트 헬퍼 함수를 테스트합니다.
실제 Claude API 호출이 필요한 run_agent는 통합 테스트에서 검증합니다.
"""

import pytest

from core.agent import parse_sections, _match_section_header, _build_initial_context


# ── parse_sections ────────────────────────────────────────────────

def test_parse_sections_general_5_sections():
    """일반정보 응답에서 5개 섹션을 추출해야 합니다."""
    response = """## 기업개요
삼성전자는 대한민국의 대표 전자기업입니다.

## AX 관련 최근행보
삼성전자는 AI 반도체 투자를 확대하고 있습니다.

## 사업 관련 최근행보
메모리 반도체 시장 회복 기조.

## AX 영업 인사이트
AI 반도체 수요 증가에 따른 AX 기회.

## 스몰톡 소재
CES 2024에서 새 제품 발표.
"""
    sections = parse_sections("general", response)
    assert "company_overview" in sections
    assert "ax_moves" in sections
    assert "biz_moves" in sections
    assert "ax_insights" in sections
    assert "smalltalk" in sections
    assert len(sections) == 5


def test_parse_sections_finance():
    """재무정보 응답에서 섹션을 추출해야 합니다."""
    response = """## 최근 3년 재무 요약
| 항목 | 2023 | 2022 | 2021 |

## 재무건전성 평가
부채비율 30%로 건전합니다.

## 핵심 변화
영업이익이 크게 감소했습니다.
"""
    sections = parse_sections("finance", response)
    assert "financial_summary" in sections
    assert "financial_health" in sections
    assert "key_changes" in sections


def test_parse_sections_empty_response():
    """빈 응답에서는 빈 dict를 반환합니다."""
    sections = parse_sections("general", "")
    assert sections == {}


def test_parse_sections_no_headers():
    """섹션 헤더가 없으면 빈 dict를 반환합니다."""
    sections = parse_sections("general", "그냥 텍스트입니다.")
    assert sections == {}


def test_parse_sections_unknown_agent_returns_full():
    """알 수 없는 에이전트 유형이면 전체 텍스트를 반환합니다."""
    text = "전체 텍스트"
    sections = parse_sections("unknown", text)
    assert sections == {"full": text}


# ── _match_section_header ─────────────────────────────────────────

def test_match_section_header_with_title():
    """제목과 매칭되는 섹션 키를 반환합니다."""
    from db.artifacts import SECTION_SCHEMAS
    schemas = SECTION_SCHEMAS["general"]
    assert _match_section_header("## 기업개요", schemas) == "company_overview"
    assert _match_section_header("### AX 관련 최근행보", schemas) == "ax_moves"


def test_match_section_header_no_match():
    """매칭되지 않으면 빈 문자열을 반환합니다."""
    from db.artifacts import SECTION_SCHEMAS
    schemas = SECTION_SCHEMAS["general"]
    assert _match_section_header("일반 텍스트", schemas) == ""
    assert _match_section_header("# 큰 제목", schemas) == ""


# ── _build_initial_context ────────────────────────────────────────

def test_build_initial_context_includes_corp_name():
    """기업 컨텍스트에 기업명이 포함되어야 합니다."""
    company = {"corp_name": "삼성전자", "jurir_no": "1101110000000"}
    context = _build_initial_context("general", company)
    assert "삼성전자" in context


def test_build_initial_context_includes_dart_status():
    """has_dart 여부가 반영되어야 합니다."""
    company = {"corp_name": "테스트", "jurir_no": "1234", "has_dart": True}
    context = _build_initial_context("general", company)
    assert "사용 가능" in context

    company2 = {"corp_name": "테스트", "jurir_no": "1234", "has_dart": False}
    context2 = _build_initial_context("general", company2)
    assert "사용 불가" in context2


def test_build_initial_context_includes_optional_fields():
    """선택 필드가 있으면 포함되어야 합니다."""
    company = {
        "corp_name": "테스트",
        "jurir_no": "1234",
        "corp_code": "00126380",
        "industry": "전자부품",
        "ceo_nm": "한종희",
    }
    context = _build_initial_context("general", company)
    assert "00126380" in context
    assert "전자부품" in context
    assert "한종희" in context
