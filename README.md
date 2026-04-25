# Bon Vivant — Weekly Local Newsletter

A self-hosted weekly newsletter that uses Claude AI to research and write a
personalized local newsletter for your city, posted to a Google Group every
Sunday morning so all group members receive it.

## How It Works

1. Every Sunday at ~9–10 AM ET, GitHub Actions runs `generate_newsletter.py`
2. The script loads your prompt from `newsletter_prompt.md`
3. Each newsletter section (Music, Art, Food, Talks) is researched in parallel by **Claude Sonnet** (web search) and **Gemini 2.0 Flash** (Google Search); results are deduplicated by Claude Haiku
4. **Claude Opus** synthesizes the deduplicated research into the final newsletter HTML
5. The newsletter is posted to your Google Group by emailing the group's address via Gmail SMTP

## Setup (~10 minutes)

### 1. Customize your newsletter prompt

Open `newsletter_prompt.md` and fill in the **USER-EDITABLE SECTION** near the top:

- **City / Neighborhood** — your city and any neighborhood specifics
- **Reader context** — optional interests, family situation, etc.

Commit and push:
```bash
git add newsletter_prompt.md
git commit -m "Set my city and preferences"
git push
```

### 2. Get your credentials

**Anthropic API key**
1. Go to [console.anthropic.com](https://console.anthropic.com/) and create a key

**Gemini API key**
1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) and create a key

**Gmail App Password** (not your login password)
1. Enable 2-Step Verification: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Create an App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - App: "Mail", Device: "Other" → name it "bon-vivant"
3. Copy the 16-character password

**Google Group**
1. Create (or choose) a group at [groups.google.com](https://groups.google.com/)
2. In the group's **Settings → Posting policies**, make sure **email posting is enabled**
3. Under **Who can post**, allow your `GMAIL_SENDER` address to post
   (easiest: add that address as a member of the group)
4. Note the group's address (e.g. `my-newsletter@googlegroups.com`)

### 3. Add GitHub Actions secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GEMINI_API_KEY` | Your Gemini API key (from Google AI Studio) |
| `GMAIL_SENDER` | Gmail address that posts the newsletter (must be allowed to post to the group) |
| `GOOGLE_GROUP_EMAIL` | The Google Group's email address (e.g. `my-newsletter@googlegroups.com`) |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from step 2 |

### 4. Test it now

Go to **Actions → Weekly Local Newsletter → Run workflow → Run workflow**.

Check the group (at [groups.google.com](https://groups.google.com/) or in subscribers' inboxes) in 2–3 minutes. If the post doesn't appear, check the Actions run log and the group's moderation queue.

### 5. Optional: run locally

```bash
cp .env.example .env
# Edit .env with your real values

pip install -r requirements.txt
python generate_newsletter.py
```

## Customization

**Change your city or interests** — edit `newsletter_prompt.md` and push. Takes effect immediately (or test via "Run workflow").

**Change the delivery time** — edit `.github/workflows/weekly-newsletter.yml`:
```yaml
- cron: '0 14 * * 0'   # 2 PM UTC = 9 AM ET (winter) / 10 AM ET (summer)
```
Use [crontab.guru](https://crontab.guru/) to find your preferred UTC time.

**Change the newsletter style entirely** — `newsletter_prompt.md` drives everything. Rewrite it however you like.

**Curate venues to always include or always exclude** — drop markdown files into `sources/include/` (venues the agent must always check) or `sources/exclude/` (venues, organizers, or categories the agent must never feature). One file per category, bulleted lists grouped under `**Neighborhood**` headers. Every `.md` file in those directories is picked up on the next run — no code change required. See `sources/README.md` for the exact format.

## Costs

| Service | Cost |
|---|---|
| Anthropic API | ~$0.10–$0.50 per newsletter (Sonnet × 4 + Haiku × 4 + Opus × 1) |
| Gemini API | Free tier covers typical usage; see [AI Studio pricing](https://ai.google.dev/pricing) |
| GitHub Actions | Free (well within free tier) |
| Gmail | Free |

~$5–25/year at 52 newsletters.

## Troubleshooting

**"Environment variable not set"** — a GitHub secret is missing or misspelled (they're case-sensitive).

**Gmail authentication failed** — you used your login password instead of an App Password. App Passwords are 16 characters.

**Post not appearing in the group** — check the group's moderation queue, confirm `GMAIL_SENDER` is allowed to post, and confirm email posting is enabled in the group's posting policies. Bounce messages will arrive in the `GMAIL_SENDER` inbox.

**Posts going to spam for group members** — individual members can mark one as "Not spam" and add the group's address to their contacts.

## File Structure

```
bon-vivant/
├── generate_newsletter.py          # Main script
├── newsletter_prompt.md            # YOUR prompt — edit this!
├── sources/                        # Curated venue lists (include & exclude)
│   ├── README.md
│   ├── include/
│   │   ├── galleries.md
│   │   ├── jazz.md
│   │   ├── classical-music-venues.md
│   │   └── independent.md
│   └── exclude/
│       └── venues.md
├── requirements.txt
├── .env.example                    # Documents required env vars
├── .github/
│   └── workflows/
│       └── weekly-newsletter.yml  # Sunday morning schedule
└── README.md
```
