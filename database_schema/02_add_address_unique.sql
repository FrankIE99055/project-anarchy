-- Migrace: přidání unikátního omezení na 'address', aby šlo dělat
-- hromadné (bulk) upserty nemovitostí bez Eircode (starší záznamy před r. 2015).
-- Bez tohoto by šlo dedupe adres dělat jen řádek po řádku (pomalé).
--
-- Pozn.: Ve vzácných případech mohou dvě různé nemovitosti mít identický
-- textový popis adresy bez Eircode - pro účely MVP/testovací fáze to
-- akceptujeme jako kompromis pro rychlost importu.

ALTER TABLE properties
    ADD CONSTRAINT properties_address_key UNIQUE (address);
