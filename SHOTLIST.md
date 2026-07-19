# Stanley-san — *Never Away From Home*

A ~85–90s **anime short film** (not a montage) for Stanley's move from Bengaluru → Mumbai.
Full cel-shaded anime styling, English subtitles + **Japanese voiceover** inner monologue,
custom anime ending-theme song. The group photo comes alive at the very end.

All prompts, timings, narration and lyrics live in **`shotlist.json`** (the single source of
truth the scripts read). Edit that file, not the scripts, to change the film.

## Story beats
- **Act I – Departure (~12s):** Stanley boards a *flight* out of Bengaluru; the city falls away, whiting out into memory.
- **Act II – Memories (~48s):** each of the 12 friends appears *inside a scene* from his life — the hills, city nights, the grand dress-up days, ordinary days. Costumes kept from the real photos.
- **Act III – Mumbai / finale (~25s):** flight banks over Mumbai; Stanley alone at Marine Drive; then the **group photo comes alive**, and the end card: *"You're never away from home."*

## Shot table
| # | Source | Beat | Dur | EN subtitle | JA VO |
|---|--------|------|-----|-------------|-------|
| 01 | generated | Bengaluru dawn, suitcase by the door | 4s | Today, I leave Bengaluru. | 今日、僕はベンガルールを発つ。 |
| 02 | stanley | Plane window seat, wistful | 5s | Twenty-one years. One city. And everything in it. | 21年。ひとつの街。その、すべて。 |
| 03 | generated | Takeoff, city falls away → white flash | 3s | — | — |
| 04 | c | Misty hilltop, protagonist wind shot | 5s | Some days we chased the fog up a mountain… | 霧を追いかけて、山を登った日もあった… |
| 05 | a | Green trail, head-back laugh | 4s | — | — |
| 06 | b | Fog-white lake, quiet nod | 3s | …some said everything without saying much. | 多くを語らず、すべてを伝えるやつもいた。 |
| 07 | e | Neon night market, deadpan sip | 5s | Some nights, the city belonged to us. | 夜になれば、この街は僕らのものだった。 |
| 08 | j | Party lights, wink + peace sign | 2s | — | — |
| 09 | d | Golden hilltop, raises branch like a staff | 5s | Some days, we dressed up like the main characters… | 主人公みたいに着飾った日もあった… |
| 10 | f | Lamplit palace corridor, saree turn | 5s | — | — |
| 11 | g | Cozy café, dessert candle | 4s | …and every small sweet thing. | 小さくて甘い、そんな瞬間も。 |
| 12 | i | College fest, big grin/laugh | 3s | But mostly, it was the ordinary days. | でも、ほとんどは何気ない日々だった。 |
| 13 | h | Court, glances up and smiles | 3s | — | — |
| 14 | k | Playful anime punch at camera (speed-lines) | 4s | — | — |
| 15 | l | Warm portrait, smile deepens | 3s | The people who made a city a home. | この街を『家』にしてくれた人たち。 |
| 16 | generated | Flight banks over Mumbai coastline | 4s | — | — |
| 17 | stanley | Marine Drive at dusk, alone | 5s | A new city. New streets. No familiar faces… | 新しい街。知らない道。知った顔は、ない… |
| 18 | group | **Group photo comes alive** | 5s | …and yet. | それでも。 |
| 19 | group | Group, light blooms gold | 5s | Some things don't change with the pin code. | 住所が変わっても、変わらないものがある。 |
| 20 | generated | End card + title | 5s | *You're never away from home.* | どこにいても、家はここにある。 |

> Shots 08 and 14 have no narration on purpose — comedy beats land better clean.
> Photo→character map is intentionally name-free (per request). Reassign any photo by
> editing its `source` in `shotlist.json`.

## Pipeline
```
pip install -r requirements.txt        # fal-client, requests
sudo apt-get install -y ffmpeg fonts-noto-cjk   # ffmpeg + a font that renders Japanese
export FAL_KEY=<your fal key>

python scripts/01_stylize.py           # (1) anime stills  — CHEAP, iterate here
#   review work/stills/  → re-roll any: 01_stylize.py --only 09 --force
python scripts/02_animate.py           # (2) animate stills — EXPENSIVE (~$0.35/clip)
python scripts/03_music.py             # (3) song (custom lyrics); --take 2 for another
python scripts/04_voiceover.py         # (4) Japanese VO lines
python scripts/05_assemble.py --song work/audio/song_take1.mp3   # (5) FREE local ffmpeg
#   → output/final.mp4  +  output/final_720p.mp4
```
- **Everything is cached** in `work/manifest.json` — re-running never re-bills finished shots.
  Change a prompt in `shotlist.json` (or pass `--force`) and only that shot re-runs.
- **`fonts-noto-cjk` is required** for the Japanese end-card glyph (shot 20) to render.
  Set `FONT`/`FONT_BOLD` env vars to override the subtitle font.

## Models (defaults; swap in the scripts if pricing/quality shifts)
| Stage | Model | Why |
|---|---|---|
| Stills (photos) | `fal-ai/flux-pro/kontext` | edits a photo → anime while keeping face + costume |
| Stills (scenes) | `fal-ai/flux/dev` | text-to-image anime backgrounds |
| Video | `fal-ai/kling-video/v2.5-turbo/pro/image-to-video` | best-value image-to-video, 5s |
| Song | `fal-ai/minimax-music/v1.5` | vocals from custom lyrics |
| Voiceover | `fal-ai/minimax/speech-02-hd` | Japanese TTS narration |

### Premium native-audio option (optional, per shot)
For 2–3 hero shots (e.g. 09 the branch-raise, 14 the punch, 18 the group coming alive) you can
swap to a native-audio video model for built-in sound effects/ambience:
```
python scripts/02_animate.py --only 14 --model fal-ai/veo3/fast/image-to-video --force
```
Veo 3 Fast (with audio) is roughly **$3+ per 8s clip** — check `fal.ai/pricing` first. See the
budget notes in the plan; doing the whole film on it would blow past $20, so keep it to a few shots.

## Budget (Kling default path)
~$1.30 stills · ~$9.50 video (incl. retries) · ~$1 song · ~$0.30 VO ≈ **$12 total** → fits $15–20
with headroom. Verify live prices at run time; if credits get tight, switch stage 2 to
`fal-ai/wan/v2.2-a14b` (about half the video cost).
