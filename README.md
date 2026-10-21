# AI History Shorts

Turns researched scripts into narrated vertical Shorts (1080x1920) with AI images,
camera-motion effects, captions and optional background music. Runs entirely on
GitHub Actions; no API keys or secrets are needed.

## How it works

1. Each script in `queue/` is a JSON file: title, description, hashtags and 8 scenes
   (narration + image prompt).
2. Every day, the **Daily Short** workflow renders the oldest script:
   - images: Pollinations (Flux)
   - voice: edge-tts
   - zoom/pan motion, fades and burned-in captions: ffmpeg
3. The video is published as a GitHub Release (`final.mp4`, `thumb.jpg`, upload text),
   and the script moves to `done/`.

## Run one now

Actions tab → **Daily Short** → **Run workflow**.

## Add background music

Commit a royalty-free `music.mp3` to the repo root (e.g. from the YouTube Audio Library).
It loops under the narration at low volume.

## Script format

```json
{
  "title": "...",
  "description": "...",
  "hashtags": ["#History", "#Shorts"],
  "scenes": [
    {"narration": "...", "image_prompt": "..."}
  ]
}
```
