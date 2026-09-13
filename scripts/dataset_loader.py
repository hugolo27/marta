"""Shared dataset loading for phase1-classifier (tasks 1.1-1.3). Reads the manifest built by
08_assemble_dataset.py and serves it two ways: a flat per-pixel feature table for Random Forest,
and a patch tensor dataset for the CNN."""

import csv
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "data" / "study_area" / "dataset" / "manifest.csv"
CLASS_TO_ID = {"bosque": 0, "pasto": 1, "cultivo": 2}
CLASS_NAMES = [name for name, _ in sorted(CLASS_TO_ID.items(), key=lambda kv: kv[1])]


@lru_cache(maxsize=None)
def load_manifest(split=None):
    """Cached: the 5-seed comparison loop calls this (via load_pixel_features/PatchDataset)
    once per seed even though the dataset never changes across seeds (code review 2026-09-04)."""
    with open(MANIFEST_PATH) as f:
        rows = list(csv.DictReader(f))
    if split is not None:
        rows = [r for r in rows if r["split"] == split]
    return rows


@lru_cache(maxsize=None)
def load_pixel_features(split):
    """Center-pixel spectral features for Random Forest: (N, 13) array + (N,) labels."""
    rows = load_manifest(split)
    X = np.zeros((len(rows), 13), dtype=np.float32)
    y = np.zeros(len(rows), dtype=np.int64)
    for i, row in enumerate(rows):
        patch = np.load(REPO_ROOT / row["path"])
        center = patch.shape[0] // 2  # derived from the actual array, not a hardcoded 16
        X[i] = patch[center, center, :]
        y[i] = CLASS_TO_ID[row["class"]]
    return X, y


class PatchDataset(Dataset):
    """33x33x13 patches for the CNN, channel-first for PyTorch conv layers."""

    def __init__(self, split, augment=False):
        self.rows = load_manifest(split)
        self.augment = augment

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        row = self.rows[idx]
        patch = np.load(REPO_ROOT / row["path"]).astype(np.float32)
        if self.augment:
            k = np.random.randint(4)
            patch = np.rot90(patch, k, axes=(0, 1))
            if np.random.rand() < 0.5:
                patch = np.flip(patch, axis=0)
            if np.random.rand() < 0.5:
                patch = np.flip(patch, axis=1)
        patch = np.ascontiguousarray(patch.transpose(2, 0, 1))  # (13, 33, 33)
        label = CLASS_TO_ID[row["class"]]
        return torch.from_numpy(patch), label
