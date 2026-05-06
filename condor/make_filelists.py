#!/usr/bin/env python3
"""Create non-overlapping Condor chunk lists for AK15 processing."""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build per-job input lists and a Condor queue table."
    )
    parser.add_argument("--tag", required=True, help="Short dataset tag used in file names.")
    parser.add_argument(
        "--input",
        required=True,
        help="Input directory, glob, text file, ROOT file, DAS dataset, or xrootd URL.",
    )
    parser.add_argument("--mode", choices=("phase1", "phase2", "both"), default="both")
    parser.add_argument("--is-signal", choices=("0", "1"), default="1")
    parser.add_argument("--files-per-job", type=int, default=20)
    parser.add_argument("--limit-files", type=int, default=0)
    parser.add_argument("--limit-jobs", type=int, default=0)
    parser.add_argument("--max-events", default="-1")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--return-dir",
        default="",
        help="Submit-side directory where Condor should transfer the ROOT output tarball.",
    )
    parser.add_argument("--save-nano", choices=("0", "1"), default="1")
    parser.add_argument("--use-x509", action="store_true")
    parser.add_argument(
        "--require-hdfs",
        choices=("auto", "0", "1"),
        default="auto",
        help="Require TARGET.HAS_CMS_HDFS. Auto enables it for /hdfs inputs or outputs.",
    )
    parser.add_argument("--cmssw-version", default="CMSSW_10_6_17")
    parser.add_argument("--scram-arch", default="slc7_amd64_gcc700")
    parser.add_argument(
        "--xrootd-prefix",
        default="root://cms-xrd-global.cern.ch//",
        help="Prefix used for DAS /store logical file names.",
    )
    parser.add_argument(
        "--hdfs-xrootd-prefix",
        default="root://cmsxrootd.hep.wisc.edu//",
        help="Prefix used by --input-prefix xrootd-wisc for /hdfs/store paths.",
    )
    parser.add_argument(
        "--input-prefix",
        choices=("auto", "file", "none", "xrootd-wisc"),
        default="auto",
        help="How to normalize local absolute paths before writing chunk lists.",
    )
    parser.add_argument(
        "--generated-dir",
        default="condor/.generated",
        help="Directory for generated chunk lists and job table.",
    )
    parser.add_argument("--clear", action="store_true", help="Replace generated files for this tag.")
    return parser.parse_args()


def repo_root():
    return Path(__file__).resolve().parents[1]


def is_url(value):
    return value.startswith(("root://", "davs://", "gsiftp://", "https://"))


def has_glob(value):
    return any(char in value for char in "*?[]")


def read_text_list(path):
    entries = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                entries.append(line)
    return entries


def run_dasgoclient(dataset):
    if shutil.which("dasgoclient") is None:
        raise RuntimeError("dasgoclient is not available; run inside a CMS environment.")
    query = f"file dataset={dataset}"
    completed = subprocess.run(
        ["dasgoclient", "--query", query],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def discover_inputs(spec):
    if is_url(spec):
        return [spec]

    path = Path(spec)
    if path.exists():
        if path.is_dir():
            return sorted(str(item) for item in path.rglob("*.root") if item.is_file())
        if path.suffix in (".txt", ".list"):
            return read_text_list(path)
        return [str(path)]

    if has_glob(spec):
        return sorted(item for item in glob.glob(spec, recursive=True) if Path(item).is_file())

    if spec.startswith("/") and spec.count("/") >= 3:
        return run_dasgoclient(spec)

    raise RuntimeError(f"Could not resolve input: {spec}")


def join_xrootd(prefix, logical_path):
    if prefix.endswith("/"):
        return prefix + logical_path.lstrip("/")
    return prefix + "/" + logical_path.lstrip("/")


def normalize_entry(entry, input_prefix, xrootd_prefix, hdfs_xrootd_prefix):
    if entry.startswith("file:") or is_url(entry):
        return entry
    if entry.startswith("/hdfs/store/") and input_prefix == "xrootd-wisc":
        return join_xrootd(hdfs_xrootd_prefix, entry[len("/hdfs") :])
    if entry.startswith("/store/"):
        return join_xrootd(xrootd_prefix, entry)
    if entry.startswith("/"):
        if input_prefix == "none":
            return entry
        return "file:" + entry
    return entry


def requires_hdfs(entries, output_dir, setting):
    if setting != "auto":
        return setting
    if output_dir.startswith("/hdfs"):
        return "1"
    for entry in entries:
        if entry.startswith("/hdfs") or entry.startswith("file:/hdfs"):
            return "1"
    return "0"


def default_return_dir(output_dir, root, tag):
    if output_dir.startswith("/"):
        return output_dir
    return str(root / "condor" / ".returned" / tag)


def chunk_entries(entries, size):
    for start in range(0, len(entries), size):
        yield entries[start : start + size]


def main():
    args = parse_args()
    if args.files_per_job < 1:
        raise SystemExit("--files-per-job must be >= 1")

    root = repo_root()
    generated = root / args.generated_dir / args.tag
    chunks_dir = generated / "chunks"
    if args.clear and generated.exists():
        shutil.rmtree(generated)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    raw_entries = discover_inputs(args.input)
    if not raw_entries:
        raise SystemExit(f"No input ROOT files found for {args.input}")

    entries = [
        normalize_entry(item, args.input_prefix, args.xrootd_prefix, args.hdfs_xrootd_prefix)
        for item in raw_entries
    ]

    if args.limit_files > 0:
        entries = entries[: args.limit_files]
    if args.limit_jobs > 0:
        entries = entries[: args.limit_jobs * args.files_per_job]

    chunks = list(chunk_entries(entries, args.files_per_job))
    if args.limit_jobs > 0:
        chunks = chunks[: args.limit_jobs]

    hdfs_flag = requires_hdfs(entries, args.output_dir, args.require_hdfs)
    return_dir = args.return_dir or default_return_dir(args.output_dir, root, args.tag)
    job_table = generated / "job_table.txt"
    manifest = {
        "created_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tag": args.tag,
        "input": args.input,
        "mode": args.mode,
        "is_signal": args.is_signal,
        "files_per_job": args.files_per_job,
        "jobs": [],
        "output_dir": args.output_dir,
        "return_dir": return_dir,
        "save_nano": args.save_nano,
        "use_x509": args.use_x509,
        "require_hdfs": hdfs_flag,
        "cmssw_version": args.cmssw_version,
        "scram_arch": args.scram_arch,
    }

    with open(job_table, "w", encoding="utf-8") as table:
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{idx:04d}"
            chunk_path = chunks_dir / f"{args.tag}_{chunk_id}.txt"
            with open(chunk_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(chunk))
                handle.write("\n")
            rel_chunk = os.path.relpath(chunk_path, root)
            row = [
                args.tag,
                chunk_id,
                rel_chunk,
                args.mode,
                args.is_signal,
                args.max_events,
                args.output_dir,
                args.save_nano,
                "True" if args.use_x509 else "False",
                hdfs_flag,
                args.cmssw_version,
                args.scram_arch,
                return_dir,
            ]
            table.write(" ".join(row) + "\n")
            manifest["jobs"].append(
                {"chunk_id": chunk_id, "input_list": rel_chunk, "n_files": len(chunk)}
            )

    with open(generated / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"Wrote {len(chunks)} jobs covering {sum(len(c) for c in chunks)} files.")
    print(f"Job table: {os.path.relpath(job_table, root)}")
    print(f"Manifest: {os.path.relpath(generated / 'manifest.json', root)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(1)
