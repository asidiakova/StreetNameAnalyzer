FROM postgis/postgis:15-3.3
RUN apt-get update && apt-get install -y --no-install-recommends osm2pgsql \
    && rm -rf /var/lib/apt/lists/*
