-- Pomocný skript: znovu vytvoří planning_staging (prázdnou), naimportuje
-- CSV a spustí KROK 2/2b/3 v jednom běhu (bez opětovného DROPnutí).

SET statement_timeout TO 0;

DROP TABLE IF EXISTS planning_staging;

CREATE TABLE planning_staging (
    application_number TEXT,
    planning_authority TEXT,
    development_description TEXT,
    development_address TEXT,
    development_postcode TEXT,
    application_type TEXT,
    application_status TEXT,
    decision TEXT,
    land_use_code TEXT,
    area_of_site NUMERIC,
    num_residential_units NUMERIC,
    one_off_house TEXT,
    floor_area NUMERIC,
    received_date DATE,
    decision_date DATE,
    grant_date DATE,
    expiry_date DATE,
    itm_easting DOUBLE PRECISION,
    itm_northing DOUBLE PRECISION
);

\copy planning_staging FROM 'D:/Project Anarchy/data_pipeline/raw_data/planning_clean.csv' WITH (FORMAT csv, HEADER true);

-- KROK 2
INSERT INTO properties (eircode, address, location)
SELECT DISTINCT ON (development_address)
       NULL,
       development_address,
       CASE
           WHEN itm_easting IS NOT NULL AND itm_northing IS NOT NULL
           THEN ST_Transform(ST_SetSRID(ST_MakePoint(itm_easting, itm_northing), 2157), 4326)::geography
           ELSE NULL
       END
FROM planning_staging
WHERE development_address IS NOT NULL AND development_address <> ''
ON CONFLICT DO NOTHING;

-- KROK 2b
UPDATE properties p
SET location = sub.location
FROM (
    SELECT DISTINCT ON (development_address)
           development_address,
           ST_Transform(ST_SetSRID(ST_MakePoint(itm_easting, itm_northing), 2157), 4326)::geography AS location
    FROM planning_staging
    WHERE itm_easting IS NOT NULL AND itm_northing IS NOT NULL
) sub
WHERE p.address = sub.development_address AND p.location IS NULL;

-- KROK 3
INSERT INTO planning_permissions (
    property_id, application_number, description, decision_date, category,
    planning_authority, development_address, development_postcode,
    application_type, application_status, decision, land_use_code,
    area_of_site, num_residential_units, one_off_house, floor_area,
    received_date, grant_date, expiry_date, itm_easting, itm_northing
)
SELECT
    p.id,
    s.application_number,
    s.development_description,
    s.decision_date,
    CASE
        WHEN s.application_type ILIKE '%RETENTION%' OR s.decision ILIKE '%RETENTION%' THEN 'Retention'
        WHEN s.application_type ILIKE '%EXTENSION%' THEN 'Extension'
        WHEN s.application_type ILIKE '%OUTLINE%' THEN 'Outline'
        ELSE 'Other'
    END,
    s.planning_authority, s.development_address, s.development_postcode,
    s.application_type, s.application_status, s.decision, s.land_use_code,
    s.area_of_site, s.num_residential_units, s.one_off_house, s.floor_area,
    s.received_date, s.grant_date, s.expiry_date, s.itm_easting, s.itm_northing
FROM planning_staging s
JOIN properties p ON p.address = s.development_address
WHERE s.application_number IS NOT NULL AND s.application_number <> ''
ON CONFLICT (application_number) DO NOTHING;

SELECT
    (SELECT count(*) FROM planning_permissions) AS planning_permissions_count,
    (SELECT count(*) FROM planning_permissions WHERE category = 'Retention') AS retention_count,
    (SELECT count(*) FROM planning_permissions WHERE property_id IS NOT NULL) AS linked_count;
