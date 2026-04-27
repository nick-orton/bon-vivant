# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Bon Vivant is a Python script that generates and emails a weekly HTML newsletter of NYC cultural events (music, art, food, talks) every Sunday. It uses a multi-model AI pipeline to research, deduplicate, and synthesize events.

## Running

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in API keys and email credentials
python generate_newsletter.py
```

Required environment variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `GROUP_EMAIL`.

Set `NEWSLETTER_PARALLEL=0` to use legacy single-model (Opus-only) mode instead of the parallel pipeline.

The newsletter also runs automatically via GitHub Actions every Sunday at 9 AM ET (`.github/workflows/weekly-newsletter.yml`).

## Architecture

**Entry point:** `generate_newsletter.py` 

**Pipeline (default multi-model mode):**
1. **Parallel research** — Claude Sonnet 4.6 (web search tool) and Gemini 2.0 Flash (Google Search) each research all 4 sections concurrently using `prompts/section_research.md`
2. **Deduplication** — Claude Haiku merges Sonnet + Gemini results per section
3. **Synthesis** — Claude Opus assembles deduplicated sections into a polished HTML newsletter using `prompts/synthesis.md`
4. **Delivery** — Gmail SMTP posts HTML to a Google Group

**Sections** (hardcoded in script): Music (classical/jazz), Art (galleries), Food (new restaurants), Talks (intellectual events).

**Customizable content files:**
- `newsletter_prompt.md` — top section is user-editable (city, neighborhood, reader context); rest is research instruction
- `sources/include/` — venue lists that research prompts must check (galleries.md, jazz.md, classical-music-venues.md, independent.md)
- `sources/exclude/venues.md` — venues/organizers to never feature
- `templates/email_wrapper.html` — wraps generated HTML; uses `{subject}` and `{content}` placeholders
- `prompts/system.md` — shared system prompt used by all Claude API calls
- `prompts/section_research.md` — research prompt template
- `prompts/dedup.md` — deduplication prompt template (uses `{section_heading}` placeholder)
- `prompts/synthesis.md` — synthesis prompt template

**Prompt caching:** Anthropic API calls use `"cache_control": {"type": "ephemeral"}` on large system prompts to reduce cost.

**Tool use pattern:** Claude's `web_search_20250305` tool uses server-side execution; the script handles `pause_turn` stop reasons by re-submitting the conversation.

## No Tests

There is no test suite. Manual testing is done by triggering the GitHub Actions workflow via "Run workflow" in the Actions tab.


## Git Workflow
- Always create a feature branch on the current branch before making changes
- Branch naming: `feature/*`, `bugfix/*`, `hotfix/*`
- Base branch: `main`


