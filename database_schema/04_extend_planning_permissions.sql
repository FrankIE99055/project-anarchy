-- 04_extend_planning_permissions.sql
-- ------------------------------------------------------------------
-- Rozšíření tabulky planning_permissions o pole z National Planning
-- Applications datasetu (ArcGIS REST, data.gov.ie). Záměrně NEukládáme
-- žádná osobní data žadatelů (ApplicantForename/Surname/Address) -
-- pracujeme čistě s adresou/nemovitostí, ne s lidmi (GDPR).
-- ------------------------------------------------------------------

ALTER TABLE planning_permissions
    ADD COLUMN IF NOT EXISTS planning_authority VARCHAR(100),
    ADD COLUMN IF NOT EXISTS development_address TEXT,
    ADD COLUMN IF NOT EXISTS development_postcode VARCHAR(50),
    ADD COLUMN IF NOT EXISTS application_type VARCHAR(150),
    ADD COLUMN IF NOT EXISTS application_status VARCHAR(100),
    ADD COLUMN IF NOT EXISTS decision TEXT,
    ADD COLUMN IF NOT EXISTS land_use_code VARCHAR(100),
    ADD COLUMN IF NOT EXISTS area_of_site NUMERIC,
    ADD COLUMN IF NOT EXISTS num_residential_units INTEGER,
    ADD COLUMN IF NOT EXISTS one_off_house VARCHAR(10),
    ADD COLUMN IF NOT EXISTS floor_area NUMERIC,
    ADD COLUMN IF NOT EXISTS received_date DATE,
    ADD COLUMN IF NOT EXISTS grant_date DATE,
    ADD COLUMN IF NOT EXISTS expiry_date DATE,
    ADD COLUMN IF NOT EXISTS itm_easting DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS itm_northing DOUBLE PRECISION;

-- Index pro rychlé dohledání "signálu" Retention žádostí
CREATE INDEX IF NOT EXISTS planning_permissions_category_idx ON planning_permissions(category);
CREATE INDEX IF NOT EXISTS planning_permissions_dev_address_idx ON planning_permissions(development_address);
