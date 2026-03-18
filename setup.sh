#!/bin/bash
set -e

PBF_URL="https://download.geofabrik.de/europe/slovakia-latest.osm.pbf"
PBF_FILE="data/slovakia-latest.osm.pbf"

mkdir -p data

if [ ! -f "$PBF_FILE" ]; then
    echo "Downloading Slovakia OSM extract (~300 MB)..."
    curl -L -o "$PBF_FILE" "$PBF_URL"
else
    echo "PBF file already exists, skipping download."
fi

echo "Stopping any existing containers..."
docker compose down 2>/dev/null || true
for name in postgis_osm martin; do
    docker rm -f "$name" 2>/dev/null || true
done

echo "Building and starting PostGIS..."
docker compose up -d --build postgis

echo "Waiting for PostGIS to be ready..."
until docker compose exec postgis pg_isready -U osmuser -d osm > /dev/null 2>&1; do
    sleep 2
done
echo "PostGIS is ready."

echo "Loading OSM data with osm2pgsql (this may take several minutes)..."
docker compose exec postgis osm2pgsql \
    --create --slim --hstore \
    -d osm -U osmuser \
    /data/slovakia-latest.osm.pbf

echo "Creating streets vector-tile function..."
docker compose exec -T postgis psql -U osmuser -d osm -f /init.sql

echo "Starting Martin tile server..."
docker compose up -d martin

echo ""
echo "===== Setup complete ====="
echo "PostGIS:  localhost:5434  (user: osmuser, password: osmpass, db: osm)"
echo "Martin:   http://localhost:3001"
echo ""
echo "Next steps:"
echo "  1. Copy src/.env.example to src/.env and fill in your API keys"
echo "  2. pip install -r requirements.txt"
echo "  3. cd src && python -m analysis.compute"
