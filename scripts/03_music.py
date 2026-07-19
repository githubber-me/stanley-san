#!/usr/bin/env python3
"""Stage 3 — the song. Anime ending-theme ballad with the custom lyrics in shotlist.json.

Usage:
  python scripts/03_music.py                # take 1 -> work/audio/song_take1.mp3
  python scripts/03_music.py --take 2      # generate another take (~$0.35 each)
  python scripts/03_music.py --instrumental  # fallback: instrumental OST (stable-audio)

Pick the best take and pass it to stage 5:  05_assemble.py --song work/audio/song_take2.mp3
If the endpoint rejects the arguments, check the live schema at
https://fal.ai/models/<model-id>/api and adjust `arguments` below.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fal_client  # noqa: E402
from fal_common import (AUDIO, ensure_dirs, find_audio_url, fingerprint,  # noqa: E402
                        load_shotlist, require_key, run_cached)

INSTRUMENTAL_MODEL = "fal-ai/stable-audio"
INSTRUMENTAL_PROMPT = (
    "Emotional Japanese anime OST, cinematic instrumental ballad, gentle piano and warm "
    "strings building to a heartfelt sweeping final chorus, bittersweet, hopeful, 90 seconds"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--instrumental", action="store_true")
    args = ap.parse_args()

    require_key()
    ensure_dirs()
    music = load_shotlist()["music"]

    if args.instrumental:
        model = INSTRUMENTAL_MODEL
        arguments = {"prompt": INSTRUMENTAL_PROMPT, "seconds_total": 90}
        out = AUDIO / f"instrumental_take{args.take}.mp3"
    else:
        model = music["model"]
        arguments = {"prompt": music["style_prompt"], "lyrics": music["lyrics"]}
        out = AUDIO / f"song_take{args.take}.mp3"

    def fn():
        res = fal_client.subscribe(model, arguments=arguments)
        return find_audio_url(res)

    fp = fingerprint(model, str(sorted(arguments.items())), args.take)
    run_cached(f"music:take{args.take}:{'inst' if args.instrumental else 'vocal'}",
               fp, out, fn, force=args.force)
    print(f"\nListen to {out}. Generate more takes with --take N, then pass the winner "
          "to 05_assemble.py --song <path>.")


if __name__ == "__main__":
    main()
