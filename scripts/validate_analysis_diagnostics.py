#!/usr/bin/env python
from __future__ import print_function

import argparse
import math

import ROOT


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description="Validate diagnostic compact analysis output.")
    parser.add_argument("input")
    parser.add_argument("--expect-ht15-complete", choices=("yes", "no", "any"), default="any")
    parser.add_argument("--require-final-selection", action="store_true")
    args = parser.parse_args()

    source = ROOT.TFile.Open(args.input)
    require(source and not source.IsZombie(), "input ROOT file is unreadable")
    tree = source.Get("Events")
    eta_hist = source.Get("ak4_jet_eta_preselection")
    eta_raw_hist = source.Get("ak4_jet_eta_preselection_raw")
    metadata = source.Get("AnalysisMetadata")
    require(tree, "Events tree is missing")
    require(eta_hist and eta_raw_hist, "AK4 eta diagnostic histograms are missing")

    branches = {branch.GetName() for branch in tree.GetListOfBranches()}
    required = {
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
    require(required.issubset(branches), "diagnostic branches are incomplete")

    complete_values = set()
    for entry in range(tree.GetEntries()):
        require(tree.GetEntry(entry) > 0, "failed to read selected event %d" % entry)
        require(abs(float(tree.eventHT) - float(tree.eventHT4)) < 1.0e-3, "eventHT alias mismatch")
        require(float(tree.met_pt) >= 0.0, "invalid MET")
        require(0.0 <= float(tree.muonMetDeltaPhi) <= math.pi, "invalid muon-MET delta phi")
        require(float(tree.muonMetTransverseMass) >= 0.0, "invalid transverse mass")
        require(0.0 <= float(tree.metJetDeltaPhi) <= math.pi, "invalid MET-AK15 delta phi")
        if args.require_final_selection:
            final_checks = (
                (float(tree.selectedMuonPt) > 55.0, "muon pT"),
                (abs(float(tree.selectedMuonEta)) < 2.5, "muon eta"),
                (float(tree.selectedMuonIso) < 0.15, "muon isolation"),
                (int(tree.selectedMuonTightId) == 1, "tight muon ID"),
                (float(tree.jet_pt) > 200.0 and abs(float(tree.jet_eta)) < 3.0, "AK15 kinematics"),
                (float(tree.muonJetDeltaPhi) > 1.5, "muon-AK15 delta phi"),
                (float(tree.eventHT4) > 200.0, "AK4 HT"),
                (float(tree.met_pt) > 30.0, "MET"),
                (float(tree.muonMetTransverseMass) > 50.0, "transverse mass"),
                (float(tree.metJetDeltaPhi) > 1.0, "MET-AK15 delta phi"),
            )
            for passed, label in final_checks:
                require(passed, "selected event %d fails %s" % (entry, label))
        complete = int(tree.eventHT15IsComplete)
        require(complete in (0, 1), "invalid HT15 completeness flag")
        if complete:
            require(float(tree.eventHT15) >= float(tree.jet_pt), "complete HT15 is below leading AK15 pT")
        complete_values.add(complete)

    if args.require_final_selection:
        require(metadata and metadata.GetEntry(0) > 0, "analysis metadata is missing")
        expected = {
            "jetPtMin": 200.0,
            "jetEtaMax": 3.0,
            "muonPtMin": 55.0,
            "muonEtaMax": 2.5,
            "muonIsoMax": 0.15,
            "minDeltaPhi": 1.5,
            "htJetPtMin": 30.0,
            "htJetEtaMax": 3.0,
            "minEventHT": 200.0,
            "minMetPt": 30.0,
            "minMuonMetTransverseMass": 50.0,
            "minMetJetDeltaPhi": 1.0,
        }
        for branch, value in expected.items():
            require(abs(float(getattr(metadata, branch)) - value) < 1.0e-6,
                    "metadata mismatch for %s" % branch)
    if args.expect_ht15_complete == "yes":
        require(complete_values != {0}, "HT15 was expected to be complete")
    elif args.expect_ht15_complete == "no":
        require(1 not in complete_values, "HT15 was expected to be incomplete")

    print("selected_events=%d" % tree.GetEntries())
    print("ak4_eta_entries=%d" % eta_hist.GetEntries())
    print("ak4_eta_sum_event_weights=%.17g" % eta_hist.Integral(0, eta_hist.GetNbinsX() + 1))
    print("ht15_complete_values=%s" % ",".join(str(value) for value in sorted(complete_values)))
    print("diagnostics_valid=1")


if __name__ == "__main__":
    main()
