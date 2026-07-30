-- 18_map_bucket_rank_materialized.sql
-- ------------------------------------------------------------------
-- properties_map z 17_map_stratified_sample.sql počítal ROW_NUMBER() OVER
-- (PARTITION BY ...) NAŽIVO při každém dotazu - přes 423 811 řádků to
-- narazilo na PostgRESTův statement timeout (stejný problém jako dřív
-- u property_propensity_score v1, viz 11_propensity_score.sql).
--
-- Řešení: stejný vzor jako u skóre - spočítat bucket_rank JEDNOU touhle
-- migrací a uložit ho přímo na properties, s indexem. /properties/map
-- pak dělá jen rychlý indexovaný SELECT, žádný live window function.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

ALTER TABLE properties ADD COLUMN IF NOT EXISTS map_bucket_rank INT;

WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY width_bucket(propensity_score, 0, 100, 10)
            ORDER BY id
        ) AS bucket_rank
    FROM properties
    WHERE location IS NOT NULL
)
UPDATE properties p
SET map_bucket_rank = r.bucket_rank
FROM ranked r
WHERE r.id = p.id;

CREATE INDEX IF NOT EXISTS properties_map_bucket_rank_idx
    ON properties (map_bucket_rank)
    WHERE location IS NOT NULL;

-- properties_map: teď jen jednoduchá projekce, žádný live window function
CREATE OR REPLACE VIEW properties_map AS
SELECT
    id,
    address,
    eircode,
    propensity_score,
    key_drivers,
    map_bucket_rank AS bucket_rank,
    ST_Y(location::geometry) AS latitude,
    ST_X(location::geometry) AS longitude
FROM properties
WHERE location IS NOT NULL;

-- Kontrola
SELECT count(*) FILTER (WHERE map_bucket_rank IS NOT NULL) AS with_bucket_rank
FROM properties;
