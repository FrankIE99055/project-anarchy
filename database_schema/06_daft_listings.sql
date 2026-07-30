-- 06_daft_listings.sql
-- ------------------------------------------------------------------
-- Tabulka pro scrapnutá data z Daft.ie (druhý Supabase projekt uživatele,
-- staženo přes REST API do CSV a odsud hromadně naimportováno).
--
-- Tento dataset je obrovský přínos oproti veřejným zdrojům: obsahuje
-- BER rating PŘÍMO navázaný na konkrétní inzerát/adresu (na rozdíl od
-- anonymizovaného SEAI BER Research Tool datasetu) a přímé GPS souřadnice
-- (bez nutnosti převodu z ITM).
-- ------------------------------------------------------------------

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
