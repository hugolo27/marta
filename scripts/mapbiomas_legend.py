"""MapBiomas Chaco Collection 5 legend (chaco.mapbiomas.org/en/legend-codes/), remapped to 3
per-date classes. NOT the Brazil/Amazon legend — codes differ (e.g. 6 = "Flooded woodland" here,
"Mangrove" there). "desmonte" isn't a class code (MapBiomas has no "recently cleared" state, see
docs/FOUNDATION.md point 4, derived via temporal comparison instead). Critical: code 15
("Pastura", managed pasture) != codes 11/12/42/43/44 ("Pastizal", natural grassland) despite the
similar names — only 15 counts as "pasto"."""

MAPBIOMAS_ASSET = "projects/mapbiomas-public/assets/chaco/lulc/collection5/mapbiomas_chaco_collection5_integration_v2"

BOSQUE = [3, 4, 6, 45]  # natural wooded vegetation
PASTO = [15]  # managed pasture only, not natural grassland
CULTIVO = [18, 19, 57, 58, 36, 9]  # agriculture + plantations
OTHER = [10, 11, 12, 22, 23, 24, 25, 26, 27, 42, 43, 44, 61]  # natural grassland, bare, water, n/a

CLASS_NAMES = {1: "bosque", 2: "pasto", 3: "cultivo", 0: "other"}


def remap_expression(band_name):
    """Builds an ee.Image.remap()-compatible (from, to) pair for the given classification band."""
    from_codes = BOSQUE + PASTO + CULTIVO + OTHER
    to_codes = [1] * len(BOSQUE) + [2] * len(PASTO) + [3] * len(CULTIVO) + [0] * len(OTHER)
    return from_codes, to_codes
