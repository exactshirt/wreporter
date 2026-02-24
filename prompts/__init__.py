"""
프롬프트 로더.

prompts/ 디렉토리의 .md 파일을 읽어 문자열로 반환합니다.
"""

from pathlib import Path

_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """
    프롬프트 파일을 읽어 반환합니다.

    Args:
        name: 파일명 (확장자 없이). 예: "system_general"

    Returns:
        프롬프트 내용 문자열.

    Raises:
        FileNotFoundError: 파일이 없을 때.
    """
    path = _DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"프롬프트 파일 없음: {path}")
    return path.read_text(encoding="utf-8")


def list_prompts() -> list[str]:
    """사용 가능한 프롬프트 이름 목록을 반환합니다."""
    return [p.stem for p in _DIR.glob("*.md")]
