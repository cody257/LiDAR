# lidar-arch web — coverage picker + run-on-the-map

Draw or type a bounding box on a map, see which USGS 3DEP LiDAR collection covers it
(with a density-based quality signal), then **Run** it and watch the SVF/LRM/RRIM result
appear overlaid on the map where you drew.

- **Front-end** (`public/`): MapLibre map, Variant B sidebar, coverage shaded by density,
  draw/typed box, coverage lookup + command, **Run** button, product toggle + opacity.
- **Worker** (`src/worker.js`): serves the app; `POST /api/run` calls the container,
  caches result PNGs in **R2** (per product), serves them at `/api/result/:key/:product.png`.
- **Container** (`container/`): the full `lidar-arch` pipeline behind a tiny HTTP server.

## Run locally (no Cloudflare account)

Two pieces — the pipeline container, and the Worker that calls it:

    # 1) build + run the pipeline container (the engine) — needs Docker running
    npm run container:build         # docker build -> lidar-arch:dev  (~2 min first time)
    npm run container:run           # docker run -p 8080:8080 lidar-arch:dev

    # 2) in another shell — the Worker + app (R2 simulated locally by Miniflare)
    npm install                     # first time only
    npm run dev                     # wrangler dev -> http://127.0.0.1:8787

Open **http://127.0.0.1:8787**, draw a box over an area with 3DEP coverage (try Phoenix),
then click **Run this box** (~5-8 s) → the LRM overlay appears. Toggle products
(LRM/RRIM/SVF/Slope/Openness), blend with the opacity slider, or Clear.

## Coverage data

`public/coverage.json` (~4 MB, 2,266 collections) is derived from
[`hobuinc/usgs-lidar/boundaries/resources.geojson`], enriched with `year` (from the name)
and `density` (pts/m² from `count` ÷ geodesic area). Regenerate (needs the `lidar-arch`
conda env for GDAL + pyproj):

    curl -L -o data/resources.raw.geojson https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/resources.geojson
    conda run -n lidar-arch ogr2ogr -f GeoJSON data/coverage.simplified.geojson data/resources.raw.geojson -simplify 0.002 -lco COORDINATE_PRECISION=4 -select name,count,url
    conda run -n lidar-arch python scripts/prep_coverage.py

## Deploy (Cloudflare) — later

`wrangler deploy` builds + pushes the container, deploys the Worker. Before that, swap the
local `CONTAINER_URL` var for a Cloudflare **Container** binding (Durable Object) and create
the R2 bucket (`wrangler r2 bucket create lidar-results`). Requires the Workers Paid plan.

## Files

    web/
      public/  index.html  app.js  styles.css  coverage.json
      src/worker.js          # the Worker (app + /api/run + R2)
      container/             # Dockerfile, server.py, env.yml
      scripts/prep_coverage.py
      wrangler.jsonc  package.json
