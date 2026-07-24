#!/usr/bin/env python
from __future__ import print_function

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_weighted_plots as plotting


DATA_SAMPLES = [
    "SingleMuon_Run2018A",
    "SingleMuon_Run2018B",
    "SingleMuon_Run2018C",
    "SingleMuon_Run2018D_partial",
]

BACKGROUND_SAMPLES = [
    ("WJets_HT100to200", "W+jets HT 100-200", 400),
    ("WJets_HT200to400", "W+jets HT 200-400", 401),
    ("WJets_HT400to600", "W+jets HT 400-600", 800),
    ("WJets_HT600to800", "W+jets HT 600-800", 801),
    ("WJets_HT800to1200", "W+jets HT 800-1200", 632),
    ("WJets_HT1200to2500", "W+jets HT 1200-2500", 633),
    ("WJets_HT2500toInf", "W+jets HT 2500-Inf", 616),
    ("TTTo2L2Nu", "t#bar{t} dilepton", 600),
    ("TTToHadronic", "t#bar{t} hadronic", 880),
    ("TTToSemiLeptonic", "t#bar{t} semileptonic", 416),
]


def clone_hist(source, name):
    hist = source.Get(name)
    if not hist:
        raise RuntimeError("missing histogram: %s" % name)
    result = hist.Clone(name + "_replot")
    result.SetDirectory(0)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Redraw reconstructed event HT with separate W+jets generator-HT components."
    )
    parser.add_argument("--input", required=True, help="histograms.root from make_weighted_plots.py")
    parser.add_argument(
        "--provisional-ht70-input",
        help="Optional histograms.root containing WJets_HT70to100_event_ht.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lumi-pb", required=True, type=float)
    parser.add_argument("--note", default="Tight muon selection, reconstructed H_{T}")
    args = parser.parse_args()

    ROOT = plotting.load_root()
    plotting.mkdir_p(args.output_dir)
    source = ROOT.TFile.Open(args.input)
    if not source or source.IsZombie():
        raise RuntimeError("could not open %s" % args.input)

    data_hist = None
    for sample in DATA_SAMPLES:
        hist = clone_hist(source, sample + "_event_ht")
        if data_hist is None:
            data_hist = hist
            data_hist.SetName("data_event_ht_replot")
        else:
            data_hist.Add(hist)
    data_hist.SetMarkerStyle(20)
    data_hist.SetMarkerSize(0.8)
    data_hist.SetLineColor(ROOT.kBlack)
    data_hist.SetMarkerColor(ROOT.kBlack)

    backgrounds = []
    ht70_source = None
    if args.provisional_ht70_input:
        ht70_source = ROOT.TFile.Open(args.provisional_ht70_input)
        if not ht70_source or ht70_source.IsZombie():
            raise RuntimeError("could not open %s" % args.provisional_ht70_input)
        hist = clone_hist(ht70_source, "WJets_HT70to100_event_ht")
        row = {
            "sample": "WJets_HT70to100",
            "label": "W+jets HT 70-100 (provisional)",
            "type": "background",
        }
        plotting.style_hist(ROOT, row, hist, 418)
        backgrounds.append((row, hist))

    for sample, label, color in BACKGROUND_SAMPLES:
        hist = clone_hist(source, sample + "_event_ht")
        row = {"sample": sample, "label": label, "type": "background"}
        plotting.style_hist(ROOT, row, hist, color)
        backgrounds.append((row, hist))

    for log_y in (True, False):
        plotting.draw_stack_plot(
            ROOT,
            "event_ht_by_wjets_bin",
            "W+jets source-bin composition",
            "AK4-jet H_{T} [GeV]",
            data_hist,
            backgrounds,
            [],
            args.output_dir,
            args.lumi_pb,
            args.note,
            log_y,
        )
    source.Close()
    if ht70_source:
        ht70_source.Close()
    print("Wrote reconstructed-HT component plots to", args.output_dir)


if __name__ == "__main__":
    main()
