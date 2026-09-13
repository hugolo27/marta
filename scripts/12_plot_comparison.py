"""Bar+dots chart of the RF vs. CNN 5-seed comparison (phase1-classifier task 4), for showing
the tutor. Reads 11_compare_classifiers.py's saved output, not hardcoded numbers, so it never goes
stale. Colors validated CVD-safe via the dataviz skill's validate_palette.js."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

RESULTS_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "comparison_results.json"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "rf_vs_cnn_comparison.png"
COLOR_RF, COLOR_CNN = "#2a78d6", "#d95926"


def main():
    if not RESULTS_PATH.exists():
        raise SystemExit(f"{RESULTS_PATH} not found — run 11_compare_classifiers.py first.")
    results = json.loads(RESULTS_PATH.read_text())

    fig, ax = plt.subplots(figsize=(6, 5))
    all_scores = []
    for x, scores, color, label in [
        (0, results["rf_scores"], COLOR_RF, "Random Forest"),
        (1, results["cnn_scores"], COLOR_CNN, "CNN"),
    ]:
        mean, std = np.mean(scores), np.std(scores)
        all_scores.extend(scores)
        ax.bar(x, mean, yerr=std, width=0.5, color=color, capsize=6,
               error_kw={"elinewidth": 1.5, "ecolor": "#3a3a38"})
        jitter = np.random.default_rng(0).uniform(-0.08, 0.08, size=len(scores))
        ax.scatter([x] * len(scores) + jitter, scores, color="#3a3a38", zorder=3, s=24)
        ax.text(x, mean + std + 0.015, f"{mean:.3f}", ha="center", fontsize=11, color="#1a1a19")

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Random Forest\n(baseline)", "CNN\n(candidata)"], fontsize=11)
    ax.set_ylabel("F1 macro (test, 5 semillas)", fontsize=11)
    # Padded to the actual data range instead of a fixed [0.6, 0.9] — a hardcoded range can
    # silently clip a future run's bars/points if the numbers ever move outside it (code review
    # 2026-09-13).
    ax.set_ylim(max(0, min(all_scores) - 0.08), min(1, max(all_scores) + 0.08))
    ax.set_title("Clasificación bosque/pasto/cultivo: RF vs. CNN\n(barras = media, puntos = cada semilla)", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.2)

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150)
    print(f"saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
