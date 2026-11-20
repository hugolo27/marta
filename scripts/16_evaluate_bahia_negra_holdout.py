"""Cross-region generalization check #2: Bahia Negra (Alto Paraguay): remote, forest-dominated, no agricultural-colony influence.
Since phase1-segmentation (D6) the U-Net and the Random Forest classify the whole region at 30 m
and are scored against MapBiomas on every labeled cell, 5 seeds each, with the ESA WorldCover
cross-check (holdout_eval.run_region). The 33x33 CNN point-sample version is in git history.

Usage: .venv/bin/python scripts/16_evaluate_bahia_negra_holdout.py"""

from pathlib import Path

import holdout_eval

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "bahia_negra_holdout_results.json"

if __name__ == "__main__":
    holdout_eval.run_region("bahia_negra", OUT_PATH)
