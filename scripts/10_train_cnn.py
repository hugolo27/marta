"""CNN candidate, phase1-classifier tasks 3.1-3.3. Small custom architecture (not a pretrained
backbone, see design.md), rotation/flip augmentation, early stopping. Hyperparameters and their
justification are in docs/METODOLOGIA_PIPELINE.md, "Training hyperparameters".
Run directly (`main()`), logs the reference checkpoint's run to MLflow (experiment
"phase1-classifier") -- train()/evaluate() called from elsewhere (11_compare_classifiers.py,
holdout_eval.py) log their own runs there instead, to avoid double-logging the same training."""

import random
from pathlib import Path

import mlflow
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

import classifier_report
import dataset_loader as dl

BATCH_SIZE = 32
LEARNING_RATE = 0.0001
MAX_EPOCHS = 100
EARLY_STOP_PATIENCE = 10
DROPOUT = 0.3
PATCH_PX = 3
SEASON = "drywet"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"
CHECKPOINT_PATH = OUT_DIR / "cnn_checkpoint.pt"
EXPERIMENT_NAME = "phase1-classifier"


class SmallCNN(nn.Module):
    """patch_px=3 crops the central 3x3 block (one MapBiomas pixel) out of whatever patch it gets,
    so the 33x33 data paths stay as they are; a 3x3 map can't be pooled twice (phase1-patch-size D1).
    The input is normalized per channel inside the model (train-split mean and std, set by train()
    and saved with the weights), so every caller feeds raw patches and gets the same scaling
    (phase1-dataset-v2). Bands are in the thousands and NDVI below 1, so unscaled, NDVI barely
    reaches the first layer."""

    def __init__(self, n_classes=3, dropout=DROPOUT, patch_px=PATCH_PX, season=SEASON):
        super().__init__()
        self.patch_px, self.season = patch_px, season
        in_channels = dl.SEASON_CHANNELS[season].stop
        self.register_buffer("mean", torch.zeros(in_channels))
        self.register_buffer("std", torch.ones(in_channels))
        pool = nn.MaxPool2d(2) if patch_px > 3 else nn.Identity()
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), pool,
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), pool,
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(nn.Dropout(dropout), nn.Linear(128, n_classes))

    def forward(self, x):
        start = (x.shape[-1] - self.patch_px) // 2
        # A dry model fed a dry+wet patch keeps the dry channels, so callers can always pull both.
        x = x[:, :len(self.mean), start:start + self.patch_px, start:start + self.patch_px]
        x = (x - self.mean[:, None, None]) / self.std[:, None, None]
        x = self.features(x)
        x = self.pool(x).flatten(1)
        return self.classifier(x)


def run_epoch(model, loader, optimizer, device, train=True):
    model.train() if train else model.eval()
    total_loss, correct, n = 0.0, 0, 0
    criterion = nn.CrossEntropyLoss()
    with torch.set_grad_enabled(train):
        for patches, labels in loader:
            patches, labels = patches.to(device), labels.to(device)
            if train:
                optimizer.zero_grad()
            logits = model(patches)
            loss = criterion(logits, labels)
            if train:
                loss.backward()
                optimizer.step()
            total_loss += loss.item() * len(labels)
            correct += (logits.argmax(1) == labels).sum().item()
            n += len(labels)
    return total_loss / n, correct / n


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def train(seed=42, verbose=True, batch_size=BATCH_SIZE, lr=LEARNING_RATE, dropout=DROPOUT, max_epochs=MAX_EPOCHS,
          patch_px=PATCH_PX, season=SEASON):
    seed_everything(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    train_loader = DataLoader(dl.PatchDataset("train", augment=True, season=season), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(dl.PatchDataset("val", augment=False, season=season), batch_size=batch_size)

    model = SmallCNN(dropout=dropout, patch_px=patch_px, season=season)
    mean, std = dl.channel_stats(season)
    model.mean.copy_(torch.from_numpy(mean))
    model.std.copy_(torch.from_numpy(std))
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    best_val_loss, patience_left, best_state = float("inf"), EARLY_STOP_PATIENCE, None
    for epoch in range(1, max_epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, optimizer, device, train=True)
        val_loss, val_acc = run_epoch(model, val_loader, optimizer, device, train=False)
        for key, value in [("train_loss", train_loss), ("val_loss", val_loss), ("train_acc", train_acc), ("val_acc", val_acc)]:
            history[key].append(value)
        if verbose and epoch % 5 == 0:
            print(f"  epoch {epoch}: train_loss={train_loss:.3f} val_loss={val_loss:.3f} "
                  f"train_acc={train_acc:.3f} val_acc={val_acc:.3f}")

        if val_loss < best_val_loss:
            best_val_loss, patience_left = val_loss, EARLY_STOP_PATIENCE
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_left -= 1
            if patience_left == 0:
                if verbose:
                    print(f"  early stop at epoch {epoch} (best val_loss={best_val_loss:.3f})")
                break

    model.load_state_dict(best_state)
    return model, device, history


def epochs(history):
    """Best epoch (lowest val loss, the weights train() keeps) and the epoch training stopped at."""
    return int(np.argmin(history["val_loss"])) + 1, len(history["val_loss"])


def evaluate(model, device, split="test"):
    loader = DataLoader(dl.PatchDataset(split, augment=False, season=model.season), batch_size=BATCH_SIZE)
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for patches, labels in loader:
            logits = model(patches.to(device))
            all_preds.append(logits.argmax(1).cpu().numpy())
            all_labels.append(labels.numpy())
    y_pred, y_true = np.concatenate(all_preds), np.concatenate(all_labels)
    return classifier_report.evaluate_predictions(y_true, y_pred)


def save_checkpoint(model, seed, path=CHECKPOINT_PATH):
    """Persists trained weights so a downstream script (phase1-temporal-comparison) can apply
    the exact same decision boundary to more than one date, instead of retraining per use --
    every prior phase1-classifier script trained transiently since none needed that (design.md)."""
    torch.save({"state_dict": model.state_dict(), "seed": seed, "patch_px": model.patch_px, "season": model.season}, path)


def load_checkpoint(path=CHECKPOINT_PATH, device=None):
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(path, map_location=device)
    model = SmallCNN(patch_px=checkpoint.get("patch_px", 33), season=checkpoint.get("season", "dry")).to(device)
    # checkpoints from before phase1-dataset-v2 have no mean/std: they keep the identity defaults
    model.load_state_dict({**model.state_dict(), **checkpoint["state_dict"]})
    model.eval()
    return model, device


def plot_training_curve(history, out_path=OUT_DIR / "cnn_training_curve.png"):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(history["train_loss"], label="train", color="#2a78d6")
    axes[0].plot(history["val_loss"], label="val", color="#d95926")
    axes[0].set_title("Loss"); axes[0].legend(); axes[0].set_xlabel("epoch")
    axes[1].plot(history["train_acc"], label="train", color="#2a78d6")
    axes[1].plot(history["val_acc"], label="val", color="#d95926")
    axes[1].set_title("Accuracy"); axes[1].legend(); axes[1].set_xlabel("epoch")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"training curve saved: {out_path}")


def main():
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="reference_checkpoint_seed42"):
        print("Training CNN...")
        model, device, history = train()
        plot_training_curve(history)
        results = evaluate(model, device)
        classifier_report.print_evaluation(results, "CNN")
        save_checkpoint(model, seed=42)
        print(f"checkpoint saved: {CHECKPOINT_PATH}")

        best_epoch, stop_epoch = epochs(history)
        mlflow.log_params({
            "seed": 42, "batch_size": BATCH_SIZE, "lr": LEARNING_RATE, "dropout": DROPOUT, "patch_px": PATCH_PX, "season": SEASON,
            "best_epoch": best_epoch, "stop_epoch": stop_epoch,
        })
        mlflow.log_metric("macro_f1", results["report"]["macro avg"]["f1-score"])
        mlflow.log_metric("accuracy", results["report"]["accuracy"])
        for cls, iou in zip(dl.CLASS_NAMES, results["iou_per_class"]):
            mlflow.log_metric(f"iou_{cls}", iou)
        mlflow.log_artifact(str(CHECKPOINT_PATH))
        mlflow.log_artifact(str(OUT_DIR / "cnn_training_curve.png"))


if __name__ == "__main__":
    main()
