#!/usr/bin/env python3
import argparse
import csv
import os
import unicodedata
from typing import Dict


def normalize_key(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def load_bios(bios_csv: str) -> Dict[str, str]:
    bios: Dict[str, str] = {}
    with open(bios_csv, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        # Detect header
        first = next(reader, None)
        if first is None:
            return bios
        # If header contains 'bio', switch to DictReader for clarity
        if any(h.lower() == "bio" for h in first if isinstance(h, str)):
            f.seek(0)
            dreader = csv.DictReader(f)
            for row in dreader:
                name = (row.get("name") or row.get("Name") or "").strip()
                bio = (row.get("bio") or row.get("Bio") or "").strip()
                if name and bio:
                    bios[normalize_key(name)] = bio
            return bios
        else:
            # Assume columns: name,title,bio or name,email,title,bio,status; take third (index 2) as bio
            # Re-include the first row as data
            rows = [first] + list(reader)
            for r in rows:
                if not r:
                    continue
                name = (r[0] if len(r) > 0 else "").strip()
                bio = (r[2] if len(r) > 2 else "").strip()
                if name and bio:
                    bios[normalize_key(name)] = bio
            return bios


def main() -> int:
    ap = argparse.ArgumentParser(description="Join bios into speaker_threads_map.csv by name")
    ap.add_argument("--map", default=os.path.join("email_outreach","speaker_threads_map.csv"))
    ap.add_argument("--bios", default=os.path.join("email_outreach","speaker_bios_clean.csv"))
    ap.add_argument("--out", default=os.path.join("email_outreach","speaker_threads_map.csv"))
    args = ap.parse_args()

    bios_by_name = load_bios(args.bios)

    # Read map
    with open(args.map, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Add/overwrite bio column
    for r in rows:
        name = (r.get("name") or "").strip()
        r["bio"] = bios_by_name.get(normalize_key(name), r.get("bio", ""))

    # Write out (preserving column order + bio at the end)
    fieldnames = list(rows[0].keys()) if rows else ["email","name","threadId","lastMessageId","bio"]
    if "bio" not in fieldnames:
        fieldnames.append("bio")

    tmp_out = args.out + ".tmp"
    with open(tmp_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # Backup original then replace
    backup = args.out + ".backup"
    if os.path.abspath(args.out) == os.path.abspath(args.map):
        try:
            if os.path.exists(args.out):
                os.replace(args.out, backup)
        except Exception:
            pass
    os.replace(tmp_out, args.out)
    print(f"Updated {args.out} with bio column. Backup: {backup if os.path.exists(backup) else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


