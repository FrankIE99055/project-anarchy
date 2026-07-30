-- 23_duplicate_photo.sql
-- ------------------------------------------------------------------
-- Na žádost uživatele: nová tabulka `duplicate_photo`, která duplikuje
-- nemovitosti z Derelict/Vacant registru napárované na Daft.ie inzerát,
-- doplněná o skutečné URL fotek stažené přímo ze zdrojového Daft
-- Supabase projektu (viz data_pipeline/build_duplicate_photo_export.py -
-- naše vlastní `daft_listings` fotky neobsahuje, byly při importu
-- záměrně vynechány).
--
-- POZOR: jen 8 ze 114 inzerátů mělo v Daft datech nějaké fotky (`images`
-- pole bylo u drtivé většiny prázdné - buď scraper fotky nezachytil,
-- nebo inzerát žádné neměl). photo_urls je tedy u většiny řádků prázdné
-- pole, ne chyba.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

DROP TABLE IF EXISTS duplicate_photo_staging;

CREATE TABLE duplicate_photo_staging (
    property_id UUID,
    address TEXT,
    eircode TEXT,
    propensity_score NUMERIC,
    key_drivers TEXT,
    daft_id BIGINT,
    daft_url TEXT,
    photo_urls TEXT
);

\copy duplicate_photo_staging FROM 'D:/Project Anarchy/data_pipeline/raw_data/duplicate_photo_raw.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS duplicate_photo;

CREATE TABLE duplicate_photo (
    id BIGSERIAL PRIMARY KEY,
    property_id UUID,
    address TEXT,
    eircode TEXT,
    propensity_score NUMERIC,
    key_drivers TEXT,
    daft_id BIGINT,
    daft_url TEXT,
    photo_urls TEXT[],
    photo_count INT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO duplicate_photo (property_id, address, eircode, propensity_score, key_drivers, daft_id, daft_url, photo_urls, photo_count)
SELECT
    property_id,
    address,
    eircode,
    propensity_score,
    key_drivers,
    daft_id,
    daft_url,
    CASE WHEN photo_urls IS NULL OR photo_urls = '' THEN ARRAY[]::TEXT[] ELSE string_to_array(photo_urls, '|') END,
    CASE WHEN photo_urls IS NULL OR photo_urls = '' THEN 0 ELSE array_length(string_to_array(photo_urls, '|'), 1) END
FROM duplicate_photo_staging;

-- Sanity check
SELECT count(*) AS total_rows,
       count(*) FILTER (WHERE photo_count > 0) AS rows_with_photos,
       sum(photo_count) AS total_photo_urls
FROM duplicate_photo;
