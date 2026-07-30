-- 13_propensity_score_v2.sql
-- ------------------------------------------------------------------
-- Propensity Score v2 - PERCENTILE-BASED skóre místo prostého sčítání bodů.
--
-- PROBLÉM ve v1 (11_propensity_score.sql): body za jednotlivé signály se
-- prostě sečetly a ořízly na 100. V praxi se ale silné signály (roky od
-- prodeje + retention + derelict + Daft...) skoro nikdy nesejdou u jedné
-- nemovitosti najednou, takže reálné maximum bylo jen ~55 a 40-50 bylo
-- skoro prázdné pásmo (jen 59 nemovitostí z 988k). Skóre tak nebylo
-- realisticky rozprostřené po celé škále 0-100.
--
-- ŘEŠENÍ v2: surové (neomezené) skóre ze stejných signálů se použije jen
-- k SEŘAZENÍ nemovitostí vůči sobě navzájem (PERCENT_RANK), výsledné
-- skóre 0-100 je tedy relativní percentil v rámci celé populace - to je
-- standardní přístup u "propensity/lead scoring" modelů a zaručuje
-- rovnoměrné, realistické rozprostření po celé škále.
--
-- Navíc přidává prostor pro budoucí AI-research signál (viz
-- ai_signal_score/ai_signal_note na properties) - AI, která pro
-- konkrétní nemovitost dohledá veřejné události (inzerát, zpráva,
-- úřední oznámení), může přičíst bonus body nad rámec percentilu.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

-- Sloupce pro transparentnost + budoucí AI-research vrstvu
ALTER TABLE properties ADD COLUMN IF NOT EXISTS raw_signal_score NUMERIC;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS ai_signal_score NUMERIC DEFAULT 0;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS ai_signal_note TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS ai_signal_researched_at TIMESTAMPTZ;

CREATE OR REPLACE VIEW property_propensity_score_v2 AS
WITH raw AS (
    SELECT
        s.property_id,
        s.address,
        s.eircode,
        -- Surové (neomezené) heuristické skóre - používá se JEN k relativnímu
        -- seřazení nemovitostí mezi sebou (viz PERCENT_RANK níže), není to
        -- finální skóre samo o sobě.
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
),
ranked AS (
    SELECT
        r.*,
        -- Relativní percentil (0-100) v rámci celé populace nemovitostí
        PERCENT_RANK() OVER (ORDER BY r.raw_score) * 100 AS percentile_score
    FROM raw r
)
SELECT
    ranked.property_id,
    ranked.address,
    ranked.eircode,
    ranked.raw_score,
    ranked.percentile_score,
    LEAST(100, ROUND((ranked.percentile_score + COALESCE(p.ai_signal_score, 0))::numeric, 1)) AS propensity_score,
    CASE
        WHEN p.ai_signal_note IS NOT NULL AND p.ai_signal_score > 0
            THEN ranked.base_key_drivers || ARRAY[p.ai_signal_note]
        ELSE ranked.base_key_drivers
    END AS key_drivers
FROM ranked
JOIN properties p ON p.id = ranked.property_id;

-- Promítnutí zpět do properties (stejný vzor jako v1 - materializace kvůli
-- rychlosti čtení přes Supabase REST API)
UPDATE properties p
SET propensity_score = s.propensity_score,
    raw_signal_score = s.raw_score,
    key_drivers = s.key_drivers,
    last_updated = CURRENT_TIMESTAMP
FROM property_propensity_score_v2 s
WHERE s.property_id = p.id;

-- Rychlá kontrola nové distribuce
SELECT
    width_bucket(propensity_score, 0, 100, 10) AS bucket,
    count(*),
    round(min(propensity_score)::numeric, 1) AS min_s,
    round(max(propensity_score)::numeric, 1) AS max_s
FROM properties
GROUP BY 1
ORDER BY 1;

SELECT
    round(avg(propensity_score)::numeric, 2) AS avg,
    round(stddev(propensity_score)::numeric, 2) AS stddev,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY propensity_score)::numeric, 2) AS median,
    round(percentile_cont(0.95) WITHIN GROUP (ORDER BY propensity_score)::numeric, 2) AS p95,
    max(propensity_score) AS mx
FROM properties;
