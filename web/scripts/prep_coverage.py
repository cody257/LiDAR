#!/usr/bin/env python
"""Slim hobuinc/usgs-lidar resources.geojson into web/public/coverage.json for the map app.

Adds two derived fields the raw index lacks:
  - `year`    parsed from the collection name (e.g. AZ_MaricopaPinal_1_2020 -> 2020)
  - `density` estimated pts/m^2 = count / geodesic footprint area (the quality signal)

Run (geometry already simplified by ogr2ogr upstream):
  conda run -n lidar-arch python web/scripts/prep_coverage.py [in.geojson] [out.json]
"""
import json, os, re, sys
from pyproj import Geod

IN = sys.argv[1] if len(sys.argv) > 1 else "web/data/coverage.simplified.geojson"
OUT = sys.argv[2] if len(sys.argv) > 2 else "web/public/coverage.json"
GEOD = Geod(ellps="WGS84")


def year_of(name):
    yrs = re.findall(r"(?:19|20)\d{2}", name or "")
    return int(yrs[-1]) if yrs else None


def ring_area(ring):
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    area, _ = GEOD.polygon_area_perimeter(lons, lats)
    return abs(area)


def geom_area(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    total = 0.0
    for poly in polys:
        if not poly:
            continue
        total += max(ring_area(poly[0]) - sum(ring_area(r) for r in poly[1:]), 0.0)
    return total  # m^2


def main():
    data = json.load(open(IN, encoding="utf-8"))
    feats = []
    for f in data["features"]:
        p = f["properties"]
        name = p.get("name") or ""
        area = geom_area(f["geometry"])
        count = p.get("count") or 0
        feats.append({
            "type": "Feature",
            "properties": {
                "name": name,
                "year": year_of(name),
                "count": count,
                "density": round(count / area, 1) if area > 0 else None,
                "url": p.get("url"),
            },
            "geometry": f["geometry"],
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats},
              open(OUT, "w", encoding="utf-8"), separators=(",", ":"))

    sz = os.path.getsize(OUT) / 1e6
    dens = sorted(x["properties"]["density"] for x in feats if x["properties"]["density"])
    print(f"wrote {OUT}: {len(feats)} features, {sz:.1f} MB")
    if dens:
        import statistics as s
        print(f"density pts/m^2 -- min {dens[0]}, median {s.median(dens):.1f}, max {dens[-1]}")
    az = [x["properties"] for x in feats if "MaricopaPinal" in x["properties"]["name"]]
    print("MaricopaPinal sample:", az[:2])


if __name__ == "__main__":
    main()
