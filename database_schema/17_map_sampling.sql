-- 17_map_sampling.sql
-- ------------------------------------------------------------------
-- Oprava mapy: /properties/map řadil podle propensity_score DESC a bral
-- jen prvních `limit` (max 5000) záznamů. Po percentilovém přepočtu
-- skóre (13/14_propensity_score_v2.sql) vzniknou obrovské "plošiny"
-- nemovitostí se STEJNÝM skóre (164 557 na ~80.7, 26 157 na ~97.4) -
-- takže "top 1500 podle skóre" jsou teď VŠECHNY z jedné plošiny a mapa
-- vykreslí samé červené tečky (žádná barevná ani geografická rozmanitost).
--
-- Oprava: mapa má ukazovat NÁHODNÝ geografický vzorek (obarvený podle
-- skóre), ne "top N podle skóre" - PostgREST neumí ORDER BY random(),
-- proto přidáváme stabilní předpočítaný sloupec map_sort_key = random(),
-- podle kterého se dá přes PostgREST řadit normálně.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

ALTER TABLE properties ADD COLUMN IF NOT EXISTS map_sort_key DOUBLE PRECISION;
ALTER TABLE properties ALTER COLUMN map_sort_key SET DEFAULT random();

UPDATE properties SET map_sort_key = random() WHERE map_sort_key IS NULL;

CREATE INDEX IF NOT EXISTS properties_map_sort_key_idx
    ON properties (map_sort_key)
    WHERE location IS NOT NULL;

CREATE OR REPLACE VIEW properties_map AS
SELECT
    id,
    address,
    eircode,
    propensity_score,
    key_drivers,
    map_sort_key,
    ST_Y(location::geometry) AS latitude,
    ST_X(location::geometry) AS longitude
FROM properties
WHERE location IS NOT NULL;
