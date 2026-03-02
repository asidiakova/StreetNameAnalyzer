# NOTES AND OBSERVATIONS

### USEFUL TERMS:

* #### Spatial reference system (SRS) / Coordinate reference system (CRS)
= A framework used to precisely measure locations on the surface of Earth as coordinates.
https://en.wikipedia.org/wiki/Spatial_reference_system


* #### EPSG code

= A numeric label for a coordinate reference system (CRS)
https://en.wikipedia.org/wiki/EPSG_Geodetic_Parameter_Dataset


* #### geometry in PostGIS
= A fundamental PostGIS data type used to represent a feature in planar (Euclidean) coordinate systems.
All spatial operations on geometry use the units of the Spatial Reference System the geometry is in.
https://postgis.net/docs/geometry.html


* #### geography in PostGIS
= A spatial data type used to represent a feature in geodetic coordinate systems. Geodetic coordinate systems model the earth using an ellipsoid.
Spatial operations on the geography type provide more accurate results by taking the ellipsoidal model into account.
https://postgis.net/docs/geography.html

(Analogy: geometry is like measuring on a paper map (accurate only if the map projection - SRS/CRS is chosen well), geography is like measuring on a globe — correct everywhere)


#### 1. Initial query:
`SELECT
  name,
  SUM(
    CASE
      WHEN ST_SRID(way) = 4326 THEN ST_Length(way::geography)
      ELSE ST_Length(ST_Transform(way, 3857))
    END
  ) AS total_length_m,
  COUNT(*) AS segments
FROM planet_osm_line
WHERE name IS NOT NULL
  AND (highway IS NOT NULL)
GROUP BY name
ORDER BY total_length_m DESC;
`


This was giving incorrect results due to measuring 3857 geometry in meters (Projected coordinate system - see https://epsg.io/3857), not on the ellipsoid. It significantly distorts the size of landmasses further from the equator, which resulted in the output being around 1.5 times higher than expected.
Distance scales in 3857 increase as scale = 1 / cos(latitude).
Slovakia’s latitude ≈ 48.7°.
1 / cos(48.7°) ≈ 1.51.

The correct way would be to either use 

`ST_Length(ST_Transform(way, 4326)::geography)`

for general global measurements (see https://epsg.io/4326), 


OR


`ST_Length(ST_Transform(way, 5514))`

a local accurate projection depending on the region.
For Slovakia (and Czech Republic), EPSG:5514 is the most accurate projection for distance measurements (see https://epsg.io/5514).
Note that it cannot be cast to geography and already gives the results in meters.

So, when we're using ST_Transform (which returns a new geometry with its coordinates transformed to a different spatial reference system), we should either use 4326, which is universal, or a region-specific CRS.
EPSG:4326 stores coordinates (longitude, latitude) in degrees (e.g. 19.1459, 48.1486), so we cast it to geography.
EPSG:5514 stores coordinates as x, y in metres.

So, the corrected query would be:

`SELECT
  name,
  SUM(ST_Length(ST_Transform(way, 4326)::geography)) AS total_length_m,
  COUNT(*) AS segments
FROM planet_osm_line
WHERE name IS NOT NULL
  AND highway IS NOT NULL
GROUP BY name
ORDER BY total_length_m DESC;`


OR

`SELECT
  name,
  SUM(ST_Length(ST_Transform(way, 5514))) AS total_length_m,
  COUNT(*)
FROM planet_osm_line
WHERE name IS NOT NULL
  AND highway IS NOT NULL
GROUP BY name
ORDER BY total_length_m DESC;`



## Wikidata Etymology Tags as Ground Truth

OSM supports `name:etymology:wikidata` tag linking street names to Wikidata entities.
https://wiki.openstreetmap.org/wiki/Key:name:etymology:wikidata

Example: Both "M. R. Štefánika" and "Štefánikova" map to Q319962 (Milan Rastislav Štefánik).
This provides automatic ground truth for evaluating normalization methods.


### Data Quality Issues
The etymology tags are crowd-sourced and contain noise:

1. **Over-tagging**: Mappers sometimes tag entire neighborhoods with the etymology of the district name, resulting in unrelated streets (e.g., "Dopravná") being linked to a person (e.g., Štefánik).

2. **Tagging errors**: Simple mistakes by volunteers.

3. **Indirect naming**: Streets inside named areas (e.g., "Štefánikova štvrť") may inherit the area's etymology tag even if the street itself isn't named after that person.

Raw etymology data cannot be used directly as ground truth. Requires filtering to keep only entries where the street name actually derives from the linked entity.

### Useful Queries

Check table structure:
`SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'planet_osm_line'
ORDER BY ordinal_position;`

Extract etymology data:
`SELECT name, tags->'name:etymology:wikidata' AS wikidata_id, COUNT(*)
FROM planet_osm_line
WHERE tags->'name:etymology:wikidata' IS NOT NULL
GROUP BY name, tags->'name:etymology:wikidata'
ORDER BY COUNT(*) DESC;`

Find multi-variant entities:
`SELECT 
    tags->'name:etymology:wikidata' AS wikidata_id,
    COUNT(DISTINCT name) AS variant_count,
    STRING_AGG(DISTINCT name, '; ' ORDER BY name) AS variants
FROM planet_osm_line
WHERE tags->'name:etymology:wikidata' IS NOT NULL AND name IS NOT NULL
GROUP BY tags->'name:etymology:wikidata'
HAVING COUNT(DISTINCT name) > 1
ORDER BY variant_count DESC;`

### Ground Truth Generation

The `ground_truth.py` script creates a validated dataset by cross-referencing OSM etymology tags with Wikidata. For each street-entity pair, it fetches the entity's labels/aliases from Wikidata API and computes a match confidence score (0.0–1.0) using Slovak morphological stemming. Entries with confidence >= 0.7 are treated as valid; the rest are excluded as noise. Entity types are simplified to "human" (Q5) vs "place" (everything else), with type-specific matching logic.


### Evaluation Framework

`evaluate.py` measures normalization methods against ground truth using two metrics:
- **Grouping Rate**: % of variants per Wikidata entity that share the same normalized root (higher = better at unifying variants)
- **Collision Rate**: % of normalized groups that contain multiple Wikidata entities (lower = better at keeping different entities separate)

---

## Normalization Methods

Detailed documentation for each method is in the `docs/` folder:
- `docs/suffix_stripping.md` — rule-based baseline (Slovak morphological suffix removal)
- `docs/levenshtein.md` — similarity-based greedy clustering (sequential edit distance)
- `docs/ngram.md` — similarity-based greedy clustering (set-based Jaccard on character bigrams)
