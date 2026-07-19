#!/usr/bin/env python3
"""Stage 1 — anime stills. CHEAP STAGE: iterate here until every still is right.

Photo shots  -> fal-ai/flux-pro/kontext  (identity + costume preserving anime restyle, ~$0.04)
Scene shots  -> fal-ai/flux/dev          (text-to-image backgrounds, ~$0.025)

Usage:
  python scripts/01_stylize.py                 # all shots (cached ones skipped)
  python scripts/01_stylize.py --only 09 14    # specific shots
  python scripts/01_stylize.py --only 09 --force   # re-roll a shot you don't like

Review everything in work/stills/ BEFORE running 02_animate.py — video costs ~9x more.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fal_client  # noqa: E402
from fal_common import (ROOT, STILLS, ensure_dirs, find_image_url, fingerprint,  # noqa: E402
                        load_shotlist, require_key, run_cached, upload_cached)

KONTEXT_MODEL = "fal-ai/flux-pro/kontext"
T2I_MODEL = "fal-ai/flux/dev"
REANGLE_MODEL = "fal-ai/nano-banana/edit"  # Gemini edit: same person, NEW angle/pose

# For --reangle: use the ORIGINAL photo purely as an identity/costume reference and
# compose a genuinely new camera angle (not a tracing of the source framing).
REANGLE_STYLE = (
    "Redraw ENTIRELY as a flat 2D hand-drawn Japanese ANIME screenshot — bold black "
    "outlines, flat cel shading with hard shadow shapes, simplified painted anime "
    "background, expressive large anime eyes, that classic anime-movie look. This must "
    "look UNMISTAKABLY like a 2D anime frame — NOT photorealistic, NOT a 3D render, NOT "
    "realistic lighting or realistic skin. Use the reference image ONLY for the person's "
    "identity (same face, hair, skin tone) and their exact outfit/costume. Do NOT copy "
    "the photo's framing — compose the NEW camera angle and scene described here. Same "
    "single person, same clothes. Cinematic 16:9. "
)

# Prepended to every photo shot's still_prompt. Hard anime, zero realism.
ANIME_STYLE = (
    "Transform this photograph into a vibrant 2D Japanese anime film still: bold clean "
    "line art, cel shading, expressive anime eyes, dramatic cinematic lighting with soft "
    "glow and bloom, richly painted background in the style of a modern anime movie. "
    "Absolutely NO photorealism — every element fully redrawn as anime. Keep the SAME "
    "character: identical face structure, hairstyle, facial hair, glasses, jewelry, skin "
    "tone, expression and the EXACT same clothing/costume. Do not add or remove people. "
    "Cinematic 16:9 composition. Scene: "
)
# Appended to every text-to-image scene prompt.
T2I_STYLE = (
    " Vibrant cel-shaded 2D anime, bold clean line art, cinematic glow and bloom, "
    "no photorealism, no text, no watermark, masterpiece anime background art."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="shot ids to (re)generate")
    ap.add_argument("--force", action="store_true", help="ignore cache for selected shots")
    ap.add_argument("--reangle", action="store_true",
                    help="for shots with a reangle_prompt: recompose a NEW camera angle "
                         "from the original photo (nano-banana), not a tracing of it")
    args = ap.parse_args()

    require_key()
    ensure_dirs()
    shots = load_shotlist()["shots"]

    for shot in shots:
        sid = shot["id"]
        if shot.get("still_from"):
            continue  # reuses another shot's still
        if args.only and sid not in args.only:
            continue
        out = STILLS / f"{sid}.jpg"

        if args.reangle and shot.get("reangle_prompt") and shot.get("source"):
            # Recompose a new camera angle using the original photo as identity ref.
            prompt = REANGLE_STYLE + shot["reangle_prompt"]
            image_url = upload_cached(ROOT / shot["source"])

            def fn(prompt=prompt, image_url=image_url):
                res = fal_client.subscribe(REANGLE_MODEL, arguments={
                    "prompt": prompt,
                    "image_urls": [image_url],
                    "aspect_ratio": "16:9",
                    "num_images": 1,
                    "output_format": "jpeg",
                })
                return find_image_url(res)

            fp = fingerprint(REANGLE_MODEL, prompt, shot["source"])
            model_used = REANGLE_MODEL
        elif shot.get("source"):
            prompt = ANIME_STYLE + shot["still_prompt"]
            image_url = upload_cached(ROOT / shot["source"])

            def fn(prompt=prompt, image_url=image_url):
                res = fal_client.subscribe(KONTEXT_MODEL, arguments={
                    "prompt": prompt,
                    "image_url": image_url,
                    "aspect_ratio": "16:9",
                    "output_format": "jpeg",
                })
                return find_image_url(res)

            fp = fingerprint(KONTEXT_MODEL, prompt, shot["source"])
            model_used = KONTEXT_MODEL
        else:
            prompt = shot["still_prompt"] + T2I_STYLE

            def fn(prompt=prompt):
                res = fal_client.subscribe(T2I_MODEL, arguments={
                    "prompt": prompt,
                    "image_size": "landscape_16_9",
                    "num_images": 1,
                })
                return find_image_url(res)

            fp = fingerprint(T2I_MODEL, prompt)
            model_used = T2I_MODEL

        run_cached(f"still:{sid}", fp, out, fn, force=args.force, model=model_used)

    print("\nAll stills in work/stills/ — REVIEW THEM (identity, costume, full anime look)")
    print("before spending on video. Re-roll any shot: 01_stylize.py --only <id> --force")


if __name__ == "__main__":
    main()
