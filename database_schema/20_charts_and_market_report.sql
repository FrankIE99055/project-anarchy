-- 20_charts_and_market_report.sql
-- ------------------------------------------------------------------
-- Podklady pro:
--   1) nový "Charts" tab u jedné nemovitosti (cenová historie, timeline
--      událostí, srovnání s okolím, vývoj skóre v čase)
--   2) čtvrtletní AI market report (celý irský trh) + per-property
--      čtvrtletní regenerace investorského reportu
--
-- Datový podklad pro market report: daft_listings.sold_date/sold_price
-- má 646 360 řádků pokrývajících 2010-01-01 až 2026-03-06 (ověřeno) -
-- dost dlouhá a hustá řada na smysluplný čtvrtletní trend. area_name je
-- z 97 % prázdné, takže krajské rozdělení zatím NENÍ dost spolehlivé -
-- záměrně vynecháno z v1 (nechceme AI nutit komentovat řídká data).
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

-- 1) Historie propensity_score jedné nemovitosti - zapisuje se při
-- KAŽDÉ AI-driven změně skóre (ai_research.py / timeline_analysis.py),
-- ne při hromadném přepočtu (ten mění 988k řádků najednou a nešlo by
-- o smysluplnou "historii" jedné nemovitosti, jen o šum).
CREATE TABLE IF NOT EXISTS property_score_history (
    id BIGSERIAL PRIMARY KEY,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    propensity_score NUMERIC NOT NULL,
    reason TEXT,
    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS property_score_history_property_id_idx
    ON property_score_history (property_id, recorded_at);

-- 2) Čtvrtletní statistiky trhu z Daft.ie prodejů - MATERIALIZOVANÁ
-- tabulka (ne live view - stejný důvod jako analytics_summary: agregace
-- přes 663k řádků by přes PostgREST spolehlivě narazila na statement
-- timeout). Přepočítá se ručně (re-run tohoto INSERTu) když chceme
-- osvěžit o nové čtvrtletí.
CREATE TABLE IF NOT EXISTS daft_quarterly_stats (
    year INT NOT NULL,
    quarter INT NOT NULL,
    sold_count INT NOT NULL,
    avg_sold_price NUMERIC,
    median_sold_price NUMERIC,
    PRIMARY KEY (year, quarter)
);

TRUNCATE daft_quarterly_stats;
INSERT INTO daft_quarterly_stats (year, quarter, sold_count, avg_sold_price, median_sold_price)
SELECT
    EXTRACT(YEAR FROM sold_date)::INT AS year,
    EXTRACT(QUARTER FROM sold_date)::INT AS quarter,
    count(*) AS sold_count,
    round(avg(sold_price)::numeric, 2) AS avg_sold_price,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY sold_price)::numeric, 2) AS median_sold_price
FROM daft_listings
WHERE sold_date IS NOT NULL AND sold_price IS NOT NULL AND sold_price > 0
GROUP BY 1, 2
ORDER BY 1, 2;

-- 3) Cache pro AI-generovaný čtvrtletní market report (1 řádek na
-- kalendářní čtvrtletí) - stejný "generuj a cachuj" vzor jako
-- ai_research_findings/ai_timeline_assessments.
CREATE TABLE IF NOT EXISTS market_report_snapshots (
    id BIGSERIAL PRIMARY KEY,
    year INT NOT NULL,
    quarter INT NOT NULL,
    market_overview TEXT,
    trend_analysis TEXT,
    risk_assessment TEXT,
    generated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (year, quarter)
);

-- 4) Funkce pro "srovnání s okolím" (Charts tab) - průměrné skóre
-- nemovitostí v okruhu `radius_m` metrů kolem dané nemovitosti.
-- Využívá GIST index na properties.location (ST_DWithin), takže i na
-- 988k řádcích je to rychlé (index radius search, ne full scan).
CREATE OR REPLACE FUNCTION nearby_area_stats(target_property_id UUID, radius_m INT DEFAULT 5000)
RETURNS TABLE(avg_score NUMERIC, avg_last_sale_price NUMERIC, property_count INT) AS $$
    SELECT
        round(avg(p2.propensity_score)::numeric, 1),
        round(avg(sh.price)::numeric, 2),
        count(DISTINCT p2.id)::INT
    FROM properties p1
    JOIN properties p2
        ON p2.id <> p1.id
        AND p2.location IS NOT NULL
        AND ST_DWithin(p1.location, p2.location, radius_m)
    LEFT JOIN LATERAL (
        SELECT price FROM sales_history WHERE property_id = p2.id
        ORDER BY date_of_sale DESC LIMIT 1
    ) sh ON true
    WHERE p1.id = target_property_id AND p1.location IS NOT NULL;
$$ LANGUAGE sql STABLE;

GRANT EXECUTE ON FUNCTION nearby_area_stats(UUID, INT) TO anon, authenticated;
