# lidar-arch web — coverage map picker

Draw or type a bounding box on a map, see which USGS 3DEP LiDAR collection covers it
(with a density-based quality signal), and get the `lidar-arch` command to run.

**Milestone A (this):** front-end only — it finds coverage and emits the command. It does
**not** run the pipeline yet.
**Milestone B (next):** a Cloudflare backend (Worker → Queue → Container running `lidar-arch`
→ R2 + D1) so drawing a box actually runs the pipeline and paints SVF/LRM/RRIM back on the map.

The layout is "Variant B" chosen from `prototype/map-picker/` (sidebar control panel + map;
draw on the map *or* type the four corners).

## Run (local, no Cloudflare account)

    cd web
    npm install
    npm run dev          # wrangler pages dev public  ->  http://127.0.0.1:8788

(Any static server also works, e.g. `python -m http.server 8788 --directory public`.)

## Coverage data

`public/coverage.json` (~4 MB, 2,266 collections) is derived from the canonical index
[`hobuinc/usgs-lidar/boundaries/resources.geojson`], enriched with `year` (parsed from the
collection name) and `density` (pts/m² estimated from `count` ÷ geodesic footprint area).

To regenerate (needs the `lidar-arch` conda env for GDAL + pyproj):

    # 1. download the raw index
    curl -L -o data/resources.raw.geojson \
      https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/resources.geojson
    # 2. simplify geometry + trim precision (8.3 MB -> ~4.5 MB)
    conda run -n lidar-arch ogr2ogr -f GeoJSON data/coverage.simplified.geojson \
      data/resources.raw.geojson -simplify 0.002 -lco COORDINATE_PRECISION=4 -select name,count,url
    # 3. enrich with year + density -> public/coverage.json
    conda run -n lidar-arch python scripts/prep_coverage.py

> Real-data signal: median collection density is only ~4.7 pts/m². Below ~8 pts/m² subtle
> earthworks (canals, low mounds) are hard to resolve — hence the per-collection quality hint.
> `data/` intermediates are gitignored; `public/coverage.json` is committed so the app just runs.

## Files

    web/
      public/
        index.html      # sidebar + map + legend
        app.js          # map, coverage lookup, draw/typed box, command
        styles.css      # Variant B palette + layout
        coverage.json   # slim enriched coverage index (committed)
      scripts/prep_coverage.py
      package.json       # wrangler devDep + "dev" script
