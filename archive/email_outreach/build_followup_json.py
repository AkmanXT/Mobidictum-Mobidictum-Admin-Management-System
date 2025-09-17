#!/usr/bin/env python3
import argparse
import csv
import json
import os


SUBJECT = "Your Mobidictum speaker bio + form by 15 September"

TEMPLATE = (
    "Subject: Your Mobidictum speaker bio + form by 15 September\n\n"
    "Hi {first_name},\n\n"
    "Quick follow-up for Mobidictum Conference 2025 (21 to 22 October, Istanbul).\n\n"
    "We recently implemented a feature to speed up speaker page production: a short bio generated from public sources with an AI tool. It is a starting point, not a final source of truth—we do not assume it is 100% accurate. We’d love your feedback on whether this helps the process.\n\n"
    "Proposed short bio:\n{bio}\n\n"
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
    "Best regards,\n\n"
    "Serdar\n"
    "Marketing Manager, Mobidictum\n"
)


def first_name(full: str) -> str:
    return (full or "").strip().split(" ")[0] or "there"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build follow-up JSON with thread IDs and template bodies")
    ap.add_argument("--map", default=os.path.join("email_outreach","speaker_threads_map.csv"), help="CSV with email,name,threadId,lastMessageId")
    ap.add_argument("--out", default=os.path.join("email_outreach","followups_to_send.json"))
    ap.add_argument("--cc", nargs="*", default=["bavucan@mobidictum.com","serdar@mobidictumc.com"], help="CC addresses")
    args = ap.parse_args()

    with open(args.map, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    messages = []
    for r in rows:
        email = (r.get("email") or "").strip()
        name = (r.get("name") or "").strip()
        thread_id = (r.get("threadId") or "").strip()
        if not email or not thread_id:
            continue

        body = TEMPLATE.format(first_name=first_name(name), bio="[PASTE 2–3 SENTENCE BIO HERE]")
        messages.append({
            "to": [email],
            "cc": args.cc,
            "subject": SUBJECT,
            "text": body,
            "threadId": thread_id,
            "metadata": {
                "name": name,
                "email": email,
            },
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(messages)} messages to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


