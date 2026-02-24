-- Phase 2 최적화: 검색 인덱스 + 통계 RPC

-- 1. pg_trgm 확장 활성화 + 검색 인덱스
-- ILIKE 검색 시 풀 테이블 스캔 방지 (70만 건 → 인덱스 스캔)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_companies_corp_name_trgm
    ON companies USING gin (corp_name gin_trgm_ops);

-- 2. admin 통계를 단일 쿼리로 조회하는 RPC 함수
-- 기존: 6회 순차 COUNT → 최적화: 1회 쿼리
CREATE OR REPLACE FUNCTION get_company_stats()
RETURNS TABLE(
    total bigint,
    with_corp_code bigint,
    cls_y bigint,
    cls_k bigint,
    cls_n bigint,
    cls_e bigint
)
AS $$
    SELECT
        COUNT(*),
        COUNT(corp_code),
        COUNT(*) FILTER (WHERE corp_cls = 'Y'),
        COUNT(*) FILTER (WHERE corp_cls = 'K'),
        COUNT(*) FILTER (WHERE corp_cls = 'N'),
        COUNT(*) FILTER (WHERE corp_cls = 'E')
    FROM companies;
$$ LANGUAGE sql STABLE;
