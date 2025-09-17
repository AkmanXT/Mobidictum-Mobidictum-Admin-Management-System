#!/usr/bin/env python3
import argparse
import csv
import json
import os


def main() -> int:
    ap = argparse.ArgumentParser(description="Update followups_to_send.json from a preview CSV with edited bodies")
    ap.add_argument("--json-in", default=os.path.join("email_outreach","followups_to_send.json"))
    ap.add_argument("--csv-in", default=os.path.join("email_outreach","followups_preview_from_json.csv"))
    ap.add_argument("--json-out", default=os.path.join("email_outreach","followups_to_send.json"))
    args = ap.parse_args()

    msgs = json.load(open(args.json_in, "r", encoding="utf-8"))

    # Build lookup by primary to email
    by_email = { (m.get("to") or [""])[0].lower(): m for m in msgs }

    with open(args.csv_in, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            email = (row.get("email") or "").strip().lower()
            body = (row.get("body") or "").replace("\r\n", "\n")
            if email in by_email:
                by_email[email]["text"] = body

    # Write back
    os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(list(by_email.values()), f, ensure_ascii=False, indent=2)
    print(f"Updated {len(by_email)} messages in {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


