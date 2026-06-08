# lidar-arch web — coverage picker + run-on-the-map

Draw or type a bounding box on a map, see which USGS 3DEP LiDAR collection covers it
(with a density-based quality signal), then **Run** it and watch the SVF/LRM/RRIM result
appear overlaid on the map where you drew.

- **Front-end** (`public/`): MapLibre map, Variant B sidebar, coverage shaded by density,
  draw/typed box, coverage lookup + command, **Run** button, product toggle + opacity.
- **Worker** (`src/worker.js`): serves the app; `POST /api/run` calls the container,
  caches result PNGs in **R2** (per product), serves them at `/api/result/:key/:product.png`.
  In production it reaches the container through the `LidarContainer` Durable Object
  binding (`env.LIDAR`); in local dev it uses `CONTAINER_URL` (see `.dev.vars`).
- **Container** (`container/`): the full `lidar-arch` pipeline behind a tiny HTTP server.
  Self-contained: it installs `lidar-arch` from a pre-built wheel (`container/wheels/`,
  gitignored) so its Docker build context is just `container/` — see `container/build-wheel.md`.

## Run locally (no Cloudflare account)

Two pieces — the pipeline container, and the Worker that calls it:

    # 0) build the lidar-arch wheel the container installs (re-run if Python src changes)
    npm run container:wheel         # -> container/wheels/lidar_arch-*.whl

    # 1) build + run the pipeline container (the engine) — needs Docker running
    npm run container:build         # docker build -t lidar-arch:dev container  (~2 min first time)
    npm run container:run           # docker run -p 8080:8080 lidar-arch:dev

    # 2) in another shell — the Worker + app (R2 simulated locally by Miniflare)
    npm install                     # first time only
    npm run dev                     # wrangler dev -> http://127.0.0.1:8787

Local dev reads `web/.dev.vars` (gitignored) for `CONTAINER_URL=http://127.0.0.1:8080`,
so the Worker talks to the Docker container directly. Create it if missing:

    CONTAINER_URL="http://127.0.0.1:8080"

(`wrangler dev` sets `enable_containers: false` in `wrangler.jsonc` so it does **not**
try to build/manage the container itself — managed containers aren't supported in
local dev on Windows. Production is unaffected.)

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

## Deploy (Cloudflare)

Requires the **Workers Paid** plan (Containers + Durable Objects). `wrangler deploy`
builds `container/Dockerfile`, pushes the image to Cloudflare's registry, and deploys the
Worker with the R2 bucket, the `LidarContainer` Durable Object, and its `containers[]`
config. Production has **no** `CONTAINER_URL`, so the Worker uses the `env.LIDAR` binding.

    cd web
    npm install                                 # wrangler v4 + @cloudflare/containers
    npm run container:wheel                      # build container/wheels/*.whl (needed by the image)

    npx wrangler login                           # one-time auth (opens a browser)
    npx wrangler r2 bucket create lidar-results  # one-time: create the R2 bucket

    npx wrangler deploy --dry-run                # optional: validate config + build image, no push
    npx wrangler deploy                          # build + push image, deploy Worker (first push is slow)

Notes:
- The container is **linux/amd64** (required by Cloudflare Containers); Docker must be running.
- `instance_type` / `max_instances` live in `wrangler.jsonc` under `containers[]`.
- `migrations` (`new_sqlite_classes: ["LidarContainer"]`) registers the Durable Object on
  first deploy — keep it in place; add new `tag`s for future schema changes.

## Files

    web/
      public/  index.html  app.js  styles.css  coverage.json
      src/worker.js          # the Worker (app + /api/run + R2 + LidarContainer DO)
      container/             # Dockerfile, server.py, env.yml, build-wheel.{ps1,md}, wheels/ (gitignored)
      scripts/prep_coverage.py
      wrangler.jsonc         # assets, r2, containers[], durable_objects, migrations
      .dev.vars              # local-only CONTAINER_URL (gitignored)
      package.json
