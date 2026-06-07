"""lidar-arch command-line interface."""
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
def run(bbox, out_dir, resolution, products):
    """Fetch -> DTM -> visualization products for a bounding box (sane defaults)."""
    names = [p.strip() for p in products.split(",") if p.strip()]
    unknown = [n for n in names if n not in KNOWN_PRODUCTS]
    if unknown:
        raise click.ClickException(
            f"Unknown product(s): {', '.join(unknown)}. "
            f"Choose from: {', '.join(KNOWN_PRODUCTS)}.")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res = resources.resolve()
    bbox_3857 = geo.bbox_to_3857(*bbox)
    if not geo.bbox_within(bbox_3857, res.extent_3857):
        raise click.ClickException(
            f"Requested bbox is outside the {res.name} coverage area.")

    click.echo(f"Fetching ground points from {res.name} ...")
    dtm_raw = fetch.fetch_dtm(bbox_3857, res, out / "dtm_raw.tif", resolution)
    click.echo("Filling DTM holes ...")
    dtm = dem.fill_holes(dtm_raw, out / "dtm.tif")
    click.echo(f"Computing {', '.join(names)} ...")
    for name in names:
        getattr(viz, name)(dtm, out / f"{name}.tif")
    click.echo(f"Done. Outputs in {out}")
