#!/usr/bin/env python
from __future__ import print_function

import argparse
import csv
import glob
import os
import sys


def load_root():
    import ROOT

    ROOT.gROOT.SetBatch(True)
    return ROOT


def read_list(path):
    out = []
    with open(path) as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def expand_inputs(items):
    files = []
    for item in items:
        if item.startswith("@"):
            files.extend(read_list(item[1:]))
        elif os.path.isdir(item):
            files.extend(sorted(glob.glob(os.path.join(item, "*.root"))))
        elif os.path.isfile(item) and item.endswith((".txt", ".list")):
            files.extend(read_list(item))
        else:
            matches = sorted(glob.glob(item))
            files.extend(matches if matches else [item])
    return files


def leaf_value(tree, name):
    leaf = tree.GetLeaf(name)
    if not leaf:
        return None
    return leaf.GetValue()


def sum_runs_tree(root_file):
    runs = root_file.Get("Runs")
    if not runs:
        return None, 0.0
    if not runs.GetBranch("genEventSumw"):
        return None, 0.0

    total_sumw = 0.0
    total_count = 0.0
    for index in range(runs.GetEntries()):
        runs.GetEntry(index)
        total_sumw += float(leaf_value(runs, "genEventSumw") or 0.0)
        if runs.GetBranch("genEventCount"):
            total_count += float(leaf_value(runs, "genEventCount") or 0.0)
    return total_sumw, total_count


def sum_events_tree(root_file):
    events = root_file.Get("Events")
    if not events:
        return None, 0
    if not events.GetBranch("genWeight"):
        return None, events.GetEntries()

    total = 0.0
    for event in events:
        total += float(getattr(event, "genWeight"))
    return total, events.GetEntries()


def main():
    parser = argparse.ArgumentParser(
        description="Compute NanoAOD sum_genweights for MC normalization."
    )
    parser.add_argument("inputs", nargs="+", help="ROOT files, directories, globs, or text lists")
    parser.add_argument("--output", help="Optional CSV output path")
    args = parser.parse_args()

    ROOT = load_root()
    files = expand_inputs(args.inputs)
    if not files:
        raise SystemExit("No input files found")

    total_sumw = 0.0
    total_events = 0
    total_runs_events = 0.0
    methods = {}
    bad_files = []

    for path in files:
        root_file = ROOT.TFile.Open(path)
        if not root_file or root_file.IsZombie():
            bad_files.append(path)
            continue

        events = root_file.Get("Events")
        entries = int(events.GetEntries()) if events else 0
        total_events += entries

        run_sumw, run_count = sum_runs_tree(root_file)
        if run_sumw is not None:
            total_sumw += run_sumw
            total_runs_events += run_count
            methods["Runs.genEventSumw"] = methods.get("Runs.genEventSumw", 0) + 1
        else:
            event_sumw, _ = sum_events_tree(root_file)
            if event_sumw is not None:
                total_sumw += event_sumw
                methods["Events.genWeight"] = methods.get("Events.genWeight", 0) + 1
            else:
                methods["missing"] = methods.get("missing", 0) + 1
        root_file.Close()

    method_text = ";".join("%s:%s" % (key, methods[key]) for key in sorted(methods))
    print("files,%d" % len(files))
    print("bad_files,%d" % len(bad_files))
    print("events_tree_entries,%d" % total_events)
    print("runs_gen_event_count,%.17g" % total_runs_events)
    print("sum_genweights,%.17g" % total_sumw)
    print("methods,%s" % method_text)

    if bad_files:
        print("Bad files:", file=sys.stderr)
        for path in bad_files:
            print("  " + path, file=sys.stderr)

    if args.output:
        with open(args.output, "w") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "files",
                    "bad_files",
                    "events_tree_entries",
                    "runs_gen_event_count",
                    "sum_genweights",
                    "methods",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "files": len(files),
                    "bad_files": len(bad_files),
                    "events_tree_entries": total_events,
                    "runs_gen_event_count": "%.17g" % total_runs_events,
                    "sum_genweights": "%.17g" % total_sumw,
                    "methods": method_text,
                }
            )

    if bad_files:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
