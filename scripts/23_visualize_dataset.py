"""Illustrative dataset visualizations -- not a pipeline artifact (no downstream script reads
these), just for showing the tutor/slides what the training set looks like. Previously generated
by one-off scripts that weren't kept in the repo (per research_docs/BITACORA.md, 2026-09-08),
which is exactly why they went stale after the dataset was rescaled/fixed and nobody could
regenerate them without rewriting the logic from scratch -- kept here as a real script so that
doesn't happen again.
Usage: .venv/bin/python scripts/23_visualize_dataset.py -> writes
data/study_area/dataset_spatial_overview.png and data/study_area/sample_patches_grid.png
(neither versioned)."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import dataset_loader as dl

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
RGB_IDX = [3, 2, 1]  # B4, B3, B2 in S2_BANDS, matches 13_visualize_classification_map.py
CLASS_COLOR = {"bosque": "#1f8d49", "pasto": "#edde8e", "cultivo": "#e974ed"}
SPLIT_MARKER = {"train": "o", "val": "^", "test": "s"}
N_EXAMPLES = 6


def plot_spatial_overview(rows, out_path):
    fig, ax = plt.subplots(figsize=(7, 7))
    for class_name in dl.CLASS_NAMES:
        for split, marker in SPLIT_MARKER.items():
            pts = [r for r in rows if r["class"] == class_name and r["split"] == split]
            if not pts:
                continue
            ax.scatter(
                [float(r["lon"]) for r in pts], [float(r["lat"]) for r in pts],
                c=CLASS_COLOR[class_name], marker=marker, s=14, alpha=0.7, linewidths=0,
                label=f"{class_name} ({split})",
            )
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    ax.set_title(f"Dataset: {len(rows)} patches, por clase y split")
    ax.legend(fontsize=7, markerscale=1.3, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"saved: {out_path}")


def plot_sample_patches(rows, out_path):
    fig, axes = plt.subplots(len(dl.CLASS_NAMES), N_EXAMPLES, figsize=(2.2 * N_EXAMPLES, 2.2 * len(dl.CLASS_NAMES)))
    for row_i, class_name in enumerate(dl.CLASS_NAMES):
        examples = [r for r in rows if r["class"] == class_name][:N_EXAMPLES]
        for col_i, r in enumerate(examples):
            patch = np.load(REPO_ROOT / r["path"])
            rgb = np.clip(patch[:, :, RGB_IDX] / 3000, 0, 1)
            ax = axes[row_i, col_i]
            ax.imshow(rgb)
            ax.set_xticks([]); ax.set_yticks([])
            if col_i == 0:
                ax.set_ylabel(class_name, fontsize=12)
    fig.suptitle("Ejemplos de patches por clase (color verdadero)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"saved: {out_path}")


def main():
    rows = dl.load_manifest()
    print(f"{len(rows)} patches en el manifest")
    plot_spatial_overview(rows, DATA_DIR / "dataset_spatial_overview.png")
    plot_sample_patches(rows, DATA_DIR / "sample_patches_grid.png")


if __name__ == "__main__":
    main()
