#!/usr/bin/env python3
"""Stage 5 — assembly. FREE (local ffmpeg): iterate on timing/subtitles as much as you like.

Cuts the 20 clips per shotlist.json durations, burns English subtitles (anime-sub
style) and the end title card, adds the white-flash flashback transition, lays the
song under everything, drops the Japanese VO lines at their shots' start times with
the music ducked underneath, and exports:

  output/final.mp4        1080p master
  output/final_720p.mp4   WhatsApp-friendly

Usage:
  python scripts/05_assemble.py --song work/audio/song_take1.mp3
  python scripts/05_assemble.py --song work/audio/song_take2.mp3 --no-vo
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fal_common import AUDIO, CLIPS, OUTPUT, WORK, load_shotlist  # noqa: E402

W, H, FPS = 1920, 1080, 24
NORM = WORK / "norm"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
# CJK font is required to render the Japanese subtitle line (Latin fonts show boxes).
FONT_CJK_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf",
]

SUB_SIZE = 30  # subtitle font size — same for JA and EN, smaller than before

# Dreamy/nostalgic grade applied to the Act II flashback shots (soft haze, warm lift,
# gentle vignette, film grain). Applied BEFORE subtitles so text stays crisp.
DREAM_FILTERS = [
    "gblur=sigma=2.4",
    "eq=brightness=0.03:saturation=1.14:contrast=0.94",
    "curves=all='0/0.05 0.5/0.53 1/0.97'",
    "vignette=angle=PI/4.6",
    "noise=alls=6:allf=t",
]


def pick_font(candidates, env_var):
    import os
    if os.environ.get(env_var):
        return os.environ[env_var]
    for c in candidates:
        if Path(c).exists():
            return c
    raise SystemExit(f"No font found — set {env_var}=/path/to/font.ttf")


def run(cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def probe_dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def textfile(name, content):
    p = NORM / name
    p.write_text(content, encoding="utf-8")
    return p


def _fade_alpha(dur):
    return f"if(lt(t\\,0.5)\\,t/0.5\\,if(gt(t\\,{dur - 0.8:.2f})\\,max(0\\,({dur:.2f}-t)/0.8)\\,1))"


def build_subs(shot, font, cjk_font, dur):
    """Japanese subtitle line ABOVE the English one, same (small) size, gentle fade."""
    sid = shot["id"]
    alpha = _fade_alpha(dur)
    filters = []
    en, ja = shot.get("narration"), shot.get("narration_ja")
    # English on the lower line.
    if en:
        p = textfile(f"{sid}_en.txt", en)
        filters.append(
            f"drawtext=fontfile={font}:textfile={p}:fontsize={SUB_SIZE}:"
            f"fontcolor=white:borderw=2:bordercolor=black@0.75:"
            f"x=(w-text_w)/2:y=h-80:alpha='{alpha}'")
    # Japanese sits just above the English line (or bottom if no English).
    if ja:
        p = textfile(f"{sid}_ja.txt", ja)
        y = "h-124" if en else "h-80"
        filters.append(
            f"drawtext=fontfile={cjk_font}:textfile={p}:fontsize={SUB_SIZE}:"
            f"fontcolor=white:borderw=2:bordercolor=black@0.75:"
            f"x=(w-text_w)/2:y={y}:alpha='{alpha}'")
    return filters


def normalize_shot(shot, font, font_bold, cjk_font):
    sid, dur = shot["id"], float(shot["duration"])
    src = CLIPS / f"{sid}.mp4"
    out = NORM / f"{sid}.mp4"
    if not src.exists():
        raise SystemExit(f"Missing clip {src} — run 02_animate.py first.")

    vf = [
        f"scale={W}:{H}:force_original_aspect_ratio=increase",
        f"crop={W}:{H}",
        f"fps={FPS}",
        "setsar=1",
    ]
    # Dreamy nostalgic grade on the Act II flashback/memory shots.
    if str(shot.get("act", "")).startswith("II"):
        vf.extend(DREAM_FILTERS)
    # NOTE: subtitles are NOT drawn here anymore — they're burned onto the final
    # timeline (synced to the VO), so a line can span shot cuts.

    if sid == "01":
        vf.append("fade=t=in:st=0:d=0.8")
    if sid == "03":  # flashback: flash to white
        vf.append(f"fade=t=out:st={dur - 0.6:.2f}:d=0.6:color=white")
    if sid == "04":  # ...and back from white
        vf.append("fade=t=in:st=0:d=0.5:color=white")
    if sid == "15":  # end of the memories — fade out to black
        vf.append(f"fade=t=out:st={dur - 1.0:.2f}:d=1.0")
    if sid == "16":  # back to the present (Mumbai) — fade in from black
        vf.append("fade=t=in:st=0:d=1.0")
    if sid == "20":  # end title card
        main_txt = textfile("t20_main.txt", shot["title_main"])
        sub_txt = textfile("t20_sub.txt", shot["title_sub"])
        a_main = "if(lt(t\\,1.0)\\,t/1.0\\,1)"
        a_sub = "if(lt(t\\,1.6)\\,max(0\\,(t-0.8)/0.8)\\,1)"
        vf.append(f"drawtext=fontfile={font_bold}:textfile={main_txt}:fontsize=68:"
                  f"fontcolor=white:borderw=3:bordercolor=black@0.6:"
                  f"x=(w-text_w)/2:y=(h-text_h)/2-50:alpha='{a_main}'")
        vf.append(f"drawtext=fontfile={font}:textfile={sub_txt}:fontsize=34:"
                  f"fontcolor=white:borderw=2:bordercolor=black@0.6:"
                  f"x=(w-text_w)/2:y=(h)/2+40:alpha='{a_sub}'")
        vf.append(f"fade=t=out:st={dur - 1.0:.2f}:d=1.0")

    run(["ffmpeg", "-y", "-i", src, "-vf", ",".join(vf), "-t", f"{dur:.3f}",
         "-an", "-r", FPS, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", out])
    return out


def build_schedule(shots):
    """One shared timeline for BOTH the VO audio and the subtitles, so they're locked
    together. Each narrated line starts at its shot (>=+0.25s) but never before the
    previous line ends (+0.3s), so lines never overlap — a line may run past its shot
    cut, and the subtitle stays on screen with it. Returns list of dicts."""
    sched, t, prev_end = [], 0.0, 0.0
    for s in shots:
        p = AUDIO / f"vo_{s['id']}.mp3"
        if s.get("narration_ja") and p.exists():
            vlen = probe_dur(p) or 2.5
            off = max(t + 0.25, prev_end + 0.30)
            end = off + vlen
            sched.append({"id": s["id"], "off": off, "end": end, "vo": p,
                          "en": s.get("narration"), "ja": s.get("narration_ja"),
                          "endcard": bool(s.get("title_main"))})
            prev_end = end
        elif s.get("narration_ja"):
            print(f"  [warn] no VO file for shot {s['id']} — line skipped")
        t += float(s["duration"])
    return sched


def _dt_sub(fontfile, txtpath, y, off, end):
    """A synced subtitle drawtext: shown between off..end with a 0.3s alpha fade."""
    a = f"min(1\\,(t-{off:.2f})/0.3)*min(1\\,({end:.2f}-t)/0.3)"
    return (f"drawtext=fontfile={fontfile}:textfile={txtpath}:fontsize={SUB_SIZE}:"
            f"fontcolor=white:borderw=2:bordercolor=black@0.75:x=(w-text_w)/2:y={y}:"
            f"enable='between(t\\,{off:.2f}\\,{end:.2f})':alpha='{a}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--song", default="source/music.wav",
                    help="soundtrack (default: the user-provided source/music.wav)")
    ap.add_argument("--music-vol", type=float, default=0.5,
                    help="music volume (0.5 = half of the raw track)")
    ap.add_argument("--no-vo", action="store_true", help="skip the Japanese voiceover mix")
    args = ap.parse_args()

    shots = load_shotlist()["shots"]
    NORM.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    font = pick_font(FONT_CANDIDATES, "FONT")
    font_bold = pick_font(FONT_BOLD_CANDIDATES, "FONT_BOLD")
    cjk_font = pick_font(FONT_CJK_CANDIDATES, "FONT_CJK")

    # 1. Normalize + decorate every shot (no subtitles), then hard-cut concat.
    norm_files = [normalize_shot(s, font, font_bold, cjk_font) for s in shots]
    concat_list = NORM / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in norm_files))
    silent = NORM / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", silent])

    total = sum(float(s["duration"]) for s in shots)
    sched = build_schedule(shots)

    # 2. Burn subtitles on the FINAL timeline, synced to the VO windows (JA above EN,
    #    both small/same size). Endcard shot keeps its own title, so skip its line.
    sub_dts = []
    for e in sched:
        if e["endcard"]:
            continue
        end = min(e["end"], total)
        if e["en"]:
            sub_dts.append(_dt_sub(font, textfile(f"{e['id']}_en.txt", e["en"]),
                                   "h-80", e["off"], end))
        if e["ja"]:
            y = "h-124" if e["en"] else "h-80"
            sub_dts.append(_dt_sub(cjk_font, textfile(f"{e['id']}_ja.txt", e["ja"]),
                                   y, e["off"], end))
    subbed = NORM / "subbed.mp4"
    if sub_dts:
        run(["ffmpeg", "-y", "-i", silent, "-vf", ",".join(sub_dts), "-an",
             "-c:v", "libx264", "-preset", "medium", "-crf", "19",
             "-pix_fmt", "yuv420p", subbed])
    else:
        subbed = silent

    # 3. Audio: the user's music (at half volume, faded) + VO lines, music ducked under VO.
    song = Path(args.song)
    if not song.exists():
        raise SystemExit(f"Music not found: {song}")

    vo_items = [] if args.no_vo else [(e["off"], e["vo"]) for e in sched]

    inputs = ["-i", subbed, "-i", str(song)] + [x for _, p in vo_items for x in ("-i", str(p))]
    music = (f"[1:a]atrim=0:{total:.3f},volume={args.music_vol},afade=t=in:st=0:d=1.5,"
             f"afade=t=out:st={total - 3:.3f}:d=3.0[mus]")
    if vo_items:
        chains, labels = [], []
        for i, (off, _) in enumerate(vo_items):
            ms = int(off * 1000)
            chains.append(f"[{i + 2}:a]adelay={ms}|{ms}[v{i}]")
            labels.append(f"[v{i}]")
        vo_mix = (f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,"
                  f"volume=1.6,asplit=2[voA][voB]")
        duck = ("[mus][voA]sidechaincompress=threshold=0.02:ratio=6:attack=60:release=400[mduck];"
                "[mduck][voB]amix=inputs=2:normalize=0,alimiter[aout]")
        fc = ";".join([music] + chains + [vo_mix, duck])
    else:
        fc = music + ";[mus]anull[aout]"

    final = OUTPUT / "final.mp4"
    run(["ffmpeg", "-y"] + inputs + ["-filter_complex", fc,
         "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", final])

    run(["ffmpeg", "-y", "-i", final, "-vf", "scale=1280:720",
         "-c:v", "libx264", "-preset", "medium", "-crf", "23",
         "-c:a", "copy", OUTPUT / "final_720p.mp4"])

    print(f"\nDone: {final}  (runtime {total:.0f}s)  + final_720p.mp4")
    print("Tweak narration/durations in shotlist.json and re-run — assembly is free.")


if __name__ == "__main__":
    main()
