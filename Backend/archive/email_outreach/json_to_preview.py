#!/usr/bin/env python3
import argparse
import csv
import json
import os


def main() -> int:
    ap = argparse.ArgumentParser(description="Export followups_to_send.json to a readable preview CSV")
    ap.add_argument("--in", dest="inp", default=os.path.join("email_outreach","followups_to_send.json"))
    ap.add_argument("--out", dest="outp", default=os.path.join("email_outreach","followups_preview_from_json.csv"))
    args = ap.parse_args()

    data = json.load(open(args.inp, "r", encoding="utf-8"))
    rows = []
    for m in data:
        email = (m.get("to") or [""])[0]
        subject = m.get("subject") or ""
        body = m.get("text") or ""
        name = (m.get("metadata") or {}).get("name") or ""
        rows.append({
            "email": email,
            "name": name,
            "subject": subject,
            "body": body,
        })

    os.makedirs(os.path.dirname(args.outp), exist_ok=True)
    with open(args.outp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email","name","subject","body"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


