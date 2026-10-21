"""Render the next queued script into a vertical Short.

queue/*.json  ->  out/final.mp4, out/thumb.jpg, out/upload.txt
The rendered script is moved to done/ so each run makes a new video.
No API keys needed: images from Pollinations (Flux), voice from edge-tts.
"""
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
import edge_tts

ROOT = Path(__file__).parent
QUEUE, DONE, OUT = ROOT / "queue", ROOT / "done", ROOT / "out"
W, H, FPS = 1080, 1920, 30
VOICE = "en-US-AndrewNeural"
STYLE = ("cinematic photorealistic, historically accurate, dramatic natural lighting, "
         "rich detail, 35mm film still, vertical composition, no text, no watermark, no logo")
MOVES = ["in", "panr", "out", "panl"]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        sys.exit(f"command failed: {cmd[0]}")
    return r.stdout


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", str(path)]).strip())


def get_image(prompt, path, seed):
    for attempt in range(6):
        url = (f"https://image.pollinations.ai/prompt/{quote(prompt + ', ' + STYLE)}"
               f"?width={W}&height={H}&seed={seed + attempt * 1000}&nologo=true&model=flux")
        try:
            r = requests.get(url, timeout=240)
            if r.ok and r.headers.get("content-type", "").startswith("image") and len(r.content) > 20000:
                path.write_bytes(r.content)
                return
            print(f"  image attempt {attempt + 1}: HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"  image attempt {attempt + 1}: {e}")
        time.sleep(10 * (attempt + 1))
    sys.exit(f"image failed: {prompt[:60]}")


async def _tts(text, path):
    await edge_tts.Communicate(text, VOICE, rate="+6%").save(str(path))


def tts(text, path):
    for attempt in range(4):
        try:
            asyncio.run(_tts(text, path))
            if path.exists() and path.stat().st_size > 1000:
                return
        except Exception as e:  # edge-tts raises several error types
            print(f"  voice attempt {attempt + 1}: {e}")
        time.sleep(5 * (attempt + 1))
    sys.exit("voice failed")


def motion(kind, frames):
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if kind == "in":
        return f"1+0.18*on/{frames}", cx, cy
    if kind == "out":
        return f"1.18-0.18*on/{frames}", cx, cy
    if kind == "panr":
        return "1.15", f"(iw-iw/zoom)*on/{frames}", cy
    return "1.15", f"(iw-iw/zoom)*(1-on/{frames})", cy


def render_clip(img, audio, out, kind):
    dur = duration(audio) + 0.3
    frames = int(dur * FPS) + 1
    z, x, y = motion(kind, frames)
    vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS},"
          f"fade=t=in:st=0:d=0.2,fade=t=out:st={dur - 0.2:.2f}:d=0.2,format=yuv420p")
    run(["ffmpeg", "-y", "-i", str(img), "-i", str(audio), "-filter_complex",
         f"[0:v]{vf}[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-t", f"{dur:.2f}", str(out)])
    return dur


def ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def captions(scenes, durs, path, chunk=4):
    lines, t, i = [], 0.0, 1
    for sc, d in zip(scenes, durs):
        words = sc["narration"].split()
        parts = [" ".join(words[k:k + chunk]) for k in range(0, len(words), chunk)]
        total = sum(len(p) for p in parts) or 1
        speak = d - 0.3
        for p in parts:
            seg = speak * len(p) / total
            lines.append(f"{i}\n{ts(t)} --> {ts(t + seg)}\n{p.upper()}\n")
            t += seg
            i += 1
        t += 0.3
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    pending = sorted(QUEUE.glob("*.json"))
    if not pending:
        sys.exit("queue is empty - add scripts to queue/")
    src = pending[0]
    data = json.loads(src.read_text(encoding="utf-8"))
    scenes = data["scenes"]
    print(f"Rendering: {data['title']} ({len(scenes)} scenes)")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    seed = sum(map(ord, data["title"])) % 90000

    durs, clips = [], []
    for k, sc in enumerate(scenes, 1):
        print(f"Scene {k}/{len(scenes)}")
        img, aud, clip = OUT / f"img_{k:02}.jpg", OUT / f"vo_{k:02}.mp3", OUT / f"clip_{k:02}.mp4"
        get_image(sc["image_prompt"], img, seed + k)
        tts(sc["narration"], aud)
        durs.append(render_clip(img, aud, clip, MOVES[(k - 1) % len(MOVES)]))
        clips.append(clip.name)
        time.sleep(3)  # be gentle with the free image service

    (OUT / "list.txt").write_text("".join(f"file '{c}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4"], cwd=OUT)
    captions(scenes, durs, OUT / "subs.srt")

    style = ("Fontname=DejaVu Sans,Fontsize=10,Bold=1,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=70")
    sub = f"subtitles=subs.srt:force_style='{style}'"
    music = ROOT / "music.mp3"
    cmd = ["ffmpeg", "-y", "-i", "joined.mp4"]
    if music.exists():
        cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                f"[0:v]{sub}[v];[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-vf", sub]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac",
            "-movflags", "+faststart", "final.mp4"]
    run(cmd, cwd=OUT)
    shutil.copy(OUT / "img_01.jpg", OUT / "thumb.jpg")

    (OUT / "upload.txt").write_text(
        f"{data['title']}\n\n{data['description']}\n\n"
        "Visuals are AI-generated illustrations; script researched and written for this channel.\n\n"
        f"{' '.join(data['hashtags'])}\n", encoding="utf-8")
    (OUT / "title.txt").write_text(data["title"], encoding="utf-8")

    DONE.mkdir(exist_ok=True)
    src.rename(DONE / src.name)
    print(f"Done: {OUT / 'final.mp4'} ({duration(OUT / 'final.mp4'):.1f}s)")


if __name__ == "__main__":
    main()
