"""Build and run the PDAL EPT -> bare-earth DTM pipeline.

CRS dance (the #1 trap): `readers.ept` `bounds` MUST be in the EPT's native CRS
(EPSG:3857); points are then reprojected to the target UTM CRS after reading."""
import json


def build_pipeline(bbox_3857, ept_url, out_tif, resolution=1.0,
                   target_srs="EPSG:26912"):
    """Return a PDAL pipeline dict. bbox_3857 = (xmin, ymin, xmax, ymax)."""
    xmin, ymin, xmax, ymax = bbox_3857
    bounds = f"([{xmin}, {xmax}], [{ymin}, {ymax}])"  # ([xmin,xmax],[ymin,ymax]) in 3857
    return {
        "pipeline": [
            {"type": "readers.ept", "filename": ept_url, "bounds": bounds},
            {"type": "filters.reprojection", "out_srs": target_srs},
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {
                "type": "writers.gdal",
                "filename": str(out_tif),
                "gdaldriver": "GTiff",
                "output_type": "idw",
                "resolution": resolution,
                "window_size": 6,
            },
        ]
    }


def _pipeline(pipeline_dict):
    """Wrap PDAL construction so tests can monkeypatch it."""
    import pdal
    return pdal.Pipeline(json.dumps(pipeline_dict))


def fetch_dtm(bbox_3857, resource, out_tif, resolution=1.0):
    """Run the pipeline; return out_tif. Raise if zero points (usually a CRS slip)."""
    pipe = build_pipeline(bbox_3857, resource.ept_url, out_tif, resolution,
                          resource.target_srs)
    n = _pipeline(pipe).execute()
    if n == 0:
        raise RuntimeError(
            "No points returned. Check that bbox bounds are in EPSG:3857 and "
            "inside the resource coverage."
        )
    return out_tif
