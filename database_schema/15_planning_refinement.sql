-- 15_planning_refinement.sql
-- ------------------------------------------------------------------
-- Zpřesnění: NE každá "Retention" žádost znamená, že majitel chystá
-- prodej. Legalizace okna/dveří/garáže/plotu/reklamní cedule je běžná
-- svépomocná záležitost, kterou lidi řeší i bez úmyslu prodávat.
-- Silný signál "blíží se prodej" je hlavně u VĚTŠÍCH zásahů (přístavba,
-- change of use, vícejednotkové stavby, atd.) - tam je legalizace před
-- prodejem skutečně běžná praxe kvůli čistému právnímu stavu pro kupce.
--
-- Řešení: rozlišit "major" vs "minor-only" retention podle klíčových
-- slov v popisu (okna, dveře, garáž, plot, cedule, ...). Major retention
-- si drží plnou váhu (25), minor-only retention dostane sníženou váhu
-- (8) - furt je to signál (majitel se zabývá legálním stavem
-- nemovitosti), ale ne tak silný jako dřív.
-- ------------------------------------------------------------------

SET statement_timeout TO 0;

-- Klíčová slova pro "kosmetické"/drobné retention práce, které samy o
-- sobě nejsou důvod si myslet, že se blíží prodej.
-- (window/door/garage/shed/fence/signage/porch/dormer/solar panel/...)
DROP VIEW IF EXISTS property_propensity_score_v2;
DROP VIEW IF EXISTS property_propensity_signals CASCADE;

CREATE OR REPLACE VIEW property_propensity_signals AS
WITH ppr_agg AS (
    SELECT property_id, MAX(date_of_sale) AS last_sale_date
    FROM sales_history
    GROUP BY property_id
),
planning_agg AS (
    SELECT
        property_id,
        BOOL_OR(category = 'Retention') AS has_retention_permission,
        BOOL_OR(
            category = 'Retention'
            AND NOT (description ~* '(window|\ydoor\y|garage|\yshed\y|fence|boundary wall|signage|\ysign\y|advertising|porch|dormer|roof light|solar panel|canopy|awning|satellite dish|bin store|waste compactor)')
        ) AS has_major_retention
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
    COALESCE(pl.has_major_retention, false) AS has_major_retention,
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

CREATE OR REPLACE VIEW property_propensity_score_v2 AS
WITH raw AS (
    SELECT
        s.property_id,
        s.address,
        s.eircode,
        COALESCE(LEAST(s.years_since_last_sale / 15.0, 1.0) * 30, 0)
        + CASE WHEN s.has_major_retention THEN 25
               WHEN s.has_retention_permission THEN 8   -- minor-only (window/door/garage/...) - weaker signal
               WHEN s.has_any_permission THEN 5
               ELSE 0 END
        + CASE WHEN s.is_derelict_or_vacant THEN 30 ELSE 0 END
        + CASE WHEN s.rented_then_listed_for_sale THEN 15 ELSE 0 END
        + CASE WHEN s.relisting_count > 2 THEN 10 ELSE 0 END
        + CASE WHEN s.price_drop_pct > 5 THEN 10 ELSE 0 END
        AS raw_score,
        ARRAY_REMOVE(ARRAY[
            CASE WHEN s.years_since_last_sale >= 10 THEN s.years_since_last_sale::TEXT || ' years since last sale' END,
            CASE WHEN s.has_major_retention THEN 'Retention planning application' END,
            CASE WHEN s.has_retention_permission AND NOT s.has_major_retention THEN 'Minor retention application (e.g. garage/window/fence)' END,
            CASE WHEN s.is_derelict_or_vacant THEN 'Listed on Derelict/Vacant Sites Register' END,
            CASE WHEN s.rented_then_listed_for_sale THEN 'Previously rented, now for sale' END,
            CASE WHEN s.relisting_count > 2 THEN 'Relisted for sale ' || s.relisting_count || 'x' END,
            CASE WHEN s.price_drop_pct > 5 THEN 'Asking price reduced by ' || s.price_drop_pct || '%' END
        ], NULL) AS base_key_drivers
    FROM property_propensity_signals s
),
ranked AS (
    SELECT
        r.*,
        PERCENT_RANK() OVER (ORDER BY r.raw_score) * 100 AS percentile_score
    FROM raw r
)
SELECT
    ranked.property_id,
    ranked.address,
    ranked.eircode,
    ranked.raw_score,
    ranked.percentile_score,
    LEAST(100, ROUND((ranked.percentile_score + COALESCE(p.ai_signal_score, 0))::numeric, 1)) AS propensity_score,
    CASE
        WHEN p.ai_signal_note IS NOT NULL AND p.ai_signal_score > 0
            THEN ranked.base_key_drivers || ARRAY[p.ai_signal_note]
        ELSE ranked.base_key_drivers
    END AS key_drivers,
    ranked.base_key_drivers
FROM ranked
JOIN properties p ON p.id = ranked.property_id;

-- Promítnutí zpět (plný přepočet - raw_score/percentily se mění pro
-- statisíce nemovitostí, potřebujeme přeřadit celou populaci znovu)
UPDATE properties p
SET propensity_score = s.propensity_score,
    raw_signal_score = s.raw_score,
    percentile_score = s.percentile_score,
    base_key_drivers = s.base_key_drivers,
    key_drivers = s.key_drivers,
    last_updated = CURRENT_TIMESTAMP
FROM property_propensity_score_v2 s
WHERE s.property_id = p.id;

-- Kontrola dopadu (kolik nemovitostí mělo JEN minor retention, tedy
-- předtím se počítaly plnou vahou 25 a teď jen 8)
SELECT
    count(*) FILTER (WHERE has_retention_permission AND NOT has_major_retention) AS minor_only_retention_properties,
    count(*) FILTER (WHERE has_major_retention) AS major_retention_properties
FROM property_propensity_signals;

SELECT
    round(avg(propensity_score)::numeric, 2) AS avg,
    round(stddev(propensity_score)::numeric, 2) AS stddev,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY propensity_score)::numeric, 2) AS median,
    max(propensity_score) AS mx
FROM properties;
