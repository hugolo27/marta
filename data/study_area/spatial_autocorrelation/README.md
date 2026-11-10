# Spatial autocorrelation: block side for the train/val/test split

Change: `openspec/changes/phase1-dataset-v2/` (design D1). Script: `scripts/33_spatial_autocorrelation.py`.
MLflow experiment `phase1-spatial-autocorrelation`.

## Why

The split assigns whole spatial blocks to train, validation or test, so nearby points can't land on
both sides. The previous block side, ~2 km, was chosen as "more than 6 times the 330 m patch side".
The literature asks for blocks at least as large as the distance over which points still resemble
each other (Roberts et al., 2017; Valavi et al., 2019), so the side should come from that distance.

## Method

- Per year (2019, 2023): 30 random windows of 20 × 20 km over the sampling area with the held-out
  regions carved out, 300 points per window at 30 m (18,000 points in total), each with its
  MapBiomas class and its dry-season NDVI.
- For each distance bin, over pairs inside the same window: semivariance of NDVI (half the mean
  squared difference) and of the class (half the share of pairs with different classes).
- Exponential model fitted to each semivariogram. Practical range: the distance at which it reaches
  95% of its sill.
- Block side: the largest of the four practical ranges, rounded up to the next whole kilometer,
  capped at 10 km (half the window, the most the windows can measure).

A first pass with 10 km windows (exploratory, not versioned) gave 4.3-4.4 km for NDVI and 6.4-8.6
km for the class. The class curves were still rising at the window edge, so those fits
extrapolated; the 20 km windows show the plateau and replace them.

## Results

| Variable | 2019 | 2023 |
|---|---|---|
| NDVI | 3.9 km | 4.8 km |
| MapBiomas class | 5.2 km | 4.4 km |

Largest practical range 5,161 m, so **block side = 6 km**. Every range is above the previous 2 km
blocks (`semivariograms.png`, dashed line): with 2 km blocks, test points sat within the
autocorrelation range of training points, so the reported test scores are likely optimistic.

The semivariance keeps rising slowly beyond 10 km (regional differences across the Chaco). That
slow trend is not short-range autocorrelation and is not what the blocks are meant to absorb; the
held-out regions, hundreds of kilometers away, cover it.

## References

- Roberts, D. R., et al. (2017). Cross-validation strategies for data with temporal, spatial,
  hierarchical, or phylogenetic structure. *Ecography*, 40(8), 913-929. https://doi.org/10.1111/ecog.02881
- Valavi, R., Elith, J., Lahoz-Monfort, J. J., & Guillera-Arroita, G. (2019). blockCV: An R package
  for generating spatially or environmentally separated folds. *Methods in Ecology and Evolution*,
  10(2), 225-232. https://doi.org/10.1111/2041-210X.13107
