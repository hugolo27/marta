import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import hashlib
    import importlib
    import json
    import os
    import shutil
    import subprocess
    import sys
    import threading
    import time
    import urllib.error
    import urllib.request
    import zipfile
    from datetime import datetime, timezone
    from pathlib import Path

    import marimo as mo
    return (
        Path,
        datetime,
        hashlib,
        importlib,
        json,
        mo,
        os,
        shutil,
        subprocess,
        sys,
        threading,
        time,
        timezone,
        urllib,
        zipfile,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # U-Net selection on molab (phase1-segmentation, task 4.2)

    Runs `scripts/38_unet_selection.py score` on the molab GPU. The rules are the ones pre-registered in
    `data/study_area/unet_selection/README.md`; this notebook only moves files in and out:

    - clones the repo and downloads the 3,603 used tiles from a Google Drive link;
    - restores `results.json` from the `molab-state` branch, so each 12 h session resumes where the last one stopped;
    - pushes it back to that branch every time `38` saves a seed.

    **prueba** times two epochs per tile size and writes nothing to `results.json`.
    **seleccion** runs the real grid. The first selection session pins the commit, the GPU and the PyTorch
    version; later sessions refuse to run if any of them changed (README, Hardware).
    """)
    return


@app.cell
def _(mo):
    drive_url = mo.ui.text(label="Drive link to tiles_used.zip", full_width=True)
    gh_token = mo.ui.text(kind="password", label="GitHub token (contents: write on hugolo27/marta)")
    mode = mo.ui.dropdown(["prueba", "seleccion"], value="prueba", label="Mode")
    start = mo.ui.run_button(label="Run")
    mo.vstack([drive_url, gh_token, mode, start])
    return drive_url, gh_token, mode, start


@app.cell
def _(Path):
    REPO = Path.home() / "marta"
    STATE_DIR = Path.home() / "molab-state"
    BRANCH = "feat/phase1-segmentation"
    STATE_BRANCH = "molab-state"
    TILES_ZIP = Path.home() / "tiles_used.zip"
    TILES_SHA256 = "1ab2579a8043b340047490cf7760643263b4f507a7e9c1172a9e8d486139933c"
    RESULTS = REPO / "data" / "study_area" / "unet_selection" / "results.json"
    return BRANCH, REPO, RESULTS, STATE_BRANCH, STATE_DIR, TILES_SHA256, TILES_ZIP


@app.cell
def _(STATE_DIR, gh_token, json, mo, start, subprocess, sys, urllib):
    mo.stop(not start.value)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown==6.5.1", "mlflow==3.16.0", "scikit-learn==1.9.0"],
                   check=True)
    token = gh_token.value.strip()
    # Fail before the 4 GB download, not after the probe
    _req = urllib.request.Request("https://api.github.com/repos/hugolo27/marta",
                                  headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    try:
        _perms = json.loads(urllib.request.urlopen(_req).read())["permissions"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub rejected the token ({e.code}): copy it again, it starts with github_pat_") from None
    if not _perms["push"]:
        raise RuntimeError("the token cannot write to hugolo27/marta: give it Contents read and write")
    remote = f"https://hugolo27:{token}@github.com/hugolo27/marta.git"

    def git(*args, cwd=STATE_DIR):
        r = subprocess.run(["git", "-c", "user.name=hugolo27", "-c", "user.email=hugolo27@users.noreply.github.com",
                            *args], cwd=cwd, capture_output=True, text=True)
        if r.returncode:
            # The remote URL carries the token
            raise RuntimeError(f"git {args[0]} failed: {(r.stdout + r.stderr).replace(token, '***')}")
        return r.stdout.strip()
    return git, remote


@app.cell
def _(
    BRANCH,
    REPO,
    RESULTS,
    STATE_BRANCH,
    STATE_DIR,
    TILES_SHA256,
    TILES_ZIP,
    drive_url,
    git,
    hashlib,
    json,
    remote,
    shutil,
    zipfile,
):
    import gdown

    if not STATE_DIR.exists():
        git("clone", "-q", "--branch", STATE_BRANCH, remote, str(STATE_DIR), cwd=None)
    # A token pasted again in the same session must replace the one saved by the clone
    git("remote", "set-url", "origin", remote)
    git("pull", "-q")
    sessions_path = STATE_DIR / "sessions.json"
    sessions = json.loads(sessions_path.read_text()) if sessions_path.exists() else []

    if not REPO.exists():
        git("clone", "-q", "--branch", BRANCH, "https://github.com/hugolo27/marta.git", str(REPO), cwd=None)
    if sessions:
        # Same code for every selection session: the first one pinned the commit
        git("checkout", "-q", sessions[0]["commit"], cwd=REPO)
    commit = git("rev-parse", "HEAD", cwd=REPO)

    if not TILES_ZIP.exists():
        gdown.download(drive_url.value.strip(), str(TILES_ZIP), quiet=False)
    digest = hashlib.sha256()
    with open(TILES_ZIP, "rb") as _f:
        for chunk in iter(lambda: _f.read(1 << 24), b""):
            digest.update(chunk)
    if digest.hexdigest() != TILES_SHA256:
        raise ValueError("tiles zip does not match the one built from final_split.json")
    with zipfile.ZipFile(TILES_ZIP) as z:
        z.extractall(REPO)
        n_tiles = len(z.namelist())

    if (STATE_DIR / "results.json").exists():
        shutil.copy(STATE_DIR / "results.json", RESULTS)
    print(f"commit {commit}, {n_tiles} tiles, {len(sessions)} earlier selection sessions")
    return commit, sessions


@app.cell
def _(STATE_DIR, git, shutil):
    def push(local, name):
        shutil.copy(local, STATE_DIR / name)
        git("add", name)
        if git("status", "--porcelain"):
            git("commit", "-q", "-m", f"[docs] Update {name}")
            git("push", "-q", "origin", "HEAD")
    return (push,)


@app.cell
def _(REPO, commit, importlib, sys):
    sys.path.insert(0, str(REPO / "scripts"))
    selection_script = importlib.import_module("38_unet_selection")
    unet = selection_script.unet

    def torch_info():
        import torch
        return {"device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no cuda",
                "torch": torch.__version__, "cuda": torch.version.cuda}

    print(commit, torch_info())
    return selection_script, torch_info, unet


@app.cell
def _(json, mo, mode, push, selection_script, time, torch_info, unet):
    mo.stop(mode.value != "prueba")
    data = selection_script.splits()
    probe = {**torch_info(), "seconds_per_epoch": {}}
    for tile_px in selection_script.UNET_GRID["tile_px"]:
        t0 = time.time()
        # Two epochs, scores discarded: this only times the loop, it is not a selection run
        unet.train(data["train"], data["val"], tile_px=tile_px, lr=0.0003, batch_size=16, seed=42, max_epochs=2,
                   verbose=False, random_window=True)
        probe["seconds_per_epoch"][tile_px] = (time.time() - t0) / 2
        print(f"tile {tile_px}: {probe['seconds_per_epoch'][tile_px]:.1f} s per epoch", flush=True)
    with open("probe.json", "w") as _f:
        json.dump(probe, _f, indent=2)
    push("probe.json", "probe.json")
    print("probe.json pushed to molab-state")
    return


@app.cell
def _(
    REPO,
    RESULTS,
    commit,
    datetime,
    json,
    mo,
    mode,
    os,
    push,
    sessions,
    subprocess,
    sys,
    threading,
    time,
    timezone,
    torch_info,
):
    mo.stop(mode.value != "seleccion")
    info = torch_info()
    if sessions and {k: sessions[0][k] for k in info} != info:
        raise SystemExit(f"selection started on {sessions[0]}, this session has {info}: runs are never mixed")
    sessions.append({**info, "commit": commit, "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    with open("sessions.json", "w") as _f:
        json.dump(sessions, _f, indent=2)
    push("sessions.json", "sessions.json")

    seen = {}
    lock = threading.Lock()

    def sync():
        with lock:
            if RESULTS.exists() and seen.get("mtime") != RESULTS.stat().st_mtime:
                seen["mtime"] = RESULTS.stat().st_mtime
                push(RESULTS, "results.json")

    proc = subprocess.Popen([sys.executable, "scripts/38_unet_selection.py", "score"], cwd=REPO, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            # molab's Python does not put the script's own folder on the path, so 38 cannot import its siblings
                            env={**os.environ, "MLFLOW_DISABLE_AGENT_HINT": "1", "PYTHONPATH": str(REPO / "scripts")})

    def watch():
        while proc.poll() is None:
            sync()
            time.sleep(60)

    threading.Thread(target=watch, daemon=True).start()
    for line in proc.stdout:
        print(line, end="", flush=True)
    proc.wait()
    sync()
    print(f"38 score exited with {proc.returncode}")
    return


if __name__ == "__main__":
    app.run()
