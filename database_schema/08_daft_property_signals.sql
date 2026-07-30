-- 08_daft_property_signals.sql
-- ------------------------------------------------------------------
-- Odvozené signály z historie Daft inzerátů pro každou nemovitost
-- (jen ty, co jsou propojené přes property_id - viz KROK 3 v
-- 07_daft_staging_and_bulk_load.sql). Žádná nová externí data -
-- jen chytřejší dotaz nad tím, co už máme.
--
-- Signály:
--   relisting_count   - kolikrát byla nemovitost inzerována (různé ad ID)
--   ever_rented       - byla někdy inzerována k pronájmu
--   ever_for_sale     - byla někdy inzerována k prodeji
--   rented_then_listed_for_sale - "accidental landlord" signál: nejdřív
--                        pronájem, později prodej stejné nemovitosti
--   first_sale_price / last_sale_price / price_drop_pct - vývoj ceny
--   latest_ber_rating - nejnovější známý BER rating z inzerátů
--   latest_listing_type/category - aktuální stav (v prodeji/pronajato/prodáno)
--   last_scraped_at   - kdy byl naposledy zaznamenán jakýkoliv inzerát
-- ------------------------------------------------------------------

CREATE OR REPLACE VIEW daft_property_signals AS
WITH sale_prices AS (
    -- Ceny z aktivních "for_sale" inzerátů (ne z 'sold' - to je finální
    -- prodejní cena, ne vývoj nabídkové ceny). Pokles ceny mezi opakovanými
    -- 'for_sale' scrapy stejné nemovitosti = signál "těžko se prodává".
    SELECT
        property_id,
        price,
        scraped_at,
        ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY scraped_at ASC) AS rn_first,
        ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY scraped_at DESC) AS rn_last
    FROM daft_listings
    WHERE property_id IS NOT NULL
      AND listing_type = 'for_sale'
      AND price IS NOT NULL
),
latest_listing AS (
    SELECT DISTINCT ON (property_id)
        property_id, listing_type, category, ber_rating, scraped_at
    FROM daft_listings
    WHERE property_id IS NOT NULL
    ORDER BY property_id, scraped_at DESC NULLS LAST
),
rent_first AS (
    SELECT property_id, MIN(scraped_at) AS first_rent_at
    FROM daft_listings
    WHERE property_id IS NOT NULL AND listing_type IN ('for_rent', 'commercial_rent', 'sharing')
    GROUP BY property_id
),
sale_first AS (
    SELECT property_id, MIN(scraped_at) AS first_sale_at
    FROM daft_listings
    WHERE property_id IS NOT NULL AND listing_type IN ('for_sale', 'sold', 'new_homes')
    GROUP BY property_id
)
SELECT
    dl.property_id,
    COUNT(*) AS relisting_count,
    BOOL_OR(dl.listing_type IN ('for_rent', 'commercial_rent', 'sharing')) AS ever_rented,
    BOOL_OR(dl.listing_type IN ('for_sale', 'sold', 'new_homes')) AS ever_for_sale,
    (rf.first_rent_at IS NOT NULL AND sf.first_sale_at IS NOT NULL
        AND rf.first_rent_at < sf.first_sale_at) AS rented_then_listed_for_sale,
    MAX(sp_first.price) FILTER (WHERE sp_first.rn_first = 1) AS first_sale_price,
    MAX(sp_last.price) FILTER (WHERE sp_last.rn_last = 1) AS last_sale_price,
    ll.listing_type AS latest_listing_type,
    ll.category AS latest_category,
    ll.ber_rating AS latest_ber_rating,
    MAX(dl.scraped_at) AS last_scraped_at
FROM daft_listings dl
LEFT JOIN sale_prices sp_first ON sp_first.property_id = dl.property_id AND sp_first.rn_first = 1
LEFT JOIN sale_prices sp_last ON sp_last.property_id = dl.property_id AND sp_last.rn_last = 1
LEFT JOIN latest_listing ll ON ll.property_id = dl.property_id
LEFT JOIN rent_first rf ON rf.property_id = dl.property_id
LEFT JOIN sale_first sf ON sf.property_id = dl.property_id
WHERE dl.property_id IS NOT NULL
GROUP BY dl.property_id, rf.first_rent_at, sf.first_sale_at,
         ll.listing_type, ll.category, ll.ber_rating;

-- Bonus: price_drop_pct jako pohodlný sloupec navrch (počítáno z first/last)
CREATE OR REPLACE VIEW daft_property_signals_scored AS
SELECT
    *,
    CASE
        WHEN first_sale_price IS NOT NULL AND last_sale_price IS NOT NULL
             AND first_sale_price > 0 AND first_sale_price <> last_sale_price
        THEN ROUND(((first_sale_price - last_sale_price) / first_sale_price) * 100, 2)
        ELSE NULL
    END AS price_drop_pct
FROM daft_property_signals;
