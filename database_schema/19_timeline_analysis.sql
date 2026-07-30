-- 19_timeline_analysis.sql
-- ------------------------------------------------------------------
-- Krok 3 agentické AI pipeline (RAG + Chain-of-Thought analýza časové
-- osy jedné nemovitosti, viz backend/timeline_analysis.py). Na rozdíl
-- od ai_research_findings (web-search vrstva) tahle vrstva dostává
-- VÝHRADNĚ fakta z naší vlastní DB - žádné externí vyhledávání.
--
-- Finální propensity_score po tomhle kroku:
--   LEAST(100, percentile_score + ai_signal_score + timeline_signal_score)
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

CREATE TABLE IF NOT EXISTS ai_timeline_assessments (
    id BIGSERIAL PRIMARY KEY,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    reasoning_summary TEXT,
    trigger_signals TEXT[],
    score_adjustment NUMERIC,
    confidence VARCHAR(10),
    analyzed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ai_timeline_assessments_property_id_idx
    ON ai_timeline_assessments (property_id);

ALTER TABLE properties ADD COLUMN IF NOT EXISTS timeline_signal_score NUMERIC DEFAULT 0;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS timeline_signal_note TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS timeline_analyzed_at TIMESTAMPTZ;
