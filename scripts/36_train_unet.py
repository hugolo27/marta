"""U-Net candidate, phase1-segmentation D3. Every value comes from design D0: nnU-Net's rules for
depth (downsample until the map would drop below 4 px), filters (32, doubled per level, capped at
512), blocks (two conv + instance norm + leaky ReLU, strided-conv downsampling, transposed-conv
upsampling) and loss (cross-entropy + Dice) (Isensee et al., 2021), no dropout, rotations and flips.

The 10 m class probabilities are averaged over each 3x3 block, so loss and metrics are computed at
30 m, the resolution of the MapBiomas labels. Label cells outside the three classes
(dataset_loader.IGNORE) count in neither. Input is normalized per channel inside the model with
train-split statistics stored in the checkpoint, as in phase1-dataset-v2.

train() and evaluate() are called by the pilot (37) and the selection (38); main() is the
overfit check of task 2.1."""

import math
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

import classifier_report
import dataset_loader as dl

N_CLASSES = 3
BASE_FILTERS = 32
MAX_FILTERS = 512
MIN_MAP_PX = 4
MAX_EPOCHS = 100
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"
CHECKPOINT_PATH = OUT_DIR / "unet_checkpoint.pt"


def n_levels(tile_px):
    levels = 0
    while tile_px % 2 == 0 and tile_px // 2 >= MIN_MAP_PX:
        tile_px //= 2
        levels += 1
    return levels


def conv_block(c_in, c_out, stride=1):
    return nn.Sequential(
        nn.Conv2d(c_in, c_out, 3, stride=stride, padding=1), nn.InstanceNorm2d(c_out, affine=True), nn.LeakyReLU(0.01),
        nn.Conv2d(c_out, c_out, 3, padding=1), nn.InstanceNorm2d(c_out, affine=True), nn.LeakyReLU(0.01),
    )


class UNet(nn.Module):
    def __init__(self, tile_px=96, in_channels=26):
        super().__init__()
        self.tile_px = tile_px
        self.register_buffer("mean", torch.zeros(in_channels))
        self.register_buffer("std", torch.ones(in_channels))
        widths = [min(BASE_FILTERS * 2 ** i, MAX_FILTERS) for i in range(n_levels(tile_px) + 1)]
        self.down = nn.ModuleList([conv_block(in_channels, widths[0])] +
                                  [conv_block(widths[i - 1], widths[i], stride=2) for i in range(1, len(widths))])
        self.up = nn.ModuleList([nn.ConvTranspose2d(widths[i], widths[i - 1], 2, stride=2) for i in range(len(widths) - 1, 0, -1)])
        self.merge = nn.ModuleList([conv_block(2 * widths[i - 1], widths[i - 1]) for i in range(len(widths) - 1, 0, -1)])
        self.head = nn.Conv2d(widths[0], N_CLASSES, 1)

    def forward(self, x):
        """Class logits at 10 m, (B, 3, H, W)."""
        x = (x - self.mean[:, None, None]) / self.std[:, None, None]
        skips = []
        for block in self.down:
            x = block(x)
            skips.append(x)
        for up, merge, skip in zip(self.up, self.merge, reversed(skips[:-1])):
            x = merge(torch.cat([up(x), skip], dim=1))
        return self.head(x)


def probs_30m(logits):
    return F.avg_pool2d(logits.softmax(dim=1), 3)


def loss_fn(p30, labels):
    """Cross-entropy on the 30 m probabilities plus soft Dice over the batch (Milletari et al., 2016),
    both without the ignored cells. A class absent from the batch is left out of the Dice term: its
    Dice can only reach 1 by predicting it nowhere, and cross-entropy already penalizes it there."""
    keep = labels != dl.IGNORE
    ce = F.nll_loss(p30.clamp_min(1e-8).log(), labels, ignore_index=dl.IGNORE)
    onehot = F.one_hot(labels.clamp_min(0), N_CLASSES).permute(0, 3, 1, 2) * keep[:, None]
    p = p30 * keep[:, None]
    dice = (2 * (p * onehot).sum((0, 2, 3)) + 1e-5) / (p.sum((0, 2, 3)) + onehot.sum((0, 2, 3)) + 1e-5)
    present = onehot.sum((0, 2, 3)) > 0
    return ce + (1 - dice)[present].sum() / present.sum().clamp_min(1)


def device_name():
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def predict_counts(model, rows, device, batch_size=16):
    """dice_counts per tile, (N, 3, 3), for the given rows."""
    loader = DataLoader(dl.TileDataset(rows, model.tile_px), batch_size=batch_size)
    model.eval()
    counts = []
    with torch.no_grad():
        for images, labels in loader:
            pred = probs_30m(model(images.to(device))).argmax(1).cpu().numpy()
            counts += [classifier_report.dice_counts(p, l) for p, l in zip(pred, labels.numpy())]
    return np.stack(counts)


def predict_full(model, image, device):
    """30 m probabilities over a whole 192 px tile, (3, 64, 64), by windows of the model's tile size
    with half-window overlap, averaged (as nnU-Net does). Every window edge stays on the 30 m grid.
    Scoring every configuration on the whole tile puts all of them, and RF, on the same cells."""
    size, step = model.tile_px, model.tile_px // 2
    full = image.shape[-1]
    total = torch.zeros(N_CLASSES, full // 3, full // 3)
    weight = torch.zeros(full // 3, full // 3)
    starts = list(range(0, full - size + 1, step))
    windows = torch.stack([image[:, r:r + size, c:c + size] for r in starts for c in starts])
    with torch.no_grad():
        probs = probs_30m(model(windows.to(device))).cpu()
    for p, (r, c) in zip(probs, [(r, c) for r in starts for c in starts]):
        total[:, r // 3:(r + size) // 3, c // 3:(c + size) // 3] += p
        weight[r // 3:(r + size) // 3, c // 3:(c + size) // 3] += 1
    return total / weight


def predict_counts_full(model, rows, device):
    """classifier_report.dice_counts per whole 192 px tile, (N, 3, 3)."""
    model.eval()
    counts = []
    for image, label in dl.TileDataset(rows, 192):
        pred = predict_full(model, image, device).argmax(0).numpy()
        counts.append(classifier_report.dice_counts(pred, label.numpy()))
    return np.stack(counts)


def evaluate(model, rows, device):
    """On the whole 192 px tile, the cells 38 scores, so the epoch kept is the best on those cells."""
    dice, macro = classifier_report.dice_from_counts(predict_counts_full(model, rows, device).sum(axis=0))
    return {"dice": dict(zip(dl.CLASS_NAMES, dice.tolist())), "macro_dice": float(macro)}


def train(train_rows, val_rows, tile_px=96, lr=0.0003, batch_size=16, seed=42, max_epochs=MAX_EPOCHS, patience=None,
          verbose=True):
    """patience=None trains to max_epochs (the pilot). Keeps the weights of the best validation
    macro Dice. Returns the model, the device and the per-epoch history."""
    seed_everything(seed)
    device = device_name()
    model = UNet(tile_px)
    mean, std = dl.tile_channel_stats(train_rows, tile_px)
    model.mean.copy_(torch.from_numpy(mean))
    model.std.copy_(torch.from_numpy(std))
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loader = DataLoader(dl.TileDataset(train_rows, tile_px, augment=True), batch_size=batch_size, shuffle=True, drop_last=True)

    history = {"train_loss": [], "val_macro_dice": []}
    best, best_state, since_best = -math.inf, None, 0
    for epoch in range(1, max_epochs + 1):
        model.train()
        total, n = 0.0, 0
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = loss_fn(probs_30m(model(images)), labels)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(labels)
            n += len(labels)
        val = evaluate(model, val_rows, device)["macro_dice"]
        history["train_loss"].append(total / n)
        history["val_macro_dice"].append(val)
        if verbose and epoch % 5 == 0:
            print(f"  epoch {epoch}: train_loss={total / n:.3f} val_macro_dice={val:.3f}", flush=True)
        if val > best:
            best, since_best = val, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            since_best += 1
            if patience is not None and since_best >= patience:
                break
    model.load_state_dict(best_state)
    return model, device, history


def epochs(history):
    """Best epoch (highest validation macro Dice, the weights train() keeps) and the stop epoch."""
    return int(np.argmax(history["val_macro_dice"])) + 1, len(history["val_macro_dice"])


def save_checkpoint(model, seed, path=CHECKPOINT_PATH):
    torch.save({"state_dict": model.state_dict(), "seed": seed, "tile_px": model.tile_px}, path)


def load_checkpoint(path=CHECKPOINT_PATH, device=None):
    device = device or device_name()
    checkpoint = torch.load(path, map_location=device)
    model = UNet(checkpoint["tile_px"]).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, device


def main():
    """Overfit check: a handful of tiles, no augmentation, should reach a near-perfect Dice."""
    import glob
    import json
    rows = [json.loads(Path(p).read_text()) for p in sorted(glob.glob(str(dl.TILES_DIR / "data" / "*.json")))]
    rows = [r for r in rows if r["kept"] and r["px_pasto"] > 300][:4] + [r for r in rows if r["kept"] and r["px_cultivo"] > 300][:4]
    for tile_px in (48, 96, 192):
        model = UNet(tile_px)
        print(tile_px, "levels", n_levels(tile_px), "weights", sum(p.numel() for p in model.parameters()))
    seed_everything(0)
    device = device_name()
    model = UNet(96)
    mean, std = dl.tile_channel_stats(rows, 96)
    model.mean.copy_(torch.from_numpy(mean))
    model.std.copy_(torch.from_numpy(std))
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    images, labels = next(iter(DataLoader(dl.TileDataset(rows, 96), batch_size=len(rows))))
    images, labels = images.to(device), labels.to(device)
    for step in range(1, 301):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(probs_30m(model(images)), labels)
        loss.backward()
        optimizer.step()
        if step % 50 == 0:
            print(f"step {step}: loss={loss.item():.3f} {evaluate(model, rows, device)}")


if __name__ == "__main__":
    main()
