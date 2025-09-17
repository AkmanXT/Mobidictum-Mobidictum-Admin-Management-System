#!/usr/bin/env python3
import argparse
import csv
import os
import sys
import time
from typing import List


def build_prompt(text: str) -> str:
    return (
        "You are an editing assistant.\n"
        "Task: Clean and lightly copyedit the following email body.\n"
        "- Fix punctuation, spacing, capitalization, and paragraph breaks.\n"
        "- Ensure readable paragraphs and consistent newlines.\n"
        "- Do NOT change or add facts. Do NOT shorten or expand content.\n"
        "- Preserve all URLs, names, numbers, and dates exactly.\n"
        "- Keep the same language.\n"
        "- Output ONLY the cleaned body, no commentary.\n\n"
        "Text to clean:\n" + text
    )


def clean_bodies_via_openai(bodies: List[str], model: str, api_key: str, rate_limit_per_sec: float) -> List[str]:
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        print("OpenAI client not installed. Run: pip install openai", file=sys.stderr)
        raise

    client = OpenAI(api_key=api_key)

    cleaned: List[str] = []
    delay = 1.0 / max(rate_limit_per_sec, 1.0)
    for idx, body in enumerate(bodies):
        prompt = build_prompt(body)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a meticulous copyeditor that never changes meaning."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            out_text = (resp.choices[0].message.content or "").strip()
            cleaned.append(out_text)
        except Exception as e:
            # On any error, fall back to original text to avoid data loss
            cleaned.append(body)
        time.sleep(delay)
    return cleaned


def main() -> int:
    ap = argparse.ArgumentParser(description="Clean bios in preview CSV using OpenAI without changing facts")
    ap.add_argument("--in", dest="inp", default=os.path.join("email_outreach", "followups_preview_from_json.csv"))
    ap.add_argument("--out", dest="outp", default=os.path.join("email_outreach", "followups_preview_from_json.cleaned.csv"))
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--api-key", dest="api_key", default=os.environ.get("OPENAI_API_KEY", ""))
    ap.add_argument("--rps", type=float, default=2.0, help="Requests per second throttle")
    args = ap.parse_args()

    if not args.api_key:
        print("Missing OPENAI_API_KEY. Set env var or pass --api-key.", file=sys.stderr)
        return 2

    rows = []
    bodies = []
    with open(args.inp, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
            bodies.append(row.get("body") or "")

    cleaned_bodies = clean_bodies_via_openai(bodies, args.model, args.api_key, args.rps)

    # Write cleaned CSV
    fieldnames = ["email", "name", "subject", "body"]
    os.makedirs(os.path.dirname(args.outp), exist_ok=True)
    with open(args.outp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row, cleaned in zip(rows, cleaned_bodies):
            row_out = {
                "email": row.get("email", ""),
                "name": row.get("name", ""),
                "subject": row.get("subject", ""),
                "body": cleaned.replace("\r\n", "\n"),
            }
            w.writerow(row_out)

    print(f"Wrote cleaned CSV to {args.outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


