CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS hstore;

-- Simple key-value table for dataset metadata.
CREATE TABLE IF NOT EXISTS osm_metadata (key TEXT PRIMARY KEY, value TEXT);
INSERT INTO osm_metadata (key, value) VALUES ('data_date', CURRENT_DATE::TEXT)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Vector-tile function used by Martin to serve street geometries.
-- Requires the planet_osm_line table created by osm2pgsql.
CREATE OR REPLACE FUNCTION streets(z integer, x integer, y integer)
RETURNS bytea AS $$
  SELECT ST_AsMVT(tile, 'streets', 4096, 'geom') FROM (
    SELECT
      ST_AsMVTGeom(way, ST_TileEnvelope(z, x, y), 4096, 64, true) AS geom,
      name,
      highway
    FROM planet_osm_line
    WHERE way && ST_TileEnvelope(z, x, y)
      AND highway IS NOT NULL
      AND name IS NOT NULL
  ) AS tile
  WHERE geom IS NOT NULL;
$$ LANGUAGE sql STABLE;
