-- 22_search_trigram_index.sql
-- ------------------------------------------------------------------
-- Bug: GET /properties?q=... (textové vyhledávání adresy/Eircode)
-- padalo na "statement timeout" (57014) - ILIKE '%text%' se dřív dělal
-- jako sekvenční sken celé properties tabulky (teď 1.43M řádků po OSM
-- importu, žádný běžný btree index nejde použít na "obsahuje" hledání
-- s divokou kartou na začátku).
--
-- Řešení: trigram GIN index (pg_trgm) na address i eircode - Postgres
-- pak umí ILIKE '%text%' vyhledávat přes index (bitmap index scan),
-- místo aby procházel každý řádek.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS properties_address_trgm_idx
    ON properties USING GIN (address gin_trgm_ops);

CREATE INDEX IF NOT EXISTS properties_eircode_trgm_idx
    ON properties USING GIN (eircode gin_trgm_ops);

-- Sanity check - mělo by proběhnout rychle a použít Bitmap Index Scan,
-- ne Seq Scan.
EXPLAIN ANALYZE
SELECT id, address, eircode, propensity_score
FROM properties
WHERE address ILIKE '%Dublin%' OR eircode ILIKE '%Dublin%'
ORDER BY propensity_score DESC
LIMIT 25;
