-- 17_map_stratified_sample.sql
-- ------------------------------------------------------------------
-- OPRAVA: /properties/map řadil podle skóre sestupně a bral jen top N.
-- Po percentilovém přepočtu (v13/v15) existují obří "plošiny" nemovitostí
-- se STEJNÝM skóre (26 177 nemovitostí přesně na 97.4, 164 558 přesně na
-- 80.7) - takže "top 1500 podle skóre" vrátilo 1500 nemovitostí se
-- skoro identickým skóre => všechny body na mapě vyšly červené.
--
-- Řešení: DETERMINISTICKÝ stratifikovaný výběr (ne náhodný) - pro každý
-- decil skóre (0-10, 10-20, ..., 90-100) očíslujeme nemovitosti podle
-- `id` (bucket_rank) a vrátíme jen prvních N z KAŽDÉHO decilu. Tím mapa
-- vždy zobrazí zastoupení celé barevné škály (červená/oranžová/žlutá/šedá),
-- ne jen vršek jedné plošiny. Výsledek je opakovatelný (stejný běh dá
-- pokaždé stejné nemovitosti), ne náhodný.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

CREATE OR REPLACE VIEW properties_map AS
SELECT
    id,
    address,
    eircode,
    propensity_score,
    key_drivers,
    ST_Y(location::geometry) AS latitude,
    ST_X(location::geometry) AS longitude,
    ROW_NUMBER() OVER (
        PARTITION BY width_bucket(propensity_score, 0, 100, 10)
        ORDER BY id
    ) AS bucket_rank
FROM properties
WHERE location IS NOT NULL;

CREATE INDEX IF NOT EXISTS properties_location_not_null_score_idx
    ON properties (propensity_score DESC)
    WHERE location IS NOT NULL;
