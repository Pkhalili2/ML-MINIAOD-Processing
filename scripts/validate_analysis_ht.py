#!/usr/bin/env python
from __future__ import print_function

import argparse
import math

import ROOT


def key_names(root_file):
    return set(key.GetName() for key in root_file.GetListOfKeys())


def cutflow_values(hist):
    return [float(hist.GetBinContent(index)) for index in range(1, hist.GetNbinsX() + 1)]


def main():
    parser = argparse.ArgumentParser(description="Validate compact analysis HT against one source Nano file.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--is-data", type=int, choices=(0, 1), required=True)
    parser.add_argument("--max-entries", type=int, default=-1)
    args = parser.parse_args()

    output_file = ROOT.TFile.Open(args.output)
    if not output_file or output_file.IsZombie():
        raise SystemExit("Unreadable output ROOT file: %s" % args.output)
    required = set(
        ["Events", "cutflow", "cutflow_weighted", "normalization", "AnalysisMetadata", "LuminosityBlocks"]
    )
    missing = sorted(required - key_names(output_file))
    if missing:
        raise SystemExit("Missing output objects: %s" % ", ".join(missing))

    events = output_file.Get("Events")
    cutflow = output_file.Get("cutflow")
    metadata = output_file.Get("AnalysisMetadata")
    values = cutflow_values(cutflow)
    if any(values[index] < values[index + 1] for index in range(len(values) - 1)):
        raise SystemExit("Cutflow is not cumulative: %r" % values)
    if int(values[-1]) != events.GetEntries():
        raise SystemExit("Selected cutflow count does not equal Events entries")
    if metadata.GetEntries() != 1:
        raise SystemExit("AnalysisMetadata must contain exactly one entry")
    metadata.GetEntry(0)

    source_file = ROOT.TFile.Open(args.source)
    if not source_file or source_file.IsZombie():
        raise SystemExit("Unreadable source Nano ROOT file: %s" % args.source)
    source_events = source_file.Get("Events")
    if not source_events:
        raise SystemExit("Source file has no Events tree")

    entries = events.GetEntries()
    if args.max_entries >= 0:
        entries = min(entries, args.max_entries)
    minimum_ht = None
    maximum_ht = None
    for index in range(entries):
        events.GetEntry(index)
        if int(events.selectedMuonTightId) != 1:
            raise SystemExit("Selected entry %d does not pass tight muon ID" % index)
        if source_events.GetEntry(int(events.inputEntry)) <= 0:
            raise SystemExit("Could not read source entry %d" % int(events.inputEntry))

        expected_ht = 0.0
        expected_njets = 0
        for jet_index in range(int(source_events.nJet)):
            if float(source_events.Jet_pt[jet_index]) <= float(metadata.htJetPtMin):
                continue
            if abs(float(source_events.Jet_eta[jet_index])) >= float(metadata.htJetEtaMax):
                continue
            if int(source_events.Jet_jetId[jet_index]) < int(metadata.htJetIdMin):
                continue
            expected_ht += float(source_events.Jet_pt[jet_index])
            expected_njets += 1

        tolerance = max(1.0e-3, 2.0e-6 * abs(expected_ht))
        if abs(float(events.eventHT) - expected_ht) > tolerance:
            raise SystemExit(
                "HT mismatch at selected entry %d: output=%g source=%g"
                % (index, float(events.eventHT), expected_ht)
            )
        if int(events.nHTJet) != expected_njets:
            raise SystemExit(
                "HT jet-count mismatch at selected entry %d: output=%d source=%d"
                % (index, int(events.nHTJet), expected_njets)
            )
        minimum_ht = expected_ht if minimum_ht is None else min(minimum_ht, expected_ht)
        maximum_ht = expected_ht if maximum_ht is None else max(maximum_ht, expected_ht)

    if args.is_data and output_file.Get("LuminosityBlocks").GetEntries() == 0:
        raise SystemExit("Data output has no certified luminosity blocks")

    print("Validated:", args.output)
    print("  selected entries:", events.GetEntries())
    print("  checked HT entries:", entries)
    print("  cumulative cutflow:", values)
    print("  HT range:", minimum_ht, maximum_ht)
    print("  muon ID:", str(metadata.muonId))
    print("  muon pT min:", float(metadata.muonPtMin))
    print("  muon isolation max:", float(metadata.muonIsoMax))

    source_file.Close()
    output_file.Close()


if __name__ == "__main__":
    main()
