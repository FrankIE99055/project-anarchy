-- 14_ai_research.sql
-- ------------------------------------------------------------------
-- AI-research vrstva: AI při zobrazení nemovitosti sama vyhledá veřejné
-- události o KONKRÉTNÍ adrese (Daft/reality/zprávy/úřady) přes web-search
-- API a promítne nález do skóre. Výsledek se CACHUJE v DB, aby se stejná
-- nemovitost neprohledávala opakovaně (viz ai_signal_researched_at TTL
-- v backend/ai_research.py).
--
-- GDPR: ukládáme jen faktický souhrn veřejné události vázaný na adresu
-- (ne na osobu) - žádná jména vlastníků/nájemníků se neukládají, AI má
-- explicitní instrukci je vynechat i kdyby byla ve zdroji.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

CREATE TABLE IF NOT EXISTS ai_research_findings (
    id BIGSERIAL PRIMARY KEY,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    source_url TEXT,
    title TEXT,
    finding_summary TEXT,        -- GDPR-safe, faktický souhrn (bez jmen osob)
    score_impact NUMERIC DEFAULT 0,
    found_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (property_id, source_url)
);

CREATE INDEX IF NOT EXISTS ai_research_findings_property_id_idx
    ON ai_research_findings (property_id);

-- Persistované mezivýsledky z v2 percentilového skóre, aby šlo skóre
-- jedné nemovitosti přepočítat rychle (bez znovuspuštění window function
-- přes celou tabulku) poté, co AI research najde/aktualizuje nález.
ALTER TABLE properties ADD COLUMN IF NOT EXISTS percentile_score NUMERIC;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS base_key_drivers TEXT[];

UPDATE properties p
SET percentile_score = s.percentile_score,
    base_key_drivers = s.base_key_drivers
FROM (
    SELECT
        ranked.property_id,
        ranked.percentile_score,
        ranked.base_key_drivers
    FROM (
        SELECT
            r.*,
            PERCENT_RANK() OVER (ORDER BY r.raw_score) * 100 AS percentile_score
        FROM (
            SELECT
                s.property_id,
                COALESCE(LEAST(s.years_since_last_sale / 15.0, 1.0) * 30, 0)
                + CASE WHEN s.has_retention_permission THEN 25
                       WHEN s.has_any_permission THEN 5
                       ELSE 0 END
                + CASE WHEN s.is_derelict_or_vacant THEN 30 ELSE 0 END
                + CASE WHEN s.rented_then_listed_for_sale THEN 15 ELSE 0 END
                + CASE WHEN s.relisting_count > 2 THEN 10 ELSE 0 END
                + CASE WHEN s.price_drop_pct > 5 THEN 10 ELSE 0 END
                AS raw_score,
                ARRAY_REMOVE(ARRAY[
                    CASE WHEN s.years_since_last_sale >= 10 THEN s.years_since_last_sale::TEXT || ' years since last sale' END,
                    CASE WHEN s.has_retention_permission THEN 'Retention planning application' END,
                    CASE WHEN s.is_derelict_or_vacant THEN 'Listed on Derelict/Vacant Sites Register' END,
                    CASE WHEN s.rented_then_listed_for_sale THEN 'Previously rented, now for sale' END,
                    CASE WHEN s.relisting_count > 2 THEN 'Relisted for sale ' || s.relisting_count || 'x' END,
                    CASE WHEN s.price_drop_pct > 5 THEN 'Asking price reduced by ' || s.price_drop_pct || '%' END
                ], NULL) AS base_key_drivers
            FROM property_propensity_signals s
        ) r
    ) ranked
) s
WHERE s.property_id = p.id;

-- Sanity check
SELECT count(*) FILTER (WHERE percentile_score IS NOT NULL) AS with_percentile,
       count(*) FILTER (WHERE base_key_drivers IS NOT NULL) AS with_base_drivers
FROM properties;
