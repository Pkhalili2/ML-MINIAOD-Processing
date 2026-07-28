#!/usr/bin/env python3

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare xrootd object sizes with DAS catalog metadata."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--das-json", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--path-prefix", default="")
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args()


def catalog_sizes(path):
    records = json.loads(Path(path).read_text())
    result = {}
    for record in records:
        for entry in record.get("file", []):
            name = entry.get("name") or entry.get("file.name")
            size = entry.get("size") or entry.get("file_size")
            if name and size is not None:
                result[name] = int(size)
    return result


def remote_path(prefix, lfn):
    return f"{prefix.rstrip('/')}/{lfn.lstrip('/')}" if prefix else lfn


def inspect_one(endpoint, prefix, timeout, lfn, expected_size):
    path = remote_path(prefix, lfn)
    command = ["xrdfs", endpoint, "stat", path]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "lfn": lfn,
            "pfn": f"{endpoint.rstrip('/')}/{path.lstrip('/')}",
            "expected_size": expected_size,
            "remote_size": None,
            "status": "timeout",
        }
    output = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"Size:\s*(\d+)", output)
    remote_size = int(match.group(1)) if match else None
    if completed.returncode != 0 or remote_size is None:
        status = "stat_failed"
    elif remote_size != expected_size:
        status = "size_mismatch"
    else:
        status = "ok"
    return {
        "lfn": lfn,
        "pfn": f"{endpoint.rstrip('/')}/{path.lstrip('/')}",
        "expected_size": expected_size,
        "remote_size": remote_size,
        "status": status,
        "returncode": completed.returncode,
    }


def main():
    args = parse_args()
    sizes = catalog_sizes(args.das_json)
    lfns = [
        line.strip()
        for line in Path(args.manifest).read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    missing = [lfn for lfn in lfns if lfn not in sizes]
    if missing:
        raise RuntimeError(f"{len(missing)} manifest files are absent from DAS metadata")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(
                inspect_one,
                args.endpoint,
                args.path_prefix,
                args.timeout,
                lfn,
                sizes[lfn],
            )
            for lfn in lfns
        ]
        records = [future.result() for future in futures]

    valid = [record for record in records if record["status"] == "ok"]
    Path(args.output_manifest).write_text(
        "".join(f"{record['pfn']}\n" for record in valid)
    )
    summary = {
        "endpoint": args.endpoint,
        "path_prefix": args.path_prefix,
        "input_count": len(records),
        "valid_count": len(valid),
        "status_counts": {
            status: sum(record["status"] == status for record in records)
            for status in sorted({record["status"] for record in records})
        },
        "records": records,
    }
    Path(args.output_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in summary.items() if key != "records"}))
    for record in records:
        if record["status"] != "ok":
            print(
                f"{record['status']}: {record['lfn']} "
                f"catalog={record['expected_size']} remote={record['remote_size']}"
            )


if __name__ == "__main__":
    main()
