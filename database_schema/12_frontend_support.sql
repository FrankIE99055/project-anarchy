-- 12_frontend_support.sql
-- ------------------------------------------------------------------
-- Podpůrné DB objekty pro frontend/API:
--   properties_map     - view s lat/lng jako čísla (pro mapu, PostGIS
--                         geography se přes REST API nedá pohodlně
--                         parsovat na frontendu)
--   analytics_summary  - PŘEDPOČÍTANÁ (materializovaná) souhrnná
--                         statistika pro dashboard, aby frontend
--                         nemusel agregovat přes ~1M řádků při
--                         každém requestu (to by narazilo na stejný
--                         timeout jako property_propensity_score view)
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

-- properties_map: jen nemovitosti s GPS polohou, lat/lng jako float
CREATE OR REPLACE VIEW properties_map AS
SELECT
    id,
    address,
    eircode,
    propensity_score,
    key_drivers,
    ST_Y(location::geometry) AS latitude,
    ST_X(location::geometry) AS longitude
FROM properties
WHERE location IS NOT NULL;

-- Index pro rychlé WHERE location IS NOT NULL + řazení podle skóre
CREATE INDEX IF NOT EXISTS properties_location_not_null_score_idx
    ON properties (propensity_score DESC)
    WHERE location IS NOT NULL;

-- analytics_summary: snapshot tabulka (1 řádek), přepočítává se ručně
-- skriptem/SQL po každém přepočtu propensity_score (viz 11_propensity_score.sql)
CREATE TABLE IF NOT EXISTS analytics_summary (
    id INT PRIMARY KEY DEFAULT 1,
    total_properties INT,
    properties_with_location INT,
    avg_score NUMERIC,
    score_bucket_0_10 INT,
    score_bucket_10_20 INT,
    score_bucket_20_30 INT,
    score_bucket_30_40 INT,
    score_bucket_40_50 INT,
    score_bucket_50_60 INT,
    score_bucket_60_70 INT,
    score_bucket_70_80 INT,
    score_bucket_80_90 INT,
    score_bucket_90_100 INT,
    with_retention INT,
    with_derelict_or_vacant INT,
    with_daft_signal INT,
    total_sales_history INT,
    total_planning_permissions INT,
    total_derelict_sites INT,
    total_daft_listings INT,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT analytics_summary_single_row CHECK (id = 1)
);

INSERT INTO analytics_summary (
    id, total_properties, properties_with_location, avg_score,
    score_bucket_0_10, score_bucket_10_20, score_bucket_20_30, score_bucket_30_40,
    score_bucket_40_50, score_bucket_50_60, score_bucket_60_70, score_bucket_70_80,
    score_bucket_80_90, score_bucket_90_100,
    with_retention, with_derelict_or_vacant, with_daft_signal,
    total_sales_history, total_planning_permissions, total_derelict_sites, total_daft_listings
)
SELECT
    1,
    (SELECT count(*) FROM properties),
    (SELECT count(*) FROM properties WHERE location IS NOT NULL),
    (SELECT round(avg(propensity_score), 2) FROM properties),
    (SELECT count(*) FROM properties WHERE propensity_score >= 0 AND propensity_score < 10),
    (SELECT count(*) FROM properties WHERE propensity_score >= 10 AND propensity_score < 20),
    (SELECT count(*) FROM properties WHERE propensity_score >= 20 AND propensity_score < 30),
    (SELECT count(*) FROM properties WHERE propensity_score >= 30 AND propensity_score < 40),
    (SELECT count(*) FROM properties WHERE propensity_score >= 40 AND propensity_score < 50),
    (SELECT count(*) FROM properties WHERE propensity_score >= 50 AND propensity_score < 60),
    (SELECT count(*) FROM properties WHERE propensity_score >= 60 AND propensity_score < 70),
    (SELECT count(*) FROM properties WHERE propensity_score >= 70 AND propensity_score < 80),
    (SELECT count(*) FROM properties WHERE propensity_score >= 80 AND propensity_score < 90),
    (SELECT count(*) FROM properties WHERE propensity_score >= 90),
    (SELECT count(*) FROM properties WHERE 'Retention planning application' = ANY(key_drivers)),
    (SELECT count(*) FROM properties WHERE 'Listed on Derelict/Vacant Sites Register' = ANY(key_drivers)),
    (SELECT count(*) FROM properties WHERE key_drivers IS NOT NULL AND array_length(key_drivers, 1) > 0
        AND EXISTS (SELECT 1 FROM unnest(key_drivers) d WHERE d ILIKE '%relisted%' OR d ILIKE '%rented%' OR d ILIKE '%asking price%')),
    (SELECT count(*) FROM sales_history),
    (SELECT count(*) FROM planning_permissions),
    (SELECT count(*) FROM derelict_sites),
    (SELECT count(*) FROM daft_listings)
ON CONFLICT (id) DO UPDATE SET
    total_properties = EXCLUDED.total_properties,
    properties_with_location = EXCLUDED.properties_with_location,
    avg_score = EXCLUDED.avg_score,
    score_bucket_0_10 = EXCLUDED.score_bucket_0_10,
    score_bucket_10_20 = EXCLUDED.score_bucket_10_20,
    score_bucket_20_30 = EXCLUDED.score_bucket_20_30,
    score_bucket_30_40 = EXCLUDED.score_bucket_30_40,
    score_bucket_40_50 = EXCLUDED.score_bucket_40_50,
    score_bucket_50_60 = EXCLUDED.score_bucket_50_60,
    score_bucket_60_70 = EXCLUDED.score_bucket_60_70,
    score_bucket_70_80 = EXCLUDED.score_bucket_70_80,
    score_bucket_80_90 = EXCLUDED.score_bucket_80_90,
    score_bucket_90_100 = EXCLUDED.score_bucket_90_100,
    with_retention = EXCLUDED.with_retention,
    with_derelict_or_vacant = EXCLUDED.with_derelict_or_vacant,
    with_daft_signal = EXCLUDED.with_daft_signal,
    total_sales_history = EXCLUDED.total_sales_history,
    total_planning_permissions = EXCLUDED.total_planning_permissions,
    total_derelict_sites = EXCLUDED.total_derelict_sites,
    total_daft_listings = EXCLUDED.total_daft_listings,
    computed_at = CURRENT_TIMESTAMP;

SELECT * FROM analytics_summary;
