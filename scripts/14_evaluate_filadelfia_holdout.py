"""Cross-region generalization check #1: Filadelfia (Boqueron): agricultural colonies, fragmented forest.
Since phase1-segmentation (D6) the U-Net and the Random Forest classify the whole region at 30 m
and are scored against MapBiomas on every labeled cell, 5 seeds each, with the ESA WorldCover
cross-check (holdout_eval.run_region). The 33x33 CNN point-sample version is in git history.

Usage: .venv/bin/python scripts/14_evaluate_filadelfia_holdout.py"""

from pathlib import Path

import holdout_eval

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "filadelfia_holdout_results.json"

if __name__ == "__main__":
    holdout_eval.run_region("filadelfia", OUT_PATH)
