"""lidar-arch command-line interface."""
from pathlib import Path
import click
from . import geo, resources, fetch, dem, viz


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
def run(bbox, out_dir, resolution):
    """Fetch -> DTM -> SVF/LRM/Slope for a bounding box (sane defaults)."""
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
    click.echo("Computing SVF / LRM / Slope ...")
    viz.svf(dtm, out / "svf.tif")
    viz.lrm(dtm, out / "lrm.tif")
    viz.slope(dtm, out / "slope.tif")
    click.echo(f"Done. Outputs in {out}")
