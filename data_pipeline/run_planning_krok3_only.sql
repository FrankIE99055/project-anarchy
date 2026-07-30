SET statement_timeout TO 0;

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
    s.area_of_site, s.num_residential_units, TRIM(s.one_off_house), s.floor_area,
    s.received_date, s.grant_date, s.expiry_date, s.itm_easting, s.itm_northing
FROM planning_staging s
JOIN properties p ON p.address = s.development_address
WHERE s.application_number IS NOT NULL AND s.application_number <> ''
ON CONFLICT (application_number) DO NOTHING;

SELECT
    (SELECT count(*) FROM planning_permissions) AS planning_permissions_count,
    (SELECT count(*) FROM planning_permissions WHERE category = 'Retention') AS retention_count,
    (SELECT count(*) FROM planning_permissions WHERE property_id IS NOT NULL) AS linked_count;
