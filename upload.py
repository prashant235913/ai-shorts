"""Upload out/final.mp4 to YouTube and/or Instagram.

Each platform runs only if its GitHub secrets are set (see SETUP.md); otherwise it is skipped.
YouTube:   YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (optional YT_PRIVACY, default public)
Instagram: IG_TOKEN (Instagram API with Instagram Login), optional IG_USER_ID; needs VIDEO_URL
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

OUT = Path(__file__).parent / "out"
meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
video = OUT / "final.mp4"
failed = []


def youtube():
    cid, secret, refresh = (os.getenv(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    if not (cid and secret and refresh):
        print("YouTube: secrets not set, skipping")
        return
    tok = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": cid, "client_secret": secret, "refresh_token": refresh,
        "grant_type": "refresh_token"}, timeout=60)
    tok.raise_for_status()
    auth = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    body = {
        "snippet": {"title": meta["title"][:100], "description": meta["description"][:4900],
                    "tags": meta["tags"][:15], "categoryId": "27"},
        "status": {"privacyStatus": os.getenv("YT_PRIVACY", "public") or "public",
                   "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    size = video.stat().st_size
    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={**auth, "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(body), timeout=60)
    init.raise_for_status()
    with open(video, "rb") as f:
        up = requests.put(init.headers["Location"], headers={**auth, "Content-Type": "video/mp4"},
                          data=f, timeout=900)
    up.raise_for_status()
    print(f"YouTube: uploaded https://youtube.com/shorts/{up.json()['id']}")


def instagram():
    token = os.getenv("IG_TOKEN", "").strip()
    url = os.getenv("VIDEO_URL", "").strip()
    if not token:
        print("Instagram: secrets not set, skipping")
        return
    if not url:
        raise RuntimeError("VIDEO_URL missing")
    # GitHub release links redirect to a signed download URL; hand Instagram the final one.
    url = requests.head(url, allow_redirects=True, timeout=60).url
    base = "https://graph.instagram.com"
    uid = os.getenv("IG_USER_ID", "").strip() or "me"
    caption = f"{meta['title']}\n\n{meta['description']}"[:2150]
    r = requests.post(f"{base}/{uid}/media", data={
        "media_type": "REELS", "video_url": url, "caption": caption,
        "share_to_feed": "true", "access_token": token}, timeout=120)
    if not r.ok:
        raise RuntimeError(f"create container: {r.text}")
    cid = r.json()["id"]
    for _ in range(40):  # up to ~10 minutes
        time.sleep(15)
        s = requests.get(f"{base}/{cid}", params={"fields": "status_code", "access_token": token}, timeout=60).json()
        code = s.get("status_code")
        print(f"  Instagram processing: {code}")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"processing failed: {s}")
    else:
        raise RuntimeError("processing timed out")
    p = requests.post(f"{base}/{uid}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=120)
    if not p.ok:
        raise RuntimeError(f"publish: {p.text}")
    print(f"Instagram: published reel {p.json().get('id')}")


for name, fn in (("YouTube", youtube), ("Instagram", instagram)):
    try:
        fn()
    except Exception as e:  # keep going so one platform can't block the other
        print(f"{name} upload FAILED: {e}")
        failed.append(name)

if failed:
    sys.exit(f"failed: {', '.join(failed)}")
