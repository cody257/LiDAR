"""lidar-arch command-line interface."""
from dataclasses import replace
from pathlib import Path
import click
from . import geo, resources, fetch, dem, viz

KNOWN_PRODUCTS = ("svf", "lrm", "slope", "openness", "rrim")


@click.group()
def cli():
    """Archaeology-optimized terrain visualizations from USGS 3DEP LiDAR."""


@cli.command()
@click.option("--bbox", nargs=4, type=float, required=True,
              metavar="MINLON MINLAT MAXLON MAXLAT",
              help="Bounding box in lon/lat (WGS84).")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), required=True,
              help="Output directory.")
@click.option("--resolution", type=float, default=1.0, show_default=True,
              help="DTM grid resolution in metres.")
@click.option("--products", default="svf,lrm,slope,openness,rrim", show_default=True,
              help="Comma-separated visualization products to generate.")
@click.option("--resource", default="auto", show_default=True,
              help="EPT URL or known collection name. 'auto' uses the Phoenix "
                   "collection and enforces its coverage check.")
@click.option("--out-srs", "out_srs", default="auto", show_default=True,
              help="Output CRS. 'auto' picks the NAD83 UTM zone for the bbox; "
                   "or pass an explicit EPSG code (e.g. EPSG:26913).")
def run(bbox, out_dir, resolution, products, resource, out_srs):
    """Fetch -> DTM -> visualization products for a bounding box (sane defaults)."""
    names = [p.strip() for p in products.split(",") if p.strip()]
    unknown = [n for n in names if n not in KNOWN_PRODUCTS]
    if unknown:
        raise click.ClickException(
            f"Unknown product(s): {', '.join(unknown)}. "
            f"Choose from: {', '.join(KNOWN_PRODUCTS)}.")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bbox_3857 = geo.bbox_to_3857(*bbox)

    # Resolve the output CRS: 'auto' -> NAD83 UTM zone for the bbox center.
    target_srs = (f"EPSG:{geo.utm_epsg_for_bbox(bbox)}"
                  if out_srs == "auto" else out_srs)

    # Resolve the collection. 'auto' keeps the Phoenix default + coverage guard;
    # a URL or a known name builds an arbitrary resource and skips that guard
    # (the caller/map already verified coverage).
    if resource == "auto":
        res = replace(resources.resolve(), target_srs=target_srs)
        if not geo.bbox_within(bbox_3857, res.extent_3857):
            raise click.ClickException(
                f"Requested bbox is outside the {res.name} coverage area.")
    else:
        if resource.startswith("http"):
            ept_url = resource
            name = None
        elif resource in resources.KNOWN:
            ept_url = resources.KNOWN[resource].ept_url
            name = resource
        else:
            raise click.ClickException(
                f"Unknown resource '{resource}'. Pass an EPT URL (http...) or "
                f"one of: {', '.join(sorted(resources.KNOWN))}.")
        res = resources.from_ept(ept_url, target_srs, name=name)

    click.echo(f"Fetching ground points from {res.name} ...")
    dtm_raw = fetch.fetch_dtm(bbox_3857, res, out / "dtm_raw.tif", resolution)
    click.echo("Filling DTM holes ...")
    dtm = dem.fill_holes(dtm_raw, out / "dtm.tif")
    click.echo(f"Computing {', '.join(names)} ...")
    filenames = {"openness": "opns"}  # product keyword -> output stem (matches README/rvt term)
    for name in names:
        getattr(viz, name)(dtm, out / f"{filenames.get(name, name)}.tif")
    click.echo(f"Done. Outputs in {out}")
