#!/usr/bin/env python3
"""Select a deterministic whole-file tranche from a DAS dataset."""

import argparse
import csv
import json
import subprocess
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fraction", type=float, default=0.1)
    parser.add_argument("--max-selected-events", type=int, default=2_000_000)
    parser.add_argument("--audit-csv")
    return parser.parse_args()


def das_json(query):
    completed = subprocess.run(
        ["dasgoclient", "--query", query, "-json"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return json.loads(completed.stdout)


def dataset_files(dataset):
    records = das_json("file dataset=%s" % dataset)
    files = []
    for record in records:
        for item in record.get("file", []):
            if item.get("is_file_valid", 1) != 1:
                continue
            files.append(
                {
                    "name": item["name"],
                    "events": int(item.get("nevents", 0)),
                    "size": int(item.get("size", 0)),
                }
            )
    return sorted(files, key=lambda item: item["name"])


def main():
    args = parse_args()
    if not 0.0 < args.fraction <= 1.0:
        raise SystemExit("--fraction must be in (0, 1]")
    if args.max_selected_events < 1:
        raise SystemExit("--max-selected-events must be positive")

    files = dataset_files(args.dataset)
    if not files:
        raise SystemExit("DAS returned no valid files for %s" % args.dataset)
    total_events = sum(item["events"] for item in files)
    target_events = min(int(round(total_events * args.fraction)), args.max_selected_events)

    selected = []
    selected_events = 0
    for item in files:
        selected.append(item)
        selected_events += item["events"]
        if selected_events >= target_events:
            break

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(item["name"] + "\n" for item in selected), encoding="utf-8")

    audit_path = Path(args.audit_csv) if args.audit_csv else output.with_suffix(".csv")
    with audit_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("dataset", "selected", "name", "events", "size"))
        writer.writeheader()
        selected_names = {item["name"] for item in selected}
        for item in files:
            writer.writerow(
                {
                    "dataset": args.dataset,
                    "selected": int(item["name"] in selected_names),
                    "name": item["name"],
                    "events": item["events"],
                    "size": item["size"],
                }
            )

    print("dataset=%s" % args.dataset)
    print("total_files=%d" % len(files))
    print("total_events=%d" % total_events)
    print("target_events=%d" % target_events)
    print("selected_files=%d" % len(selected))
    print("selected_events=%d" % selected_events)
    print("selected_fraction=%.8f" % (float(selected_events) / total_events))
    print("output=%s" % output)
    print("audit_csv=%s" % audit_path)


if __name__ == "__main__":
    main()
