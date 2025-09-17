#!/usr/bin/env python3
"""
Send emails via Gmail API from a messages.json file.

Each entry in the JSON should be an object like:
{
  "to": ["to@example.com"],
  "cc": ["cc1@example.com"],
  "subject": "Subject",
  "text": "Plain text body",
  "html": "<p>HTML body</p>",
  "metadata": { ... }
}
"""

import argparse
import base64
import json
import os
import sys
import time
from typing import List, Dict, Any

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send messages via Gmail API from a JSON file")
    parser.add_argument("--input", "-i", required=True, help="Path to messages JSON (array of messages)")
    parser.add_argument(
        "--credentials",
        required=True,
        help="Path to Google OAuth client_secret JSON (Installed app)"
    )
    parser.add_argument(
        "--token",
        default=os.path.join("email_outreach", "token.json"),
        help="Path to store/read OAuth token"
    )
    parser.add_argument(
        "--from-address",
        default=None,
        help="Optional From header (defaults to Gmail account)"
    )
    parser.add_argument(
        "--signature",
        default=None,
        help="Email signature to append to all messages"
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not send; just print actions")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay seconds between sends")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of messages to send")
    parser.add_argument("--reauth", action="store_true", help="Force re-auth (ignore existing token)")
    parser.add_argument(
        "--export-sent",
        default=None,
        help="Export already-sent recipient emails to this path (one per line) and exit",
    )
    parser.add_argument(
        "--sent-query",
        default="subject:Mobidictum Conference 2025 Speaker -",
        help="Gmail search query to identify previously sent emails",
    )
    return parser.parse_args()


def load_messages(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list):
        raise ValueError("Input JSON must be an array or object")
    return data


def build_mime(msg: Dict[str, Any], from_address: str | None, signature: str | None = None) -> MIMEMultipart:
    mime = MIMEMultipart("alternative")
    to_list = msg.get("to") or []
    cc_list = msg.get("cc") or []
    subject = msg.get("subject") or ""
    text = msg.get("text") or ""
    html = msg.get("html")

    # Add signature if provided
    if signature:
        text += f"\n\n{signature}"
        if html:
            html += f"<br><br>{signature.replace(chr(10), '<br>')}"

    if from_address:
        mime["From"] = from_address
    mime["To"] = ", ".join(to_list)
    if cc_list:
        mime["Cc"] = ", ".join(cc_list)
    mime["Subject"] = subject

    # Attach plain text first, then HTML
    mime.attach(MIMEText(text, "plain", "utf-8"))
    if html:
        mime.attach(MIMEText(html, "html", "utf-8"))
    return mime


def ensure_gmail_service(credentials_path: str, token_path: str, reauth: bool = False):
    # Lazy import to avoid heavy deps when dry-running
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


def export_sent_recipients(service, query: str, export_path: str) -> int:
    from googleapiclient.errors import HttpError

    recipients: set[str] = set()
    try:
        page_token = None
        while True:
            resp = (
                service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=100)
                .execute()
            )
            ids = [m["id"] for m in resp.get("messages", [])]
            for mid in ids:
                msg = service.users().messages().get(userId="me", id=mid, format="metadata", metadataHeaders=["To","Cc"]).execute()
                headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
                for field in ("to", "cc"):
                    if field in headers:
                        for part in headers[field].split(","):
                            addr = part.strip()
                            # Extract email between <...> if present
                            if "<" in addr and ">" in addr:
                                addr = addr[addr.find("<")+1:addr.find(">")]
                            if addr:
                                recipients.add(addr.lower())
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except HttpError as e:
        print(f"Failed to query sent messages: {e}")
        return 1

    with open(export_path, "w", encoding="utf-8") as f:
        for r in sorted(recipients):
            f.write(r + "\n")
    print(f"Exported {len(recipients)} sent recipients to {export_path}")
    return 0


def send_via_gmail(service, mime: MIMEMultipart) -> Dict[str, Any]:
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return result


def main() -> int:
    args = parse_args()
    if getattr(args, "export_sent", None) is not None:
        service = ensure_gmail_service(args.credentials, args.token, args.reauth)
        return export_sent_recipients(service, args.sent_query, args.export_sent)

    messages = load_messages(args.input)
    total = len(messages)
    if args.limit is not None:
        messages = messages[: args.limit]

    if args.dry_run:
        print(f"[DRY RUN] Would process {len(messages)}/{total} messages from {args.input}")
        for i, msg in enumerate(messages, 1):
            to_list = msg.get("to") or []
            cc_list = msg.get("cc") or []
            print(f"[{i}] To: {', '.join(to_list)} | Cc: {', '.join(cc_list)} | Subject: {msg.get('subject','')}")
        return 0

    service = ensure_gmail_service(args.credentials, args.token, args.reauth)

    sent = 0
    for i, msg in enumerate(messages, 1):
        mime = build_mime(msg, args.from_address, args.signature)
        result = send_via_gmail(service, mime)
        sent += 1
        msg_id = result.get("id")
        print(f"[{i}] Sent message id={msg_id} to={mime['To']} cc={mime.get('Cc','')}")
        if i < len(messages) and args.delay > 0:
            time.sleep(args.delay)

    print(f"Sent {sent}/{len(messages)} messages.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)


