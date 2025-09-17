#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import unicodedata
from typing import List, Dict, Tuple


SUBJECT = "Your Mobidictum speaker bio + form by 15 September"

TEMPLATE = (
    "Subject: Your Mobidictum speaker bio + form by 15 September\n\n"
    "Hi {first_name},\n\n"
    "Quick follow-up for Mobidictum Conference 2025 (21 to 22 October, Istanbul).\n\n"
    "We recently implemented a feature to speed up speaker page production: a short bio generated from public sources with an AI tool. It is a starting point, not a final source of truth—we do not assume it is 100% accurate. We’d love your feedback on whether this helps the process.\n\n"
    "Proposed short bio:\n{proposed_bio}\n\n"
    "What to do:\n\n"
    "Please complete the speaker form by 15 September 2025 and include any edits you want to your bio:\n"
    "https://form.jotform.com/242603789142964\n\n"
    "You can use the text as is, update it, or replace it with your own version.\n\n"
    "Optional feedback:\n"
    "If you have a moment, a quick note like “works for me” or “I prefer to write my own” helps us improve this feature. I’ll be watching for your feedback.\n\n"
    "Useful details:\n"
    "• Sessions run between 10:00 and 16:00. Exact time and stage will follow.\n"
    "• Claim your Speaker ticket with code speaker2025 via the conference page:\n"
    "https://mobidictum.com/events/mobidictum-conference-2025/\n\n"
    "• Hotel discounts are listed on that page.\n"
    "• On 20 October, we host an Executive Mixer for Speakers and Executive ticket holders. You are welcome to join.\n\n"
    "Thanks in advance.\n\n"
    "Best regards,\n"
    "Serdar\n"
    "Marketing Manager, Mobidictum\n"
)


def strip_rtf(rtf: str) -> str:
    text = rtf
    # Normalize line markers first
    text = text.replace("\\line", "\n").replace("\\par", "\n")
    # Remove RTF escaped unicode markers like \'f6 etc. Keep them as-is (already rendered in this file)
    # Remove control words and groups
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    # Collapse multiple newlines
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def normalize_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()


def split_sentences(text: str, max_sentences: int = 3) -> str:
    # Simple sentence split
    parts = re.split(r"(?<=[\.!?])\s+", text.strip())
    parts = [p for p in parts if p]
    return " ".join(parts[:max_sentences])


def extract_bio_for(name: str, bios_text: str) -> str | None:
    key = normalize_key(name)
    nt = normalize_key(bios_text)
    idx = nt.find(key)
    if idx == -1:
        return None
    # Take the following block up to the next blank line
    tail = bios_text[idx: idx + 3000]  # window
    # Find first two blank lines as delimiter
    m = re.search(r"\n\s*\n", tail)
    if m:
        block = tail[m.end():]
    else:
        block = tail
    # Stop at next double newline signifying next section
    m2 = re.search(r"\n\s*\n", block)
    snippet = block[:m2.start()] if m2 else block
    # Use first 2-3 sentences
    short = split_sentences(snippet, 3)
    return short.strip() if short else None


def first_name(full: str) -> str:
    t = (full or "").strip()
    return (t.split()[0] if t else "there")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build follow-up preview messages using bios and thread map")
    ap.add_argument("--map", default=os.path.join("email_outreach","speaker_threads_map.csv"))
    ap.add_argument("--bios", default=os.path.join("email_outreach","speaker bios.rtf"))
    ap.add_argument("--bios-csv", default=os.path.join("email_outreach","speaker_bios_clean.csv"))
    ap.add_argument("--out-csv", default=os.path.join("email_outreach","followups_preview.csv"))
    ap.add_argument("--out-json", default=os.path.join("email_outreach","followups_messages.json"))
    args = ap.parse_args()

    # Load mapping
    with open(args.map, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    bios_rtf = open(args.bios, "r", encoding="utf-8", errors="ignore").read()
    bios_text = strip_rtf(bios_rtf)

    # Optional CSV bios override (clean, user-edited)
    bios_by_name: Dict[str, str] = {}
    titles_by_name: Dict[str, str] = {}
    csv_only = os.path.exists(args.bios_csv)
    if csv_only:
        with open(args.bios_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                bio = (row.get("bio") or "").strip()
                title = (row.get("title") or "").strip()
                key = normalize_key(name)
                if not key:
                    continue
                if bio:
                    bios_by_name[key] = bio
                if title:
                    titles_by_name[key] = title

    preview: List[Dict[str, str]] = []
    messages: List[Dict[str, object]] = []

    for r in rows:
        email = (r.get("email") or "").strip()
        name = (r.get("name") or "").strip()
        if not email:
            continue
        # Prefer cleaned CSV bio strictly (never substitute title).
        key = normalize_key(name)
        csv_bio = bios_by_name.get(key)
        if csv_only:
            bio = csv_bio or "We don't currently have a bio on file. Please include a 2–3 sentence bio in the form link above, or reply with your own; we'll update it."
        else:
            bio = csv_bio if csv_bio else (extract_bio_for(name, bios_text) or "We don't currently have a bio on file. Please include a 2–3 sentence bio in the form link above, or reply with your own; we'll update it.")
        body = TEMPLATE.format(first_name=first_name(name), proposed_bio=bio)

        preview.append({
            "email": email,
            "name": name,
            "subject": SUBJECT,
            "body": body,
        })
        messages.append({
            "to": [email],
            "cc": [],
            "subject": SUBJECT,
            "text": body,
            "html": None,
            "metadata": {"name": name},
        })

    # Write CSV
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email","name","subject","body"])
        w.writeheader()
        w.writerows(preview)

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(preview)} previews to {args.out_csv} and messages to {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


