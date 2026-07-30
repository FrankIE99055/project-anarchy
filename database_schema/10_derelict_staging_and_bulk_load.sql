-- 10_derelict_staging_and_bulk_load.sql
-- ------------------------------------------------------------------
-- Import registru chátrajících/prázdných nemovitostí (bez Owner/Occupier)
-- do `derelict_sites` + propojení s `properties`.
--
-- POSTUP:
-- 1) Spusť KROK 1 (staging tabulka).
-- 2) V Table Editoru nahraj data_pipeline/raw_data/derelict_sites_raw.csv
--    do tabulky `derelict_staging`.
-- 3) Spusť KROK 2 a 3.
-- ------------------------------------------------------------------

-- ============ KROK 1: STAGING TABULKA ============
DROP TABLE IF EXISTS derelict_staging;

CREATE TABLE derelict_staging (
    council TEXT,
    register_ref TEXT,
    address TEXT,
    electoral_area TEXT,
    notice_date DATE,
    entered_date DATE,
    valuation TEXT,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    source_url TEXT
);

-- ============ KROK 2: naplnění derelict_sites ============
-- longitude/latitude u DLR jsou ve skutečnosti ITM (EPSG:2157) metry, ne
-- GPS stupně (hodnoty v řádu stovek tisíc) - poznáme to podle velikosti
-- čísla a použijeme správnou transformaci; u SDCC už jsou to WGS84 stupně.
INSERT INTO derelict_sites (
    council, register_ref, address, electoral_area, notice_date,
    entered_on_register_date, valuation, location, source_url
)
SELECT
    council,
    register_ref,
    address,
    NULLIF(electoral_area, ''),
    notice_date,
    entered_date,
    NULLIF(regexp_replace(valuation, '[^\d.]', '', 'g'), '')::NUMERIC,
    CASE
        WHEN longitude IS NULL OR latitude IS NULL THEN NULL
        WHEN abs(longitude) > 180 OR abs(latitude) > 90
            THEN ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 2157), 4326)::geography
        ELSE ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
    END,
    source_url
FROM derelict_staging
ON CONFLICT (council, register_ref) DO NOTHING;

-- ============ KROK 3: propojení s properties podle nejbližšího bodu ============
-- Nemáme spolehlivý společný klíč (adresy jsou volný text, různý formát) -
-- propojujeme prostorově: najdeme nejbližší nemovitost s GPS polohou do
-- 50 metrů od chátrající nemovitosti. (Skalární korelovaný subquery v SET
-- funguje v UPDATE i s odkazem na target alias `d` - na rozdíl od LATERAL
-- ve FROM, které na `d` odkazovat nemůže.)
UPDATE derelict_sites d
SET property_id = (
    SELECT p.id
    FROM properties p
    WHERE p.location IS NOT NULL
      AND ST_DWithin(p.location, d.location, 50)
    ORDER BY p.location <-> d.location
    LIMIT 1
)
WHERE d.location IS NOT NULL AND d.property_id IS NULL;

-- Výsledné počty
SELECT
    (SELECT count(*) FROM derelict_sites) AS derelict_sites_count,
    (SELECT count(*) FROM derelict_sites WHERE property_id IS NOT NULL) AS linked_to_properties;
