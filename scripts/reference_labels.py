"""Reference-label columns and forest definitions for phase1-accuracy-assessment.

The interpreter records, per point and date, the primary label under the case-study PD's forest
definition (CDM: >= 25% crown, >= 0.5 ha, >= 5 m potential) plus the attributes that separate it
from Paraguay's FREL definition for the Región Occidental (>= 10% crown, >= 1 ha, >= 3 m; strips
count only if >= 60 m wide). The FREL label is derived from those attributes, never interpreted a
second time. Height can't be seen on imagery, so "indeterminate" is a valid value and the FREL
label is reported with and without counting it as meeting the 3 m threshold."""

DATE_FIELDS = ["label", "crown", "patch", "height", "near_threshold", "narrow_strip", "imagery_source", "imagery_date"]
LABELS = ("forest", "nonforest")
CROWN = ("lt10", "10to25", "ge25")
PATCH = ("lt0.5", "0.5to1", "ge1")
HEIGHT = ("ge5", "3to5", "lt3", "indeterminate")
YES = ("1", "true", "yes", "si", "sí", "x")


def blind_columns(dates):
    return ["point_id", "lon", "lat"] + [f"{f}_{d}" for d in dates for f in DATE_FIELDS] + ["uninterpretable_reason", "notes"]


def parse(row, date):
    """None if the point-date was left blank (uninterpretable). Raises on values outside the
    protocol or on a primary label that contradicts the recorded attributes."""
    get = lambda f: row.get(f"{f}_{date}", "").strip().lower()
    label = get("label")
    if not label:
        return None
    rec = {"label": label, "crown": get("crown"), "patch": get("patch"), "height": get("height"),
           "near_threshold": get("near_threshold") in YES, "narrow_strip": get("narrow_strip") in YES}
    pid = row["point_id"]
    if label not in LABELS or rec["crown"] not in CROWN:
        raise ValueError(f"{pid} {date}: label={label!r} crown={rec['crown']!r}")
    if rec["crown"] != "lt10" and (rec["patch"] not in PATCH or rec["height"] not in HEIGHT):
        raise ValueError(f"{pid} {date}: woody point needs patch and height, got {rec['patch']!r} / {rec['height']!r}")
    if (label == "forest") != meets_cdm(rec):
        raise ValueError(f"{pid} {date}: label={label} contradicts crown/patch/height {rec['crown']}/{rec['patch']}/{rec['height']}")
    return rec


def meets_cdm(rec):
    return rec["crown"] == "ge25" and rec["patch"] in ("0.5to1", "ge1") and rec["height"] in ("ge5", "indeterminate")


def frel_label(rec, indeterminate_height_ok=True):
    heights = ("ge5", "3to5", "indeterminate") if indeterminate_height_ok else ("ge5", "3to5")
    forest = (rec["crown"] in ("10to25", "ge25") and rec["patch"] == "ge1" and rec["height"] in heights
              and not rec["narrow_strip"])
    return "forest" if forest else "nonforest"


def sparse_woody(rec):
    """Woody vegetation that fails the CDM definition: what the old flag_sparse_woody captured."""
    return rec["label"] == "nonforest" and rec["crown"] != "lt10"
