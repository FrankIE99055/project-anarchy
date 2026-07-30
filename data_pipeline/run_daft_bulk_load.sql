-- Spustit přes: psql -f run_daft_bulk_load.sql
-- Předpokládá, že `daft_staging` už je naplněná (viz psql_import_daft.sql)
-- a `properties` tabulka existuje. Vytvoří `daft_listings` (pokud ještě
-- neexistuje) a naplní ji + propojí s properties.

SET statement_timeout TO 0;

-- KROK 0: tabulka daft_listings (idempotentní, viz 06_daft_listings.sql)
CREATE TABLE IF NOT EXISTS daft_listings (
    id BIGINT PRIMARY KEY,
    property_id UUID REFERENCES properties(id) ON DELETE SET NULL,
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
    location geography(POINT, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS daft_listings_location_idx ON daft_listings USING GIST (location);
CREATE INDEX IF NOT EXISTS daft_listings_ber_rating_idx ON daft_listings (ber_rating);
CREATE INDEX IF NOT EXISTS daft_listings_property_id_idx ON daft_listings (property_id);
CREATE INDEX IF NOT EXISTS daft_listings_eircode_idx ON daft_listings (eircode);

-- KROK 2: naplnění daft_listings z daft_staging
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

-- KROK 3: propojení daft_listings <-> properties podle Eircode
UPDATE daft_listings d
SET property_id = p.id
FROM properties p
WHERE d.eircode IS NOT NULL AND d.eircode <> ''
  AND p.eircode = d.eircode
  AND d.property_id IS NULL;

-- KROK 4: obohacení properties o chybějící Eircode/GPS z Daftu
UPDATE properties p
SET eircode = d.eircode,
    location = COALESCE(p.location, d.location)
FROM daft_listings d
WHERE p.eircode IS NULL
  AND d.eircode IS NOT NULL AND d.eircode <> ''
  AND p.address = d.address;

UPDATE properties p
SET location = d.location
FROM daft_listings d
WHERE p.location IS NULL
  AND d.location IS NOT NULL
  AND d.property_id = p.id;

-- Výsledné počty
SELECT
    (SELECT count(*) FROM daft_listings) AS daft_listings_count,
    (SELECT count(*) FROM daft_listings WHERE property_id IS NOT NULL) AS linked_to_properties,
    (SELECT count(*) FROM properties WHERE location IS NOT NULL) AS properties_with_location;
