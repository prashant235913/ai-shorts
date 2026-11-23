# Channel setup (all in a browser, nothing to install)

## 1. Every day: get the video (works now)

A new Short is rendered every morning at 06:49 IST.
GitHub → this repo → **Releases** → newest release → download `final.mp4`.
The release notes hold the title, description and hashtags. Paste them in.

To get a phone alert for each new video: open the repo in the GitHub app → **Watch** → **Custom** → **Releases**.

Until auto-upload is switched on, post it yourself (about 2 minutes):
- **YouTube app** → + → upload `final.mp4`. It is vertical and under 60s, so it becomes a Short. Turn on "Altered or synthetic content".
- **Instagram** → + → Reel → same file and caption.

## 2. Channel profile

- Name ideas: **Time Window**, **History You Never Saw**, **Ancient Eyes**, **Back In Time Shorts**
- Bio: *Step inside history. Real places, real events, as they looked back then. New Short every day.*
- Profile picture: an hourglass or keyhole over ancient ruins. Run `img_01.jpg` from any release through a free editor, or just use a thumbnail.
- Use the same name on YouTube and Instagram.

## 3. YouTube auto-upload (one time, ~20 min)

Important: YouTube locks videos uploaded by a new, unaudited API project to **private**.
Do step 3e first and wait for approval before adding the secrets. Until then, keep uploading by hand.

a. https://console.cloud.google.com → create project "ai-shorts" → **APIs & Services → Library** → enable **YouTube Data API v3**.
b. **OAuth consent screen** → External → fill the app name and your email → add yourself as a test user → **Publish app** ("In production"). Without this, the token expires after 7 days.
c. **Credentials → Create credentials → OAuth client ID** → Web application → Authorized redirect URI: `https://developers.google.com/oauthplayground`. Copy the Client ID and Client secret.
d. https://developers.google.com/oauthplayground → gear icon → tick "Use your own OAuth credentials" → paste both → in step 1 type the scope `https://www.googleapis.com/auth/youtube.upload` → Authorize (pick your channel's Google account) → **Exchange authorization code for tokens** → copy the **Refresh token**.
e. Request the API audit: https://support.google.com/youtube/contact/yt_api_form (say it uploads your own channel's daily Shorts).
f. After approval: GitHub repo → **Settings → Secrets and variables → Actions** → New secret:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

## 4. Instagram auto-upload (one time, ~15 min)

a. In Instagram: Settings → Account type → switch to **Professional (Creator)**.
b. https://developers.facebook.com → My Apps → Create app → use case **Manage messaging & content on Instagram** (Instagram API with Instagram login).
c. In the app: **Instagram → API setup with Instagram login** → add your Instagram account → **Generate token**. Allow publishing permissions. Copy the token.
d. GitHub secret `IG_TOKEN` = that token. The token lasts 60 days, so generate a new one before it expires.

Each run then posts the video as a Reel. If something fails, the run log shows why (Actions → Daily Short → Upload step). The video is still saved in Releases.

## 5. How the money comes

- **YouTube Partner Program**: 1,000 subscribers plus 10M Shorts views in 90 days, or 4,000 watch hours. After that you earn from Shorts ad revenue.
- Shorts pay little per view. Growth comes from posting daily for months.
- What builds it: comment back on early comments, pin a question, and keep the series consistent.
- Avoid "mass-produced" demonetisation: every script here is unique and researched. Keep it that way, and don't reuse the same script with small changes.
- Later: add long videos (8–10 min), which pay far more, and brand deals once you have an audience.

## 6. More scripts

The queue holds 30 scripts (one month). When it runs low, ask Claude to write the next batch in the same format into `queue/`.
