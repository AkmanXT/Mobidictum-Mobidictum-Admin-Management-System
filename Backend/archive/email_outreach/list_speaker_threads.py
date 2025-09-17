#!/usr/bin/env python3
"""
List Gmail threads for speaker outreach and mark open vs replied.

Usage (example):
  python email_outreach/list_speaker_threads.py \
    --credentials email_outreach/client_secret.json \
    --token email_outreach/token.json \
    --emails email_outreach/speakers_list.txt \
    --out email_outreach/speaker_threads.csv

Outputs a CSV with columns:
email,threadId,lastMessageId,subject,lastFrom,lastDate,messageCount,status

Status is "open" if the last message in the thread is from the sender (you), otherwise "replied".
"""

import argparse
import csv
import os
from typing import Iterable, List, Dict, Any, Set


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]


def ensure_gmail_service(credentials_path: str, token_path: str, reauth: bool = False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if not reauth and os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None
    needs_flow = False
    if not creds or not creds.valid:
        needs_flow = True
    else:
        current_scopes = set(creds.scopes or [])
        required_scopes = set(SCOPES)
        if not required_scopes.issubset(current_scopes):
            needs_flow = True
    if needs_flow:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service


def parse_emails(path: str) -> List[str]:
    emails: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            # allow comma-separated in a single line
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            for p in parts:
                emails.add(p.lower())
    return sorted(emails)


def get_header(headers: List[Dict[str, str]], name: str) -> str:
    lname = name.lower()
    for h in headers:
        if h.get("name", "").lower() == lname:
            return h.get("value", "")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="List Gmail speaker threads and mark open vs replied")
    parser.add_argument("--credentials", required=True, help="Path to Google OAuth client_secret JSON")
    parser.add_argument("--token", default=os.path.join("email_outreach", "token.json"), help="Path to OAuth token JSON")
    parser.add_argument("--emails", required=True, help="Path to newline/comma-separated emails list")
    parser.add_argument("--out", default=os.path.join("email_outreach", "speaker_threads.csv"), help="Output CSV path")
    parser.add_argument("--query", default='subject:"Mobidictum Conference 2025 Speaker -"', help="Additional Gmail search query (quoted if it contains spaces)")
    parser.add_argument("--reauth", action="store_true", help="Force re-auth")
    args = parser.parse_args()

    emails = parse_emails(args.emails)
    if not emails:
        print("No emails provided.")
        return 1

    service = ensure_gmail_service(args.credentials, args.token, args.reauth)
    profile = service.users().getProfile(userId="me").execute()
    my_email = (profile.get("emailAddress") or "").lower()

    rows: List[Dict[str, Any]] = []

    for addr in emails:
        # Search sent messages to that address, with the subject pattern
        query = f'in:sent to:{addr} {args.query}'
        resp = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
        messages = resp.get("messages", []) or []
        if not messages:
            rows.append({
                "email": addr,
                "threadId": "",
                "lastMessageId": "",
                "subject": "",
                "lastFrom": "",
                "lastDate": "",
                "messageCount": 0,
                "status": "missing",
            })
            continue

        # Choose the most recent message by internalDate
        most_recent = None
        most_recent_date = -1
        for m in messages:
            mid = m["id"]
            mg = service.users().messages().get(userId="me", id=mid, format="metadata", metadataHeaders=["Subject","Date"]).execute()
            internal = int(mg.get("internalDate", 0))
            if internal > most_recent_date:
                most_recent_date = internal
                most_recent = mg

        assert most_recent is not None
        thread_id = most_recent["threadId"]

        # Fetch the thread and determine last message and who sent it
        th = service.users().threads().get(userId="me", id=thread_id, format="metadata", metadataHeaders=["From","To","Subject","Date"]).execute()
        msgs = th.get("messages", [])
        # Sort by internalDate ascending
        msgs_sorted = sorted(msgs, key=lambda x: int(x.get("internalDate", 0)))
        last = msgs_sorted[-1]
        headers = last.get("payload", {}).get("headers", [])
        last_from = get_header(headers, "From")
        last_date = get_header(headers, "Date")

        # Extract thread subject from the first message (normalize Re:) if available
        first_headers = msgs_sorted[0].get("payload", {}).get("headers", [])
        subject = get_header(first_headers, "Subject") or get_header(headers, "Subject")

        # Determine open/replied: last message not from me -> replied, else open
        status = "open"
        if my_email and my_email in last_from.lower():
            status = "open"
        else:
            status = "replied"

        rows.append({
            "email": addr,
            "threadId": thread_id,
            "lastMessageId": last.get("id", ""),
            "subject": subject,
            "lastFrom": last_from,
            "lastDate": last_date,
            "messageCount": len(msgs_sorted),
            "status": status,
        })

    # Write CSV
    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["email","threadId","lastMessageId","subject","lastFrom","lastDate","messageCount","status"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


