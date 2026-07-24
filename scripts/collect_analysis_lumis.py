#!/usr/bin/env python
from __future__ import print_function

import argparse
import glob
import json
import os
import sys


def is_remote(path):
    return path.startswith(("root://", "davs://", "https://"))


def read_manifest(path):
    entries = []
    with open(path) as handle:
        for raw in handle:
            entry = raw.strip()
            if entry and not entry.startswith("#"):
                entries.append(entry)
    return entries


def expand_inputs(items):
    files = []
    for item in items:
        if is_remote(item):
            matches = [item]
        elif os.path.isfile(item) and item.endswith((".txt", ".list")):
            matches = read_manifest(item)
        elif os.path.isdir(item):
            matches = glob.glob(os.path.join(item, "*.root"))
        else:
            matches = glob.glob(item)
        files.extend(
            path
            for path in matches
            if is_remote(path) or (os.path.isfile(path) and os.path.getsize(path) > 0)
        )
    return sorted(set(files))


def compact_ranges(lumis):
    values = sorted(set(int(value) for value in lumis))
    if not values:
        return []
    ranges = []
    first = values[0]
    last = values[0]
    for value in values[1:]:
        if value == last + 1:
            last = value
            continue
        ranges.append([first, last])
        first = value
        last = value
    ranges.append([first, last])
    return ranges


def main():
    parser = argparse.ArgumentParser(description="Collect unique certified run/lumisection pairs from analysis outputs.")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    import ROOT

    ROOT.gROOT.SetBatch(True)
    files = expand_inputs(args.inputs)
    if not files:
        raise SystemExit("No nonempty ROOT files found")

    by_run = {}
    bad = []
    tree_files = 0
    for path in files:
        root_file = ROOT.TFile.Open(path)
        if not root_file or root_file.IsZombie():
            bad.append(path)
            continue
        tree = root_file.Get("LuminosityBlocks")
        if tree:
            tree_files += 1
            for entry in tree:
                by_run.setdefault(int(entry.run), set()).add(int(entry.luminosityBlock))
        root_file.Close()

    if bad:
        raise SystemExit("Unreadable files: " + ", ".join(bad[:5]))
    if tree_files != len(files):
        raise SystemExit("Only %d/%d files contain LuminosityBlocks" % (tree_files, len(files)))

    payload = dict((str(run), compact_ranges(lumis)) for run, lumis in sorted(by_run.items()))
    with open(args.output, "w") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")

    print("files,%d" % len(files))
    print("runs,%d" % len(payload))
    print("lumisections,%d" % sum(len(values) for values in by_run.values()))
    print("output,%s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
