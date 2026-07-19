"""Shared helpers for the Stanley-san pipeline: manifest caching, uploads, downloads.

Every billable FAL job is cached in work/manifest.json keyed by shot + a fingerprint
of its prompt/inputs, so re-running a script never re-bills completed work. Change a
prompt in shotlist.json (or pass --force) and only that shot re-runs.
"""
import hashlib
import json
import os
from pathlib import Path

import fal_client
import requests

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
STILLS = WORK / "stills"
CLIPS = WORK / "clips"
AUDIO = WORK / "audio"
OUTPUT = ROOT / "output"
MANIFEST = WORK / "manifest.json"

AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".pcm")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTS = (".mp4", ".webm", ".mov")


# ---- Budget guard -----------------------------------------------------------
# Hard ceiling for total FAL spend across ALL stages/runs, tracked in the manifest.
# The user asked to stay under $14 and be notified at $13.
BUDGET_HARD_CAP = float(os.environ.get("FAL_BUDGET_CAP", "14.0"))
BUDGET_NOTIFY_AT = float(os.environ.get("FAL_BUDGET_NOTIFY", "13.0"))

# Estimated USD per successful call, per model. VERIFY against fal.ai/pricing —
# these are conservative estimates used only to enforce the local cap.
COST_TABLE = {
    "fal-ai/flux-pro/kontext": 0.04,
    "fal-ai/flux/dev": 0.025,
    "fal-ai/kling-video/v2.5-turbo/pro/image-to-video": 0.35,
    "fal-ai/wan/v2.2-a14b": 0.15,
    "fal-ai/veo3/fast/image-to-video": 3.20,
    "fal-ai/minimax-music/v1.5": 0.35,
    "fal-ai/minimax-music": 0.35,
    "fal-ai/stable-audio": 0.05,
    "fal-ai/minimax/speech-02-hd": 0.02,
}
DEFAULT_COST = 0.35  # if a model isn't in the table, assume the priciest common tier


class BudgetExceeded(SystemExit):
    pass


def cost_of(model):
    return COST_TABLE.get(model, DEFAULT_COST)


def spend_so_far():
    return float(_load_manifest().get("_spend", {}).get("total", 0.0))


def _record_spend(model, cost, key):
    m = _load_manifest()
    s = m.setdefault("_spend", {"total": 0.0, "items": []})
    s["total"] = round(float(s.get("total", 0.0)) + cost, 4)
    s["items"].append({"key": key, "model": model, "cost": cost})
    _save_manifest(m)
    return s["total"]


def check_budget(model, key):
    """Abort BEFORE a billable call if it would push total spend over the cap."""
    current = spend_so_far()
    projected = current + cost_of(model)
    if projected > BUDGET_HARD_CAP:
        raise BudgetExceeded(
            f"\n*** BUDGET STOP *** spent ${current:.2f}, next call ({model}, "
            f"~${cost_of(model):.2f}) would reach ${projected:.2f} > cap ${BUDGET_HARD_CAP:.2f}.\n"
            f"Aborting '{key}'. Raise FAL_BUDGET_CAP to continue, or skip this shot.")


def note_spend(model, key):
    total = _record_spend(model, cost_of(model), key)
    flag = _load_manifest().get("_spend", {}).get("_notified_13", False)
    if total >= BUDGET_NOTIFY_AT and not flag:
        m = _load_manifest()
        m["_spend"]["_notified_13"] = True
        _save_manifest(m)
        print(f"\n>>> BUDGET NOTICE: FAL spend has reached ${total:.2f} "
              f"(alert threshold ${BUDGET_NOTIFY_AT:.0f}). Cap is ${BUDGET_HARD_CAP:.0f}. <<<\n")
        _write_notify_flag(total)
    print(f"  [spend]  ${cost_of(model):.2f}  |  running total ${total:.2f} / ${BUDGET_HARD_CAP:.0f}")
    return total


def _write_notify_flag(total):
    """Drop a sentinel file so the operator/agent can surface the $13 alert."""
    try:
        (WORK / "BUDGET_ALERT_13.txt").write_text(
            f"FAL spend reached ${total:.2f} — approaching ${BUDGET_HARD_CAP:.0f} cap.\n")
    except OSError:
        pass


def require_key():
    if not os.environ.get("FAL_KEY"):
        raise SystemExit("FAL_KEY is not set. Run: export FAL_KEY=<your key> and retry.")


def ensure_dirs():
    for d in (STILLS, CLIPS, AUDIO, OUTPUT):
        d.mkdir(parents=True, exist_ok=True)


def load_shotlist():
    with open(ROOT / "shotlist.json", encoding="utf-8") as f:
        return json.load(f)


def _load_manifest():
    if MANIFEST.exists():
        with open(MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
    tmp.replace(MANIFEST)


def fingerprint(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:16]


def upload_cached(path: Path) -> str:
    """Upload a local file to fal storage once; reuse the URL on later runs."""
    m = _load_manifest()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    key = f"upload:{path.name}:{digest}"
    if key in m:
        return m[key]["url"]
    url = fal_client.upload_file(str(path))
    m = _load_manifest()
    m[key] = {"url": url}
    _save_manifest(m)
    return url


def download(url: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    out_path.write_bytes(r.content)


def _find_url(obj, exts):
    """Walk an arbitrary result payload and return the first URL with a matching ext."""
    if isinstance(obj, dict):
        for v in obj.values():
            u = _find_url(v, exts)
            if u:
                return u
    elif isinstance(obj, list):
        for v in obj:
            u = _find_url(v, exts)
            if u:
                return u
    elif isinstance(obj, str) and obj.startswith("http"):
        base = obj.split("?", 1)[0].lower()
        if base.endswith(exts):
            return obj
    return None


def find_image_url(result):
    return _find_url(result, IMAGE_EXTS)


def find_video_url(result):
    return _find_url(result, VIDEO_EXTS)


def find_audio_url(result):
    return _find_url(result, AUDIO_EXTS)


def run_cached(key: str, fp: str, out_path: Path, fn, force=False, model=None):
    """Run fn() -> url and download it, unless this exact job already produced out_path.

    Cached hits cost nothing. Real calls are budget-checked before running and
    recorded to the spend ledger after success (only new spend counts toward the cap).
    """
    m = _load_manifest()
    entry = m.get(key)
    if not force and entry and entry.get("fp") == fp and out_path.exists():
        print(f"  [cached] {key} -> {out_path.name}  (no charge)")
        return out_path
    if model:
        check_budget(model, key)
    print(f"  [run]    {key} ...")
    url = fn()
    if not url:
        raise RuntimeError(f"{key}: could not find a result URL in the model response. "
                           "Print the raw result and check the model's API docs on fal.ai.")
    download(url, out_path)
    m = _load_manifest()
    m[key] = {"fp": fp, "url": url, "file": str(out_path.relative_to(ROOT))}
    _save_manifest(m)
    print(f"  [done]   {key} -> {out_path.name}")
    if model:
        note_spend(model, key)
    return out_path
