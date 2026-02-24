-- Phase 2: 통합 리서치 인터페이스용 테이블
-- 실행: Supabase SQL Editor에서 실행

-- ── 1. pinned_companies: 핀(즐겨찾기) 기업 ──────────────────────
CREATE TABLE IF NOT EXISTS pinned_companies (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    corp_code TEXT,                          -- DART 고유번호 (nullable: FSC 전용 기업)
    jurir_no TEXT NOT NULL UNIQUE,           -- 법인등록번호 (기업 고유 식별)
    corp_name TEXT NOT NULL,
    corp_cls TEXT,                           -- Y=코스피, K=코스닥, N=코넥스, E=외감
    market_label TEXT,
    source_label TEXT,
    has_dart BOOLEAN DEFAULT false,
    industry TEXT,                           -- 업종
    ceo_nm TEXT,                             -- 대표자
    pinned_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pinned_jurir ON pinned_companies(jurir_no);

-- ── 2. conversations: 에이전트 대화 히스토리 ─────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    corp_code TEXT,
    jurir_no TEXT NOT NULL,
    corp_name TEXT NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('general', 'finance', 'executives')),
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (jurir_no, agent_type)
);

CREATE INDEX IF NOT EXISTS idx_conv_jurir ON conversations(jurir_no);
CREATE INDEX IF NOT EXISTS idx_conv_agent ON conversations(agent_type);

-- ── 3. artifacts: 섹션별 아티팩트 ────────────────────────────────
CREATE TABLE IF NOT EXISTS artifacts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    jurir_no TEXT NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('general', 'finance', 'executives')),
    section_key TEXT NOT NULL,              -- 섹션 식별자 (예: "company_overview")
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',       -- Markdown 본문
    status TEXT DEFAULT 'empty' CHECK (status IN ('empty', 'loading', 'done')),
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_art_conv ON artifacts(conversation_id);
CREATE INDEX IF NOT EXISTS idx_art_jurir_agent ON artifacts(jurir_no, agent_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_art_section ON artifacts(jurir_no, agent_type, section_key);
