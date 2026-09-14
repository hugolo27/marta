"""Grad-CAM (+ Guided Grad-CAM) for the operational CNN, phase1-grad-cam tasks 1.1-2.2. Hooks
SmallCNN's last conv block (128 channels, 8x8 spatial on a 33x33 input -- the only layer with
spatial structure left before AdaptiveAvgPool2d(1) collapses it) rather than a library, matching
this project's homegrown-over-dependency preference for small, well-understood algorithms
(design.md). CNN-only by construction: Random Forest has no gradients or spatial activation maps
for Grad-CAM to attach to.
Usage: .venv/bin/python scripts/21_grad_cam.py"""

import importlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import dataset_loader as dl

train_cnn = importlib.import_module("10_train_cnn")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area"
RGB_IDX = [3, 2, 1]  # B4, B3, B2 in S2_BANDS, matches 13_visualize_classification_map.py


class GradCAM:
    """Standard Grad-CAM (Selvaraju et al. 2017): global-average-pooled gradients as per-channel
    weights, ReLU on the weighted activation sum. One instance is scoped to a single forward+
    backward pass -- always used through guided_grad_cam(), never left registered on the model."""

    def __init__(self, model):
        if not isinstance(model, train_cnn.SmallCNN):
            raise TypeError(
                "Grad-CAM only applies to the operational CNN -- Random Forest has no gradients "
                "or spatial activation maps to attach to (structural, not a missing feature)."
            )
        self.model = model
        self.target_layer = model.features[-1]  # last ReLU of the 3rd conv block
        self.activations = None
        self.gradients = None
        self._fh = self.target_layer.register_forward_hook(self._forward_hook)
        self._bh = self.target_layer.register_full_backward_hook(self._backward_hook)

    def _forward_hook(self, module, inputs, output):
        self.activations = output.detach()

    def _backward_hook(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def raw_cam(self, patch_chw, target_class, device):
        """patch_chw: (13, 33, 33) tensor. Returns the native 8x8 CAM, min-max normalized to
        [0, 1] -- attributed to target_class specifically (a different target_class on the same
        patch produces a different CAM, verified in main() rather than assumed)."""
        self.model.zero_grad()
        x = patch_chw.unsqueeze(0).to(device)
        logits = self.model(x)
        score = logits[0, target_class]
        score.backward()

        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * self.activations).sum(dim=1, keepdim=True))
        cam = cam.squeeze().cpu().numpy()
        return _minmax(cam)

    def remove(self):
        self._fh.remove()
        self._bh.remove()


def _minmax(arr):
    lo, hi = arr.min(), arr.max()
    return (arr - lo) / (hi - lo + 1e-8)


def upsample_cam(cam, size):
    t = torch.from_numpy(cam).float()[None, None]
    up = F.interpolate(t, size=(size, size), mode="bilinear", align_corners=False)
    return up[0, 0].numpy()


def _register_guided_relu_hooks(model):
    """Guided backpropagation: on top of ReLU's own backward (zeroing where the forward
    activation was <=0), also zero incoming gradients that are negative -- the "guided" half of
    Guided Grad-CAM. Hooks are removed right after use (guided_backprop_saliency's `finally`),
    never left registered for the model's ordinary forward/backward passes elsewhere."""
    handles = []

    def hook(module, grad_input, grad_output):
        return (torch.clamp(grad_input[0], min=0.0),)

    for module in model.modules():
        if isinstance(module, nn.ReLU):
            handles.append(module.register_full_backward_hook(hook))
    return handles


def guided_backprop_saliency(model, patch_chw, target_class, device):
    """Pixel-level saliency at the input's own 33x33 resolution -- not class-discriminative on
    its own (same edges light up regardless of target_class), only useful combined with
    Grad-CAM's class-specific localization (guided_grad_cam)."""
    handles = _register_guided_relu_hooks(model)
    try:
        model.zero_grad()
        x = patch_chw.clone().unsqueeze(0).to(device)
        x.requires_grad_(True)
        logits = model(x)
        score = logits[0, target_class]
        score.backward()
        saliency = x.grad.detach().squeeze(0).abs().amax(dim=0)  # max over 13 input channels
        return _minmax(saliency.cpu().numpy())
    finally:
        for h in handles:
            h.remove()


def guided_grad_cam(model, patch_chw, target_class, device):
    """Combines Grad-CAM (knows the class, 8x8 native) with guided backprop (33x33 native,
    doesn't know the class) by elementwise multiplication -- keeps only the fine detail inside
    the region Grad-CAM already identified as relevant, rather than fabricating resolution
    (design.md). Returns the raw 8x8 CAM, its upsample, the guided saliency, and the combined
    sharpened map, all normalized to [0, 1] -- the 8x8-vs-33x33 native resolutions are kept
    visible in the return value rather than hidden."""
    gc = GradCAM(model)
    try:
        raw_cam = gc.raw_cam(patch_chw, target_class, device)
    finally:
        gc.remove()
    cam_upsampled = upsample_cam(raw_cam, size=patch_chw.shape[-1])
    saliency = guided_backprop_saliency(model, patch_chw, target_class, device)
    sharpened = _minmax(cam_upsampled * saliency)
    return {
        "raw_cam_8x8": raw_cam, "cam_upsampled": cam_upsampled,
        "guided_saliency": saliency, "sharpened": sharpened,
    }


def render_overlay(patch_hwc, heatmap, title, out_path):
    """Overlay on true color, not a bare heatmap -- same true-color normalization as
    13_visualize_classification_map.py (B4/B3/B2, /3000 clipped to [0,1])."""
    rgb = np.clip(patch_hwc[:, :, RGB_IDX] / 3000, 0, 1)
    fig, axes = plt.subplots(1, 2, figsize=(6, 3.2))
    axes[0].imshow(rgb)
    axes[0].set_title("True color")
    axes[1].imshow(rgb)
    axes[1].imshow(heatmap, cmap="jet", alpha=0.5)
    axes[1].set_title("Guided Grad-CAM (8x8 native, upsampled)")
    for ax in axes:
        ax.axis("off")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, device = train_cnn.load_checkpoint(device=device)
    print(f"Loaded checkpoint: {train_cnn.CHECKPOINT_PATH}")

    # Task 1.2: confirm the CAM is attributed to the predicted class specifically, not a fixed
    # class -- compare it against a different target class on the same patch.
    example_row = dl.load_manifest("train")[0]
    example_patch = np.load(REPO_ROOT / example_row["path"]).astype(np.float32)
    example_chw = torch.from_numpy(np.ascontiguousarray(example_patch.transpose(2, 0, 1)))
    pred_class = int(model(example_chw.unsqueeze(0).to(device)).argmax(1).item())
    other_class = (pred_class + 1) % len(dl.CLASS_NAMES)
    cam_pred = guided_grad_cam(model, example_chw, pred_class, device)["raw_cam_8x8"]
    cam_other = guided_grad_cam(model, example_chw, other_class, device)["raw_cam_8x8"]
    cam_diff = float(np.abs(cam_pred - cam_other).mean())
    print(f"Sanity check: CAM(predicted class) vs CAM(other class) mean abs diff = {cam_diff:.4f} "
          f"({'class-specific, good' if cam_diff > 0.01 else 'WARNING: barely differs'})")

    # Task 1.3: refuse for a non-CNN model.
    try:
        GradCAM(model="not a model")
    except TypeError as e:
        print(f"Sanity check: non-CNN input correctly refused -- {e}")

    # Task 2.2: one example overlay per class.
    for class_name in dl.CLASS_NAMES:
        row = next(r for r in dl.load_manifest("train") if r["class"] == class_name)
        patch = np.load(REPO_ROOT / row["path"]).astype(np.float32)
        patch_chw = torch.from_numpy(np.ascontiguousarray(patch.transpose(2, 0, 1)))
        pred = int(model(patch_chw.unsqueeze(0).to(device)).argmax(1).item())
        result = guided_grad_cam(model, patch_chw, pred, device)
        out_path = OUT_DIR / f"gradcam_example_{class_name}.png"
        render_overlay(patch, result["sharpened"], f"{class_name} (predicted: {dl.CLASS_NAMES[pred]})", out_path)
        print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
