#!/usr/bin/env python3
"""
Send follow-up emails from followups_to_send.json, one per minute, replying in existing Gmail threads.

Features:
- Uses JSON messages with fields: to[], cc[], subject, text, threadId
- Replies in-thread via Gmail API using threadId and RFC headers (In-Reply-To, References)
- Delay between sends (default 60s)
- Duplicate protection via a CSV log (email,threadId,messageId,timestamp)
"""

import argparse
import base64
import csv
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Set


SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send followups from JSON, replying in threads with 1/min throttle")
    p.add_argument("--input", default=os.path.join("email_outreach", "followups_to_send.json"))
    p.add_argument("--credentials", required=True)
    p.add_argument("--token", default=os.path.join("email_outreach", "token.json"))
    p.add_argument("--log", default=os.path.join("email_outreach", "sent_log.csv"))
    p.add_argument("--delay", type=float, default=60.0, help="Seconds between sends")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def ensure_gmail_service(credentials_path: str, token_path: str):
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None
    if not creds or not creds.valid or not set(SCOPES).issubset(set(creds.scopes or [])):
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_last_message_rfc_id(service, thread_id: str) -> str | None:
    th = service.users().threads().get(userId="me", id=thread_id, format="metadata", metadataHeaders=["Message-Id"]).execute()
    msgs = th.get("messages", [])
    if not msgs:
        return None
    last = max(msgs, key=lambda x: int(x.get("internalDate", 0)))
    headers = last.get("payload", {}).get("headers", [])
    for h in headers:
        if (h.get("name") or "").lower() == "message-id":
            return h.get("value")
    return None


def build_mime(msg: Dict[str, Any], rfc_message_id: str | None) -> bytes:
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    to_list = msg.get("to") or []
    cc_list = msg.get("cc") or []
    subject = msg.get("subject") or ""
    text = msg.get("text") or ""

    mime = MIMEMultipart("alternative")
    mime["To"] = ", ".join(to_list)
    if cc_list:
        mime["Cc"] = ", ".join(cc_list)
    # Ensure reply subject
    subj = subject
    if subj and not subj.lower().startswith("re:"):
        subj = "Re: " + subj
    mime["Subject"] = subj

    if rfc_message_id:
        mime["In-Reply-To"] = rfc_message_id
        mime["References"] = rfc_message_id

    mime.attach(MIMEText(text, "plain", "utf-8"))
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
    return raw


def load_messages(path: str) -> List[Dict[str, Any]]:
    data = json.load(open(path, "r", encoding="utf-8"))
    if isinstance(data, dict):
        return [data]
    return list(data)


def read_sent_log(path: str) -> Set[str]:
    seen: Set[str] = set()
    if not os.path.exists(path):
        return seen
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            seen.add((row.get("email") or "").strip().lower())
    return seen


def append_sent_log(path: str, email: str, thread_id: str, message_id: str):
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp","email","threadId","messageId"])
        if not exists:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "email": email,
            "threadId": thread_id,
            "messageId": message_id,
        })


def main() -> int:
    args = parse_args()
    messages = load_messages(args.input)
    if args.limit is not None:
        messages = messages[: args.limit]

    seen = read_sent_log(args.log)
    service = None if args.dry_run else ensure_gmail_service(args.credentials, args.token)

    total = len(messages)
    sent = 0
    for i, msg in enumerate(messages, 1):
        to_email = (msg.get("to") or [""])[0].lower()
        thread_id = msg.get("threadId") or ""
        if not to_email or not thread_id:
            print(f"[{i}] SKIP missing to or threadId: to={to_email} threadId={thread_id}")
            continue
        if to_email in seen:
            print(f"[{i}] SKIP already sent to {to_email}")
            continue

        if args.dry_run:
            print(f"[{i}] DRY to={to_email} thread={thread_id}")
        else:
            rfc_mid = get_last_message_rfc_id(service, thread_id)
            raw = build_mime(msg, rfc_mid)
            res = service.users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id}).execute()
            gmail_id = res.get("id", "")
            append_sent_log(args.log, to_email, thread_id, gmail_id)
            sent += 1
            print(f"[{i}] SENT id={gmail_id} to={to_email} thread={thread_id}")
            if i < total and args.delay > 0:
                time.sleep(args.delay)

    print(f"Sent {sent}/{total} messages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


