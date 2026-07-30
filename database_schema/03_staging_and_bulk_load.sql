-- 03_staging_and_bulk_load.sql
-- ------------------------------------------------------------------
-- Umožňuje nahrát PPR data PŘÍMO do databáze bez Python API volání
-- (žádné síťové round-tripy na řádek -> o řády rychlejší import).
--
-- POSTUP:
-- 1) Spusť tento skript AŽ PO KROK "1) STAGING TABULKA" v Supabase SQL editoru.
-- 2) V Table Editoru otevři tabulku `ppr_staging` -> Insert -> Import data
--    from CSV -> nahraj soubor data_pipeline/raw_data/ppr_clean.csv
--    (vznikne skriptem prepare_ppr_csv.py).
-- 3) Po dokončení importu CSV spusť zbytek skriptu (KROK 2 a 3), který
--    jedním INSERT/SELECT naplní `properties` a `sales_history`.
-- ------------------------------------------------------------------

-- ============ KROK 1: STAGING TABULKA (spustit PŘED importem CSV) ============
DROP TABLE IF EXISTS ppr_staging;

CREATE TABLE ppr_staging (
    date_of_sale DATE,
    address TEXT,
    county TEXT,
    eircode TEXT,
    price NUMERIC(15,2),
    description TEXT
);

-- ============ KROK 1b: úklid případných dat z předchozího neúspěšného běhu ============
-- (adresa se v datech někdy opakuje s odlišným/chybným Eircode, což předchozí
-- dvoufázové vkládání rozbilo napůl cesty - nejdřív vyčistíme).
TRUNCATE TABLE sales_history, properties RESTART IDENTITY CASCADE;

-- ============ KROK 2: naplnění properties (spustit PO importu CSV) ============
-- Dedupe striktně podle `address` (to je jediný klíč, který je v datech vždy
-- vyplněný a jistě unikátní pro danou nemovitost). Pokud pro danou adresu
-- existuje víc záznamů, přednostně vybereme ten s vyplněným Eircode a z těch
-- nejnovější podle data prodeje.
-- Prostý `ON CONFLICT DO NOTHING` (bez uvedení sloupce) ošetří i vzácný
-- případ, kdy by stejný Eircode vyšel omylem u dvou různých adres.
INSERT INTO properties (eircode, address)
SELECT DISTINCT ON (address)
       NULLIF(eircode, '') AS eircode,
       address
FROM ppr_staging
ORDER BY address, (NULLIF(eircode, '') IS NOT NULL) DESC, date_of_sale DESC NULLS LAST
ON CONFLICT DO NOTHING;

-- ============ KROK 3: naplnění sales_history ============
-- Každá nemovitost má nyní jednu unikátní adresu, takže join podle adresy stačí.
INSERT INTO sales_history (property_id, date_of_sale, price, description)
SELECT p.id, s.date_of_sale, s.price, s.description
FROM ppr_staging s
JOIN properties p ON p.address = s.address;

-- ============ KROK 4 (volitelné): úklid staging tabulky ============
-- DROP TABLE IF EXISTS ppr_staging;
