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

QCD_SAMPLES = [
    ("QCD_HT300to500", "QCD HT 300-500", 400),
    ("QCD_HT500to700", "QCD HT 500-700", 401),
    ("QCD_HT700to1000", "QCD HT 700-1000", 800),
    ("QCD_HT1000to1500", "QCD HT 1000-1500", 801),
    ("QCD_HT1500to2000", "QCD HT 1500-2000", 632),
    ("QCD_HT2000toInf", "QCD HT 2000-Inf", 633),
]

WJETS_SAMPLES = [
    "WJets_HT100to200",
    "WJets_HT200to400",
    "WJets_HT400to600",
    "WJets_HT600to800",
    "WJets_HT800to1200",
    "WJets_HT1200to2500",
    "WJets_HT2500toInf",
]

TTBAR_SAMPLES = [
    ("TTTo2L2Nu", "t#bar{t} dilepton", 600),
    ("TTToHadronic", "t#bar{t} hadronic", 880),
    ("TTToSemiLeptonic", "t#bar{t} semileptonic", 416),
]


def clone_hist(source, name):
    hist = source.Get(name)
    if not hist:
        raise RuntimeError("missing histogram: %s" % name)
    result = hist.Clone(name + "_qcd_replot")
    result.SetDirectory(0)
    return result


def combined_hist(source, samples, name):
    result = None
    for sample in samples:
        hist = clone_hist(source, sample + "_event_ht")
        if result is None:
            result = hist
            result.SetName(name)
        else:
            result.Add(hist)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Redraw reconstructed event HT with separate QCD generator-HT components."
    )
    parser.add_argument("--input", required=True, help="histograms.root from make_weighted_plots.py")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lumi-pb", required=True, type=float)
    parser.add_argument("--note", default="Tight muon selection, reconstructed H_{T}")
    args = parser.parse_args()

    ROOT = plotting.load_root()
    plotting.mkdir_p(args.output_dir)
    source = ROOT.TFile.Open(args.input)
    if not source or source.IsZombie():
        raise RuntimeError("could not open %s" % args.input)

    data_hist = combined_hist(source, DATA_SAMPLES, "data_event_ht_qcd_replot")
    data_hist.SetMarkerStyle(20)
    data_hist.SetMarkerSize(0.8)
    data_hist.SetLineColor(ROOT.kBlack)
    data_hist.SetMarkerColor(ROOT.kBlack)

    backgrounds = []
    for sample, label, color in QCD_SAMPLES:
        hist = clone_hist(source, sample + "_event_ht")
        row = {"sample": sample, "label": label, "type": "background"}
        plotting.style_hist(ROOT, row, hist, color)
        backgrounds.append((row, hist))

    wjets_hist = combined_hist(source, WJETS_SAMPLES, "wjets_event_ht_qcd_replot")
    wjets_row = {"sample": "WJets", "label": "W+jets", "type": "background"}
    plotting.style_hist(ROOT, wjets_row, wjets_hist, 798)
    backgrounds.append((wjets_row, wjets_hist))

    for sample, label, color in TTBAR_SAMPLES:
        hist = clone_hist(source, sample + "_event_ht")
        row = {"sample": sample, "label": label, "type": "background"}
        plotting.style_hist(ROOT, row, hist, color)
        backgrounds.append((row, hist))

    for log_y in (True, False):
        plotting.draw_stack_plot(
            ROOT,
            "event_ht_by_qcd_bin",
            "QCD source-bin composition",
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
    print("Wrote reconstructed-HT QCD component plots to", args.output_dir)


if __name__ == "__main__":
    main()
