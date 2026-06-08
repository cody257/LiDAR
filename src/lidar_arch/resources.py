"""3DEP EPT resource registry. M1 hard-codes the Phoenix collection confirmed
during research (AZ_MaricopaPinal_1_2020). M2 will add lat/lon auto-lookup."""
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Resource:
    name: str
    ept_url: str
    extent_3857: tuple  # (xmin, ymin, xmax, ymax) data extent in EPSG:3857
    target_srs: str = "EPSG:26912"  # UTM 12N NAD83, Phoenix


PHOENIX = Resource(
    name="AZ_MaricopaPinal_1_2020",
    ept_url=(
        "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/"
        "AZ_MaricopaPinal_1_2020/ept.json"
    ),
    extent_3857=(-12555542.0, 3847680.0, -12363850.0, 4010355.0),
)


# Collections addressable by short name (in addition to direct EPT URLs).
KNOWN = {PHOENIX.name: PHOENIX}


def _name_from_url(ept_url: str) -> str:
    """Collection name = the path segment containing ept.json (its parent dir),
    e.g. .../AZ_MaricopaPinal_1_2020/ept.json -> AZ_MaricopaPinal_1_2020."""
    segments = [s for s in urlparse(ept_url).path.split("/") if s]
    if len(segments) >= 2:
        return segments[-2]
    return segments[-1] if segments else ept_url


def from_ept(ept_url: str, target_srs: str, name: str = None) -> Resource:
    """Build a Resource for an arbitrary 3DEP EPT collection.

    name defaults to the collection dir parsed from the URL. extent_3857 is None
    (coverage is the caller's responsibility for arbitrary collections)."""
    return Resource(
        name=name or _name_from_url(ept_url),
        ept_url=ept_url,
        extent_3857=None,
        target_srs=target_srs,
    )


def resolve(name_or_bbox=None) -> Resource:
    """M1: always the Phoenix resource. (M2: real lat/lon -> resource lookup.)"""
    return PHOENIX
