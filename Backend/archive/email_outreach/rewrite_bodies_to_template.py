#!/usr/bin/env python3
import json
import os
import re

SRC = os.path.join("email_outreach", "followups_to_send.json")

TEMPLATE = (
    "Hi {first_name},\n\n"
    "We have recently introduced a feature to support the conference production: short bios generated from public sources with the help of an AI tool. These bios are meant only as a starting point, not a final source of truth, and we know creative technology comes with its caveats.\n\n"
    "That is why we would love your feedback on whether this draft helps streamline the process.\n\n"
    "Proposed short bio:\n{bio}\n\n"
    "Next step:\n"
    "Please complete the form by 15 September so we can prepare marketing materials and ensure every session receives the attention it deserves.\n"
    "https://form.jotform.com/242603789142964\n\n"
    "You can use the text as is, update it, or replace it with your own version.\n\n"
    "Additional details\n"
    "• Sessions run between 10:00 and 16:00. Exact time and stage will be shared later.\n"
    "• Speaker tickets can be claimed using code speaker2025 on the conference page: https://mobidictum.com/events/mobidictum-conference-2025/\n"
    "• Hotel discounts are listed on the event page.\n"
    "• On 20 October we will host an Executive Mixer for Speakers and Executive ticket holders, and you are warmly invited.\n\n"
    "Thank you in advance and looking forward to your input.\n\n"
    "Best regards,\n"
    "Serdar\n"
    "Marketing Manager, Mobidictum\n"
)


def extract_first_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    return name.split()[0]


def extract_bio(text: str) -> str:
    # Grab contents after "Proposed short bio:" up to the next blank line or "Next step:"/"What to do:"/Useful details
    m = re.search(r"Proposed short bio:\s*\n([\s\S]*?)(\n\n|\nNext step:|\nWhat to do:|\nUseful details:)", text)
    if m:
        return m.group(1).strip()
    return ""


def rewrite_body(original_text: str, first_name: str) -> str:
    bio = extract_bio(original_text)
    return TEMPLATE.format(first_name=first_name or "", bio=bio or "[PASTE 2–3 SENTENCE BIO HERE]")


def main() -> int:
    data = json.load(open(SRC, "r", encoding="utf-8"))
    for msg in data:
        meta = msg.get("metadata") or {}
        name = meta.get("name") or ""
        first_name = extract_first_name(name)
        body = msg.get("text") or ""
        msg["text"] = rewrite_body(body, first_name)
    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Rewrote all bodies to the new template")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
