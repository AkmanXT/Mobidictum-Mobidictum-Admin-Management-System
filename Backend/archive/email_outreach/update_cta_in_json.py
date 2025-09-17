#!/usr/bin/env python3
import json
import os

SRC = os.path.join("email_outreach", "followups_to_send.json")

NEW_CTA = (
    "Please submit the form by 15 September so we can plan ahead in our marketing plan and make sure every session gets the attention it needs."
)


def replace_cta(text: str) -> str:
    lines = text.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("please complete the speaker form by"):
            lines[i] = NEW_CTA
            replaced = True
            break
    return "\n".join(lines), replaced


def main() -> int:
    data = json.load(open(SRC, "r", encoding="utf-8"))
    count = 0
    for msg in data:
        body = msg.get("text") or ""
        new_body, replaced = replace_cta(body)
        if replaced:
            msg["text"] = new_body
            count += 1

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated CTA in {count} messages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


