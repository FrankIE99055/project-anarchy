-- 21_osm_addresses.sql
-- ------------------------------------------------------------------
-- Import adres z OpenStreetMap (Geofabrik extrakt Ireland+NI, viz
-- data_pipeline/download_osm_addresses.py) - 449,420 unikátních adres
-- (13,799 s Eircode, 435,621 bez Eircode; Severní Irsko už vyřazeno v
-- Pythonu podle BT postcode / country tagu).
--
-- POSTUP:
-- 1) KROK 1 (staging tabulka).
-- 2) \copy z data_pipeline/raw_data/osm_addresses_raw.csv do
--    osm_addresses_staging (dělá se přímo přes psql, ne Table Editor -
--    449k řádků).
-- 3) KROK 2: GPS backfill na existující properties podle Eircode.
-- 4) KROK 3: nové properties pro adresy, které v DB ještě nejsou.
--
-- DŮLEŽITÝ DOPAD (potvrzeno uživatelem): přidání ~435k nemovitostí BEZ
-- jakéhokoli PPR/planning/Daft signálu mění percentile_score CELÉ
-- populace (property_propensity_score_v2 řadí relativně). Po tomhle
-- importu je NUTNÉ znovu spustit plný přepočet (viz konec souboru).
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

-- ============ KROK 1: STAGING TABULKA ============
DROP TABLE IF EXISTS osm_addresses_staging;

CREATE TABLE osm_addresses_staging (
    eircode TEXT,
    housenumber TEXT,
    street TEXT,
    city TEXT,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION
);

\copy osm_addresses_staging FROM 'D:/Project Anarchy/data_pipeline/raw_data/osm_addresses_raw.csv' WITH (FORMAT csv, HEADER true)

-- ============ KROK 2 (spustit AŽ PO \copy): GPS backfill ============
-- Doplní přesné GPS (skutečný bod domu/budovy z OSM, ne jen townland
-- centroid) na existující properties, které mají shodný Eircode a
-- zatím žádnou polohu.
UPDATE properties p
SET location = ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography
FROM (
    SELECT DISTINCT ON (eircode) eircode, longitude, latitude
    FROM osm_addresses_staging
    WHERE eircode IS NOT NULL
) s
WHERE p.eircode = s.eircode AND p.location IS NULL;

-- ============ KROK 3: nové properties ============
-- 3a) Adresy S Eircode, které v properties ještě neexistují.
-- ON CONFLICT DO NOTHING (bez cíle) zachytí konflikt na OBOU unikátních
-- omezeních (eircode i address - properties_address_key z
-- 02_add_address_unique.sql), protože spousta OSM adres bez čísla domu
-- se textově shoduje s už existujícím záznamem (např. jen název obce).
INSERT INTO properties (eircode, address, location)
SELECT DISTINCT ON (s.eircode)
       s.eircode,
       CONCAT_WS(', ', NULLIF(TRIM(CONCAT_WS(' ', s.housenumber, s.street)), ''), s.city),
       ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography
FROM osm_addresses_staging s
LEFT JOIN properties p ON p.eircode = s.eircode
WHERE s.eircode IS NOT NULL AND p.id IS NULL
ON CONFLICT DO NOTHING;

-- 3b) Adresy BEZ Eircode - žádný spolehlivý klíč k párování na
-- existující PPR/planning text adresy (stejná situace jako u Planning
-- Permissions v 05_planning_staging_and_bulk_load.sql), takže se
-- vkládají jako nové properties. eircode zůstává NULL (Postgres
-- UNIQUE dovoluje libovolně mnoho NULL hodnot, žádný konflikt na
-- eircode) - ON CONFLICT DO NOTHING řeší konflikt na `address`.
INSERT INTO properties (eircode, address, location)
SELECT NULL,
       CONCAT_WS(', ', NULLIF(TRIM(CONCAT_WS(' ', s.housenumber, s.street)), ''), s.city),
       ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography
FROM osm_addresses_staging s
WHERE s.eircode IS NULL
  AND TRIM(CONCAT_WS(' ', s.housenumber, s.street, s.city)) <> ''
ON CONFLICT DO NOTHING;

-- ============ KROK 4: PLNÝ PŘEPOČET SKÓRE (POVINNÉ PO IMPORTU) ============
-- Nové properties nemají žádný signál (raw_score=0), což mění percentile
-- pro CELOU populaci - property_propensity_score_v2 view se přepočítá
-- samo (je to view), stačí znovu spustit stejnou UPDATE properties jako
-- v 15_planning_refinement.sql (view definice se neměnila, jen se mění
-- podkladová data v properties).
UPDATE properties p
SET propensity_score = s.propensity_score,
    raw_signal_score = s.raw_score,
    percentile_score = s.percentile_score,
    base_key_drivers = s.base_key_drivers,
    key_drivers = s.key_drivers,
    last_updated = CURRENT_TIMESTAMP
FROM property_propensity_score_v2 s
WHERE s.property_id = p.id;

-- Sanity check
SELECT count(*) AS total_properties,
       count(*) FILTER (WHERE location IS NOT NULL) AS with_location,
       round(avg(propensity_score)::numeric, 2) AS avg_score,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY propensity_score)::numeric, 2) AS median_score
FROM properties;
