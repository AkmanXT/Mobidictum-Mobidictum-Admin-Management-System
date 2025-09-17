#!/usr/bin/env python3
import json
import os

SRC = os.path.join("email_outreach", "followups_to_send.json")

def main() -> int:
    data = json.load(open(SRC, "r", encoding="utf-8"))
    for m in data:
        m["cc"] = ["serdar@mobidictum.com"]
    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Updated CC to only serdar@mobidictum.com across all messages")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())


