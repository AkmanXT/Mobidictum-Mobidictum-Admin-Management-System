#!/usr/bin/env python3
import json
import os
import re

SRC = os.path.join("email_outreach", "followups_to_send.json")

NEW_INTRO = (
    "We recently implemented a feature to aid with the conference production: a short bio generated from public sources with an AI tool. "
    "It is a starting point, not a final source of truth—we do not assume it is all around accurate. Creative technology comes with it's caviats.\n\n"
    "Which is why we’d love your feedback on whether this helps the process.\n\n"
)


def update_body(text: str) -> str:
    # Replace the original intro block from "Quick follow-up ..." up to "Proposed short bio:" with NEW_INTRO
    text = re.sub(
        r"Quick follow-up[\s\S]*?\n\nProposed short bio:\s*\n",
        NEW_INTRO + "Proposed short bio:\n",
        text,
        count=1,
    )

    # Remove Optional feedback section block
    text = re.sub(
        r"\n\nOptional feedback:[\s\S]*?(?=\n\nUseful details:)",
        "\n\n",
        text,
        count=1,
    )

    return text


def main() -> int:
    data = json.load(open(SRC, "r", encoding="utf-8"))
    for msg in data:
        body = msg.get("text") or ""
        msg["text"] = update_body(body)

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Updated template across all messages in followups_to_send.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


