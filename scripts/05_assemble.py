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


def textfile(name, content):
    p = NORM / name
    p.write_text(content, encoding="utf-8")
    return p


def sub_filter(font, txt_path, dur, fontsize=40, y="h-130"):
    """Anime-style subtitle with a gentle fade in/out."""
    alpha = f"if(lt(t\\,0.5)\\,t/0.5\\,if(gt(t\\,{dur - 0.8:.2f})\\,max(0\\,({dur:.2f}-t)/0.8)\\,1))"
    return (f"drawtext=fontfile={font}:textfile={txt_path}:fontsize={fontsize}:"
            f"fontcolor=white:borderw=2:bordercolor=black@0.75:"
            f"x=(w-text_w)/2:y={y}:alpha='{alpha}'")


def normalize_shot(shot, font, font_bold):
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
    if shot.get("narration"):
        vf.append(sub_filter(font, textfile(f"{sid}.txt", shot["narration"]), dur))

    if sid == "01":
        vf.append("fade=t=in:st=0:d=0.8")
    if sid == "03":  # flashback: flash to white
        vf.append(f"fade=t=out:st={dur - 0.6:.2f}:d=0.6:color=white")
    if sid == "04":  # ...and back from white
        vf.append("fade=t=in:st=0:d=0.5:color=white")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--song", default=str(AUDIO / "song_take1.mp3"))
    ap.add_argument("--no-vo", action="store_true", help="skip the Japanese voiceover mix")
    args = ap.parse_args()

    shots = load_shotlist()["shots"]
    NORM.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    font = pick_font(FONT_CANDIDATES, "FONT")
    font_bold = pick_font(FONT_BOLD_CANDIDATES, "FONT_BOLD")

    # 1. Normalize + decorate every shot, then hard-cut concat.
    norm_files = [normalize_shot(s, font, font_bold) for s in shots]
    concat_list = NORM / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in norm_files))
    silent = NORM / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", silent])

    total = sum(float(s["duration"]) for s in shots)

    # 2. Audio: song + (optionally) Japanese VO lines placed at shot start times,
    #    with the music ducked under the voice.
    song = Path(args.song)
    if not song.exists():
        raise SystemExit(f"Song not found: {song} — run 03_music.py (or pass --song).")

    vo_items = []  # (offset_seconds, path)
    if not args.no_vo:
        t = 0.0
        for s in shots:
            p = AUDIO / f"vo_{s['id']}.mp3"
            if s.get("narration_ja") and p.exists():
                vo_items.append((t + 0.25, p))
            elif s.get("narration_ja"):
                print(f"  [warn] no VO file for shot {s['id']} ({p.name}) — skipping line")
            t += float(s["duration"])

    inputs = ["-i", silent, "-i", song] + [x for _, p in vo_items for x in ("-i", p)]
    music = (f"[1:a]apad,atrim=0:{total:.3f},afade=t=in:st=0:d=1.0,"
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
