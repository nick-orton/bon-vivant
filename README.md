# Bon Vivant — Weekly Local Newsletter

A self-hosted weekly newsletter that uses Claude AI to research and write a
personalized local newsletter for your city, delivered to your Gmail every
Sunday morning.

## How It Works

1. Every Sunday at ~9–10 AM ET, GitHub Actions runs `generate_newsletter.py`
2. The script loads your prompt from `newsletter_prompt.md`
3. Claude (`claude-opus-4-7`) uses live web search to research local news, events, and weather
4. The newsletter is formatted as HTML and emailed to you via Gmail

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

**Gmail App Password** (not your login password)
1. Enable 2-Step Verification: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Create an App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - App: "Mail", Device: "Other" → name it "bon-vivant"
3. Copy the 16-character password

### 3. Add GitHub Actions secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GMAIL_SENDER` | Gmail address that sends the newsletter |
| `GMAIL_RECIPIENT` | Address that receives it (can be the same) |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from step 2 |

### 4. Test it now

Go to **Actions → Weekly Local Newsletter → Run workflow → Run workflow**.

Check your inbox in 2–3 minutes. If it doesn't arrive, check the Actions run log and your spam folder.

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

## Costs

| Service | Cost |
|---|---|
| Anthropic API | ~$0.10–$0.50 per newsletter |
| GitHub Actions | Free (well within free tier) |
| Gmail | Free |

~$5–25/year at 52 newsletters.

## Troubleshooting

**"Environment variable not set"** — a GitHub secret is missing or misspelled (they're case-sensitive).

**Gmail authentication failed** — you used your login password instead of an App Password. App Passwords are 16 characters.

**Emails going to spam** — mark one as "Not spam" and add your sender address to contacts.

## File Structure

```
bon-vivant/
├── generate_newsletter.py          # Main script
├── newsletter_prompt.md            # YOUR prompt — edit this!
├── requirements.txt
├── .env.example                    # Documents required env vars
├── .github/
│   └── workflows/
│       └── weekly-newsletter.yml  # Sunday morning schedule
└── README.md
```
