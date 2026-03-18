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
