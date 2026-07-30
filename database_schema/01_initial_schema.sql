-- Povolení geografického rozšíření PostGIS pro práci s mapami
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Hlavní tabulka pro nemovitosti - středobod všeho (Eircode)
CREATE TABLE properties (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    eircode VARCHAR(10) UNIQUE, -- Unikátní identifikátor v Irsku
    address TEXT NOT NULL,
    location geography(POINT, 4326), -- GPS souřadnice pro zobrazení na heatmapě
    propensity_score NUMERIC(5,2) DEFAULT 0.00, -- AI skóre prodeje (0 až 100 %)
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Historie prodejů (data z Property Price Register - PPR)
CREATE TABLE sales_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    date_of_sale DATE NOT NULL,
    price NUMERIC(15,2) NOT NULL,
    description TEXT, -- např. "Second-Hand Dwelling House"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Stavební povolení (Planning Permissions z data.gov.ie)
CREATE TABLE planning_permissions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    application_number VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    decision_date DATE,
    category VARCHAR(50), -- Sem budeme ukládat klíčová slova jako 'Retention', 'Extension'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Energetické štítky (Building Energy Rating - BER)
CREATE TABLE property_ber (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    mprn VARCHAR(20), -- Číslo elektroměru, pokud je dostupné
    ber_rating VARCHAR(5), -- např. A1, C3, G
    date_of_issue DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Vytvoření indexů pro bleskurychlé vyhledávání
-- GIST index je zásadní pro PostGIS, aby heatmapa načítala domy bleskově i pro celé město
CREATE INDEX properties_location_idx ON properties USING GIST (location);
CREATE INDEX properties_eircode_idx ON properties(eircode);
CREATE INDEX sales_history_property_id_idx ON sales_history(property_id);
