#!/usr/bin/env python3
"""
bon-vivant: Weekly Local Newsletter Generator

Reads newsletter_prompt.md, calls Claude with web search to research
local events, then sends the result as an HTML email via Gmail SMTP.
"""

import os
import smtplib
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import markdown2
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_SENDER = os.environ["GMAIL_SENDER"]
GMAIL_RECIPIENT = os.environ["GMAIL_RECIPIENT"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

MODEL = "claude-opus-4-7"
PROMPT_FILE = Path(__file__).parent / "newsletter_prompt.md"

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}

SYSTEM_PROMPT = (
    "Knowledgeable member of the New York cultural elite who is sharing their knowledge of current events in a newsletter. "
    "Your newsletters are well-researched, engaging, and well formatted."
    "as clean, readable HTML suitable for email clients. "
    "You always verify information with web searches before including it."
    "You always include dates, locations, and times."
)

EMAIL_HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{
      font-family: Georgia, 'Times New Roman', serif;
      max-width: 680px;
      margin: 0 auto;
      padding: 24px 16px;
      background: #fafaf8;
      color: #1a1a1a;
      line-height: 1.7;
    }}
    h1 {{ color: #2c4a2e; border-bottom: 2px solid #2c4a2e; padding-bottom: 8px; }}
    h2 {{ color: #3d6b40; margin-top: 32px; }}
    h3 {{ color: #4a7a4d; }}
    a {{ color: #2c4a2e; }}
    blockquote {{
      border-left: 4px solid #2c4a2e;
      margin: 16px 0;
      padding: 8px 16px;
      background: #f0f4f0;
      font-style: italic;
    }}
    hr {{ border: none; border-top: 1px solid #d0d8d0; margin: 32px 0; }}
    ul {{ padding-left: 20px; }}
    li {{ margin-bottom: 8px; }}
    .footer {{
      font-size: 0.85em;
      color: #666;
      border-top: 1px solid #d0d8d0;
      margin-top: 40px;
      padding-top: 16px;
    }}
  </style>
</head>
<body>
{content}
<div class="footer">
  <p>You're receiving this because you set up the <strong>bon-vivant</strong> weekly newsletter.</p>
</div>
</body>
</html>
"""


def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    template = PROMPT_FILE.read_text(encoding="utf-8")
    today = date.today().strftime("%A, %B %d, %Y")
    return template.replace("{{TODAY_DATE}}", today)


def generate_newsletter_content(prompt: str) -> str:
    """
    Call Claude with web search enabled, running the tool-use loop until
    Claude reaches end_turn and returns the final text content.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": prompt}]

    print("Calling Claude API (Claude will search the web — this takes ~1-2 minutes)...")

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        )

        print(f"  stop_reason={response.stop_reason}, blocks={len(response.content)}")
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text_parts = [
                block.text
                for block in response.content
                if hasattr(block, "text") and block.text
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
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break
        else:
            # max_tokens, stop_sequence, or other — extract what we have
            print(f"Warning: unexpected stop_reason '{response.stop_reason}'")
            text_parts = [
                block.text
                for block in response.content
                if hasattr(block, "text") and block.text
            ]
            return "\n\n".join(text_parts)


def send_email(subject: str, html_body: str, plain_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = GMAIL_RECIPIENT
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"Sending to {GMAIL_RECIPIENT}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_SENDER, GMAIL_RECIPIENT, msg.as_string())
    print("Email sent.")


def main() -> None:
    today = date.today()
    subject = f"Your Weekly Local Newsletter — {today.strftime('%B %d, %Y')}"

    print("Loading prompt...")
    prompt = load_prompt()

    raw_content = generate_newsletter_content(prompt)

    # If Claude returned raw HTML, use it directly; otherwise convert markdown
    if raw_content.lstrip().startswith("<"):
        content_html = raw_content
    else:
        content_html = markdown2.markdown(
            raw_content,
            extras=["fenced-code-blocks", "tables", "header-ids", "smarty-pants"],
        )

    full_html = EMAIL_HTML_WRAPPER.format(subject=subject, content=content_html)
    send_email(subject, full_html, raw_content)
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
