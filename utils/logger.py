"""
n8n 노드 스타일 로거.

터미널과 logs/wreporter.log 에 동시 기록합니다.

사용 예시:
    from utils.logger import get_logger

    log = get_logger("DART")
    log.start("재무데이터 수집")
    log.step("API호출", "삼성전자 공시 조회 중...")
    log.ok("API호출", "20건 수신")
    log.finish("재무데이터 수집")
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "wreporter.log"

# 이름이 같은 로거를 중복 생성하지 않기 위한 레지스트리
_registry: dict[str, "WLogger"] = {}


class _FileFormatter(logging.Formatter):
    """파일용 — 타임스탬프 + 메시지."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        return f"{timestamp}  {record.getMessage()}"


class _ConsoleFormatter(logging.Formatter):
    """터미널용 — 메시지만."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


def _build_root_logger() -> logging.Logger:
    """공유 핸들러(파일 + 콘솔)를 가진 루트 로거를 한 번만 초기화합니다."""
    root = logging.getLogger("wreporter")
    if root.handlers:
        return root  # 이미 초기화됨

    root.setLevel(logging.DEBUG)

    LOG_DIR.mkdir(exist_ok=True)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(_FileFormatter())
    root.addHandler(fh)

    # Windows cp949 환경에서 이모지 출력을 위해 stdout을 UTF-8로 재설정
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(_ConsoleFormatter())
    root.addHandler(ch)

    return root


class WLogger:
    """모듈별 n8n 스타일 로거."""

    def __init__(self, module_name: str) -> None:
        self.module = module_name
        self._logger = _build_root_logger()

    # ── 상위 레벨 (들여쓰기 없음) ────────────────────────────────────────────

    def start(self, task: str) -> None:
        """🟢 [모듈] 시작: 작업명"""
        self._logger.info(f"🟢 [{self.module}] 시작: {task}")

    def finish(self, task: str) -> None:
        """🏁 [모듈] 완료: 작업명"""
        self._logger.info(f"🏁 [{self.module}] 완료: {task}")

    # ── 단계 레벨 (2칸 들여쓰기) ─────────────────────────────────────────────

    def step(self, stage: str, desc: str) -> None:
        """  📦 [단계] 설명..."""
        self._logger.info(f"  📦 [{stage}] {desc}")

    def ok(self, stage: str, msg: str = "완료") -> None:
        """  ✅ [단계] 완료"""
        self._logger.info(f"  ✅ [{stage}] {msg}")

    def warn(self, stage: str, msg: str) -> None:
        """  ⚠️  [단계] 경고"""
        self._logger.warning(f"  ⚠️  [{stage}] {msg}")

    def error(self, stage: str, msg: str) -> None:
        """  ❌ [단계] 에러 메시지"""
        self._logger.error(f"  ❌ [{stage}] {msg}")


def get_logger(module_name: str) -> WLogger:
    """모듈별 WLogger를 반환합니다. 같은 이름으로 중복 생성하지 않습니다."""
    if module_name not in _registry:
        _registry[module_name] = WLogger(module_name)
    return _registry[module_name]


if __name__ == "__main__":
    # ── 예시 1: DART 재무데이터 수집 ─────────────────────────────────────────
    log = get_logger("DART")
    log.start("재무데이터 수집")
    log.step("API호출", "삼성전자(005930) 공시 조회 중...")
    log.ok("API호출", "재무제표 20건 수신")
    log.step("파싱", "데이터 정제 중...")
    log.warn("파싱", "일부 항목 누락 — 기본값으로 대체합니다")
    log.ok("파싱")
    log.finish("재무데이터 수집")

    print()

    # ── 예시 2: Claude 리포트 생성 ───────────────────────────────────────────
    log2 = get_logger("Claude")
    log2.start("리포트 생성")
    log2.step("프롬프트", "컨텍스트 구성 중...")
    log2.ok("프롬프트")
    log2.step("LLM", "claude-sonnet-4-6 호출 중...")
    log2.error("LLM", "API 타임아웃 — 30초 초과")
    log2.finish("리포트 생성")

    print()
    print(f"[LOG] 로그 파일: {LOG_FILE.resolve()}")
