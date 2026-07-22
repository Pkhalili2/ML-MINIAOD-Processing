#!/usr/bin/env python
from __future__ import print_function

import argparse
import csv
import glob
import os
import sys


REQUIRED_OBJECTS = ["Events", "cutflow", "cutflow_weighted", "normalization"]


def expand_inputs(items):
    files = []
    for item in items:
        if os.path.isdir(item):
            matches = glob.glob(os.path.join(item, "*.root"))
        else:
            matches = glob.glob(item)
            if not matches and os.path.isfile(item):
                matches = [item]
        files.extend(path for path in matches if os.path.isfile(path) and os.path.getsize(path) > 0)
    return sorted(set(files))


def values(hist):
    return [float(hist.GetBinContent(index)) for index in range(1, hist.GetNbinsX() + 1)]


def is_nonincreasing(items):
    return all(right <= left + max(1.0e-6, abs(left) * 1.0e-9) for left, right in zip(items, items[1:]))


def main():
    parser = argparse.ArgumentParser(description="Audit compact AK15 analysis ROOT outputs.")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--expected-files", type=int)
    parser.add_argument("--require-lumis", action="store_true")
    parser.add_argument("--output-csv")
    args = parser.parse_args()

    import ROOT

    ROOT.gROOT.SetBatch(True)
    files = expand_inputs(args.inputs)
    if not files:
        raise SystemExit("No nonempty ROOT files found")
    if args.expected_files is not None and len(files) != args.expected_files:
        raise SystemExit("Expected %d files, found %d" % (args.expected_files, len(files)))

    rows = []
    failures = []
    for path in files:
        root_file = ROOT.TFile.Open(path)
        problems = []
        entries = -1
        selected = -1.0
        raw_monotonic = False
        weighted_monotonic = False
        if not root_file or root_file.IsZombie():
            problems.append("unreadable")
        else:
            missing = [name for name in REQUIRED_OBJECTS if not root_file.Get(name)]
            if args.require_lumis and not root_file.Get("LuminosityBlocks"):
                missing.append("LuminosityBlocks")
            if missing:
                problems.append("missing:" + ";".join(missing))
            events = root_file.Get("Events")
            cutflow = root_file.Get("cutflow")
            weighted = root_file.Get("cutflow_weighted")
            if events:
                entries = int(events.GetEntries())
            if cutflow:
                raw_values = values(cutflow)
                selected = raw_values[-1] if raw_values else -1.0
                raw_monotonic = is_nonincreasing(raw_values)
                if not raw_monotonic:
                    problems.append("raw_cutflow_not_cumulative")
                if entries >= 0 and abs(selected - entries) > 0.5:
                    problems.append("selected_entries_mismatch")
            if weighted:
                weighted_monotonic = is_nonincreasing(values(weighted))
            root_file.Close()

        status = "ok" if not problems else "error"
        rows.append(
            {
                "path": path,
                "status": status,
                "events_entries": entries,
                "selected_cutflow": "%.17g" % selected,
                "raw_cutflow_monotonic": int(raw_monotonic),
                "weighted_cutflow_monotonic": int(weighted_monotonic),
                "problems": ";".join(problems),
            }
        )
        if problems:
            failures.append((path, problems))

    if args.output_csv:
        with open(args.output_csv, "w") as handle:
            fieldnames = [
                "path",
                "status",
                "events_entries",
                "selected_cutflow",
                "raw_cutflow_monotonic",
                "weighted_cutflow_monotonic",
                "problems",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print("files,%d" % len(files))
    print("valid,%d" % (len(files) - len(failures)))
    print("invalid,%d" % len(failures))
    print("weighted_monotonic,%d" % sum(row["weighted_cutflow_monotonic"] for row in rows))
    if failures:
        for path, problems in failures[:10]:
            print("invalid_file,%s,%s" % (path, ";".join(problems)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
