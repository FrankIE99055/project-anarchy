-- 09_derelict_sites.sql
-- ------------------------------------------------------------------
-- Registr chátrajících/prázdných nemovitostí (Derelict Sites Act 1990 /
-- Urban Regeneration & Housing Act 2015). Zdrojová data z jednotlivých
-- County/City Councils (data.gov.ie) OBSAHUJÍ pole Owner/Occupier -
-- ta se ZÁMĚRNĚ nikdy nestahují ani neukládají (viz poznámka v
-- download_derelict_sites.py). Ukládáme jen informace o nemovitosti.
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS derelict_sites (
    id BIGSERIAL PRIMARY KEY,
    property_id UUID REFERENCES properties(id) ON DELETE SET NULL,
    council TEXT NOT NULL,
    register_ref TEXT,
    address TEXT,
    electoral_area TEXT,
    notice_date DATE,
    entered_on_register_date DATE,
    valuation NUMERIC,
    location geography(POINT, 4326),
    source_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (council, register_ref)
);

CREATE INDEX IF NOT EXISTS derelict_sites_location_idx ON derelict_sites USING GIST (location);
CREATE INDEX IF NOT EXISTS derelict_sites_property_id_idx ON derelict_sites (property_id);
CREATE INDEX IF NOT EXISTS derelict_sites_address_idx ON derelict_sites (address);
