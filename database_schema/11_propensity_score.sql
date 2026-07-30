-- 11_propensity_score.sql
-- ------------------------------------------------------------------
-- Propensity Score v1 (pravděpodobnost prodeje) - transparentní vážené
-- skóre 0-100 postavené na signálech, které už máme v databázi:
--
--   PPR:       roky od posledního prodeje (starý prodej = vyšší skóre)
--   Planning:  Retention žádost (silný signál - "legalizace před prodejem")
--   Derelict:  zápis na registru chátrajících/prázdných nemovitostí
--   Daft:      přeinzerování, pokles ceny, pronájem->prodej
--
-- Je to VYSVĚTLITELNÝ heuristický model (ne černá skříňka) - časem ho
-- nahradíme skutečným ML modelem, až budeme mít historická data o tom,
-- co se reálně prodalo (backtesting).
-- ------------------------------------------------------------------

-- KROK 0: index potřebný pro rychlý JOIN (pokud ještě neexistuje)
SET statement_timeout TO 0;
CREATE INDEX IF NOT EXISTS planning_permissions_property_id_idx ON planning_permissions(property_id);

-- Sloupec pro key_drivers přímo v properties (view property_propensity_score
-- je moc pomalý na dotazování přes Supabase REST API - je nematerializovaný
-- a přepočítává se nad ~1M řádků při každém requestu, což narazí na
-- statement_timeout PostgRESTu. Proto skóre i drivers materializujeme
-- přímo do properties, kde je to rychlé (indexováno).
ALTER TABLE properties ADD COLUMN IF NOT EXISTS key_drivers TEXT[];

-- KROK 1: syrové signály za nemovitost (pro debug/transparentnost/UI)
-- Používáme set-based agregace (GROUP BY) místo korelovaných subquery
-- na řádek - u 688k nemovitostí je to řádově rychlejší (hash joiny
-- místo miliónů jednotlivých dotazů).
CREATE OR REPLACE VIEW property_propensity_signals AS
WITH ppr_agg AS (
    SELECT property_id, MAX(date_of_sale) AS last_sale_date
    FROM sales_history
    GROUP BY property_id
),
planning_agg AS (
    SELECT property_id, BOOL_OR(category = 'Retention') AS has_retention_permission
    FROM planning_permissions
    WHERE property_id IS NOT NULL
    GROUP BY property_id
),
derelict_agg AS (
    SELECT DISTINCT property_id
    FROM derelict_sites
    WHERE property_id IS NOT NULL
)
SELECT
    p.id AS property_id,
    p.address,
    p.eircode,
    ppr.last_sale_date,
    EXTRACT(YEAR FROM AGE(CURRENT_DATE, ppr.last_sale_date)) AS years_since_last_sale,
    COALESCE(pl.has_retention_permission, false) AS has_retention_permission,
    (pl.property_id IS NOT NULL) AS has_any_permission,
    (d.property_id IS NOT NULL) AS is_derelict_or_vacant,
    dps.relisting_count,
    dps.rented_then_listed_for_sale,
    dps.price_drop_pct,
    dps.latest_ber_rating
FROM properties p
LEFT JOIN ppr_agg ppr ON ppr.property_id = p.id
LEFT JOIN planning_agg pl ON pl.property_id = p.id
LEFT JOIN derelict_agg d ON d.property_id = p.id
LEFT JOIN daft_property_signals_scored dps ON dps.property_id = p.id;

-- KROK 2: vážené skóre 0-100
CREATE OR REPLACE VIEW property_propensity_score AS
SELECT
    property_id,
    address,
    eircode,
    LEAST(
        100,
        -- PPR: až 30 bodů, lineárně do 15 let od posledního prodeje
        COALESCE(LEAST(years_since_last_sale / 15.0, 1.0) * 30, 0)
        -- Planning: Retention je silný signál, jiné povolení slabší
        + CASE WHEN has_retention_permission THEN 25
               WHEN has_any_permission THEN 5
               ELSE 0 END
        -- Derelict/Vacant registr: velmi silný signál
        + CASE WHEN is_derelict_or_vacant THEN 30 ELSE 0 END
        -- Daft: "accidental landlord" (pronájem -> prodej)
        + CASE WHEN rented_then_listed_for_sale THEN 15 ELSE 0 END
        -- Daft: opakované přeinzerování (těžko se prodává)
        + CASE WHEN relisting_count > 2 THEN 10 ELSE 0 END
        -- Daft: viditelný pokles nabídkové ceny
        + CASE WHEN price_drop_pct > 5 THEN 10 ELSE 0 END
    ) AS propensity_score,
    -- "Key Drivers" - human-readable reasons for the score (for the UI)
    ARRAY_REMOVE(ARRAY[
        CASE WHEN years_since_last_sale >= 10 THEN years_since_last_sale::TEXT || ' years since last sale' END,
        CASE WHEN has_retention_permission THEN 'Retention planning application' END,
        CASE WHEN is_derelict_or_vacant THEN 'Listed on Derelict/Vacant Sites Register' END,
        CASE WHEN rented_then_listed_for_sale THEN 'Previously rented, now for sale' END,
        CASE WHEN relisting_count > 2 THEN 'Relisted for sale ' || relisting_count || 'x' END,
        CASE WHEN price_drop_pct > 5 THEN 'Asking price reduced by ' || price_drop_pct || '%' END
    ], NULL) AS key_drivers
FROM property_propensity_signals;

-- KROK 3: promítnutí skóre + key_drivers zpátky do properties
-- (aby se dalo snadno filtrovat/řadit/dotazovat bez nutnosti joinovat view)
UPDATE properties p
SET propensity_score = s.propensity_score,
    key_drivers = s.key_drivers,
    last_updated = CURRENT_TIMESTAMP
FROM property_propensity_score s
WHERE s.property_id = p.id;

-- Index pro rychlé řazení/filtrování podle skóre (Top-N dotazy z API)
CREATE INDEX IF NOT EXISTS properties_propensity_score_idx ON properties (propensity_score DESC);

-- Rychlá kontrola distribuce skóre
SELECT
    count(*) AS total_properties,
    round(avg(propensity_score), 2) AS avg_score,
    count(*) FILTER (WHERE propensity_score >= 70) AS high_score_70plus,
    count(*) FILTER (WHERE propensity_score >= 50) AS medium_score_50plus,
    max(propensity_score) AS max_score
FROM properties;
