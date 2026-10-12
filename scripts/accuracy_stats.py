"""Area and accuracy estimators for phase1-accuracy-assessment, plus the VM0007 gate.

olofsson()   -- stratified random sampling where the strata ARE the map classes (Olofsson et al.
               2014, RSE 148:42-57): error matrix in area proportions, error-adjusted area
               proportions, user's/producer's/overall accuracy, all with standard errors.
stehman()    -- same outputs when the strata are NOT the map classes (Stehman 2014, IJRS
               35:4923-4939). Needed because the AOI sample is stratified by change class but
               per-date accuracy is asked of each date's own map, and the held-out samples are
               stratified by WorldCover, not by our map.

Verified against Olofsson 2014's worked example (Table 8 and its printed results) and against
the reference R implementation (mapaccuracy::olofsson / stehman2014) on both papers' examples,
see phase1-accuracy-assessment tasks 2.1-2.2."""

import numpy as np

Z95 = 1.959963984540054
VM0007_MIN_PER_CLASS = 50
VM0007_MIN_OA = 0.90


def olofsson(ref, mapped, n_map_class):
    """ref/mapped: per-sample labels. n_map_class: {class: mapped area or pixel count}."""
    ref, mapped = np.asarray(ref), np.asarray(mapped)
    classes = list(n_map_class)
    total = sum(n_map_class.values())
    w = np.array([n_map_class[c] / total for c in classes])
    counts = np.array([[np.sum((mapped == i) & (ref == j)) for j in classes] for i in classes], dtype=float)
    n_i = counts.sum(1)
    frac = counts / n_i[:, None]
    p = w[:, None] * frac

    area = p.sum(0)
    se_area = np.sqrt(((w[:, None] ** 2) * frac * (1 - frac) / (n_i[:, None] - 1)).sum(0))
    ua = np.diag(frac)
    se_ua = np.sqrt(ua * (1 - ua) / (n_i - 1))
    oa = np.trace(p)
    se_oa = np.sqrt(np.sum(w ** 2 * ua * (1 - ua) / (n_i - 1)))

    pa = np.diag(p) / area
    n_hat_col = (np.array([n_map_class[c] for c in classes])[:, None] / n_i[:, None] * counts).sum(0)
    n_map = np.array([n_map_class[c] for c in classes])
    se_pa = np.empty(len(classes))
    for j in range(len(classes)):
        others = [i for i in range(len(classes)) if i != j]
        term1 = n_map[j] ** 2 * (1 - pa[j]) ** 2 * ua[j] * (1 - ua[j]) / (n_i[j] - 1)
        term2 = pa[j] ** 2 * sum(n_map[i] ** 2 * frac[i, j] * (1 - frac[i, j]) / (n_i[i] - 1) for i in others)
        se_pa[j] = np.sqrt((term1 + term2) / n_hat_col[j] ** 2)

    return {
        "classes": classes, "counts": counts, "matrix": p,
        "area": area, "se_area": se_area, "ua": ua, "se_ua": se_ua, "pa": pa, "se_pa": se_pa,
        "oa": oa, "se_oa": se_oa,
    }


def _stratum_moments(strata, n_strata, y, x=None):
    out = []
    for h in n_strata:
        sel = strata == h
        yh = y[sel].astype(float)
        xh = x[sel].astype(float) if x is not None else None
        out.append((n_strata[h], sel.sum(), yh, xh))
    return out


def _mean_est(strata, n_strata, y):
    total = sum(n_strata.values())
    est, var = 0.0, 0.0
    for big_n, n, yh, _ in _stratum_moments(strata, n_strata, y):
        est += big_n * yh.mean()
        var += big_n ** 2 * (1 - n / big_n) * yh.var(ddof=1) / n
    return est / total, np.sqrt(var) / total


def _ratio_est(strata, n_strata, y, x):
    moments = _stratum_moments(strata, n_strata, y, x)
    y_hat = sum(big_n * yh.mean() for big_n, _, yh, _ in moments)
    x_hat = sum(big_n * xh.mean() for big_n, _, _, xh in moments)
    r = y_hat / x_hat
    var = 0.0
    for big_n, n, yh, xh in moments:
        s_xy = np.cov(yh, xh, ddof=1)[0, 1]
        var += big_n ** 2 * (1 - n / big_n) * (yh.var(ddof=1) + r ** 2 * xh.var(ddof=1) - 2 * r * s_xy) / n
    return r, np.sqrt(var) / x_hat


def stehman(strata, ref, mapped, n_strata, classes=None):
    """strata/ref/mapped: per-sample labels. n_strata: {stratum: population size (pixels or area)}."""
    strata, ref, mapped = np.asarray(strata), np.asarray(ref), np.asarray(mapped)
    if classes is None:
        classes = sorted(set(ref) | set(mapped))
    k = len(classes)
    matrix = np.array([[_mean_est(strata, n_strata, (mapped == i) & (ref == j))[0] for j in classes] for i in classes])
    area, se_area = map(np.array, zip(*(_mean_est(strata, n_strata, ref == c) for c in classes)))
    oa, se_oa = _mean_est(strata, n_strata, ref == mapped)
    ua, se_ua, pa, se_pa = (np.full(k, np.nan) for _ in range(4))
    for idx, c in enumerate(classes):
        hit = (mapped == c) & (ref == c)
        if (mapped == c).any():
            ua[idx], se_ua[idx] = _ratio_est(strata, n_strata, hit, mapped == c)
        if (ref == c).any():
            pa[idx], se_pa[idx] = _ratio_est(strata, n_strata, hit, ref == c)
    return {
        "classes": classes, "matrix": matrix, "area": area, "se_area": se_area,
        "ua": ua, "se_ua": se_ua, "pa": pa, "se_pa": se_pa, "oa": oa, "se_oa": se_oa,
    }


def vm0007_gate(ref, mapped, oa, classes=("forest", "nonforest")):
    """VM0007 as written in the case-study PD: >= 50 points each for forest and non-forest,
    overall accuracy >= 90%. The PD doesn't say whether "points per class" means map or
    reference class, so both are counted and both must pass."""
    ref, mapped = np.asarray(ref), np.asarray(mapped)
    by_map = {c: int((mapped == c).sum()) for c in classes}
    by_ref = {c: int((ref == c).sum()) for c in classes}
    enough = all(v >= VM0007_MIN_PER_CLASS for v in [*by_map.values(), *by_ref.values()])
    return {
        "points_by_map_class": by_map, "points_by_reference_class": by_ref,
        "min_points_per_class": VM0007_MIN_PER_CLASS, "enough_points": enough,
        "overall_accuracy": float(oa), "min_overall_accuracy": VM0007_MIN_OA,
        "passed": bool(enough and oa >= VM0007_MIN_OA),
    }
