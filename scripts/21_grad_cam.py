"""Seg-Grad-CAM (+ guided backpropagation) for the operational U-Net (phase1-segmentation D6). For
segmentation the score explained is the class logit summed over a region of the output, not one
label per patch (Vinogradova et al., 2020); the rest is Grad-CAM (Selvaraju et al., 2017): spatially
averaged gradients of that score as per-channel weights of the target layer's activations, ReLU of
the weighted sum. The target layer is the bottleneck (the last encoder block, 6x6 on a 48 px window),
the one Vinogradova et al. show, and the map is sharpened with guided backpropagation at 10 m, as
the CNN's was. Hooks are homegrown, not a library, as before; Random Forest has no gradients or
activation maps for this to attach to. The 33x33 CNN version is in git history.
Usage: .venv/bin/python scripts/21_grad_cam.py (class-specificity check on a training tile)"""

import importlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import dataset_loader as dl

unet = importlib.import_module("36_train_unet")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area"
RGB_IDX = [3, 2, 1]  # B4, B3, B2 in S2_BANDS, matches 13_visualize_classification_map.py


def _minmax(arr):
    lo, hi = arr.min(), arr.max()
    return (arr - lo) / (hi - lo + 1e-8)


def region_score(logits, region_10m, target_class):
    return (logits[0, target_class] * region_10m).sum()


def seg_grad_cam(model, window_chw, region_10m, target_class, device):
    """window_chw: (26, S, S) float tensor; region_10m: (S, S) 0/1 tensor. Returns the native CAM
    of the bottleneck, normalized to [0, 1]."""
    if not isinstance(model, unet.UNet):
        raise TypeError("Seg-Grad-CAM applies to the U-Net only: Random Forest has no gradients or activation maps")
    store = {}
    layer = model.down[-1]
    fh = layer.register_forward_hook(lambda m, i, o: store.update(act=o.detach()))
    bh = layer.register_full_backward_hook(lambda m, gi, go: store.update(grad=go[0].detach()))
    try:
        model.zero_grad()
        region_score(model(window_chw[None].to(device)), region_10m.to(device), target_class).backward()
    finally:
        fh.remove()
        bh.remove()
    weights = store["grad"].mean(dim=(2, 3), keepdim=True)
    cam = torch.relu((weights * store["act"]).sum(dim=1))[0]
    return _minmax(cam.cpu().numpy())


def guided_backprop_saliency(model, window_chw, region_10m, target_class, device):
    """Pixel-level saliency at 10 m: negative gradients are zeroed at every LeakyReLU on the way
    back. Not class-discriminative on its own, only combined with the CAM."""
    handles = [m.register_full_backward_hook(lambda m, gi, go: (torch.clamp(gi[0], min=0.0),))
               for m in model.modules() if isinstance(m, nn.LeakyReLU)]
    try:
        model.zero_grad()
        x = window_chw.clone()[None].to(device).requires_grad_(True)
        region_score(model(x), region_10m.to(device), target_class).backward()
        return _minmax(x.grad.detach()[0].abs().amax(dim=0).cpu().numpy())
    finally:
        for h in handles:
            h.remove()


def guided_seg_grad_cam(model, window_chw, region_10m, target_class, device):
    """The CAM (knows the class, 6x6 native) upsampled to the window and multiplied by the guided
    saliency (10 m, does not know the class): keeps only the detail inside what the CAM already
    marks, without making up resolution. The native CAM stays in the result."""
    raw = seg_grad_cam(model, window_chw, region_10m, target_class, device)
    size = window_chw.shape[-1]
    up = F.interpolate(torch.from_numpy(raw)[None, None].float(), size=(size, size), mode="bilinear", align_corners=False)[0, 0].numpy()
    saliency = guided_backprop_saliency(model, window_chw, region_10m, target_class, device)
    return {"raw_cam": raw, "cam_upsampled": up, "guided_saliency": saliency, "sharpened": _minmax(up * saliency)}


def render_overlay(window_hwc, heatmap, region_10m, title, out_path, cam_px):
    """Overlay on true color (B4/B3/B2, /3000 clipped to [0, 1]), with the explained region outlined."""
    rgb = np.clip(window_hwc[:, :, RGB_IDX] / 3000, 0, 1)
    fig, axes = plt.subplots(1, 2, figsize=(6, 3.2))
    axes[0].imshow(rgb)
    axes[0].set_title("True color")
    axes[1].imshow(rgb)
    axes[1].imshow(heatmap, cmap="jet", alpha=0.5)
    axes[1].set_title(f"Guided Seg-Grad-CAM ({cam_px}x{cam_px} native)")
    for ax in axes:
        ax.contour(region_10m, levels=[0.5], colors="white", linewidths=1)
        ax.axis("off")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    """The CAM must depend on the class explained: on one window of a training tile, the predicted
    class and another class over the same region give different maps; and a non-U-Net is refused."""
    import glob
    import json

    model, device = unet.load_checkpoint()
    path = next(p for p in sorted(glob.glob(str(dl.TILES_DIR / "data" / "*.json"))) if json.loads(Path(p).read_text())["kept"])
    image, _ = dl.load_tile(json.loads(Path(path).read_text())["path"], model.tile_px)
    window = torch.from_numpy(np.ascontiguousarray(dl.tile_to_float(image).transpose(2, 0, 1)))
    with torch.no_grad():
        pred = unet.probs_30m(model(window[None].to(device)))[0].argmax(0).cpu().numpy()
    cls = int(np.bincount(pred.ravel()).argmax())
    region = torch.from_numpy(np.kron(pred == cls, np.ones((3, 3)))).float()
    cam_pred = seg_grad_cam(model, window, region, cls, device)
    cam_other = seg_grad_cam(model, window, region, (cls + 1) % len(dl.CLASS_NAMES), device)
    diff = float(np.abs(cam_pred - cam_other).mean())
    print(f"CAM({dl.CLASS_NAMES[cls]}) vs CAM(other class) over the same region, mean abs diff = {diff:.4f} "
          f"({'class-specific' if diff > 0.01 else 'WARNING: barely differs'})")
    try:
        seg_grad_cam("not a model", window, region, cls, device)
    except TypeError as e:
        print(f"non-U-Net refused: {e}")


if __name__ == "__main__":
    main()
