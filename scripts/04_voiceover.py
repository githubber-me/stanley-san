#!/usr/bin/env python3
"""Stage 4 — Japanese voiceover. Stanley's inner monologue, spoken like anime narration.

Generates one audio file per narrated shot (work/audio/vo_<id>.mp3) from the
`narration_ja` lines in shotlist.json. Stage 5 places each at its shot's start
time and ducks the music underneath. Costs cents per line.

Usage:
  python scripts/04_voiceover.py                       # all lines
  python scripts/04_voiceover.py --only 18 19 --force  # re-do specific lines
  python scripts/04_voiceover.py --voice-id <id>       # pick a specific voice

If the default voice doesn't sound right for calm Japanese narration, open
https://fal.ai/models/fal-ai/minimax/speech-02-hd/api , pick a Japanese voice id,
and pass it via --voice-id.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fal_client  # noqa: E402
from fal_common import (AUDIO, ensure_dirs, find_audio_url, fingerprint,  # noqa: E402
                        load_shotlist, require_key, run_cached)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--voice-id", default=None,
                    help="minimax voice id (see the model's API page for the list)")
    args = ap.parse_args()

    require_key()
    ensure_dirs()
    data = load_shotlist()
    model = data["voiceover"]["model"]

    for shot in data["shots"]:
        sid = shot["id"]
        text = shot.get("narration_ja")
        if not text:
            continue
        if args.only and sid not in args.only:
            continue
        out = AUDIO / f"vo_{sid}.mp3"

        def fn(text=text):
            arguments = {"text": text}
            if args.voice_id:
                arguments["voice_setting"] = {"voice_id": args.voice_id, "speed": 0.95}
            res = fal_client.subscribe(model, arguments=arguments)
            return find_audio_url(res)

        fp = fingerprint(model, text, args.voice_id)
        run_cached(f"vo:{sid}", fp, out, fn, force=args.force)

    print("\nVO lines in work/audio/vo_*.mp3 — listen to a couple; if the voice is off,")
    print("re-run with --voice-id (see the model's API page) --force.")


if __name__ == "__main__":
    main()
