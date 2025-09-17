#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
from html import escape as html_escape


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate personalized email messages JSON from a speakers CSV."
    )
    parser.add_argument(
        "--input",
        "-i",
        default="Conference Speaker Schedule 2025 - Sheet28.csv",
        help="Path to input CSV with columns: Speakers, Confirmed, Email",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=os.path.join("email_outreach", "messages.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--subject",
        default='Mobidictum Conference 2025 Speaker - {speaker_name}',
        help="Email subject. Use {speaker_name} placeholder to include the name",
    )
    parser.add_argument(
        "--cc",
        nargs="*",
        default=["serdar@mobidictum.com", "batuhan@mobidictum.com"],
        help="Email addresses to CC on every message",
    )
    parser.add_argument(
        "--template",
        default=os.path.join("email_outreach", "template.txt"),
        help="Path to plain-text template with placeholders {{speaker_name}}, {{form_url}}, {{ticket_code}}",
    )
    parser.add_argument(
        "--form-url",
        default="https://form.jotform.com/242603789142964",
        help="Speaker registration form URL",
    )
    parser.add_argument(
        "--ticket-code",
        default="speaker2025",
        help="Ticket discount/promo code to include",
    )
    parser.add_argument(
        "--include-unconfirmed",
        action="store_true",
        help="Include rows where Confirmed is not 'Yes'",
    )
    parser.add_argument(
        "--send-to-all-on-row",
        action="store_true",
        help="If a row contains multiple emails, send to all parsed addresses",
    )
    parser.add_argument(
        "--exclude-file",
        default=None,
        help="Optional path to a newline-separated list of emails to exclude",
    )
    parser.add_argument(
        "--preview-csv",
        default=None,
        help="Optional path to write a preview CSV of messages to be sent",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optionally limit the number of generated messages (for testing)",
    )
    return parser.parse_args()


def read_template(template_path: str) -> str:
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def parse_email_field(email_field: str) -> list[str]:
    if not email_field:
        return []
    # Split on comma/semicolon and strip whitespace
    parts = re.split(r"[;,]", email_field)
    emails: list[str] = []
    for p in parts:
        e = p.strip()
        if not e:
            continue
        emails.append(e)
    # De-duplicate while preserving order
    seen = set()
    unique: list[str] = []
    for e in emails:
        if e.lower() in seen:
            continue
        seen.add(e.lower())
        unique.append(e)
    return unique


def to_html(text: str) -> str:
    # Basic plain-text to HTML conversion: escape, linkify URLs, preserve line breaks.
    escaped = html_escape(text)
    # Linkify URLs
    url_pattern = re.compile(r"(https?://[^\s]+)")
    linked = url_pattern.sub(lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', escaped)
    # Convert line breaks
    return linked.replace("\n", "<br/>")


def extract_first_name(full_name: str) -> str:
    name = (full_name or "").strip()
    # Remove surrounding quotes if present
    if len(name) >= 2 and ((name[0] == '"' and name[-1] == '"') or (name[0] == "'" and name[-1] == "'")):
        name = name[1:-1].strip()
    # Split by whitespace and take the first token
    parts = re.split(r"\s+", name)
    return parts[0] if parts and parts[0] else name


def personalize(template_text: str, speaker_name: str, form_url: str, ticket_code: str) -> str:
    # Support both explicit placeholders and literal fallback strings
    text = template_text
    replacements = {
        "{{speaker_name}}": speaker_name,
        "{{first_name}}": speaker_name,
        "Speaker Name": speaker_name,  # fallback if template hasn't been updated
        "{{form_url}}": form_url,
        "{{ticket_code}}": ticket_code,
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def load_rows(csv_path: str) -> list[dict]:
    rows: list[dict] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def main() -> int:
    args = parse_args()

    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    template_text = read_template(args.template)
    rows = load_rows(args.input)

    # Load exclusion list if provided
    exclude_set: set[str] = set()
    if args.exclude_file and os.path.exists(args.exclude_file):
        with open(args.exclude_file, "r", encoding="utf-8") as f:
            for line in f:
                e = line.strip().lower()
                if e:
                    exclude_set.add(e)

    preview_rows: list[tuple[str, str, str]] = []  # (email, first_name, subject)

    messages = []
    for row in rows:
        name = (row.get("Speakers") or "").strip()
        first_name = extract_first_name(name)
        confirmed = (row.get("Confirmed") or "").strip()
        email_field = (row.get("Email") or "").strip()

        if not args.include_unconfirmed and confirmed.lower() != "yes":
            continue

        to_emails = parse_email_field(email_field)
        if not to_emails:
            # Skip rows with no email
            continue

        # Filter out excluded emails
        to_emails = [e for e in to_emails if e.lower() not in exclude_set]
        # If not sending to all, just keep the first remaining email
        if not args.send_to_all_on_row:
            to_emails = to_emails[:1]

        text_body = personalize(
            template_text=template_text,
            speaker_name=first_name,
            form_url=args["form_url"] if isinstance(args, dict) and "form_url" in args else args.form_url,
            ticket_code=args["ticket_code"] if isinstance(args, dict) and "ticket_code" in args else args.ticket_code,
        )

        html_body = to_html(text_body)

        message = {
            "to": to_emails,
            "cc": args.cc,
            "subject": (args.subject or '').format(speaker_name=first_name),
            "text": text_body,
            "html": html_body,
            "metadata": {
                "speaker_name": name,
                "first_name": first_name,
                "confirmed": confirmed,
            },
        }
        if to_emails:
            messages.append(message)
            # Add preview rows
            for e in to_emails:
                preview_rows.append((e, first_name, (args.subject or '').format(speaker_name=first_name)))

        if args.limit is not None and len(messages) >= args.limit:
            break

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    if args.preview_csv:
        import csv as _csv
        with open(args.preview_csv, "w", encoding="utf-8", newline="") as pf:
            writer = _csv.writer(pf)
            writer.writerow(["email", "first_name", "subject"])
            writer.writerows(preview_rows)

    print(f"Wrote {len(messages)} messages to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)


