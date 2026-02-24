"""
핀(즐겨찾기) 기업 관리 CRUD.

pinned_companies 테이블을 사용하여 핀된 기업 목록을 영속적으로 관리합니다.
"""

from db.client import get_client
from utils.logger import get_logger

log = get_logger("Pins")


async def get_all_pins() -> list[dict]:
    """
    모든 핀된 기업을 pinned_at 내림차순으로 반환합니다.

    Returns:
        핀된 기업 리스트. 없으면 빈 리스트.
    """
    log.start("핀 목록 조회")
    try:
        client = await get_client()
        resp = (
            await client.table("pinned_companies")
            .select("*")
            .order("pinned_at", desc=True)
            .execute()
        )
        data = resp.data or []
        log.ok("조회", f"{len(data)}건")
        log.finish("핀 목록 조회")
        return data
    except Exception as e:
        log.error("조회", str(e))
        raise


async def add_pin(company: dict) -> str:
    """
    기업을 핀 목록에 추가합니다.

    이미 핀되어 있으면(jurir_no 중복) 무시하고 기존 id를 반환합니다.

    Args:
        company: 기업 정보 dict. 필수: jurir_no, corp_name.

    Returns:
        생성(또는 기존)된 pinned_companies 레코드의 id.
    """
    jurir_no = company["jurir_no"]
    log.start(f"핀 추가: {company.get('corp_name', jurir_no)}")
    try:
        client = await get_client()

        # 이미 핀되어 있는지 확인
        existing = (
            await client.table("pinned_companies")
            .select("id")
            .eq("jurir_no", jurir_no)
            .limit(1)
            .execute()
        )
        if existing.data:
            log.warn("추가", "이미 핀됨 — 기존 레코드 반환")
            log.finish(f"핀 추가: {company.get('corp_name', jurir_no)}")
            return existing.data[0]["id"]

        row = {
            "corp_code": company.get("corp_code"),
            "jurir_no": jurir_no,
            "corp_name": company["corp_name"],
            "corp_cls": company.get("corp_cls"),
            "market_label": company.get("market_label"),
            "source_label": company.get("source_label"),
            "has_dart": company.get("has_dart", False),
            "industry": company.get("industry"),
            "ceo_nm": company.get("ceo_nm"),
        }
        resp = (
            await client.table("pinned_companies")
            .insert(row)
            .execute()
        )
        pin_id = resp.data[0]["id"]
        log.ok("추가", pin_id)
        log.finish(f"핀 추가: {company.get('corp_name', jurir_no)}")
        return pin_id
    except Exception as e:
        log.error("추가", str(e))
        raise


async def remove_pin(jurir_no: str) -> None:
    """
    핀을 해제(삭제)합니다.

    Args:
        jurir_no: 법인등록번호.
    """
    log.start(f"핀 삭제: {jurir_no}")
    try:
        client = await get_client()
        await (
            client.table("pinned_companies")
            .delete()
            .eq("jurir_no", jurir_no)
            .execute()
        )
        log.ok("삭제")
        log.finish(f"핀 삭제: {jurir_no}")
    except Exception as e:
        log.error("삭제", str(e))
        raise


async def is_pinned(jurir_no: str) -> bool:
    """기업이 핀되어 있는지 확인합니다."""
    client = await get_client()
    resp = (
        await client.table("pinned_companies")
        .select("id")
        .eq("jurir_no", jurir_no)
        .limit(1)
        .execute()
    )
    return bool(resp.data)
