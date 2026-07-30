-- 16_townland_geocoding.sql
-- ------------------------------------------------------------------
-- Doplnění GPS souřadnic pro nemovitosti, které je zatím nemají.
--
-- 790 955 z 987 948 nemovitostí (PPR-only, bez Eircode/Daft shody) nemá
-- location - hodně irských venkovských adres v PPR je zapsáno jen jako
-- "TOWNLAND, PARISH" (např. "ROCHESTOWN, CLONGEEN") bez Eircode a bez GPS.
--
-- Přesné geokódování celé adresy přes Nominatim/Google by u ~790k adres
-- buď trvalo přes týden (Nominatim limit 1 req/s + zákaz hromadného
-- použití zdarma), nebo stálo peníze (placené API). Místo toho použijeme
-- Tailte Éireann "Townlands - National Placenames Gazetteer" (CC BY 4.0,
-- 50 380 townlandů s bodovou souřadnicí) - když adresa nemovitosti
-- obsahuje název townlandu, přiřadíme jí souřadnici středu toho
-- townlandu. Je to JEN PŘIBLIŽNÉ umístění (townland může mít stovky
-- hektarů), ale pro zobrazení na mapě je to zásadně lepší než nic.
--
-- Kraj (county) z ppr_staging (pořád v DB, viz 03_staging_and_bulk_load.sql)
-- se používá k rozlišení stejnojmenných townlandů v různých krajích.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

-- ============ KROK 1: staging tabulka pro gazetteer CSV ============
DROP TABLE IF EXISTS townland_staging;
CREATE TABLE townland_staging (
    english_name TEXT,
    county TEXT,
    itm_e INTEGER,
    itm_n INTEGER
);

-- Import CSV do staging
\copy townland_staging FROM 'data_pipeline/raw_data/townlands_raw.csv' WITH (FORMAT csv, HEADER true)

-- ============ KROK 2: produkční tabulka s geography location ============
DROP TABLE IF EXISTS townland_gazetteer;
CREATE TABLE townland_gazetteer (
    id BIGSERIAL PRIMARY KEY,
    english_name TEXT NOT NULL,
    county TEXT,
    location geography(POINT, 4326)
);

INSERT INTO townland_gazetteer (english_name, county, location)
SELECT
    UPPER(TRIM(english_name)),
    UPPER(TRIM(county)),
    ST_Transform(ST_SetSRID(ST_MakePoint(itm_e, itm_n), 2157), 4326)::geography
FROM townland_staging
WHERE itm_e IS NOT NULL AND itm_n IS NOT NULL AND english_name IS NOT NULL;

CREATE INDEX townland_gazetteer_name_county_idx
    ON townland_gazetteer (english_name, county);

-- ============ KROK 3: backfill properties.location ============
-- Pro každou nemovitost bez location: rozdělíme adresu na čárkami oddělené
-- kousky, zkusíme každý kousek (trim, upper) najít přesně mezi townlandy
-- ve stejném kraji (county z ppr_staging podle shodné adresy). Pokud
-- najdeme víc shod, vezmeme první (DISTINCT ON) - je to aproximace, ne
-- přesná GPS poloha.
WITH candidates AS (
    SELECT DISTINCT ON (p.id)
        p.id AS property_id,
        g.location
    FROM properties p
    JOIN ppr_staging s ON s.address = p.address
    CROSS JOIN LATERAL unnest(string_to_array(p.address, ',')) AS token(value)
    JOIN townland_gazetteer g
        ON g.english_name = UPPER(TRIM(token.value))
        AND g.county = UPPER(TRIM(s.county))
    WHERE p.location IS NULL
    ORDER BY p.id, g.id
)
UPDATE properties p
SET location = c.location,
    last_updated = CURRENT_TIMESTAMP
FROM candidates c
WHERE c.property_id = p.id;

-- Kontrola dopadu
SELECT
    count(*) AS total_properties,
    count(*) FILTER (WHERE location IS NOT NULL) AS with_location
FROM properties;
