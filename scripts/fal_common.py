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


def run_cached(key: str, fp: str, out_path: Path, fn, force=False):
    """Run fn() -> url and download it, unless this exact job already produced out_path."""
    m = _load_manifest()
    entry = m.get(key)
    if not force and entry and entry.get("fp") == fp and out_path.exists():
        print(f"  [cached] {key} -> {out_path.name}")
        return out_path
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
    return out_path
