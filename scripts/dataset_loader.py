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
# Patches hold the dry composite (12 bands + NDVI) and, since phase1-dataset-v2, the wet one after it.
SEASON_CHANNELS = {"dry": slice(0, 13), "drywet": slice(0, 26)}


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
def load_pixel_features(split, season="dry"):
    """Center-pixel spectral features for Random Forest: (N, 13 or 26) array + (N,) labels."""
    rows = load_manifest(split)
    channels = SEASON_CHANNELS[season]
    X = np.zeros((len(rows), channels.stop - channels.start), dtype=np.float32)
    y = np.zeros(len(rows), dtype=np.int64)
    for i, row in enumerate(rows):
        patch = np.load(REPO_ROOT / row["path"])
        center = patch.shape[0] // 2  # derived from the actual array, not a hardcoded 16
        X[i] = patch[center, center, channels]
        y[i] = CLASS_TO_ID[row["class"]]
    return X, y


@lru_cache(maxsize=None)
def channel_stats(season="dry"):
    """Per-channel mean and standard deviation over every pixel of the train split, used to
    normalize the CNN input (phase1-dataset-v2). Train only: val and test must not shape it."""
    patches = np.stack([load_patch(r["path"])[..., SEASON_CHANNELS[season]] for r in load_manifest("train")])
    flat = patches.reshape(-1, patches.shape[-1]).astype(np.float64)
    return flat.mean(axis=0).astype(np.float32), flat.std(axis=0).astype(np.float32)


@lru_cache(maxsize=None)
def load_patch(path):
    """Cached: every epoch of every seed re-reads the same ~2,400 small files, which dominated
    training time (phase1-patch-size). Callers get a read-only array and copy before changing it."""
    patch = np.load(REPO_ROOT / path).astype(np.float32)
    patch.flags.writeable = False
    return patch


class PatchDataset(Dataset):
    """33x33x13 patches for the CNN, channel-first for PyTorch conv layers."""

    def __init__(self, split, augment=False, season="dry"):
        self.rows = load_manifest(split)
        self.augment = augment
        self.channels = SEASON_CHANNELS[season]

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        row = self.rows[idx]
        patch = load_patch(row["path"])[..., self.channels]
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


# Tiles for the U-Net (phase1-segmentation), built by 35_assemble_tiles.py. Labels are MapBiomas at
# 30 m (0 other, 1 bosque, 2 pasto, 3 cultivo) and are served as CLASS_TO_ID ids, with IGNORE for 0.
TILES_DIR = REPO_ROOT / "data" / "study_area" / "tiles"
TILE_NDVI_SCALE = 10000
TILE_NDVI_CHANNELS = [12, 25]
IGNORE = -1


@lru_cache(maxsize=None)
def load_tile_manifest():
    with open(TILES_DIR / "manifest.csv") as f:
        return list(csv.DictReader(f))


def tile_block(row):
    """The 6 km block of a tile, so callers split by block (08_assemble_dataset.block_key)."""
    import importlib
    return importlib.import_module("08_assemble_dataset").block_key(float(row["lon"]), float(row["lat"]))


@lru_cache(maxsize=None)
def load_tile(path, tile_px=192):
    """Center crop of a tile as int16 image (H, W, 26) and int64 label (H/3, W/3), cached because
    every epoch re-reads the same files. The crop keeps the 3x3 alignment: tiles are 192 px and the
    allowed sizes are multiples of 48."""
    data = np.load(REPO_ROOT / path)
    offset = (data["image"].shape[0] - tile_px) // 2
    image = data["image"][offset:offset + tile_px, offset:offset + tile_px]
    label = data["label"][offset // 3:(offset + tile_px) // 3, offset // 3:(offset + tile_px) // 3].astype(np.int64) - 1
    image.flags.writeable = False
    label.flags.writeable = False
    return image, label


def tile_to_float(image):
    image = image.astype(np.float32)
    image[..., TILE_NDVI_CHANNELS] /= TILE_NDVI_SCALE
    return image


def tile_channel_stats(rows, tile_px=192):
    """Per-channel mean and standard deviation over every pixel of the given (training) tiles."""
    total, total_sq, n = np.zeros(26), np.zeros(26), 0
    for row in rows:
        image = tile_to_float(load_tile(row["path"], tile_px)[0]).reshape(-1, 26).astype(np.float64)
        total += image.sum(axis=0)
        total_sq += (image ** 2).sum(axis=0)
        n += len(image)
    mean = total / n
    return mean.astype(np.float32), np.sqrt(total_sq / n - mean ** 2).astype(np.float32)


def block_features(rows, tile_px=192):
    """Random Forest input at 30 m: the mean of the 26 channels over each 3x3 block, one row per
    labeled cell (phase1-segmentation D3)."""
    X, y = [], []
    for row in rows:
        image, label = load_tile(row["path"], tile_px)
        cells = tile_to_float(image).reshape(tile_px // 3, 3, tile_px // 3, 3, 26).mean(axis=(1, 3))
        keep = label != IGNORE
        X.append(cells[keep])
        y.append(label[keep])
    return np.concatenate(X), np.concatenate(y)


class TileDataset(Dataset):
    """Tiles channel-first, with the 30 m label map; rotations and flips move both together."""

    def __init__(self, rows, tile_px=192, augment=False):
        self.rows = rows
        self.tile_px = tile_px
        self.augment = augment

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        image, label = load_tile(self.rows[idx]["path"], self.tile_px)
        image = tile_to_float(image)
        if self.augment:
            k = np.random.randint(4)
            image, label = np.rot90(image, k, axes=(0, 1)), np.rot90(label, k)
            if np.random.rand() < 0.5:
                image, label = np.flip(image, axis=0), np.flip(label, axis=0)
            if np.random.rand() < 0.5:
                image, label = np.flip(image, axis=1), np.flip(label, axis=1)
        image = np.ascontiguousarray(image.transpose(2, 0, 1))
        return torch.from_numpy(image), torch.from_numpy(np.array(label))
