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
    **test** runs the runs of `38 test` once, on the same commit and GPU: the five U-Nets, then the five
    Random Forests, each in its own process. Each run is pushed to `test_runs.json` as it ends, so a
    reclaimed sandbox resumes at the next one; the seed 42 checkpoint (the final model) and the final
    `results.json` also go to `molab-state`.
    """)
    return


@app.cell
def _(mo):
    drive_url = mo.ui.text(label="Drive link to tiles_used.zip", full_width=True)
    gh_token = mo.ui.text(kind="password", label="GitHub token (contents: write on hugolo27/marta)")
    mode = mo.ui.dropdown(["prueba", "seleccion", "test"], value="prueba", label="Mode")
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
def _(REPO, os, subprocess, sys):
    def run_py(*args):
        return subprocess.Popen([sys.executable, *args], cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                # molab's Python does not put the script's own folder on the path, so 38 cannot import its siblings
                                env={**os.environ, "MLFLOW_DISABLE_AGENT_HINT": "1", "PYTHONPATH": str(REPO / "scripts")})
    return (run_py,)


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
def _(commit, datetime, json, push, sessions, timezone, torch_info):
    def log_session(stage):
        info = torch_info()
        if sessions and {k: sessions[0][k] for k in info} != info:
            raise SystemExit(f"selection started on {sessions[0]}, this session has {info}: runs are never mixed")
        sessions.append({**info, "commit": commit, "stage": stage,
                         "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        with open("sessions.json", "w") as _f:
            json.dump(sessions, _f, indent=2)
        push("sessions.json", "sessions.json")
    return (log_session,)


@app.cell
def _(RESULTS, log_session, mo, mode, push, run_py, threading, time):
    mo.stop(mode.value != "seleccion")
    log_session("score")

    seen = {}
    lock = threading.Lock()

    def sync():
        with lock:
            if RESULTS.exists() and seen.get("mtime") != RESULTS.stat().st_mtime:
                seen["mtime"] = RESULTS.stat().st_mtime
                push(RESULTS, "results.json")

    proc = run_py("scripts/38_unet_selection.py", "score")

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


@app.cell
def _():
    # One Random Forest test run in a fresh process, as in the selection: run in the kernel next to the U-Net,
    # it ran out of memory. Lines joined, not a triple-quoted block: molab re-indents cell bodies and broke it
    RF_TEST = "\n".join([
        "import importlib, json, sys",
        "s = importlib.import_module('38_unet_selection')",
        "seed, sel = int(sys.argv[1]), json.loads(s.RESULTS_PATH.read_text())['selection']",
        "data, decisions = s.splits(), s.pilot_decisions()",
        "rf = s.train_rf.train_tiles(data['train'], seed=seed, max_samples=decisions['rf_max_samples'], **sel['rf'])",
        "dice, macro = s.classifier_report.dice_from_counts(s.train_rf.predict_counts_tiles(rf, data['test']).sum(axis=0))",
        "print(json.dumps({'seed': seed, 'macro_dice': float(macro), 'dice': dict(zip(s.dl.CLASS_NAMES, dice.tolist()))}))",
    ])
    return (RF_TEST,)


@app.cell
def _(RESULTS, RF_TEST, STATE_DIR, json, log_session, mo, mode, push, run_py, selection_script, unet):
    mo.stop(mode.value != "test")
    _s = selection_script
    _s.check_preregistration()
    _results = json.loads(RESULTS.read_text())
    if "test" in _results:
        raise SystemExit("test already run once")
    _s.check_hardware(_results)
    log_session("test")
    _data, _decisions, _sel = _s.splits(), _s.pilot_decisions(), _results["selection"]
    # Same runs as 38 test, but each one is pushed as it ends: a reclaimed sandbox loses one run, not ten.
    # All U-Nets first, then all Random Forests: every run has its own seed, so the order changes no score
    try:
        _runs = json.loads((STATE_DIR / "test_runs.json").read_text())
    except FileNotFoundError:
        _runs = {"unet": {}, "rf": {}}

    def _record(model, run):
        _runs[model][str(run["seed"])] = run
        with open("test_runs.json", "w") as f:
            json.dump(_runs, f, indent=2)
        push("test_runs.json", "test_runs.json")
        print(f"seed {run['seed']}: {model} test macro Dice {run['macro_dice']:.4f}, pushed", flush=True)

    for _seed in _s.selection.SEEDS:
        if str(_seed) in _runs["unet"]:
            continue
        print(f"seed {_seed}: training U-Net {_sel['unet']}", flush=True)
        _model, _device, _ = unet.train(_data["train"], _data["val"], seed=_seed, max_epochs=_sel["unet_max_epochs"],
                                        patience=_decisions["patience"] or _decisions["max_epochs"], verbose=True,
                                        random_window=True, **_sel["unet"])
        if _seed == 42:
            # Before the score: once seed 42 is recorded it is never retrained, so its checkpoint must already be up
            unet.save_checkpoint(_model, _seed)
            push(unet.CHECKPOINT_PATH, "unet_checkpoint.pt")
            print("seed 42: unet_checkpoint.pt pushed", flush=True)
        _dice, _macro = _s.classifier_report.dice_from_counts(unet.predict_counts_full(_model, _data["test"], _device).sum(axis=0))
        _record("unet", {"seed": _seed, "macro_dice": float(_macro), "dice": dict(zip(_s.dl.CLASS_NAMES, _dice.tolist()))})

    # The U-Nets leave every tile they read cached in the kernel (about 7 GB): freed so the Random Forest process fits
    _s.dl._load_full_tile.cache_clear()
    for _seed in _s.selection.SEEDS:
        if str(_seed) in _runs["rf"]:
            continue
        print(f"seed {_seed}: training Random Forest {_sel['rf']}", flush=True)
        _proc = run_py("-c", RF_TEST, str(_seed))
        _lines = []
        for _line in _proc.stdout:
            print(_line, end="", flush=True)
            _lines.append(_line)
        if _proc.wait():
            raise RuntimeError(f"Random Forest seed {_seed} exited with {_proc.returncode}")
        _record("rf", json.loads(_lines[-1]))

    _results["test"] = {m: [_runs[m][str(seed)] for seed in _s.selection.SEEDS] for m in ("unet", "rf")}
    _s.save(_results)
    push(RESULTS, "results.json")
    for _name, _r in _results["test"].items():
        _macro = [r["macro_dice"] for r in _r]
        print(f"{_name}: test macro Dice {_s.np.mean(_macro):.4f} +/- {_s.np.std(_macro, ddof=1):.4f}")
    return


if __name__ == "__main__":
    app.run()
