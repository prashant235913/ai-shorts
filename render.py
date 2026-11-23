"""Render the next queued script into a vertical Short.

queue/*.json  ->  out/final.mp4, out/thumb.jpg, out/upload.txt, out/meta.json
The rendered script is moved to done/ so each run makes a new video.
No API keys needed: images from Pollinations (Flux), voice from edge-tts.

Retention features: big hook text on screen for the first seconds, and
word-by-word captions with the spoken word highlighted.
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
RATE = "+8%"
PAD = 0.25  # silence after each scene
STYLE = ("cinematic photorealistic, historically accurate, dramatic natural lighting, "
         "rich detail, 35mm film still, vertical composition, no text, no watermark, no logo")
MOVES = ["in", "panr", "out", "panl"]
HOOK_SECS = 2.8


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
    """Save speech to path; return [(start, end, word)] in seconds (may be empty)."""
    try:
        comm = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
    except TypeError:  # older edge-tts: word boundaries are the default
        comm = edge_tts.Communicate(text, VOICE, rate=RATE)
    words = []
    with open(path, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append((s, s + ch["duration"] / 1e7, ch["text"]))
    return words


def tts(text, path):
    for attempt in range(4):
        try:
            words = asyncio.run(_tts(text, path))
            if path.exists() and path.stat().st_size > 1000:
                return words
        except Exception as e:  # edge-tts raises several error types
            print(f"  voice attempt {attempt + 1}: {e}")
        time.sleep(5 * (attempt + 1))
    sys.exit("voice failed")


def fallback_words(text, dur):
    """Spread words over the clip by length when edge-tts gives no timings."""
    ws = text.split()
    total = sum(len(w) + 1 for w in ws) or 1
    t, out = 0.0, []
    for w in ws:
        d = dur * (len(w) + 1) / total
        out.append((t, t + d, w))
        t += d
    return out


def motion(kind, frames):
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if kind == "in":
        return f"1+0.20*on/{frames}", cx, cy
    if kind == "out":
        return f"1.20-0.20*on/{frames}", cx, cy
    if kind == "panr":
        return "1.16", f"(iw-iw/zoom)*on/{frames}", cy
    return "1.16", f"(iw-iw/zoom)*(1-on/{frames})", cy


def render_clip(img, audio, out, kind):
    dur = duration(audio) + PAD
    frames = int(dur * FPS) + 1
    z, x, y = motion(kind, frames)
    vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS},"
          f"fade=t=in:st=0:d=0.15,fade=t=out:st={dur - 0.15:.2f}:d=0.15,format=yuv420p")
    run(["ffmpeg", "-y", "-i", str(img), "-i", str(audio), "-filter_complex",
         f"[0:v]{vf}[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-t", f"{dur:.2f}", str(out)])
    return dur


def ass_time(t):
    cs = int(round(max(t, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def esc(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def write_ass(words, hook, path, group=3):
    """words: [(start, end, word)] on the full timeline."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,70,70,560,1
Style: Hook,DejaVu Sans,96,&H0000E5FF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,0,0,3,22,0,8,60,60,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    if hook:
        ev.append(f"Dialogue: 1,{ass_time(0)},{ass_time(HOOK_SECS)},Hook,,0,0,0,,"
                  f"{{\\fad(0,250)\\t(0,180,\\fscx112\\fscy112)\\t(180,360,\\fscx100\\fscy100)}}"
                  f"{esc(hook.upper())}")
    for g in range(0, len(words), group):
        chunk = words[g:g + group]
        for k, (s, e, _) in enumerate(chunk):
            end = chunk[k + 1][0] if k + 1 < len(chunk) else e + 0.12
            if g + group < len(words) and k + 1 == len(chunk):
                end = min(end, words[g + group][0])
            parts = []
            for j, (_, _, w) in enumerate(chunk):
                w = esc(w.upper())
                parts.append(f"{{\\c&H0000E5FF&\\fscx110\\fscy110}}{w}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}"
                             if j == k else w)
            ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(max(end, s + 0.05))},Cap,,0,0,0,,{' '.join(parts)}")
    path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


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

    clips, timeline, t0 = [], [], 0.0
    for k, sc in enumerate(scenes, 1):
        print(f"Scene {k}/{len(scenes)}")
        img, aud, clip = OUT / f"img_{k:02}.jpg", OUT / f"vo_{k:02}.mp3", OUT / f"clip_{k:02}.mp4"
        get_image(sc["image_prompt"], img, seed + k)
        words = tts(sc["narration"], aud)
        dur = render_clip(img, aud, clip, MOVES[(k - 1) % len(MOVES)])
        if not words:
            words = fallback_words(sc["narration"], dur - PAD)
        timeline += [(t0 + s, t0 + e, w) for s, e, w in words]
        t0 += dur
        clips.append(clip.name)
        time.sleep(3)  # be gentle with the free image service

    (OUT / "list.txt").write_text("".join(f"file '{c}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4"], cwd=OUT)
    write_ass(timeline, data.get("hook", ""), OUT / "subs.ass")

    sub = "ass=subs.ass"
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

    tags = [h.lstrip("#") for h in data["hashtags"]]
    desc = (f"{data['description']}\n\n"
            "Visuals are AI-generated illustrations; script researched and written for this channel.\n\n"
            f"{' '.join(data['hashtags'])}")
    (OUT / "upload.txt").write_text(f"{data['title']}\n\n{desc}\n", encoding="utf-8")
    (OUT / "title.txt").write_text(data["title"], encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(
        {"title": data["title"], "description": desc, "tags": tags}, ensure_ascii=False), encoding="utf-8")

    DONE.mkdir(exist_ok=True)
    src.rename(DONE / src.name)
    print(f"Done: {OUT / 'final.mp4'} ({duration(OUT / 'final.mp4'):.1f}s)")


if __name__ == "__main__":
    main()
