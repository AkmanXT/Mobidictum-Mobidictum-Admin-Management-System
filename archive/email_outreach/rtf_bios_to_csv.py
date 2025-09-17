#!/usr/bin/env python3
"""
Convert the speaker bios RTF into a clean CSV aligned to the thread map.

Inputs:
  --rtf   path to RTF bios file (default: email_outreach/speaker bios.rtf)
  --map   path to map CSV (email,name,threadId,lastMessageId)
  --out   output CSV path (default: email_outreach/speaker_bios_clean.csv)

Outputs CSV columns: name,email,title,bio,status
  status = 'found' if a bio block was extracted from the RTF, else 'missing'
"""

import argparse
import csv
import os
import re
import unicodedata
from typing import Dict, List, Tuple


def strip_rtf(rtf: str) -> str:
    # Normalize common RTF paragraph markers
    text = rtf.replace("\\line", "\n").replace("\\par", "\n")
    # Remove most control words (e.g., \\fs22, \\lang9, \\f0) and their optional numeric args
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    # Remove group braces
    text = text.replace("{", "").replace("}", "")
    # Collapse spaces
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\t", " ", text)
    # Trim excessive newlines
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def normalize_key(s: str) -> str:
    # Remove accents/diacritics and lower-case to make matching resilient
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()


def extract_block_after(text: str, start_idx: int) -> Tuple[str, str]:
    """Given index where a name occurs, extract (title, bio_block).
    Assumes the next non-empty line is the title, and the following paragraph(s)
    until the next blank line belong to the bio.
    """
    # Move to end of the current line
    end_line = text.find("\n", start_idx)
    if end_line == -1:
        end_line = len(text)
    cursor = end_line + 1

    # Skip blank lines
    while cursor < len(text) and text[cursor] in "\n \t":
        cursor += 1

    # Next line is title
    next_nl = text.find("\n", cursor)
    title = text[cursor: next_nl if next_nl != -1 else len(text)].strip()
    cursor = (next_nl + 1) if next_nl != -1 else len(text)

    # Skip blank lines before bio
    while cursor < len(text) and text[cursor] in "\n \t":
        cursor += 1

    # Bio stops at first double newline
    m = re.search(r"\n\s*\n", text[cursor:])
    bio = text[cursor: cursor + m.start()] if m else text[cursor:]
    bio = bio.strip()
    return title, bio


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse speaker bios RTF to CSV")
    ap.add_argument("--rtf", default=os.path.join("email_outreach","speaker bios.rtf"))
    ap.add_argument("--map", default=os.path.join("email_outreach","speaker_threads_map.csv"))
    ap.add_argument("--out", default=os.path.join("email_outreach","speaker_bios_clean.csv"))
    args = ap.parse_args()

    rtf_text = open(args.rtf, "r", encoding="utf-8", errors="ignore").read()
    plain = strip_rtf(rtf_text)
    plain_norm = normalize_key(plain)

    # Load mapping of emails to names
    with open(args.map, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    out_rows: List[Dict[str, str]] = []
    missing: List[str] = []

    for r in rows:
        name = (r.get("name") or "").strip()
        email = (r.get("email") or "").strip()
        if not name:
            continue
        key = normalize_key(name)
        idx = plain_norm.find(key)
        if idx == -1:
            out_rows.append({
                "name": name,
                "email": email,
                "title": "",
                "bio": "",
                "status": "missing",
            })
            missing.append(name)
            continue

        # Map back to original text index by slicing lengths (safe due to same normalization only removing diacritics)
        # Find approximate real index by searching original text around the normalized hit
        # Fallback: search in original text directly
        real_idx = plain.lower().find(name.split()[0].lower(), max(0, idx - 50), idx + 200)
        if real_idx == -1:
            real_idx = idx
        title, bio = extract_block_after(plain, real_idx)
        # Keep first 3 sentences for preview cleanliness
        sentences = re.split(r"(?<=[\.!?])\s+", bio)
        short_bio = " ".join([s for s in sentences if s][:3]).strip()

        out_rows.append({
            "name": name,
            "email": email,
            "title": title,
            "bio": short_bio or bio,
            "status": "found",
        })

    # Write CSV
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name","email","title","bio","status"])
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {args.out}; missing bios: {len(missing)}")
    if missing:
        print("Missing:")
        for m in missing:
            print(" -", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


