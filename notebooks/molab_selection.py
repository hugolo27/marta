import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import hashlib
    import importlib
    import json
    import os
    import sqlite3
    import subprocess
    import sys
    import threading
    import time
    import zipfile
    from datetime import datetime, timezone
    from pathlib import Path
    from shutil import copy as shutil_copy

    import marimo as mo
    return (
        Path,
        datetime,
        hashlib,
        importlib,
        json,
        mo,
        os,
        shutil_copy,
        sqlite3,
        subprocess,
        sys,
        threading,
        time,
        timezone,
        zipfile,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # U-Net selection on molab (phase1-segmentation, tasks 4.2)

    Runs `scripts/38_unet_selection.py score` on the molab GPU. The rules are the ones pre-registered in
    `data/study_area/unet_selection/README.md`; this notebook only moves files in and out:

    - clones the repo and downloads the 3,603 used tiles from a private Hugging Face dataset;
    - restores `results.json` and `mlflow.db` from the dataset, so each 12 h session resumes where the last one stopped;
    - uploads both every time `38` saves a seed.

    **prueba** times two epochs per tile size and writes nothing to `results.json`.
    **seleccion** runs the real grid. The first selection session pins the commit, the GPU and the PyTorch
    version; later sessions refuse to run if any of them changed (README, Hardware).
    """)
    return


@app.cell
def _(mo):
    token = mo.ui.text(kind="password", label="Hugging Face token (write)")
    dataset = mo.ui.text(label="Dataset (user/name)")
    mode = mo.ui.dropdown(["prueba", "seleccion"], value="prueba", label="Mode")
    start = mo.ui.run_button(label="Run")
    mo.vstack([token, dataset, mode, start])
    return dataset, mode, start, token


@app.cell
def _(Path):
    REPO = Path.home() / "marta"
    BRANCH = "feat/phase1-segmentation"
    TILES_ZIP = "tiles_used.zip"
    TILES_SHA256 = "1ab2579a8043b340047490cf7760643263b4f507a7e9c1172a9e8d486139933c"
    SELECTION_DIR = REPO / "data" / "study_area" / "unet_selection"
    # Local path -> path in the dataset
    STATE = {SELECTION_DIR / "results.json": "state/results.json", REPO / "mlflow.db": "state/mlflow.db"}
    SESSIONS = "state/sessions.json"
    return BRANCH, REPO, SELECTION_DIR, SESSIONS, STATE, TILES_SHA256, TILES_ZIP


@app.cell
def _(dataset, mo, start, subprocess, sys, token):
    mo.stop(not start.value)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub", "mlflow==3.16.0", "scikit-learn==1.9.0"],
                   check=True)
    from huggingface_hub import HfApi, hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError

    api = HfApi(token=token.value)
    repo_id = dataset.value.strip()

    def fetch(name):
        try:
            return hf_hub_download(repo_id, name, repo_type="dataset", token=token.value, force_download=True)
        except EntryNotFoundError:
            return None

    def push(local, name):
        api.upload_file(path_or_fileobj=str(local), path_in_repo=name, repo_id=repo_id, repo_type="dataset",
                        commit_message=f"Update {name}")
    return fetch, hf_hub_download, push, repo_id


@app.cell
def _(
    BRANCH,
    REPO,
    SESSIONS,
    STATE,
    TILES_SHA256,
    TILES_ZIP,
    fetch,
    hashlib,
    hf_hub_download,
    json,
    repo_id,
    shutil_copy,
    subprocess,
    token,
    zipfile,
):
    sessions_path = fetch(SESSIONS)
    sessions = json.loads(open(sessions_path).read()) if sessions_path else []
    if not REPO.exists():
        subprocess.run(["git", "clone", "--branch", BRANCH, "https://github.com/hugolo27/marta.git", str(REPO)], check=True)
    if sessions:
        # Same code for every selection session: the first one pinned the commit
        subprocess.run(["git", "-C", str(REPO), "checkout", "-q", sessions[0]["commit"]], check=True)
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    zip_path = hf_hub_download(repo_id, TILES_ZIP, repo_type="dataset", token=token.value)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if not all((REPO / n).exists() for n in names):
            digest = hashlib.sha256()
            with open(zip_path, "rb") as _f:
                for chunk in iter(lambda: _f.read(1 << 24), b""):
                    digest.update(chunk)
            if digest.hexdigest() != TILES_SHA256:
                raise ValueError("tiles zip does not match the one built from final_split.json")
            z.extractall(REPO)

    for local, name in STATE.items():
        remote = fetch(name)
        if remote:
            shutil_copy(remote, local)
    print(f"commit {commit}, {len(names)} tiles, {len(sessions)} earlier selection sessions")
    return commit, sessions


@app.cell
def _(REPO, importlib, sys, torch_info):
    sys.path.insert(0, str(REPO / "scripts"))
    selection_script = importlib.import_module("38_unet_selection")
    unet = selection_script.unet
    print(torch_info())
    return selection_script, unet


@app.cell
def _():
    def torch_info():
        import torch
        return {"device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no cuda",
                "torch": torch.__version__, "cuda": torch.version.cuda}
    return (torch_info,)


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
    push("probe.json", "state/probe.json")
    print("probe.json uploaded")
    return


@app.cell
def _(
    REPO,
    SESSIONS,
    STATE,
    commit,
    datetime,
    json,
    mo,
    mode,
    os,
    push,
    sessions,
    sqlite3,
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
    push("sessions.json", SESSIONS)

    def snapshot(local):
        # mlflow.db may be mid-write: upload a consistent copy, not the live file
        if local.suffix != ".db":
            return local
        copy = local.with_name("upload.db")
        with sqlite3.connect(local) as src, sqlite3.connect(copy) as dst:
            src.backup(dst)
        return copy

    seen = {}

    def sync():
        for local, name in STATE.items():
            if local.exists() and seen.get(local) != local.stat().st_mtime:
                seen[local] = local.stat().st_mtime
                push(snapshot(local), name)

    proc = subprocess.Popen([sys.executable, "scripts/38_unet_selection.py", "score"], cwd=REPO, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env={**os.environ, "MLFLOW_DISABLE_AGENT_HINT": "1"})

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
