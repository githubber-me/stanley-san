# Rendering the film / getting the output

The finished anime short is **`output/final_720p.mp4`** (committed, ~17 MB) — the
share-friendly cut. The 1080p master is too large for GitHub (>100 MB), so it is
**not** committed, but you can regenerate it for **free** from the raw assets that
*are* committed here — no FAL key or credits needed.

## What's committed (the raw assets)
| Path | What it is |
|------|-----------|
| `work/stills/*.jpg` | The 20 anime stills (one per shot; `19.jpg` is the group) |
| `work/clips/*.mp4`  | The 20 animated 5-second clips |
| `work/audio/vo_*.mp3` | The Japanese voiceover lines |
| `source/music.wav`  | The soundtrack |
| `shotlist.json`     | Single source of truth: prompts, narration, durations |
| `scripts/`          | The pipeline |

## Regenerate the 1080p master (free — local ffmpeg only)
Requires `ffmpeg` and a CJK font (`fonts-noto-cjk`) for the Japanese subtitle line.
```bash
sudo apt-get install -y ffmpeg fonts-noto-cjk
python3 scripts/05_assemble.py --song source/music.wav
# -> output/final.mp4 (1080p master) + output/final_720p.mp4
```
Assembly reads the committed `work/clips`, `work/audio`, and `shotlist.json`. It burns
the subtitles (Japanese above English, synced to the voiceover), applies the dreamy
grade to the flashback shots, mixes the music at half volume under the voiceover, and
adds the fades. It never calls FAL, so it is free and repeatable.

Tweak subtitle wording/timing/durations in `shotlist.json` and re-run — still free.

## Rebuild an individual shot (costs FAL credits)
Only if you want to change a shot's *image or motion*. Needs `pip install -r
requirements.txt` and `export FAL_KEY=<key>` (or a `fal.key` file at the repo root).
Approx costs: still ≈ $0.03–0.05, clip ≈ $0.35.
```bash
python3 scripts/01_stylize.py --only 10 --reangle --force   # re-image shot 10
python3 scripts/02_animate.py --only 10 --force             # re-animate shot 10
python3 scripts/05_assemble.py --song source/music.wav      # re-stitch (free)
```
Every FAL result is cached in `work/manifest.json` with a running spend total and a
hard budget cap (`FAL_BUDGET_CAP`, default $14) — see `scripts/fal_common.py`. Check
spend anytime with `python3 scripts/cost.py`. Full creative/script details are in
`SHOTLIST.md`.
