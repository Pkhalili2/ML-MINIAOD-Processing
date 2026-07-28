#!/usr/bin/env python3
"""Select a reproducible fraction of complete files from a DAS dataset."""

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Select complete DAS files until an event-fraction target is reached."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--fraction", type=float, required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument(
        "--allowed-files",
        type=Path,
        help="Optional newline-delimited LFN allowlist, such as files at a chosen disk RSE.",
    )
    parser.add_argument("--seed", default="ak15")
    return parser.parse_args()


def query_files(dataset):
    if shutil.which("dasgoclient") is None:
        raise RuntimeError("dasgoclient is not available")
    result = subprocess.run(
        ["dasgoclient", "--query", f"file dataset={dataset}", "--json"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return json.loads(result.stdout)


def read_records(payload):
    records = []
    for item in payload:
        for source in item.get("file", []):
            name = source.get("name")
            events = source.get("nevents")
            size = source.get("size")
            valid = source.get("is_file_valid", 1)
            if name and events is not None and size is not None and valid:
                records.append(
                    {
                        "name": str(name),
                        "events": int(events),
                        "size": int(size),
                    }
                )
    if not records:
        raise RuntimeError("DAS returned no valid file records")
    if len({record["name"] for record in records}) != len(records):
        raise RuntimeError("DAS returned duplicate file names")
    return records


def selection_key(seed, name):
    return hashlib.sha256(f"{seed}\0{name}".encode("utf-8")).hexdigest()


def main():
    args = parse_args()
    if not 0 < args.fraction <= 1:
        raise RuntimeError("--fraction must be greater than zero and at most one")

    if args.cache and args.cache.exists():
        with args.cache.open(encoding="utf-8") as source:
            payload = json.load(source)
    else:
        payload = query_files(args.dataset)
        if args.cache:
            args.cache.parent.mkdir(parents=True, exist_ok=True)
            with args.cache.open("x", encoding="utf-8") as target:
                json.dump(payload, target)
                target.write("\n")

    all_records = read_records(payload)
    total_events = sum(record["events"] for record in all_records)
    target_events = math.ceil(total_events * args.fraction)

    records = all_records
    if args.allowed_files:
        with args.allowed_files.open(encoding="utf-8") as source:
            allowed = {line.strip() for line in source if line.strip()}
        records = [record for record in all_records if record["name"] in allowed]
        if not records:
            raise RuntimeError("--allowed-files did not match any DAS records")
        if sum(record["events"] for record in records) < target_events:
            raise RuntimeError(
                "allowed files do not contain enough events to reach the dataset fraction"
            )

    ordered = sorted(records, key=lambda record: selection_key(args.seed, record["name"]))

    selected = []
    selected_events = 0
    for record in ordered:
        selected.append(record)
        selected_events += record["events"]
        if selected_events >= target_events:
            break

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as target:
        for record in selected:
            target.write(record["name"] + "\n")

    metadata = {
        "dataset": args.dataset,
        "fraction": args.fraction,
        "seed": args.seed,
        "total_files": len(all_records),
        "total_events": total_events,
        "total_bytes": sum(record["size"] for record in all_records),
        "candidate_files": len(records),
        "candidate_events": sum(record["events"] for record in records),
        "allowed_files": str(args.allowed_files) if args.allowed_files else "",
        "target_events": target_events,
        "selected_files": len(selected),
        "selected_events": selected_events,
        "selected_bytes": sum(record["size"] for record in selected),
        "manifest": str(args.output),
        "selection": selected,
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    with args.metadata.open("x", encoding="utf-8") as target:
        json.dump(metadata, target, indent=2, sort_keys=True)
        target.write("\n")

    print(
        f"Selected {len(selected)} of {len(records)} files: "
        f"{selected_events} of {total_events} events "
        f"({selected_events / total_events:.4%})."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
