#!/usr/bin/env python3
"""
Detect mapped speakers without bios and schedule Gmail replies in their threads.

Inputs:
  --map: CSV with columns email,name,threadId,lastMessageId (open loops)
  --threads: CSV with columns including 'email' and 'subject' (to reuse subject)
  --bios: RTF file path containing bios text
  --credentials, --token: Gmail OAuth
  --delay-minutes: minutes to wait before sending
  --only-email: optional single email to target; finds the thread by Gmail search

This sends a reply in each thread using the provided template, addressed to the speaker's email.
"""

import argparse
import base64
import csv
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Any


SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


TEMPLATE = (
    "Your Mobidictum speaker bio + form by 15 September\n\n"
    "Hi {first_name},\n\n"
    "A quick follow-up for Mobidictum Conference 2025 (21 to 22 October, Istanbul).\n\n"
    "To speed up production, we prepared a short bio for your speaker page using publicly available info and a generative tool. This is a simple measure to keep timelines on track.\n\n"
    "Proposed short bio:\n{proposed_bio}\n\n"
    "What to do:\n\n"
    "Please complete the speaker form by 15 September 2025 and include any bio edits there:\n"
    "https://form.jotform.com/242603789142964\n\n"
    "You can use the bio as is, update it, or replace it with your own version. No need to reply unless you have questions.\n\n"
    "Useful details:\n"
    "• Sessions run between 10:00 and 16:00. Exact time and stage will follow.\n"
    "• Claim your Speaker ticket with code speaker2025 via the conference page:\n"
    "https://mobidictum.com/events/mobidictum-conference-2025/\n\n"
    "• Hotel discounts are listed on that page.\n"
    "• On 20 October, there is an Executive Mixer for Speakers and Executive ticket holders. You are welcome to join.\n\n"
    "If you have already filled the form, you are all set. Thank you.\n\n"
    "Best regards,\n"
    "Serdar\n"
    "Marketing Manager, Mobidictum\n"
)


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


def load_threads_subjects(path: str) -> Dict[str, str]:
    subjects: Dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            email = (row.get("email") or "").strip().lower()
            subj = (row.get("subject") or "").strip()
            if email and subj and email not in subjects:
                subjects[email] = subj
    return subjects


def load_map(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize(s: str) -> str:
    return (s or "").lower()


def has_bio(name: str, bios_text: str) -> bool:
    if not name:
        return False
    return normalize(name) in normalize(bios_text)


def build_body(name: str) -> str:
    first = (name or "").strip().split(" ")[0] or "there"
    proposed = (
        "We don't currently have a bio on file. Please paste a 2–3 sentence bio in the form above, "
        "or reply with your preferred version and we'll update it."
    )
    return TEMPLATE.format(first_name=first, proposed_bio=proposed)


def reply_in_thread(service, to_email: str, thread_id: str, subject: str, body_text: str, rfc_message_id: str | None = None):
    # Ensure subject starts with Re:
    subj = subject or "Mobidictum Conference 2025 Speaker"
    if not subj.lower().startswith("re:"):
        subj = "Re: " + subj

    msg = MIMEMultipart("alternative")
    msg["To"] = to_email
    msg["Subject"] = subj
    # Add RFC threading headers for reliability
    if rfc_message_id:
        msg["In-Reply-To"] = rfc_message_id
        msg["References"] = rfc_message_id
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id}).execute()


def header_lookup(headers: List[Dict[str, str]], name: str) -> str:
    ln = name.lower()
    for h in headers:
        if (h.get("name") or "").lower() == ln:
            return h.get("value") or ""
    return ""


def find_thread_by_email(service, target_email: str, subject_prefix: str) -> Dict[str, str] | None:
    # Search by subject first; then filter by To/Cc containing the email
    query = f'subject:"{subject_prefix}"'
    resp = service.users().messages().list(userId="me", q=query, maxResults=100).execute()
    msgs = resp.get("messages", []) or []
    latest: Dict[str, str] | None = None
    latest_internal = -1
    for m in msgs:
        mg = service.users().messages().get(userId="me", id=m["id"], format="metadata", metadataHeaders=["To","Cc","Subject"]).execute()
        headers = mg.get("payload", {}).get("headers", [])
        to = header_lookup(headers, "To")
        cc = header_lookup(headers, "Cc")
        subj = header_lookup(headers, "Subject")
        # Double-check: subject starts with prefix (ignoring Re:), and target is in To or Cc
        subj_norm = subj
        if subj_norm.lower().startswith("re: "):
            subj_norm = subj_norm[4:]
        if subj_norm.lower().startswith(subject_prefix.lower()) and (target_email.lower() in (to or '').lower() or target_email.lower() in (cc or '').lower()):
            internal = int(mg.get("internalDate", 0))
            if internal > latest_internal:
                latest_internal = internal
                latest = {"threadId": mg["threadId"], "subject": subj, "id": mg["id"]}
    return latest


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
    return latest


def main() -> int:
    p = argparse.ArgumentParser(description="Schedule speaker follow-up replies for missing bios")
    p.add_argument("--map", required=True, help="Mapping CSV: email,name,threadId,lastMessageId")
    p.add_argument("--threads", required=True, help="Threads CSV with 'email' and 'subject'")
    p.add_argument("--bios", required=True, help="RTF file with bios")
    p.add_argument("--credentials", required=True)
    p.add_argument("--token", default=os.path.join("email_outreach","token.json"))
    p.add_argument("--delay-minutes", type=int, default=15)
    p.add_argument("--only-email", default=None, help="Target only this email; find thread by subject prefix")
    args = p.parse_args()

    subjects_by_email = load_threads_subjects(args.threads)
    bios_text = open(args.bios, "r", encoding="utf-8", errors="ignore").read()

    service = ensure_gmail_service(args.credentials, args.token)
    subject_prefix = "Mobidictum Conference 2025 Speaker"

    targets: List[Dict[str, str]] = []

    if args.only_email:
        email = args.only_email.strip().lower()
        # Prefer threadId from mapping if present; otherwise search
        map_rows = [r for r in load_map(args.map) if (r.get("email") or '').lower() == email]
        name = (map_rows[0].get("name") if map_rows else "") or ""
        thread_id = (map_rows[0].get("threadId") if map_rows else "") or ""
        subject = subjects_by_email.get(email, "")
        if not thread_id:
            found = find_thread_by_email(service, email, subject_prefix)
            if not found:
                print(f"No thread found for {email} with subject starting '{subject_prefix}'")
                return 1
            thread_id = found["threadId"]
            subject = found["subject"]
        rfc_mid = get_last_message_rfc_id(service, thread_id)
        targets.append({"email": email, "name": name or "Serdar Akman", "threadId": thread_id, "subject": subject or subject_prefix, "rfc_mid": rfc_mid})
    else:
        mapping = load_map(args.map)
        for row in mapping:
            email = (row.get("email") or "").strip()
            name = (row.get("name") or "").strip()
            if not has_bio(name, bios_text):
                rfc_mid = get_last_message_rfc_id(service, row.get("threadId") or "")
                targets.append({
                    "email": email,
                    "name": name,
                    "threadId": row.get("threadId") or "",
                    "subject": subjects_by_email.get(email.lower(), subject_prefix + " - " + (name or "")),
                    "rfc_mid": rfc_mid,
                })

    print(f"Will send {len(targets)} follow-ups after {args.delay_minutes} minutes.")
    if args.delay_minutes > 0:
        time.sleep(args.delay_minutes * 60)

    sent = 0
    for t in targets:
        body = build_body(t["name"]) 
        reply_in_thread(service, t["email"], t["threadId"], t["subject"], body, t.get("rfc_mid"))
        sent += 1
    print(f"Sent {sent} follow-ups.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


