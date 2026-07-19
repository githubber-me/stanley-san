#!/usr/bin/env python3
"""Stage 2 — animate the approved anime stills. EXPENSIVE STAGE (~$0.35/clip).

Default model: Kling 2.5 Turbo Pro image-to-video, 5s, no native audio (we add the
song + Japanese VO ourselves in stage 5).

Optional per-shot premium upgrade (native audio, e.g. the punch or the finale):
  python scripts/02_animate.py --only 14 --model fal-ai/veo3/fast/image-to-video
(Veo 3 Fast w/ audio is ~$3.20 per 8s clip — check fal.ai/pricing before using.)

Usage:
  python scripts/02_animate.py                 # all shots (cached ones skipped)
  python scripts/02_animate.py --only 18 19    # specific shots
  python scripts/02_animate.py --only 07 --force   # re-roll a clip
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fal_client  # noqa: E402
from fal_common import (CLIPS, STILLS, ensure_dirs, find_video_url, fingerprint,  # noqa: E402
                        load_shotlist, require_key, run_cached, upload_cached)

DEFAULT_MODEL = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"

MOTION_SUFFIX = (
    " Consistent 2D cel anime style throughout, stable character design, "
    "smooth anime motion, no photorealism."
)
NEGATIVE = (
    "photorealistic, live action, 3D render, face distortion, morphing, identity change, "
    "changing clothes, extra people, extra fingers, deformed hands, text, watermark, glitch"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="shot ids to (re)animate")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="fal image-to-video endpoint (per-shot premium swaps allowed)")
    args = ap.parse_args()

    require_key()
    ensure_dirs()
    shots = load_shotlist()["shots"]

    missing = [s["id"] for s in shots
               if not (STILLS / f"{s.get('still_from') or s['id']}.jpg").exists()]
    if missing:
        raise SystemExit(f"Missing stills for shots {missing} — run 01_stylize.py first.")

    for shot in shots:
        sid = shot["id"]
        if args.only and sid not in args.only:
            continue
        still = STILLS / f"{shot.get('still_from') or sid}.jpg"
        out = CLIPS / f"{sid}.mp4"
        prompt = shot["motion_prompt"] + MOTION_SUFFIX
        image_url = upload_cached(still)

        def fn(prompt=prompt, image_url=image_url, model=args.model):
            arguments = {
                "prompt": prompt,
                "image_url": image_url,
                "duration": "5",
                "negative_prompt": NEGATIVE,
            }
            try:
                res = fal_client.subscribe(model, arguments=arguments)
            except Exception:
                # Some endpoints (e.g. Veo) reject kling-specific params — retry minimal.
                res = fal_client.subscribe(model, arguments={
                    "prompt": prompt, "image_url": image_url,
                })
            return find_video_url(res)

        fp = fingerprint(args.model, prompt, still.name)
        run_cached(f"clip:{sid}", fp, out, fn, force=args.force)

    print("\nAll clips in work/clips/ — spot-check each one: no face morphing, no costume")
    print("changes, no extra people (group shot must keep all 13).")


if __name__ == "__main__":
    main()
