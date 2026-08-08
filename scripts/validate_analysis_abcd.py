#!/usr/bin/env python
from __future__ import print_function

import argparse
import math

import ROOT


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def histogram_values(histogram):
    return [histogram.GetBinContent(index) for index in range(1, histogram.GetNbinsX() + 1)]


def main():
    parser = argparse.ArgumentParser(description="Validate a trigger and ABCD compact analysis ROOT file.")
    parser.add_argument("input")
    parser.add_argument("--is-data", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()

    ROOT.gROOT.SetBatch(True)
    source = ROOT.TFile.Open(args.input)
    require(source and not source.IsZombie(), "Could not open %s" % args.input)

    required = [
        "Events",
        "ABCDEvents",
        "cutflow",
        "cutflow_weighted",
        "abcd_yields",
        "abcd_yields_weighted",
        "normalization",
        "AnalysisMetadata",
    ]
    if args.is_data:
        required.append("LuminosityBlocks")
    for name in required:
        require(source.Get(name), "Missing required object: %s" % name)

    events = source.Get("Events")
    candidates = source.Get("ABCDEvents")
    cutflow = source.Get("cutflow")
    yields = source.Get("abcd_yields")
    normalization = source.Get("normalization")
    metadata = source.Get("AnalysisMetadata")

    raw_cutflow = histogram_values(cutflow)
    require(
        all(raw_cutflow[index] <= raw_cutflow[index - 1] for index in range(1, len(raw_cutflow))),
        "Raw cutflow is not cumulative",
    )
    require(int(round(raw_cutflow[-1])) == events.GetEntries(), "Selected cutflow does not match Events")
    require(
        int(round(normalization.GetBinContent(4))) == events.GetEntries(),
        "normalization selected_events does not match Events",
    )

    region_counts = [0, 0, 0, 0]
    for entry in candidates:
        region = int(entry.abcdRegion)
        require(1 <= region <= 4, "Invalid ABCD region %d" % region)
        isolation = float(entry.selectedMuonIso)
        transverse_mass = float(entry.muonMetTransverseMass)
        finite = not any(math.isnan(value) or math.isinf(value) for value in (isolation, transverse_mass))
        require(finite, "Non-finite ABCD coordinate")
        if region == 1:
            require(isolation < 0.15 and transverse_mass > 50.0, "Region A boundary violation")
        elif region == 2:
            require(isolation < 0.15 and transverse_mass <= 50.0, "Region B boundary violation")
        elif region == 3:
            require(0.15 <= isolation < 0.5 and transverse_mass > 50.0, "Region C boundary violation")
        else:
            require(0.15 <= isolation < 0.5 and transverse_mass <= 50.0, "Region D boundary violation")
        region_counts[region - 1] += 1

    histogram_counts = [int(round(value)) for value in histogram_values(yields)]
    require(region_counts == histogram_counts, "ABCDEvents counts do not match abcd_yields")
    require(region_counts[0] == events.GetEntries(), "Region A count does not match Events")

    metadata.GetEntry(0)
    require(int(metadata.abcdMode) == 1, "AnalysisMetadata abcdMode is not enabled")
    require(str(metadata.requiredHlt) == "HLT_Mu50", "AnalysisMetadata requiredHlt is not HLT_Mu50")

    print("ABCD validation passed:", args.input)
    print("  selected A events:", events.GetEntries())
    print("  candidate events A/B/C/D:", region_counts)
    print("  cumulative cutflow:", raw_cutflow)
    source.Close()


if __name__ == "__main__":
    main()
