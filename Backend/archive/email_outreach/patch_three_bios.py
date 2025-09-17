#!/usr/bin/env python3
import csv
import os
import re

SRC = os.path.join("email_outreach", "followups_preview_from_json.csv")
OUT = os.path.join("email_outreach", "followups_preview_from_json.patched.csv")

TARGET_BIOS = {
    "barbara.kotlusek@outfit7.com": (
        "Barbara Erman is Marketing & Partnerships Lead at Outfit7, where she shapes go-to-market plans and partner activations across key titles. "
        "She collaborates with product and publishing teams to translate player insights into positioning and high-performing campaigns."
    ),
    "eray@recontactgame.com": (
        "Eray Dinç is the co-founder and creative lead at Recontact Games, a studio known for mobile titles that blend cinematic storytelling with interactive gameplay. "
        "He directs the creative vision and partnerships around the Recontact series and related projects."
    ),
    "olga.romanovich@zephyrmobile.com": (
        "Olga Romanovich leads marketing at Zephyr Mobile, overseeing user acquisition, App Store optimization, and creative testing across puzzle and casual titles. "
        "She partners closely with product to align monetization strategy and roadmap priorities with audience growth."
    ),
}


def replace_bio_section(body: str, new_bio: str) -> str:
    # Find the section after "Proposed short bio:" up to the next double newline or "What to do:" line
    pattern = r"(Proposed short bio:\s*)([\s\S]*?)(\n\n|\r\n\r\n|\nWhat to do:|\r\nWhat to do:)"
    def _repl(match: re.Match) -> str:
        prefix = match.group(1)
        suffix = match.group(3)
        return f"{prefix}{new_bio}{suffix}"

    return re.sub(pattern, _repl, body, count=1)


def main() -> int:
    with open(SRC, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if email in TARGET_BIOS:
            row["body"] = replace_bio_section(row.get("body") or "", TARGET_BIOS[email])

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email","name","subject","body"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote patched CSV to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


