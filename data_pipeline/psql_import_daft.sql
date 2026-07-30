-- Spustit přes: psql -f psql_import_daft.sql
-- Vytvoří (znovu) staging tabulku a rovnou do ní nahraje CSV nativním
-- COPY protokolem (mnohem rychlejší než webové UI).

\encoding UTF8
SET statement_timeout TO 0;

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

\copy daft_staging FROM 'D:/Project Anarchy/data_pipeline/raw_data/daft_clean.csv' WITH (FORMAT csv, HEADER true);

SELECT count(*) AS imported_rows FROM daft_staging;
