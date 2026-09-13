"""CNN candidate, phase1-classifier tasks 3.1-3.3. Small custom architecture (not a pretrained
backbone, see design.md), rotation/flip augmentation, early stopping. Hyperparameters and their
justification are in docs/METODOLOGIA_PIPELINE.md, "Training hyperparameters"."""

import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

import classifier_report
import dataset_loader as dl

BATCH_SIZE = 32
LEARNING_RATE = 0.001
MAX_EPOCHS = 100
EARLY_STOP_PATIENCE = 10
DROPOUT = 0.4
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"
CHECKPOINT_PATH = OUT_DIR / "cnn_checkpoint.pt"


class SmallCNN(nn.Module):
    def __init__(self, in_channels=13, n_classes=3, dropout=DROPOUT):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(nn.Dropout(dropout), nn.Linear(128, n_classes))

    def forward(self, x):
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


def train(seed=42, verbose=True):
    seed_everything(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    train_loader = DataLoader(dl.PatchDataset("train", augment=True), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(dl.PatchDataset("val", augment=False), batch_size=BATCH_SIZE)

    model = SmallCNN().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    best_val_loss, patience_left, best_state = float("inf"), EARLY_STOP_PATIENCE, None
    for epoch in range(1, MAX_EPOCHS + 1):
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


def evaluate(model, device, split="test"):
    loader = DataLoader(dl.PatchDataset(split, augment=False), batch_size=BATCH_SIZE)
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
    torch.save({"state_dict": model.state_dict(), "seed": seed}, path)


def load_checkpoint(path=CHECKPOINT_PATH, device=None):
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(path, map_location=device)
    model = SmallCNN().to(device)
    model.load_state_dict(checkpoint["state_dict"])
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
    print("Training CNN...")
    model, device, history = train()
    plot_training_curve(history)
    results = evaluate(model, device)
    classifier_report.print_evaluation(results, "CNN")
    save_checkpoint(model, seed=42)
    print(f"checkpoint saved: {CHECKPOINT_PATH}")


if __name__ == "__main__":
    main()
