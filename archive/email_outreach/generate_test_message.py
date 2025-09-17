#!/usr/bin/env python3
import argparse
import json
import os
import re
from html import escape as html_escape


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a single test email message JSON.")
    parser.add_argument("--to", required=True, help="Primary recipient email address")
    parser.add_argument("--cc", nargs="*", default=[], help="CC recipients (space-separated)")
    parser.add_argument(
        "--subject",
        default='Mobidictum Conference 2025 Speaker - {speaker_name}',
        help="Email subject. Use {speaker_name} placeholder to include the name",
    )
    parser.add_argument(
        "--name", default="Serdar", help="Speaker name to personalize the template"
    )
    parser.add_argument(
        "--form-url",
        default="https://form.jotform.com/242603789142964",
        help="Speaker registration form URL",
    )
    parser.add_argument(
        "--ticket-code", default="speaker2025", help="Ticket code to include"
    )
    parser.add_argument(
        "--template",
        default=os.path.join("email_outreach", "template.txt"),
        help="Path to the text template",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("email_outreach", "test_message.json"),
        help="Output JSON path",
    )
    return parser.parse_args()


def read_template(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def personalize(template_text: str, speaker_name: str, form_url: str, ticket_code: str) -> str:
    text = template_text
    replacements = {
        "{{speaker_name}}": speaker_name,
        "Speaker Name": speaker_name,
        "{{form_url}}": form_url,
        "{{ticket_code}}": ticket_code,
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def to_html(text: str) -> str:
    escaped = html_escape(text)
    linked = re.sub(r"(https?://[^\s]+)", lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', escaped)
    return linked.replace("\n", "<br/>")


def main() -> int:
    args = parse_args()
    if not os.path.exists(os.path.dirname(os.path.abspath(args.output))):
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    template_text = read_template(args.template)
    text_body = personalize(template_text, args.name, args.form_url, args.ticket_code)
    html_body = to_html(text_body)

    message = {
        "to": [args.to],
        "cc": list(args.cc) if args.cc else [],
        "subject": (args.subject or '').format(speaker_name=args.name),
        "text": text_body,
        "html": html_body,
        "metadata": {"speaker_name": args.name, "confirmed": "Test"},
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump([message], f, ensure_ascii=False, indent=2)

    print(f"Wrote test message to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


