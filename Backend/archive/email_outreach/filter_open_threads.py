#!/usr/bin/env python3
import argparse
import csv


def main() -> int:
    p = argparse.ArgumentParser(description="Filter speaker_threads.csv for open loops and build a map")
    p.add_argument("--in", dest="inp", required=True, help="Input CSV (speaker_threads.csv)")
    p.add_argument("--open", dest="open_out", required=True, help="Output CSV for open rows")
    p.add_argument("--map", dest="map_out", required=True, help="Output CSV mapping: email,threadId,lastMessageId")
    args = p.parse_args()

    rows = list(csv.DictReader(open(args.inp, newline='', encoding='utf-8')))
    open_rows = [r for r in rows if (r.get('status') or '').lower() == 'open']

    if open_rows:
        # Write open rows with all columns
        with open(args.open_out, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=open_rows[0].keys())
            w.writeheader()
            w.writerows(open_rows)
        # Write map
        with open(args.map_out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['email','threadId','lastMessageId'])
            for r in open_rows:
                w.writerow([r.get('email',''), r.get('threadId',''), r.get('lastMessageId','')])
    else:
        # Create empty files with headers
        with open(args.open_out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['email','threadId','lastMessageId','subject','lastFrom','lastDate','messageCount','status'])
        with open(args.map_out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['email','threadId','lastMessageId'])

    print(f"Open rows: {len(open_rows)} | wrote {args.open_out} and {args.map_out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


