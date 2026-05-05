#!/usr/bin/env python
"""Count Events entries in AK15 phase 1 and phase 2 ROOT outputs."""

from __future__ import print_function

import argparse
import glob
import io
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Count ROOT tree entries over AK15 outputs.")
    parser.add_argument("inputs", nargs="+", help="ROOT files, directories, globs, or text lists.")
    parser.add_argument("--tree", default="Events")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any input file cannot be opened or lacks the tree.",
    )
    return parser.parse_args()


def read_text_list(path):
    entries = []
    with io.open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                entries.append(line)
    return entries


def expand_inputs(items):
    files = []
    for item in items:
        if os.path.isdir(item):
            for root, _, names in os.walk(item):
                for name in sorted(names):
                    if name.endswith(".root"):
                        files.append(os.path.join(root, name))
        elif os.path.isfile(item) and os.path.splitext(item)[1] in (".txt", ".list"):
            files.extend(read_text_list(item))
        elif any(char in item for char in "*?[]"):
            files.extend(sorted(glob.glob(item)))
        else:
            files.append(item)
    return files


def classify(tree):
    branches = set()
    branch_list = tree.GetListOfBranches()
    for index in range(branch_list.GetEntries()):
        branches.add(branch_list.At(index).GetName())
    if "selectedJetIdx" in branches or "sourceLabel" in branches:
        return "phase2_flat"
    if "nSuperFatJetAK15" in branches or "SuperFatJetAK15_pt" in branches:
        return "phase1_nano"
    return "unknown"


def count_file(root_module, filename, tree_name):
    handle = root_module.TFile.Open(filename)
    if not handle or handle.IsZombie():
        return {"file": filename, "ok": False, "error": "could not open", "entries": 0}
    tree = handle.Get(tree_name)
    if not tree:
        handle.Close()
        return {"file": filename, "ok": False, "error": "missing tree {0}".format(tree_name), "entries": 0}
    entries = int(tree.GetEntries())
    phase = classify(tree)
    handle.Close()
    return {"file": filename, "ok": True, "phase": phase, "entries": entries}


def main():
    args = parse_args()
    try:
        import ROOT
    except Exception as err:
        print("ERROR: could not import ROOT. Run after cmsenv or in a ROOT environment.", file=sys.stderr)
        print(str(err), file=sys.stderr)
        return 2

    ROOT.gROOT.SetBatch(True)
    files = expand_inputs(args.inputs)
    if not files:
        print("ERROR: no ROOT files matched the requested inputs", file=sys.stderr)
        return 2

    results = [count_file(ROOT, filename, args.tree) for filename in files]
    total = sum(item["entries"] for item in results if item["ok"])
    failed = [item for item in results if not item["ok"]]
    by_phase = {}
    for item in results:
        if item["ok"]:
            by_phase[item["phase"]] = by_phase.get(item["phase"], 0) + item["entries"]

    summary = {
        "tree": args.tree,
        "files": len(results),
        "ok_files": len(results) - len(failed),
        "failed_files": len(failed),
        "total_entries": total,
        "entries_by_phase": by_phase,
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for item in results:
            if item["ok"]:
                print("{0:12d}  {1:12s}  {2}".format(item["entries"], item["phase"], item["file"]))
            else:
                print("{0:>12s}  {1:12s}  {2}".format("ERROR", item["error"], item["file"]))
        print("-" * 72)
        print("{0:12d}  total entries in {1} ok files".format(total, len(results) - len(failed)))
        for phase, count in sorted(by_phase.items()):
            print("{0:12d}  {1}".format(count, phase))

    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
