#!/usr/bin/env python
from __future__ import print_function

import argparse
import csv
import glob
import math
import os
import sys


REQUIRED_OBJECTS = ["Events", "cutflow", "cutflow_weighted", "normalization"]
REQUIRED_DIAGNOSTIC_OBJECTS = [
    "ak4_jet_eta_preselection",
    "ak4_jet_eta_preselection_raw",
]
REQUIRED_DIAGNOSTIC_BRANCHES = {
    "eventHT",
    "eventHT4",
    "eventHT15",
    "eventHT15IsComplete",
    "met_pt",
    "met_phi",
    "muonMetDeltaPhi",
    "metJetDeltaPhi",
    "muonMetTransverseMass",
}
REQUIRED_ABCD_OBJECTS = [
    "ABCDEvents",
    "abcd_yields",
    "abcd_yields_weighted",
    "AnalysisMetadata",
]


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
            if not matches and os.path.isfile(item):
                matches = [item]
        files.extend(
            path
            for path in matches
            if is_remote(path) or (os.path.isfile(path) and os.path.getsize(path) > 0)
        )
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
    parser.add_argument("--require-diagnostics", action="store_true")
    parser.add_argument("--require-abcd", action="store_true")
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
        abcd_counts = [-1, -1, -1, -1]
        abcd_candidates = -1
        abcd_boundaries_valid = False
        if not root_file or root_file.IsZombie():
            problems.append("unreadable")
        else:
            missing = [name for name in REQUIRED_OBJECTS if not root_file.Get(name)]
            if args.require_lumis and not root_file.Get("LuminosityBlocks"):
                missing.append("LuminosityBlocks")
            if args.require_diagnostics:
                missing.extend(
                    name
                    for name in REQUIRED_DIAGNOSTIC_OBJECTS
                    if not root_file.Get(name)
                )
            if args.require_abcd:
                missing.extend(
                    name for name in REQUIRED_ABCD_OBJECTS if not root_file.Get(name)
                )
            if missing:
                problems.append("missing:" + ";".join(missing))
            events = root_file.Get("Events")
            cutflow = root_file.Get("cutflow")
            weighted = root_file.Get("cutflow_weighted")
            if events:
                entries = int(events.GetEntries())
                if args.require_diagnostics:
                    branches = {
                        branch.GetName()
                        for branch in events.GetListOfBranches()
                    }
                    missing_branches = sorted(
                        REQUIRED_DIAGNOSTIC_BRANCHES - branches
                    )
                    if missing_branches:
                        problems.append(
                            "missing_branches:" + ";".join(missing_branches)
                        )
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
            if args.require_abcd and not any(
                not root_file.Get(name) for name in REQUIRED_ABCD_OBJECTS
            ):
                candidates = root_file.Get("ABCDEvents")
                yields = root_file.Get("abcd_yields")
                metadata = root_file.Get("AnalysisMetadata")
                observed = [0, 0, 0, 0]
                boundary_problem = False
                for candidate in candidates:
                    region = int(candidate.abcdRegion)
                    isolation = float(candidate.selectedMuonIso)
                    transverse_mass = float(candidate.muonMetTransverseMass)
                    if region < 1 or region > 4 or not all(
                        math.isfinite(value) for value in (isolation, transverse_mass)
                    ):
                        boundary_problem = True
                        continue
                    valid_region = (
                        (region == 1 and isolation < 0.15 and transverse_mass > 50.0)
                        or (region == 2 and isolation < 0.15 and transverse_mass <= 50.0)
                        or (
                            region == 3
                            and 0.15 <= isolation < 0.5
                            and transverse_mass > 50.0
                        )
                        or (
                            region == 4
                            and 0.15 <= isolation < 0.5
                            and transverse_mass <= 50.0
                        )
                    )
                    if not valid_region:
                        boundary_problem = True
                    observed[region - 1] += 1
                abcd_candidates = int(candidates.GetEntries())
                abcd_counts = observed
                histogram_counts = [int(round(value)) for value in values(yields)]
                if observed != histogram_counts:
                    problems.append("abcd_histogram_mismatch")
                if sum(observed) != abcd_candidates:
                    problems.append("abcd_candidate_count_mismatch")
                if entries >= 0 and observed[0] != entries:
                    problems.append("abcd_region_a_entries_mismatch")
                if boundary_problem:
                    problems.append("abcd_boundary_violation")
                abcd_boundaries_valid = not boundary_problem
                if metadata.GetEntries() != 1:
                    problems.append("abcd_metadata_entries")
                else:
                    metadata.GetEntry(0)
                    if int(metadata.abcdMode) != 1:
                        problems.append("abcd_mode_disabled")
                    if str(metadata.requiredHlt) != "HLT_Mu50":
                        problems.append("required_hlt_mismatch")
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
                "abcd_candidates": abcd_candidates,
                "abcd_a": abcd_counts[0],
                "abcd_b": abcd_counts[1],
                "abcd_c": abcd_counts[2],
                "abcd_d": abcd_counts[3],
                "abcd_boundaries_valid": int(abcd_boundaries_valid),
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
                "abcd_candidates",
                "abcd_a",
                "abcd_b",
                "abcd_c",
                "abcd_d",
                "abcd_boundaries_valid",
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
