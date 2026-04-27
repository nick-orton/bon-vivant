#!/usr/bin/env python3
"""
bon-vivant: Weekly Local Newsletter Generator

Reads newsletter_prompt.md, calls Claude with web search to research
local events, then posts the result as an HTML message to a Google Group
by emailing the group's address via Gmail SMTP.
"""

import os
import re
import smtplib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import google.genai as genai
import google.genai.types as genai_types
import markdown2
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GMAIL_SENDER = os.environ["GMAIL_SENDER"]
GOOGLE_GROUP_EMAIL = os.environ["GOOGLE_GROUP_EMAIL"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

MODEL = "claude-opus-4-7"  # legacy single-model constant (rollback path)
RESEARCH_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-2.0-flash"
DEDUP_MODEL = "claude-haiku-4-5-20251001"
SYNTHESIS_MODEL = "claude-opus-4-7"

PROMPT_FILE = Path(__file__).parent / "newsletter_prompt.md"
RESEARCH_PROMPT_FILE = Path(__file__).parent / "prompts" / "section_research.md"
SYNTHESIS_PROMPT_FILE = Path(__file__).parent / "prompts" / "synthesis.md"
DEDUP_PROMPT_FILE = Path(__file__).parent / "prompts" / "dedup.md"
SOURCES_DIR = Path(__file__).parent / "sources"
EMPTY_SOURCE_PLACEHOLDER = "_(none curated yet)_"

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}

SECTIONS = [
    {
        "id": "music",
        "heading": "Music",
        "description": "Live classical music and jazz performances in NYC in the next 14 days.",
        "venue_files": ["jazz", "classical-music-venues"],
    },
    {
        "id": "art",
        "heading": "Art",
        "description": "Gallery openings and museum exhibition openings. Prioritize smaller independent galleries over major institutions.",
        "venue_files": ["galleries", "independent"],
    },
    {
        "id": "food",
        "heading": "Food",
        "description": "New restaurant openings, special chef tastings, and wine events in NYC next 14 days.",
        "venue_files": [],
    },
    {
        "id": "talks",
        "heading": "Talks",
        "description": "Talks by artists, scientists, or other intellectual figures in NYC next 14 days.",
        "venue_files": [],
    },
]

SYSTEM_PROMPT = (
    "You are a knowledgeable member of the New York cultural elite writing a weekly newsletter. "
    "Your newsletters are well-researched, engaging, and formatted as clean, readable HTML suitable for email clients. "
    "You always verify information with web searches before including it. "
    "You always include dates, locations, and times. "
    "IMPORTANT: Your response must consist solely of the newsletter HTML. "
    "Begin directly with the <h1> tag. "
    "Do not write any preamble, commentary, summary of your research, or explanation before or after the HTML."
)

_EMAIL_TEMPLATE_PATH = Path(__file__).parent / "templates" / "email_wrapper.html"


def _load_source_dir(subdir: str) -> str:
    """
    Concatenate every .md file in SOURCES_DIR/<subdir> in sorted filename
    order, prefixing each with a bolded `**filename**` line so the model sees
    category boundaries. Returns EMPTY_SOURCE_PLACEHOLDER if the directory is
    missing or contains no markdown files.
    """
    directory = SOURCES_DIR / subdir
    if not directory.is_dir():
        return EMPTY_SOURCE_PLACEHOLDER
    files = sorted(directory.glob("*.md"))
    if not files:
        return EMPTY_SOURCE_PLACEHOLDER
    sections = [
        f"**{path.stem}**\n\n{path.read_text(encoding='utf-8').strip()}"
        for path in files
    ]
    return "\n\n".join(sections)


def _load_venues_for_section(section: dict) -> str:
    """Load only the venue .md files listed in section['venue_files']."""
    stems = section.get("venue_files", [])
    if not stems:
        return EMPTY_SOURCE_PLACEHOLDER
    parts = []
    for stem in stems:
        path = SOURCES_DIR / "include" / f"{stem}.md"
        if path.exists():
            parts.append(f"**{stem}**\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) if parts else EMPTY_SOURCE_PLACEHOLDER


def _build_section_research_prompt(
    section: dict, today: str, exclude_venues: str
) -> str:
    """Build a focused research prompt for a single newsletter section."""
    include_venues = _load_venues_for_section(section)
    template = RESEARCH_PROMPT_FILE.read_text(encoding="utf-8")
    return (
        template
        .replace("{{TODAY}}", today)
        .replace("{{SECTION_HEADING}}", section["heading"])
        .replace("{{SECTION_DESCRIPTION}}", section["description"])
        .replace("{{INCLUDE_VENUES}}", include_venues)
        .replace("{{EXCLUDE_VENUES}}", exclude_venues)
    )


def _build_synthesis_prompt(section_results: dict[str, str], today: str) -> str:
    """Build the Opus synthesis prompt from pre-researched section content."""
    sections_text = ""
    for section in SECTIONS:
        events = section_results.get(section["id"], "").strip() or "No events found this week."
        sections_text += f"\n\n=== {section['heading']} (researched events) ===\n{events}"

    template = SYNTHESIS_PROMPT_FILE.read_text(encoding="utf-8")
    return (
        template
        .replace("{{TODAY}}", today)
        .replace("{{SECTIONS_TEXT}}", sections_text)
    )


def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    template = PROMPT_FILE.read_text(encoding="utf-8")
    today = date.today().strftime("%A, %B %d, %Y")
    return (
        template
        .replace("{{TODAY_DATE}}", today)
        .replace("{{INCLUDE_VENUES}}", _load_source_dir("include"))
        .replace("{{EXCLUDE_VENUES}}", _load_source_dir("exclude"))
    )


def _research_section_sonnet(section: dict, today: str, exclude_venues: str) -> str:
    """Call Sonnet with web search for one section; return raw event text."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = _build_section_research_prompt(section, today, exclude_venues)
    messages = [{"role": "user", "content": prompt}]
    print(f"  [sonnet/{section['id']}] starting research...")
    return _run_tool_loop(client, RESEARCH_MODEL, SYSTEM_PROMPT, messages, max_tokens=16384)


def _research_section_gemini(section: dict, today: str, exclude_venues: str) -> str:
    """Call Gemini 2.0 Flash with Google Search grounding for one section; return raw event text."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = _build_section_research_prompt(section, today, exclude_venues)
    print(f"  [gemini/{section['id']}] starting research...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            temperature=0.2,
        ),
    )
    print(f"  [gemini/{section['id']}] done.")
    return response.text or ""


def _run_tool_loop(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list,
    max_tokens: int = 16384,
    tools: list | None = None,
) -> str:
    """Run the Anthropic tool-use loop until end_turn; return final text."""
    if tools is None:
        tools = [WEB_SEARCH_TOOL]

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=tools,
            messages=messages,
        )

        print(f"  [{model}] stop_reason={response.stop_reason}, blocks={len(response.content)}")
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for i, block in enumerate(response.content):
                preview = getattr(block, "text", getattr(block, "thinking", ""))[:120].replace("\n", " ")
                print(f"    block[{i}] type={block.type!r} preview={preview!r}")
            text_parts = [
                block.text
                for block in response.content
                if block.type == "text" and block.text
            ]
            if not text_parts:
                raise ValueError("Claude returned no text in final response.")
            return "\n\n".join(text_parts)

        if response.stop_reason == "tool_use":
            # web_search_20250305 executes server-side; this handles any
            # standard tool_use blocks that require client acknowledgement.
            tool_results = [
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Search executed.",
                }
                for block in response.content
                if block.type == "tool_use"
            ]
            if not tool_results:
                raise RuntimeError(
                    "Claude returned stop_reason='tool_use' with no tool_use blocks."
                )
            messages.append({"role": "user", "content": tool_results})
            continue

        if response.stop_reason == "pause_turn":
            # Server-side tool (e.g. web_search_20250305) paused the turn;
            # continue the loop without adding any new user content.
            continue

        if response.stop_reason == "max_tokens":
            # Collect all text generated across every prior assistant turn so
            # we return partial results rather than failing the whole section.
            all_text = []
            for msg in messages:
                if msg.get("role") == "assistant":
                    content = msg["content"]
                    if isinstance(content, list):
                        for block in content:
                            t = getattr(block, "text", None)
                            if t and t.strip():
                                all_text.append(t)
            print(f"  WARNING: {model} hit max_tokens after {len(messages)} turns; returning partial results ({len(all_text)} text blocks collected)")
            if all_text:
                return "\n\n".join(all_text)
            raise RuntimeError(
                f"Claude ({model}) hit the max_tokens limit with no text generated."
            )

        raise RuntimeError(
            f"Unexpected stop_reason from Claude ({model}): {response.stop_reason!r}"
        )


def _deduplicate_section_results(
    section: dict, sonnet_events: str, gemini_events: str
) -> str:
    """Merge Sonnet and Gemini event lists via Haiku, removing duplicates."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    combined = (
        f"=== Claude Sonnet results ===\n{sonnet_events}"
        f"\n\n=== Gemini results ===\n{gemini_events}"
    )
    dedup_system = DEDUP_PROMPT_FILE.read_text().format(
        section_heading=section["heading"]
    )
    messages = [{"role": "user", "content": combined}]
    print(f"  [haiku/{section['id']}] deduplicating...")
    return _run_tool_loop(client, DEDUP_MODEL, dedup_system, messages, max_tokens=4096, tools=[])


def _research_section_parallel(
    section: dict, today: str, exclude_venues: str
) -> tuple[str, str]:
    """Fire Sonnet and Gemini concurrently for one section, then deduplicate."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_sonnet = executor.submit(_research_section_sonnet, section, today, exclude_venues)
        f_gemini = executor.submit(_research_section_gemini, section, today, exclude_venues)
        sonnet_result = f_sonnet.result()
        try:
            gemini_result = f_gemini.result()
        except Exception as exc:
            print(f"  [gemini/{section['id']}] failed, using sonnet-only: {exc}")
            return (section["id"], sonnet_result)
    deduped = _deduplicate_section_results(section, sonnet_result, gemini_result)
    return (section["id"], deduped)


def research_all_sections(today: str, exclude_venues: str) -> dict[str, str]:
    """Run parallel dual-model research for all SECTIONS concurrently."""
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(SECTIONS)) as executor:
        futures = {
            executor.submit(_research_section_parallel, section, today, exclude_venues): section
            for section in SECTIONS
        }
        for future in as_completed(futures):
            section = futures[future]
            try:
                section_id, events = future.result()
                results[section_id] = events
                print(f"  [{section_id}] research complete ({len(events)} chars)")
            except Exception as exc:
                print(f"  WARNING: {section['id']} research failed: {exc}")
                results[section["id"]] = ""
    return results


def synthesize_newsletter(section_results: dict[str, str], today: str) -> str:
    """Call Opus with all pre-researched content to write the final newsletter HTML."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = _build_synthesis_prompt(section_results, today)
    messages = [{"role": "user", "content": prompt}]
    print("  Calling Opus for synthesis (no web search)...")
    return _run_tool_loop(client, SYNTHESIS_MODEL, SYSTEM_PROMPT, messages, max_tokens=16384, tools=[])


def generate_newsletter_content(prompt: str) -> str:
    """Legacy single-model path. Kept for rollback via NEWSLETTER_PARALLEL=0."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": prompt}]
    print("Calling Claude API (Claude will search the web — this takes ~1-2 minutes)...")
    return _run_tool_loop(client, MODEL, SYSTEM_PROMPT, messages)


def post_to_google_group(subject: str, html_body: str, plain_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = GOOGLE_GROUP_EMAIL
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"Posting to Google Group {GOOGLE_GROUP_EMAIL}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_SENDER, GOOGLE_GROUP_EMAIL, msg.as_string())
    print("Posted to Google Group.")


def main() -> None:
    today = date.today()
    subject = f"Your Weekly Local Newsletter — {today.strftime('%B %d, %Y')}"
    today_str = today.strftime("%A, %B %d, %Y")

    if os.environ.get("NEWSLETTER_PARALLEL", "1") == "0":
        print("Running in legacy single-model mode (NEWSLETTER_PARALLEL=0)...")
        prompt = load_prompt()
        raw_content = generate_newsletter_content(prompt)
    else:
        print("Running in parallel multi-model mode...")
        exclude_venues = _load_source_dir("exclude")
        print("Researching sections (parallel Sonnet + Gemini)...")
        section_results = research_all_sections(today_str, exclude_venues)
        print("Synthesizing newsletter...")
        raw_content = synthesize_newsletter(section_results, today_str)

    # Strip any <thinking>...</thinking> blocks the model may have emitted inline.
    raw_content = re.sub(r"<thinking>.*?</thinking>", "", raw_content, flags=re.DOTALL).strip()

    # Strip any preamble (plain text or HTML paragraphs) before the newsletter
    # title. The prompt requires starting with <h1>, so anything before it is
    # unwanted narration or thinking that leaked into the text output.
    h1_match = re.search(r"<h1[\s>]", raw_content, re.IGNORECASE)
    if h1_match and h1_match.start() > 0:
        print(f"  Stripping {h1_match.start()} chars of pre-newsletter preamble")
        raw_content = raw_content[h1_match.start():]

    # If Claude returned raw HTML, use it directly; otherwise convert markdown
    if raw_content.lstrip().startswith("<"):
        content_html = raw_content
    else:
        content_html = markdown2.markdown(
            raw_content,
            extras=["fenced-code-blocks", "tables", "header-ids", "smarty-pants"],
        )

    full_html = (
        _EMAIL_TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace("{subject}", subject)
        .replace("{content}", content_html)
    )
    post_to_google_group(subject, full_html, raw_content)
    print("Done!")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"ERROR: Required environment variable not set: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
