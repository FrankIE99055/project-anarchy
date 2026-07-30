-- Pomocný skript: spustí jen KROK 2+3 z 10_derelict_staging_and_bulk_load.sql
-- (staging tabulka derelict_staging už je naplněná, nechceme ji znovu DROPnout)

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

SELECT
    (SELECT count(*) FROM derelict_sites) AS derelict_sites_count,
    (SELECT count(*) FROM derelict_sites WHERE property_id IS NOT NULL) AS linked_to_properties,
    (SELECT count(*) FROM derelict_sites WHERE location IS NOT NULL) AS with_location;
