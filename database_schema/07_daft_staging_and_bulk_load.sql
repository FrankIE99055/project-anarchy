-- 07_daft_staging_and_bulk_load.sql
-- ------------------------------------------------------------------
-- Import scrapnutých dat z Daft.ie (data_pipeline/raw_data/daft_clean.csv)
-- do tabulky `daft_listings` + propojení s `properties` a obohacení
-- o Eircode/GPS polohu tam, kde ještě chyběly.
--
-- POSTUP:
-- 1) Spusť KROK 1 (staging tabulka) a KROK 0 (tabulka daft_listings,
--    pokud jsi ještě nespustil 06_daft_listings.sql).
-- 2) V Table Editoru nahraj data_pipeline/raw_data/daft_clean.csv
--    do tabulky `daft_staging` (Insert -> Import data from CSV).
-- 3) Spusť KROK 2, 3 a 4.
-- ------------------------------------------------------------------

-- ============ KROK 1: STAGING TABULKA (spustit PŘED importem CSV) ============
DROP TABLE IF EXISTS daft_staging;

CREATE TABLE daft_staging (
    id BIGINT,
    url TEXT,
    address TEXT,
    eircode TEXT,
    price NUMERIC(15,2),
    sold_price NUMERIC(15,2),
    sold_date DATE,
    bedrooms INTEGER,
    bathrooms INTEGER,
    property_type TEXT,
    category TEXT,
    listing_type TEXT,
    floor_area_sqm NUMERIC,
    date_of_construction TEXT,
    area_name TEXT,
    description TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    ber_code TEXT,
    ber_rating TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

-- ============ KROK 2: naplnění daft_listings (spustit PO importu CSV) ============
INSERT INTO daft_listings (
    id, url, address, eircode, price, sold_price, sold_date, bedrooms,
    bathrooms, property_type, category, listing_type, floor_area_sqm,
    date_of_construction, area_name, description, scraped_at, ber_code,
    ber_rating, location
)
SELECT
    id, url, address, NULLIF(eircode, ''), price, sold_price, sold_date,
    bedrooms, bathrooms, property_type, category, listing_type,
    floor_area_sqm, date_of_construction, area_name, description,
    scraped_at, ber_code, ber_rating,
    CASE
        WHEN latitude IS NOT NULL AND longitude IS NOT NULL
        THEN ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        ELSE NULL
    END
FROM daft_staging
ON CONFLICT (id) DO NOTHING;

-- ============ KROK 3: propojení daft_listings <-> properties podle Eircode ============
-- Eircode z titulku Daft inzerátu je spolehlivější klíč než textová shoda
-- adres (Daft a PPR/Planning formátují adresy jinak).
UPDATE daft_listings d
SET property_id = p.id
FROM properties p
WHERE d.eircode IS NOT NULL AND d.eircode <> ''
  AND p.eircode = d.eircode
  AND d.property_id IS NULL;

-- ============ KROK 4: obohacení properties o chybějící Eircode/GPS z Daftu ============
-- Pro nemovitosti z PPR, které eircode nemají, ale mají shodnou adresu
-- v Daft datech s vyplněným Eircode, doplníme eircode i polohu.
UPDATE properties p
SET eircode = d.eircode,
    location = COALESCE(p.location, d.location)
FROM daft_listings d
WHERE p.eircode IS NULL
  AND d.eircode IS NOT NULL AND d.eircode <> ''
  AND p.address = d.address;

-- Doplnění polohy k nemovitostem, které už Eircode mají (přes KROK 3 shodu),
-- ale zatím nemají GPS location (např. založené jen z PPR).
UPDATE properties p
SET location = d.location
FROM daft_listings d
WHERE p.location IS NULL
  AND d.location IS NOT NULL
  AND d.property_id = p.id;

-- ============ KROK 5 (volitelné): úklid staging tabulky ============
-- DROP TABLE IF EXISTS daft_staging;
