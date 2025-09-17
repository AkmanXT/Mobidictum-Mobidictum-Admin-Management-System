#!/usr/bin/env python3
import csv
import json
import os
import re
from typing import List, Dict, Any

CSV_PATH = os.path.join("email_outreach", "followups_preview_from_json.csv")
JSON_PATH = os.path.join("email_outreach", "followups_to_send.json")


def extract_bio_from_body(body: str) -> str:
    m = re.search(r"Proposed short bio:\s*\n([\s\S]*?)(\n\n|\nNext step:)", body)
    return (m.group(1).strip() if m else "")


def qc_rows(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    issues = []
    emails = []
    for r in rows:
        email = (r.get("email") or "").strip().lower()
        emails.append(email)
        body = r.get("body") or ""
        bio = extract_bio_from_body(body)
        if not bio or bio == "[PASTE 2–3 SENTENCE BIO HERE]":
            issues.append({"type": "missing_bio", "email": email})
        if "Optional feedback:" in body:
            issues.append({"type": "optional_feedback_present", "email": email})
        if "https://form.jotform.com/242603789142964" not in body:
            issues.append({"type": "missing_form_link", "email": email})
        if "https://mobidictum.com/events/mobidictum-conference-2025/" not in body:
            issues.append({"type": "missing_conf_link", "email": email})
        if "speaker2025" not in body:
            issues.append({"type": "missing_speaker_code", "email": email})
        if not body.startswith("Hi "):
            issues.append({"type": "missing_greeting", "email": email})

    # Duplicate emails
    dupes = {e for e in emails if emails.count(e) > 1}
    for e in sorted(dupes):
        issues.append({"type": "duplicate_email", "email": e})

    return {"total": len(rows), "issues": issues}


def main() -> int:
    # CSV
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    csv_report = qc_rows(csv_rows)

    # JSON
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        msgs = json.load(f)
    json_rows = []
    for m in msgs:
        json_rows.append({
            "email": (m.get("to") or [""])[0],
            "body": m.get("text") or "",
        })
    json_report = qc_rows(json_rows)

    print("CSV:")
    print(f"  total_rows: {csv_report['total']}")
    print(f"  issues: {len(csv_report['issues'])}")
    for i in csv_report['issues']:
        print(f"    - {i['type']}: {i['email']}")

    print("JSON:")
    print(f"  total_msgs: {json_report['total']}")
    print(f"  issues: {len(json_report['issues'])}")
    for i in json_report['issues']:
        print(f"    - {i['type']}: {i['email']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


