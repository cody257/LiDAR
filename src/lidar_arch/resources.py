"""3DEP EPT resource registry. M1 hard-codes the Phoenix collection confirmed
during research (AZ_MaricopaPinal_1_2020). M2 will add lat/lon auto-lookup."""
from dataclasses import dataclass


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


def resolve(name_or_bbox=None) -> Resource:
    """M1: always the Phoenix resource. (M2: real lat/lon -> resource lookup.)"""
    return PHOENIX
